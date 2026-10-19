"""Bounded functional query execution shared by service and CLI (contract v1)."""
import hashlib
import json
import re
import difflib
import pandas as pd
from ngraph_functional_paths import CAUTION, render_query
from ngraph_climate_context import climate_question, climate_result

CONTRACT='functional-query-1'
STOP={'which','what','who','are','is','the','a','an','of','for','in','and','have','has','with','modules','module','functions','function','functional','associated','enriched','biosynthesis','support','supports','supporting','carriers','taxa','taxon','show','me','please','do','does','can','could','compare','between','tell','about','potential','central','members','profile','profiles','core','cores','depth','age','time','change','changes','that','those','their','it','them','these','along','by','to','from','using','over','through','without','this'}

def words(text):
    tokens=set(re.findall(r'[a-z][a-z0-9]*',str(text).lower()))-STOP
    return {token for token in tokens if not re.fullmatch(r'm\d+|k\d+|st\d+|geob\w+',token) and token not in {'enrichment','across','all','summary','summarize'}}

def clean_records(frame):
    return json.loads(frame.to_json(orient='records'))

def normalize_module_references(question):
    return re.sub(r'\bmodule\s+(?:number\s+|#\s*)?(\d{1,3})(?!\d)',lambda m:'module M'+str(int(m[1])),question,flags=re.I)

def functional_question(question):
    return bool(re.search(r'function|enrich|biosynthesis|\bmodules?\b|M\d{5}|K\d{5}|\bM[1-9]\d{0,2}\b|\bKO\b|\bkey findings\b|\bmain results\b|\boverview of (?:the |this )?(?:dataset|graph)\b',question,re.I)) or climate_question(question)

class FunctionalQuery:
    def __init__(self, app):
        self.app=app;self.retrieval=app.functional_retrieval
        self.scope=app.functional_path_scope();self.scope['kg_snapshot_id']=app.kg_dir.name
        self.definitions=self.retrieval.table('function_definitions.tsv').fillna('')
        self.functions=self.retrieval.table('module_functions.tsv')
        self.module_nodes=app.kg_nodes[app.kg_nodes.node_type.eq('Module') & app.kg_nodes.module_system.eq(self.scope['module_system'])]
        self.modules=sorted(self.module_nodes.module_id.astype(str).unique())
        self.names={str(r.module_id):str(r.module_name) for r in self.definitions.itertuples()}
        self.taxa=app.kg_nodes[app.kg_nodes.node_type.eq('Taxon')]
        self.catalog_modules=app.kg_nodes[app.kg_nodes.node_type.eq('Module')].copy()
        canonical=self.catalog_modules.node_id.str.startswith('module:')
        prefix='module:'+':'.join(self.scope[k] for k in ['branch','threshold','method'])+':'
        self.catalog_modules=self.catalog_modules[~canonical|self.catalog_modules.node_id.str.startswith(prefix)]
        for key in ['branch','threshold','method']:
            if key in self.catalog_modules:
                values=self.catalog_modules[key]
                self.catalog_modules=self.catalog_modules[values.isna()|values.eq('')|values.eq(self.scope[key])]
        self.module_nodes=self.catalog_modules[self.catalog_modules.module_system.eq(self.scope['module_system'])]
        self.modules=sorted(self.module_nodes.module_id.astype(str).unique())

    def module_selection(self,question,context,requested_scope):
        """Resolve identity separately from availability of functional annotation."""
        ids=list(dict.fromkeys(m.upper() for m in re.findall(r'(?<!\w)(M[1-9]\d{0,2})(?!\d)',question,re.I)))
        explicit=re.search(r'\b(vgae|diffpool)\b',question,re.I)
        for identifier in re.findall(r'module:[\w.\-]+:prev_\d+:[\w.\-]+:[\w.\-]+:M\d+',question):
            if identifier not in self.app.kg_node_ids or identifier.split(':')[1:4]!=[self.scope[k] for k in ['branch','threshold','method']]:
                return None
        system=explicit[1].lower() if explicit else requested_scope.get('module_system') or context.get('scope',{}).get('module_system') or self.scope['module_system']
        if not ids and re.search(r'\b(that|those|their|its|it|them|these)\b|\b(?:what|how) about\b',question,re.I):
            ids=context.get('entities',{}).get('modules',[])
        if not ids:
            if system!=self.scope['module_system'] and system in set(self.catalog_modules.module_system):
                return dict(ids=[],system=system,records=[])
            return None
        catalog=self.catalog_modules
        available=catalog[catalog.module_id.isin(ids)]
        if not explicit and not context.get('entities',{}).get('modules') and not requested_scope.get('module_system'):
            choices=[s for s,g in available.groupby('module_system') if set(ids)<=set(g.module_id)]
            if self.scope['module_system'] not in choices and len(choices)==1:system=choices[0]
        selected=available[available.module_system.eq(system)]
        if set(ids)-set(selected.module_id):return None
        return dict(ids=ids,system=system,records=clean_records(selected))

    def unavailable_annotation(self,question,selection):
        scope=dict(self.scope,module_system=selection['system'])
        entities=dict(modules=selection['ids'],functions=[],taxa=[])
        system_label='DiffPool' if selection['system']=='diffpool' else selection['system'].upper()
        labels=', '.join(system_label+' '+m for m in selection['ids']) or system_label+' module system'
        lines=[labels+' exists in this graph, but functional enrichment has not been computed for this module system in the selected analysis.',
               'Available functional enrichment is for '+self.scope['module_system'].upper()+' '+', '.join(self.modules)+'. No enrichment score can be reported for the selected module; this is unavailable annotation, not biological absence.',
               'Specify VGAE M3, for example, to switch analyses. The selected module identity is preserved for follow-up questions.']
        return dict(query_type='functional_kg',contract=CONTRACT,query=question,resolution_status='unannotated',llm_status='annotation_unavailable',
                    llm_provider='local',scope=scope,annotation_scope=self.scope,entities=entities,answer_lines=lines,markdown='\n\n'.join(lines),
                    retrieved_cards=[dict(card_id='module-identity:'+r['node_id'],card_type='module_identity',entity_id=r['node_id'],title=r.get('label',labels),
                                          summary='Recorded module identity; no functional enrichment in this analysis.',evidence=r) for r in selection['records']],
                    context=dict(schema=CONTRACT,scope=scope,entities=entities,core='',intent='module',module_refs=[r['node_id'] for r in selection['records']]))

    def resolve(self, question,context):
        selected_system=re.search(r'\b(vgae|diffpool)\b',question,re.I)
        if selected_system and selected_system[1].lower()!=self.scope['module_system']:return {},'unknown',['The named module system is not the selected functional analysis.']
        for identifier in re.findall(r'module:[\w.\-]+:prev_\d+:[\w.\-]+:[\w.\-]+:M\d+',question):
            parts=identifier.split(':')
            if identifier not in self.app.kg_node_ids or parts[1:5]!=[self.scope[k] for k in ['branch','threshold','method','module_system']]:return {},'unknown',[identifier]
        module_ids=[m.upper() for m in re.findall(r'(?<!\w)(M[1-9]\d{0,2})(?!\d)',question,re.I)]
        function_ids=[m.upper() for m in re.findall(r'(?<!\w)(M\d{5})(?!\d)',question,re.I)]
        taxa=re.findall(r'(?:taxon:)?(S__[\w.\-]+)',question)
        candidates=[]
        if not function_ids:
            query_words=words(question)
            matches=[]
            for code,name in self.names.items():
                meaningful=query_words & words(name)
                if meaningful:
                    # Extra prose words do not force fuzzy equivalence; rank only recorded label matches.
                    matches.append((len(meaningful),code,name))
            if matches:
                best=max(r[0] for r in matches);matches=[r for r in matches if r[0]==best]
                if len(matches)==1:function_ids=[matches[0][1]]
                else:candidates=[dict(function_id=r[1],label=r[2]) for r in sorted(matches)[:12]]
        if not taxa:
            for row in self.taxa[['node_id','label']].itertuples():
                label=str(row.label)
                if len(label)>3 and not label.startswith('S__') and re.search(r'(?<!\w)'+re.escape(label)+r'(?!\w)',question,re.I):taxa.append(row.node_id.removeprefix('taxon:'))
        inherited=context.get('entities',{}) if context else {}
        followup=bool(re.search(r'\b(that|those|their|its|it|them|these)\b|\b(?:what|how) about\b',question,re.I))
        if followup and not (module_ids or function_ids or taxa):
            if any(len(inherited.get(k,[]))>1 for k in ['modules','functions','taxa']):return {},'ambiguous',['Select which previous entity you mean.']
            module_ids=list(inherited.get('modules',[]));function_ids=list(inherited.get('functions',[]));taxa=list(inherited.get('taxa',[]))
        unknown=[m for m in module_ids if m not in self.modules]+[f for f in function_ids if f not in self.names]+[t for t in taxa if 'taxon:'+t not in self.app.kg_node_ids]
        if unknown:return {},'unknown',unknown
        if candidates:return {},'ambiguous',candidates
        if not (module_ids or function_ids or taxa) and words(question) and not followup:
            vocabulary=set().union(*(words(name) for name in self.names.values()))
            suggestions=set()
            for word in words(question):suggestions.update(difflib.get_close_matches(word,sorted(vocabulary),n=2,cutoff=.82))
            candidates=[dict(function_id=code,label=name) for code,name in self.names.items() if words(name)&suggestions][:12]
            return {},'ambiguous' if candidates else 'unknown',candidates or ['No recorded function name matched. Choose a function or module ID.']
        return dict(modules=list(dict.fromkeys(module_ids)),functions=list(dict.fromkeys(function_ids)),taxa=list(dict.fromkeys(taxa))),'resolved',[]

    def execute(self,question,context=None,requested_scope=None):
        context=context or {};requested_scope=requested_scope or {}
        question=normalize_module_references(question)
        overview_requested=bool(re.search(r'\bkey findings\b|\bmain results\b|\boverview of (?:the |this )?(?:dataset|graph)\b',question,re.I))
        relevant=functional_question(question)
        if not relevant and context and re.search(r'\b(that|those|their|it|them|these)\b|central|depth|age|core|\b(?:what|how) about\b',question,re.I):relevant=True
        if not relevant and re.search(r'which.*(?:taxa|members|carriers).*support.*(?:that|those|it)|(?:show|how).*that.*(?:depth|age)',question,re.I):relevant=True
        relevant=relevant or climate_question(question) or overview_requested
        if not relevant:return None
        result=dict(contract=CONTRACT,query_type='functional_kg',query=question,scope=self.scope,resolution_status='resolved',answer_lines=[],retrieved_cards=[],retrieved_links=[],llm_status='rule_based',llm_provider='local')
        for supplied in [requested_scope,context.get('scope',{})]:
            if not isinstance(supplied,dict):
                result.update(resolution_status='stale_scope',llm_status='context_reset',answer_lines=['Invalid analysis context. Clear the session and select entities again.']);return result
            if any(value and self.scope.get(key)!=value for key,value in supplied.items() if key!='module_system'):
                result.update(resolution_status='stale_scope',llm_status='context_reset',answer_lines=['The selected analysis or evidence snapshot changed. Clear this context or select the current analysis explicitly.']);return result
            if supplied.get('module_system') and supplied['module_system'] not in set(self.catalog_modules.module_system):
                result.update(resolution_status='stale_scope',llm_status='context_reset',answer_lines=['Unknown module system in the supplied context. Clear the session.']);return result
        selection=self.module_selection(question,context,requested_scope)
        if climate_question(question):
            entities=dict(modules=selection['ids'] if selection else [],functions=[f for f in re.findall(r'\bM\d{5}\b',question) if f in self.names],taxa=[])
            return climate_result(question,dict(self.scope,module_system=selection['system']) if selection else self.scope,entities)
        if selection and selection['system']!=self.scope['module_system']:
            return self.unavailable_annotation(question,selection)
        if overview_requested and not re.search(r'\bM\d+\b|S__',question):
            entities,status,candidates=dict(modules=[],functions=[],taxa=[]),'resolved',[]
        else:entities,status,candidates=self.resolve(question,context)
        result.update(entities=entities,resolution_status=status,candidates=candidates)
        if status!='resolved':
            prefix='No recorded entity in the selected analysis matched. Available functional modules: '+', '.join(self.modules)+'. Details: ' if status=='unknown' else 'Choose an unambiguous recorded entity. Candidates: '
            result.update(llm_status='needs_entities',answer_lines=[prefix+json.dumps(candidates)]);return result
        modules,functions,taxa=[entities[k] for k in ['modules','functions','taxa']]
        core_match=re.search(r'\b(ST\d+|GeoB25202(?:_R[12])?)\b',question,re.I)
        core=core_match[1] if core_match else context.get('core','')
        if core.upper().startswith('ST'):core=core.upper()
        elif core.lower().startswith('geob'):core='GeoB25202'+('_R'+core[-1] if '_r' in core.lower() else '')
        intent='components' if re.search(r'\bKOs?\b|K\d{5}|categor|\bGO\b|\bEC\b',question,re.I) else 'profiles' if re.search(r'depth|\bage\b|\btime\b|profile',question,re.I) else 'centrality' if re.search(r'central|hub|driver|driving|connectivity',question,re.I) else 'carriers' if re.search(r'carriers|which taxa|which species|which members',question,re.I) else 'tested' if re.search(r'all test|non.?significant|unqualified|tested results',question,re.I) else 'comparison' if len(modules)>1 else 'taxon' if taxa else 'module' if modules else 'function' if functions else 'overview'
        if core_match and re.search(r'\b(?:what|how) about\b',question,re.I) and context.get('intent') in {'profiles','centrality','carriers','components','module','function'}:intent=context['intent']
        result.update(intent=intent,core=core)
        if intent=='carriers' and not functions:
            result.update(llm_status='needs_entities',resolution_status='ambiguous',answer_lines=['Choose a function to identify its supporting carriers.']);return result
        graph_results=[];lines=[];cards=[]
        if intent in {'profiles','centrality','tested','components'}:
            self.tables(result,entities,intent,core)
        else:
            tasks=[]
            if taxa:
                tasks=[(t,functions[0] if functions else '', 'taxon_module_function') for t in taxa[:4]]
                tasks=[('taxon:'+a,b,c) for a,b,c in tasks]
            elif intent=='carriers' and functions:tasks=[(f,'','function_module_taxon') for f in functions[:4]]
            elif modules:tasks=[(m,f if functions else '', 'module_function') for m in modules[:6] for f in (functions[:4] or [''])]
            elif functions:tasks=[(f,'','function_module') for f in functions[:4]]
            else:tasks=[(m,'','module_function') for m in self.modules]
            for source,target,preset in tasks:
                g=self.app.kg_connectivity(source,target,preset,limit=20,core=core,carriers_only=intent=='carriers')
                graph_results.append(g);answer=render_query(g,question)
                lines.extend(answer['answer_lines'][1:]);cards.extend(answer['retrieved_cards'])
                if not g.get('paths'):lines.append(source+' has no qualified result in this scope; this is not biological absence.')
            # Each result preserves its own proof deep link, not merely the final query.
            result['graph_results']=graph_results
            result['graph_evidence']=next((g for g in graph_results if g.get('paths')),graph_results[0] if graph_results else {})
            result['answer_lines']=[CAUTION]+lines
            result['retrieved_cards']=cards
        if overview_requested:
            result['answer_lines'].insert(1,'This overview summarizes the available functional KG annotations in the selected analysis. Climate-association results have not been computed.')
        if not result['retrieved_cards']:
            # Scoped definition/summary cards provide context without converting them into assertions.
            matches=self.retrieval.search(question,20)
            result['retrieved_cards']=[c for c in matches if c.get('card_type')!='functional_modulefunctionalassociation' and
                (any(str(c.get('entity_id','')).endswith(':'+m) for m in modules) or
                 any(str(c.get('entity_id','')).endswith(':'+f) for f in functions))][:8]
        refs=self.module_nodes[self.module_nodes.module_id.isin(modules)].node_id.tolist()
        result['context']=dict(schema=CONTRACT,scope=self.scope,entities=entities,core=core,intent=intent,module_refs=refs)
        result['markdown']='\n\n'.join(result['answer_lines'])
        return result

    def tables(self,result,entities,intent,core):
        modules,functions=entities['modules'],entities['functions']
        if intent=='components':
            frame=self.definitions.rename(columns={'module_id':'function_id'}).copy()
            codes=re.findall(r'K\d{5}',result['query'])
            if codes:frame=frame[frame.module_definition.map(lambda d:any(k in d for k in codes))]
            if modules and not functions:
                selected=self.functions[self.functions.module_id.isin(modules)&self.functions.publish_kg.eq(True)].function_id
                frame=frame[frame.function_id.isin(selected)]
            frame['recorded_ko_ids']=frame.module_definition.map(lambda d:';'.join(sorted(set(re.findall(r'K\d{5}',d)))))
            message='Recorded KO definition components and categories; AND/OR/optional logic is retained. These are not separate KO or category enrichment tests. No GO/EC equivalence is inferred.'
        elif intent=='tested':
            frame=self.functions.copy();message='All tested results are descriptive records, not published positive assertions.'
        elif intent=='profiles':
            if not modules and not functions:
                result.update(llm_status='needs_entities',answer_lines=['Choose a module or function for a depth/age profile.']);return
            frame=self.retrieval.table('function_profiles.tsv' if functions else 'module_profiles.tsv')
            message='Sample-wide reference-function profile.' if functions else 'Community-module relative profile.'
            message+=' Values are relative abundance summaries, not measured activity, absolute abundance, or a trend significance test.'
        else:
            frame=self.retrieval.table('module_centrality.tsv')
            if functions:
                members=self.retrieval.table('module_function_members.tsv');members=members[members.function_id.isin(functions)&members.is_carrier.eq(True)]
                qualified=self.functions[self.functions.publish_kg.eq(True)][['module_id','function_id']].drop_duplicates()
                members=members.merge(qualified,on=['module_id','function_id'])
                frame=frame.merge(members[['module_id','taxon','function_id']].drop_duplicates(),on=['module_id','taxon'])
            message=('Structurally central supporting members of published functional associations; ' if functions else 'Structural members without a selected functional-support criterion; ')+'centrality does not establish causal functional drivers. Bootstraps condition on fixed module membership.'
        if 'module_id' in frame and modules and not (intent=='profiles' and functions):frame=frame[frame.module_id.isin(modules)]
        if 'function_id' in frame and functions:frame=frame[frame.function_id.isin(functions)]
        if core and 'core' in frame:
            frame=frame[frame.core.eq(core)|(frame.get('physical_core',pd.Series('',index=frame.index)).eq(core))]
        elif intent=='centrality' and 'core' in frame and frame.core.eq('all').any():frame=frame[frame.core.eq('all')]
        if intent=='centrality' and 'centrality_percentile' in frame:frame=frame.sort_values('centrality_percentile',ascending=False)
        count=len(frame);rows=clean_records(frame.head(40));scope=self.scope
        card_id='table:functional:'+hashlib.sha256(json.dumps([scope,intent,entities,core,rows],sort_keys=True).encode()).hexdigest()[:24]
        result['table_evidence']=dict(intent=intent,rows=rows,total_count=count,returned_count=len(rows),truncated=count>len(rows),profile_scope='sample_wide_function' if intent=='profiles' and functions else 'module',units=dict(depth_cm='centimetres',age_kyr='kyr BP',y_bp='years BP') if intent=='profiles' else {},core=core,entities=entities,scope=self.scope)
        result['answer_lines']=[CAUTION,message,f'{count} matching records; showing {len(rows)}. [{card_id}]']
        if not rows:result['answer_lines'].append('No exported records in the selected scope; this is not absence of biological function.')
        result['retrieved_cards']=[dict(card_id=card_id,card_type='functional_'+intent,title=message,summary=message,evidence=result['table_evidence'],scope=scope)]
        result['table_evidence']['card_id']=card_id
        filename='function_definitions.tsv' if intent=='components' else 'module_functions.tsv' if intent=='tested' else 'function_profiles.tsv' if intent=='profiles' and functions else 'module_profiles.tsv' if intent=='profiles' else 'module_centrality.tsv'
        source=self.retrieval.evidence_directory/'tables'/filename if hasattr(self.retrieval,'evidence_directory') else None
        root=__import__('pathlib').Path(__file__).resolve().parents[1]
        if source and source.is_relative_to(root):
            result['table_evidence']['source_file']=source.relative_to(root).as_posix()


def load_backend(branch):
    """Reuse the service's bounded graph adapter from CLI without starting HTTP."""
    import importlib.util
    from pathlib import Path
    from ngraph_kg_snapshots import active_directory
    from ngraph_functional_retrieval import FunctionalRetrieval
    root=Path(__file__).resolve().parents[1];kg=root/'results/ngraph'/branch/'knowledge_graph';directory=active_directory(kg)
    if not (directory/'indexes/functional/manifest.json').exists():return None
    spec=importlib.util.spec_from_file_location('ngraph_functional_backend',root/'scripts/14_ngraph_local_browser.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    app=object.__new__(module.ConstellationsService);app.branch=branch;app.kg_dir=directory;app.kg_root_dir=kg
    app.kg_nodes=pd.read_csv(directory/'tables/kg_nodes.tsv',sep='\t',low_memory=False);app.kg_edges=pd.read_csv(directory/'tables/kg_edges.tsv',sep='\t',low_memory=False)
    app.kg_manifest=json.loads((directory/'kg_manifest.json').read_text());app.kg_node_ids=set(app.kg_nodes.node_id);app.kg_node_lookup=app.kg_nodes.set_index('node_id')
    app.functional_retrieval=FunctionalRetrieval(directory)
    return FunctionalQuery(app)
