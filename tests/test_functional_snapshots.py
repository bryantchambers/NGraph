"""Publication is idempotent, historical files stay intact, and pointer changes are atomic."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import sys
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ngraph_kg_snapshots import publish,active_directory,verify_active,activate
class SnapshotTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'tables').mkdir();(self.root/'tables/original.tsv').write_text('historical\n')
  self.nodes=pd.DataFrame([{'node_id':'T','node_type':'Taxon'}]);self.edges=pd.DataFrame([{'edge_id':'e','source_id':'T','target_id':'T'}]);self.manifest={'schema_version':'fixture'};self.projection={'scope':{'branch':'demo'}}
 def tearDown(self):self.temp.cleanup()
 def test_idempotence_history_and_integrity(self):
  one=publish(self.root,self.nodes,self.edges,self.manifest,self.projection);two=publish(self.root,self.nodes,self.edges,self.manifest,self.projection)
  self.assertEqual(one,two);self.assertEqual((self.root/'tables/original.tsv').read_text(),'historical\n');self.assertEqual(verify_active(self.root)['status'],'passed')
  (active_directory(self.root)/'tables/kg_nodes.tsv').write_text('tampered')
  with self.assertRaises(ValueError):verify_active(self.root)
 def test_failed_activation_retains_previous_complete_bundle(self):
  first=publish(self.root,self.nodes,self.edges,self.manifest,self.projection);self.nodes.loc[0,'label']='new'
  with patch('ngraph_kg_snapshots.os.replace',side_effect=OSError('interrupted activation')):
   with self.assertRaises(OSError):publish(self.root,self.nodes,self.edges,self.manifest,self.projection)
  self.assertEqual(active_directory(self.root).name,first);self.assertEqual(verify_active(self.root)['status'],'passed')
 def test_staged_candidate_requires_validation_and_retains_active(self):
  first=publish(self.root,self.nodes,self.edges,self.manifest,self.projection);self.nodes.loc[0,'label']='candidate'
  candidate=publish(self.root,self.nodes,self.edges,self.manifest,self.projection,activate_snapshot=False)
  self.assertEqual(active_directory(self.root).name,first)
  with self.assertRaises(FileNotFoundError):activate(self.root,candidate,require_validation=True)
  self.assertEqual(active_directory(self.root).name,first)
  directory=self.root/'validation_history';directory.mkdir();(directory/f'{candidate}.json').write_text(json.dumps({'status':'passed','kg_snapshot_id':candidate}))
  activate(self.root,candidate,require_validation=True);self.assertEqual(active_directory(self.root).name,candidate)
