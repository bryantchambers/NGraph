"""Regression coverage for the reported climate → DiffPool module conversation."""
import sys,unittest,tempfile,json,importlib.util
from pathlib import Path
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from test_functional_query_integration import App
from ngraph_functional_query import FunctionalQuery
from ngraph_climate_context import audit_mis,climate_result
from ngraph_rag_orchestrator import augment_functional_result,augment_result,validate_general_synthesis,build_retrieval_bundle,statistic_matches,validate_functional_claims

class ScopeTests(unittest.TestCase):
 def setUp(self):
  self.app=App();scope=dict(self.app.functional_path_scope(),module_system='diffpool')
  self.app.kg_nodes=pd.concat([self.app.kg_nodes,pd.DataFrame([dict(node_id='module:demo:prev_10:pearson:diffpool:M24',node_type='Module',module_id='M24',label='DiffPool M24',**scope)])],ignore_index=True)
  self.app.kg_node_ids=set(self.app.kg_nodes.node_id);self.engine=FunctionalQuery(self.app)
 def test_module_number_alias(self):
  self.assertEqual(self.engine.execute('key functional enrichments in module 3')['entities']['modules'],['M3'])
 def test_known_other_system_is_unannotated_not_unknown(self):
  for text in ['key functional enrichments in M24','key functional enrichments in module 24','key functional enrichments in DiffPool M24']:
   r=self.engine.execute(text);self.assertEqual(r['resolution_status'],'unannotated');self.assertEqual(r['scope']['module_system'],'diffpool');self.assertIn('not been computed',' '.join(r['answer_lines']));self.assertNotIn('q=',str(r))
 def test_followup_preserves_unannotated_identity(self):
  r=self.engine.execute('functions in M24');follow=self.engine.execute('What about its enrichment scores?',r['context']);self.assertEqual(follow['entities']['modules'],['M24']);self.assertEqual(follow['llm_status'],'annotation_unavailable')
 def test_canonical_id_supplies_nullable_scope_columns(self):
  self.app.kg_nodes.loc[self.app.kg_nodes.module_id.eq('M24'),['threshold','method']]=None
  engine=FunctionalQuery(self.app);self.assertEqual(engine.execute('functions in module 24')['resolution_status'],'unannotated')
 def test_explicit_model_switch(self):
  r=self.engine.execute('functions in M24');follow=self.engine.execute('functions in VGAE module 3',r['context']);self.assertEqual(follow['resolution_status'],'resolved');self.assertEqual(follow['scope']['module_system'],'vgae')
 def test_overview_does_not_silently_switch_system(self):
  r=self.engine.execute('functions in M24');follow=self.engine.execute('What are the key findings in this dataset?',r['context']);self.assertEqual(follow['scope']['module_system'],'diffpool');self.assertEqual(follow['resolution_status'],'unannotated')
  fresh=self.engine.execute('What are the key findings in this dataset?');self.assertEqual(fresh['intent'],'overview');self.assertEqual(fresh['scope']['module_system'],'vgae')
 def test_cli_uses_same_module_and_climate_scope(self):
  path=Path(__file__).resolve().parents[1]/'scripts/13_ngraph_query_engine.py';spec=importlib.util.spec_from_file_location('query_scope_fixture',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  data=dict(branch='demo',_functional_backend=self.engine)
  r=module.run_query('functional enrichment in module 24',data,llm_provider='local');self.assertEqual(r['scope']['module_system'],'diffpool');self.assertEqual(r['resolution_status'],'unannotated')
  r=module.run_query('How does MIS relate to that?',data,llm_provider='local');self.assertEqual(r['scope']['module_system'],'diffpool');self.assertEqual(r['entities']['modules'],['M24']);self.assertEqual(r['llm_status'],'analysis_unavailable')
 def test_climate_conversation_does_not_invent_modules(self):
  r=self.engine.execute('What taxa work together to transition from glacial to interglacial periods?');self.assertEqual(r['query_type'],'climate_context');self.assertEqual(r['llm_status'],'analysis_unavailable');self.assertFalse(r['entities']['modules'])
  follow=self.engine.execute('functional enrichments in module 24',r['context']);self.assertEqual(follow['resolution_status'],'unannotated')
 def test_unavailable_analysis_does_not_call_gemini(self):
  for q in ['functions in M24','How does MIS link with functional enrichment?']:
   with patch('ngraph_rag_orchestrator.call_gemini') as provider:
    r=augment_functional_result(self.engine.execute(q),'gemini');provider.assert_not_called();self.assertFalse(r['llm_answer'])
 def test_real_function_path_does_not_support_climate_claim(self):
  r=self.engine.execute('functions in M3');card=r['retrieved_cards'][0]['card_id']
  with self.assertRaises(ValueError):validate_functional_claims([dict(type='association',text='M3 is associated with M00091 during glacial transitions.',evidence_ids=[card])],r['retrieved_cards'])
 def test_forged_module_system_and_snapshot_rejected(self):
  context=dict(scope=dict(self.engine.scope,module_system='unrecorded'),entities=dict(modules=['M24']))
  self.assertEqual(self.engine.execute('functions in M24',context)['llm_status'],'context_reset')
  context['scope']=dict(self.engine.scope,kg_snapshot_id='old')
  self.assertEqual(self.engine.execute('functions in M24',context)['llm_status'],'context_reset')

class ClimateTests(unittest.TestCase):
 def test_source_failure_is_explicit_and_not_verified(self):
  with patch('ngraph_climate_context.audit_mis',side_effect=ValueError('invalid reference')):r=climate_result('What does MIS mean?')
  self.assertEqual(r['metadata_semantics']['status'],'unresolved');self.assertIn('unresolved',r['retrieved_cards'][0]['summary'])
 def test_all_comparable_source_rows_match(self):
  r=audit_mis();self.assertEqual(r['status'],'verified_lr04_interpolation');self.assertEqual(r['matching_rows'],r['compared_rows']);self.assertGreater(r['compared_rows'],500);self.assertFalse(r['is_stage_number']);self.assertFalse(r['is_local_measurement']);self.assertLess(r['max_absolute_error'],1e-8)
 def test_changed_values_and_outside_range_not_approved(self):
  with tempfile.TemporaryDirectory() as d:
   m=Path(d)/'meta.tsv';s=Path(d)/'stack.tsv'
   pd.DataFrame(dict(label=['x','y'],core=['ST8','ST8'],y_bp=[500,20000],mis=[9,3])).to_csv(m,sep='\t',index=False)
   pd.DataFrame(dict(Time_ka=[0,1],Benthic_d18O=[3,4])).to_csv(s,sep='\t',index=False)
   r=audit_mis(m,s);self.assertEqual(r['status'],'unresolved');self.assertEqual(r['compared_rows'],1);self.assertEqual(r['unassessed_rows'],1)
 def test_cli_transition_cannot_execute_median_split(self):
  p=Path(__file__).resolve().parents[1]/'scripts/13_ngraph_query_engine.py';spec=importlib.util.spec_from_file_location('query_engine_fixture',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  r=module.build_transition_answer('glacial transition',{});self.assertEqual(r['llm_status'],'analysis_unavailable');self.assertNotIn('top_taxa',r)

class GeneralGroundingTests(unittest.TestCase):
 def setUp(self):
  self.cards=pd.DataFrame([dict(card_id='v3',card_type='module',entity_id='vgae:M3',title='VGAE M3',summary='Recorded module membership'),dict(card_id='d24',card_type='module',entity_id='diffpool:M24',title='DiffPool M24',summary='Legacy module')])
 def test_retrieval_does_not_mix_module_systems(self):
  r=build_retrieval_bundle('modules',dict(semantic_hits=self.cards),dict(cards=self.cards,analysis_scope=dict(module_system='vgae')))
  self.assertEqual(set(r['retrieved_cards'].card_id),{'v3'})
 def test_unknown_citation_rejected(self):
  with self.assertRaises(ValueError):validate_general_synthesis(dict(answer='Recorded module M3',evidence_ids=['unknown']),self.cards,dict(module_system='vgae'))
 def test_cross_system_and_invented_entities_rejected(self):
  for answer in ['DiffPool M24 is annotated','VGAE M24 is annotated','Taxon S__invented is a member']:
   with self.assertRaises(ValueError):validate_general_synthesis(dict(answer=answer,evidence_ids=['v3']),self.cards,dict(module_system='vgae'))
 def test_cooperation_and_confidence_claims_rejected(self):
  for answer in ['Taxa function in concert during glacial transitions.','Taxa do not only cooperate but drive carbon cycling.','Taxa have confidence 0.993.']:
   with self.assertRaises(ValueError):validate_general_synthesis(dict(answer=answer,evidence_ids=['v3']),self.cards,dict(module_system='vgae'))
 def test_rejected_synthesis_preserves_local_result(self):
  with patch('ngraph_rag_orchestrator.call_gemini',return_value=dict(status='ok',json=dict(answer='Taxa function in concert during glacial transitions.',evidence_ids=['v3']))):
   r=augment_result('modules',dict(answer_lines=['Local evidence'],semantic_hits=self.cards),dict(cards=self.cards),llm_provider='gemini')
  self.assertEqual(r['llm_status'],'validation_failed');self.assertEqual(r['llm_answer'],'');self.assertEqual(r['answer_lines'],['Local evidence'])
 def test_scoped_summary_and_negated_caution_allowed(self):
  self.assertTrue(validate_general_synthesis(dict(answer='VGAE M3 is a recorded module. Network links do not establish cooperation.',evidence_ids=['v3']),self.cards,dict(module_system='vgae')))
  self.assertTrue(validate_general_synthesis(dict(answer='VGAE M3 is recorded reference potential rather than measured metabolic activity or causality.',evidence_ids=['v3']),self.cards,dict(module_system='vgae')))
 def test_general_association_requires_same_pair_and_statistic(self):
  payload=dict(node_type='ModuleFunctionalAssociation',node_id='A',module_system='vgae',module_id='M3',function_id='M00091',q_value=.00374999)
  cards=pd.DataFrame([dict(card_id='assoc',card_type='functional_modulefunctionalassociation',entity_id='A',evidence=json.dumps(payload))])
  for text in ['VGAE M3 is associated with M00091; q-value of 0.5.','VGAE M4 is associated with M00091.']:
   with self.assertRaises(ValueError):validate_general_synthesis(dict(answer=text,evidence_ids=['assoc']),cards,dict(module_system='vgae'))
  self.assertTrue(validate_general_synthesis(dict(answer='VGAE M3 is associated with M00091; q-value of 0.0037.',evidence_ids=['assoc']),cards,dict(module_system='vgae')))
 def test_statistic_rounding_does_not_accept_false_zero(self):
  self.assertTrue(statistic_matches('0.0037',[.00374999]));self.assertFalse(statistic_matches('0',[.00374999]));self.assertFalse(statistic_matches('0.5',[.00374999]))

if __name__=='__main__':unittest.main()
