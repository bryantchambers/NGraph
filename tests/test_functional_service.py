"""Regression checks for alias resolution, support status and conservative Query."""
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('path_browser',ROOT/'scripts/14_ngraph_local_browser.py');browser=importlib.util.module_from_spec(spec);spec.loader.exec_module(browser)
from test_functional_paths import fixture,SCOPE

class FunctionalServiceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.app=object.__new__(browser.ConstellationsService)
  self.app.branch='demo';self.app.kg_dir=Path(self.temp.name);(self.app.kg_dir/'indexes').mkdir()
  nodes,edges=fixture();nodes[2]['module_id']='M3';nodes.append(dict(node_id='kegg.module:M00091',node_type='FunctionalConcept',label='PC'))
  self.app.kg_nodes=pd.DataFrame(nodes);self.app.kg_edges=pd.DataFrame(edges);self.app.kg_node_ids=set(self.app.kg_nodes.node_id);self.app.kg_node_lookup=self.app.kg_nodes.set_index('node_id')
  self.app.kg_manifest={'functional_projection':{'scope':dict(SCOPE,model='vgae')}}
  with closing(sqlite3.connect(self.app.kg_dir/'indexes/support_status.sqlite')) as conn, conn:
   conn.execute('CREATE TABLE support_status(taxon,function_id,is_carrier,status)');conn.execute("INSERT INTO support_status VALUES('T2','M00091',0,'recorded_catalog_supported_framework')")
   conn.execute('CREATE TABLE inventory(taxon,background_status)')
 def tearDown(self):
  self.app.scoped_connectivity.cache_clear();self.temp.cleanup()
 def test_aliases_and_missing_id(self):
  scope=self.app.functional_path_scope();self.assertEqual(self.app.resolve_functional_id('M00091',scope),'F');self.assertEqual(self.app.resolve_functional_id('M3',scope),'M');self.assertEqual(self.app.resolve_functional_id('kegg.module:M00091',scope),'F')
  self.assertEqual(self.app.kg_connectivity('missing',target='M00091')['status'],'missing')
 def test_member_only_catalog_status_and_scope(self):
  result=self.app.kg_connectivity('T2','M00091','taxon_module_function');self.assertEqual(result['paths'][0]['carrier_status'],'no_complete_support_recorded');self.assertFalse(result['paths'][0]['witnesses'])
  self.assertEqual(self.app.kg_connectivity('T2','M00091','taxon_module_function',snapshot='other')['status'],'missing')
  self.assertEqual(self.app.kg_connectivity('kegg.module:M00091',metapath='function_module_taxon',snapshot='other')['status'],'missing')
 def test_query_no_arbitrary_execution_and_unknowns(self):
  result=self.app.query('Which modules are enriched for M00091?');self.assertEqual(result['query_type'],'functional_kg');self.assertTrue(result['retrieved_cards'])
  self.assertIn('not measured activity',result['markdown']);self.assertTrue(self.app.query('What functional roles are present?')['answer_lines'])
  self.assertEqual(self.app.recorded_carrier_status("x' OR 1=1 --",'M00091'),'not_evaluated')
