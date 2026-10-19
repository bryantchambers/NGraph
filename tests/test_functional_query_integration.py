"""Functional names, scope, follow-ups, tables and provider grounding fixtures."""
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ngraph_functional_query import FunctionalQuery
from ngraph_rag_orchestrator import augment_functional_result,validate_functional_claims
from test_functional_paths import fixture,SCOPE
from ngraph_kg_connectivity import ConnectivityIndex

class Retrieval:
 def __init__(self):
  self.frames={'function_definitions.tsv':pd.DataFrame([dict(module_id='M00091',module_name='Phosphatidylcholine PC biosynthesis PE PC',module_definition='K00570',definition_sha256='hash',module_category='Lipid metabolism'),dict(module_id='M00121',module_name='Heme biosynthesis glutamate',module_definition='K00001',definition_sha256='hash',module_category='Cofactor metabolism')]),'module_functions.tsv':pd.DataFrame([dict(module_id='M3',function_id='M00091',publish_kg=True,q_value=.01)]),'module_function_members.tsv':pd.DataFrame([dict(module_id='M3',function_id='M00091',taxon='T1',is_carrier=True)]),'module_centrality.tsv':pd.DataFrame([dict(module_id='M3',taxon='T1',core='all',centrality_percentile=.9),dict(module_id='M3',taxon='T2',core='all',centrality_percentile=.99)]),'function_profiles.tsv':pd.DataFrame([dict(function_id='M00091',sample='S1',core='ST8',depth_cm=4.5,age_kyr=1.2,logratio=.1)]),'module_profiles.tsv':pd.DataFrame([dict(module_id='M3',sample='S1',core='ST8',depth_cm=4.5,age_kyr=1.2,module_logratio=.3)])}
 def table(self,name):return self.frames.get(name,pd.DataFrame()).copy()
 def search(self,*args):return []

class App:
 def __init__(self):
  n,e=fixture();n[2]['module_id']='M3';n[2]['label']='M3';n += [dict(node_id='M4',node_type='Module',label='M4',module_id='M4',**SCOPE)]
  self.kg_nodes=pd.DataFrame(n);self.kg_node_ids=set(self.kg_nodes.node_id);self.kg_dir=Path('/fixture/snapshots/functional-fixture');self.functional_retrieval=Retrieval();self.index=ConnectivityIndex(n,e,SCOPE)
 def functional_path_scope(self):return dict(SCOPE)
 def kg_connectivity(self,source,target='',metapath='',**kw):
  a={'M3':'M','M00091':'F','M00121':'missing'}
  return self.index.search(a.get(source,source),a.get(target,target),metapath,limit=kw.get('limit',20),carriers_only=kw.get('carriers_only',False))

class FunctionalQueryIntegrationTests(unittest.TestCase):
 def setUp(self):self.app=App();self.engine=FunctionalQuery(self.app)
 def test_recorded_name_and_id_same_proof(self):
  by_name=self.engine.execute('Which modules support phosphatidylcholine biosynthesis?');by_id=self.engine.execute('Which modules support M00091?')
  self.assertEqual(by_name['entities']['functions'],['M00091']);self.assertEqual(by_name['retrieved_cards'][0]['card_id'],by_id['retrieved_cards'][0]['card_id'])
 def test_community_id_is_not_a_definition_name_search(self):
  self.engine.names['M00872']='O-glycan biosynthesis mannose core M3'
  self.assertEqual(self.engine.execute('Which functions are associated with module M3?')['entities']['functions'],[])
 def test_unknown_and_ambiguous_names(self):
  self.assertEqual(self.engine.execute('Which functions are enriched in M99?')['resolution_status'],'unknown')
  self.assertEqual(self.engine.execute('Which functions are enriched in DiffPool M3?')['resolution_status'],'unknown')
  self.assertEqual(self.engine.execute('Which modules support unicorn metabolism?')['resolution_status'],'unknown')
  self.engine.names['M00092']='Phosphatidylcholine biosynthesis alternate';self.assertEqual(self.engine.execute('Which modules support phosphatidylcholine biosynthesis?')['resolution_status'],'ambiguous')
 def test_overview_and_comparison_keep_empty_modules(self):
  r=self.engine.execute('Summarize functional enrichment across all modules');self.assertEqual(r['intent'],'overview');self.assertTrue(any('M4 has no qualified' in s for s in r['answer_lines']))
  r=self.engine.execute('Compare functions in M3 and M4');self.assertEqual(r['intent'],'comparison');self.assertEqual(len(r['graph_results']),2)
 def test_followup_and_scope_reset(self):
  r=self.engine.execute('Which modules support M00091?');follow=self.engine.execute('Which taxa support that?',r['context']);self.assertEqual(follow['intent'],'carriers');self.assertEqual(follow['graph_evidence']['path_count'],1)
  context=dict(r['context'],scope=dict(r['context']['scope'],kg_snapshot_id='other'));self.assertEqual(self.engine.execute('Which taxa support that?',context)['resolution_status'],'stale_scope')
  self.assertEqual(self.engine.execute('Which functions are associated with module:foreign:prev_10:pearson:vgae:M3?')['resolution_status'],'unknown')
 def test_ambiguous_followup_and_forged_entity(self):
  context=dict(scope=self.engine.scope,entities=dict(functions=['M00091','M00121'],modules=[],taxa=[]));self.assertEqual(self.engine.execute('Which taxa support those?',context)['resolution_status'],'ambiguous')
  context['entities']['functions']=['M99999'];self.assertEqual(self.engine.execute('Which taxa support that?',context)['resolution_status'],'unknown')
 def test_explicit_selection_overrides_context(self):
  r=self.engine.execute('Which modules support M00091?');follow=self.engine.execute('Show function M00121',r['context']);self.assertEqual(follow['entities']['functions'],['M00121'])
 def test_centrality_only_supporting_carriers(self):
  r=self.engine.execute('Which central taxa support M00091?');self.assertEqual(r['table_evidence']['total_count'],1);self.assertEqual(r['table_evidence']['rows'][0]['taxon'],'T1');self.assertIn('does not establish',r['answer_lines'][1])
 def test_profile_scope_and_units(self):
  r=self.engine.execute('Show profile of M00091 in M3 along depth in ST8');self.assertEqual(r['table_evidence']['profile_scope'],'sample_wide_function');self.assertEqual(r['table_evidence']['total_count'],1);self.assertEqual(r['table_evidence']['units']['age_kyr'],'kyr BP')
  next_result=self.engine.execute('What about ST13?',r['context']);self.assertEqual(next_result['intent'],'profiles');self.assertEqual(next_result['core'],'ST13')
 def test_components_are_not_KO_enrichment(self):
  r=self.engine.execute('Which KOs support M00091?');self.assertEqual(r['intent'],'components');self.assertEqual(r['table_evidence']['rows'][0]['recorded_ko_ids'],'K00570');self.assertIn('not separate',r['answer_lines'][1])
 def test_tested_records_never_positive_assertions(self):
  r=self.engine.execute('Show all tested results for M3');self.assertEqual(r['intent'],'tested');self.assertFalse(r.get('graph_results'));self.assertIn('not published',r['answer_lines'][1])
 def test_provider_claims_and_failure(self):
  r=self.engine.execute('Which functions support M3?');card=r['retrieved_cards'][0]['card_id']
  r['retrieved_cards'][0]['proof']['statistics']['null_carrier_count_sd']=float('nan')
  claim=dict(type='association',text='M00091 is associated with M3; q=0.01.',evidence_ids=[card])
  with patch('ngraph_rag_orchestrator.call_gemini',return_value=dict(status='ok',json={'claims':[claim]},model='fixture')):
   output=augment_functional_result(r,'gemini');self.assertEqual(output['llm_status'],'validated');self.assertIn(card,output['llm_answer'])
  for bad in [dict(claim,evidence_ids=['invented']),dict(claim,text='M3 q=0.8'),dict(claim,text='The taxa perform M00091'),dict(claim,type='causality')]:
   with self.subTest(bad=bad),self.assertRaises(ValueError):validate_functional_claims([bad],r['retrieved_cards'])
  with self.assertRaises(ValueError):validate_functional_claims([dict(claim,text='M4 is associated with M00091.')],r['retrieved_cards'])
  with patch('ngraph_rag_orchestrator.call_gemini',side_effect=RuntimeError('provider unavailable')):
   output=augment_functional_result(r,'gemini');self.assertEqual(output['llm_status'],'provider_error');self.assertEqual(output['answer_lines'],r['answer_lines'])
if __name__=='__main__':unittest.main()
