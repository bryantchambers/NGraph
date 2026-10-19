"""Frozen, scope-bound functional cards and TF-IDF retrieval inside KG bundles."""
from pathlib import Path
import hashlib
import json
import pickle
import re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import save_npz, load_npz
from ngraph_functional_paths import CAUTION


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def build(directory,nodes,projection,evidence_directory):
    destination=Path(directory)/'indexes/functional';destination.mkdir(parents=True,exist_ok=True)
    evidence=Path(evidence_directory)
    scope=dict(projection['scope']);scope['module_system']=scope.pop('model')
    source_manifest=json.loads((evidence/'manifest.json').read_text())
    for name,expected in source_manifest.get('artifacts',{}).items():
        source=(evidence/name).resolve()
        if not source.is_relative_to(evidence.resolve()) or digest(source)!=expected:raise ValueError('Functional retrieval source hash mismatch')
    rows=[]
    for node in nodes[nodes.node_type.isin(['ModuleFunctionalAssociation','FunctionalFeature','Module'])].to_dict('records'):
        if node['node_type']=='Module' and (node.get('module_system')!=scope['module_system']):continue
        payload={k:(None if pd.isna(v) else v) for k,v in node.items()}
        card_id='card:functional:'+hashlib.sha256((node['node_id']+json.dumps(scope,sort_keys=True)).encode()).hexdigest()[:24]
        rows.append(dict(card_id=card_id,card_type='functional_'+node['node_type'].lower(),entity_id=node['node_id'],title=str(node['label']),summary=CAUTION,evidence=json.dumps(payload,sort_keys=True),observed_status='qualified_reference_potential' if node['node_type']=='ModuleFunctionalAssociation' else 'definition_or_membership_context'))
    definitions=evidence/'tables/function_definitions.tsv'
    if definitions.exists():
        for row in pd.read_csv(definitions,sep='\t').fillna('').to_dict('records'):
            code=row.get('module_id',row.get('function_id',''))
            rows.append(dict(card_id='definition:'+scope['db_snapshot']+':'+code,card_type='functional_definition',entity_id='kegg.module:'+code,title=str(row.get('module_name',code)),summary='Recorded definition; this card is not an enrichment assertion. '+CAUTION,evidence=json.dumps(row,sort_keys=True),observed_status='recorded_definition'))
    frame=pd.DataFrame(rows)
    if frame.empty:return None
    project_root=Path(__file__).resolve().parents[1]
    legacy=project_root/'results/ngraph'/scope['branch']/'deep_knowledge_discovery/cards/evidence_cards.tsv'
    if legacy.exists():
        old=pd.read_csv(legacy,sep='\t').fillna('')
        old['observed_status']='historical_descriptive_metadata'
        frame=pd.concat([frame,old],ignore_index=True,sort=False).fillna('')
    frame=frame.drop_duplicates('card_id')
    frame.to_csv(destination/'cards.tsv',sep='\t',index=False)
    vectorizer=TfidfVectorizer(ngram_range=(1,2),stop_words='english');matrix=vectorizer.fit_transform(frame.title+' '+frame.summary+' '+frame.evidence)
    with (destination/'vectorizer.pkl').open('wb') as f:pickle.dump(vectorizer,f)
    save_npz(destination/'matrix.npz',matrix)
    spec=dict(schema='functional-retrieval-1',scope=scope,evidence_directory=str(evidence.resolve()),graph_sha256={name:digest(Path(directory)/'tables'/name) for name in ['kg_nodes.tsv','kg_edges.tsv']},source_manifest_sha256=digest(evidence/'manifest.json'),source_hashes=source_manifest.get('artifacts',{}),files={p.name:digest(p) for p in sorted(destination.iterdir()) if p.name!='manifest.json'},card_count=len(frame),seed=42)
    (destination/'manifest.json').write_text(json.dumps(spec,indent=2,sort_keys=True)+'\n')
    return spec


class FunctionalRetrieval:
    def __init__(self,kg_directory):
        self.kg_directory=Path(kg_directory);root=self.kg_directory/'indexes/functional'
        self.manifest=json.loads((root/'manifest.json').read_text())
        for name,value in self.manifest['graph_sha256'].items():
            if digest(self.kg_directory/'tables'/name)!=value:raise ValueError('KG/retrieval scope mismatch')
        for name,value in self.manifest['files'].items():
            path=(root/name).resolve()
            if not path.is_relative_to(root.resolve()) or digest(path)!=value:raise ValueError('Functional retrieval integrity mismatch')
        self.evidence_directory=Path(self.manifest['evidence_directory'])
        if digest(self.evidence_directory/'manifest.json')!=self.manifest['source_manifest_sha256']:raise ValueError('Functional source manifest changed')
        for relative,expected in self.manifest['source_hashes'].items():
            path=(self.evidence_directory/relative).resolve()
            if not path.is_relative_to(self.evidence_directory.resolve()) or digest(path)!=expected:raise ValueError('Frozen functional source changed')
        self.cards=pd.read_csv(root/'cards.tsv',sep='\t').fillna('')
        with (root/'vectorizer.pkl').open('rb') as f:self.vectorizer=pickle.load(f)
        self.matrix=load_npz(root/'matrix.npz')
        self._tables={}
    def table(self,name):
        if name not in self._tables:
            relative='tables/'+name;path=self.evidence_directory/relative
            expected=self.manifest['source_hashes'].get(relative)
            if not expected or not path.is_file():return pd.DataFrame()
            if digest(path)!=expected:raise ValueError('Frozen functional table changed: '+name)
            self._tables[name]=pd.read_csv(path,sep='\t',low_memory=False)
        return self._tables[name].copy()
    def search(self,query,limit=12):
        scores=(self.matrix@self.vectorizer.transform([query]).T).toarray().ravel()
        ids=scores.argsort()[::-1][:min(40,max(1,limit))];frame=self.cards.iloc[ids].copy();frame['score']=scores[ids]
        return frame[frame.score>0].to_dict('records')
