"""Frozen cards are tied to graph and analysis hashes, not a mutable shared index."""
import json
import sys
import tempfile
from pathlib import Path
import unittest
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ngraph_functional_retrieval import build,FunctionalRetrieval,digest

class RetrievalBundleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.kg=self.root/'kg';self.evidence=self.root/'evidence';(self.kg/'tables').mkdir(parents=True);(self.evidence/'tables').mkdir(parents=True)
  self.nodes=pd.DataFrame([dict(node_id='M',node_type='Module',label='M3',module_system='vgae'),dict(node_id='F',node_type='FunctionalFeature',label='Phosphatidylcholine biosynthesis',function_id='M00091'),dict(node_id='A',node_type='ModuleFunctionalAssociation',label='M3 associated with M00091',q_value=.01)])
  self.nodes.to_csv(self.kg/'tables/kg_nodes.tsv',sep='\t',index=False);(self.kg/'tables/kg_edges.tsv').write_text('edge_id\tsource_id\ttarget_id\ne\tM\tA\n')
  pd.DataFrame([dict(module_id='M00091',module_name='Phosphatidylcholine biosynthesis',module_definition='K00570')]).to_csv(self.evidence/'tables/function_definitions.tsv',sep='\t',index=False)
  artifacts={'tables/function_definitions.tsv':digest(self.evidence/'tables/function_definitions.tsv')};(self.evidence/'manifest.json').write_text(json.dumps({'artifacts':artifacts}))
  self.projection={'scope':dict(branch='fixture_retrieval',threshold='prev_10',method='pearson',model='vgae',db_snapshot='catalog')}
 def tearDown(self):self.temp.cleanup()
 def test_search_and_scope_hashes(self):
  build(self.kg,self.nodes,self.projection,self.evidence);index=FunctionalRetrieval(self.kg)
  self.assertTrue(index.search('phosphatidylcholine'));self.assertEqual(index.manifest['scope']['module_system'],'vgae')
  self.assertEqual(index.table('function_definitions.tsv').module_id.iloc[0],'M00091')
 def test_wrong_graph_and_source_rejected(self):
  build(self.kg,self.nodes,self.projection,self.evidence)
  path=self.kg/'tables/kg_nodes.tsv';original=path.read_bytes();path.write_bytes(original+b'\n')
  with self.assertRaisesRegex(ValueError,'scope mismatch'):FunctionalRetrieval(self.kg)
  path.write_bytes(original);source=self.evidence/'tables/function_definitions.tsv';source.write_text(source.read_text()+'\n')
  with self.assertRaisesRegex(ValueError,'source changed'):FunctionalRetrieval(self.kg)
 def test_definition_cards_are_not_association_assertions(self):
  build(self.kg,self.nodes,self.projection,self.evidence);index=FunctionalRetrieval(self.kg)
  definitions=index.cards[index.cards.card_type.eq('functional_definition')]
  self.assertTrue(definitions.observed_status.eq('recorded_definition').all())
if __name__=='__main__':unittest.main()
