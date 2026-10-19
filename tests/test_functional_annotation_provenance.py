"""Fresh evidence must agree with execution, full reference and native KO hits."""
import hashlib,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ngraph_functional_references import parse_kofam,parse_eggnog
spec=importlib.util.spec_from_file_location('functional_runner',Path(__file__).resolve().parents[1]/'scripts/17_ngraph_module_functions.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

class ProvenanceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'tables').mkdir()
  self.fasta=self.root/'protein.faa';self.fasta.write_text('>gene1\nMKK\n')
  self.output=self.root/'GCF_000000001.1.detail.tsv';self.output.write_text('*\tgene1\tK00001\t50.0\t60.0\t1e-20\tdescription\n')
  self.signature=dict(command=['exec_annotation',str(self.fasta)],proteome_sha256=sha(self.fasta),db_snapshot='frozen',database_content_sha256='database-hash',tool_version='1.3.0')
  self.marker=self.root/'GCF_000000001.1.completed.json';self.marker.write_text(json.dumps(dict(signature=self.signature,output_sha256=sha(self.output))))
  self.database=self.root/'database_hash_manifest_kofam.json';self.database.write_text(json.dumps(dict(content_sha256='database-hash')))
  entry=dict(genome_id='GCF_000000001.1',taxon='T',output_path=str(self.output),**self.signature)
  (self.root/'annotation_run_kofam.json').write_text(json.dumps(dict(database_fingerprint=dict(manifest_path=str(self.database),content_sha256='database-hash'),runs=[entry])))
  frame=pd.DataFrame(list(parse_kofam(self.output,'T','GCF_000000001.1','frozen')))
  frame.iloc[:0].to_csv(self.root/'tables/reference_annotations.tsv.gz',sep='\t',index=False)
  frame.to_csv(self.root/'tables/reference_annotations_kofam.tsv.gz',sep='\t',index=False)
  pd.DataFrame([dict(genome_id=entry['genome_id'],proteome_sha256=sha(self.fasta),proteome_path=str(self.fasta),protein_count=1)]).to_csv(self.root/'tables/retrieval_manifest.tsv',sep='\t',index=False)
 def tearDown(self):self.temp.cleanup()
 def test_valid_complete_evidence(self):
  frame,units=runner.annotation_selection(self.root);self.assertEqual(units,{'GCF_000000001.1'});self.assertEqual(frame.feature_id.tolist(),['K00001'])
 def test_database_signature_mismatch(self):
  proof=json.loads(self.marker.read_text());proof['signature']['database_content_sha256']='other';self.marker.write_text(json.dumps(proof))
  with self.assertRaisesRegex(ValueError,'signature mismatch'):runner.annotation_selection(self.root)
 def test_altered_inventory_not_trusted(self):
  p=self.root/'tables/reference_annotations_kofam.tsv.gz';f=pd.read_csv(p,sep='\t');f['feature_id']='K99999';f.to_csv(p,sep='\t',index=False)
  with self.assertRaisesRegex(ValueError,'inventory differs'):runner.annotation_selection(self.root)
 def test_changed_full_proteome(self):
  self.fasta.write_text('>gene1\nMMM\n')
  with self.assertRaisesRegex(ValueError,'proteome differs'):runner.annotation_selection(self.root)
 def test_sequence_count_mismatch(self):
  p=self.root/'tables/retrieval_manifest.tsv';f=pd.read_csv(p,sep='\t');f['protein_count']=2;f.to_csv(p,sep='\t',index=False)
  with self.assertRaisesRegex(ValueError,'sequence-count'):runner.annotation_selection(self.root)
 def test_unknown_native_sequence_identifier(self):
  self.output.write_text('*\tunknown_gene\tK00001\t50.0\t60.0\t1e-20\tdescription\n')
  proof=json.loads(self.marker.read_text());proof['output_sha256']=sha(self.output);self.marker.write_text(json.dumps(proof))
  with self.assertRaisesRegex(ValueError,'IDs outside'):runner.annotation_selection(self.root)
 def test_eggnog_preserves_go_ec_and_cog_letters(self):
  p=self.root/'sample.emapper.annotations';p.write_text('#query\tCOG_category\tGOs\tEC\tKEGG_ko\teggNOG_OGs\tPFAMs\n'+'gene1\tAB\tGO:0000001,GO:0000002\t1.1.1.1\tko:K00001\tOG1\tPF0001\n')
  rows=list(parse_eggnog(p,'T','G','db'));features={(r['feature_namespace'],r['feature_id']) for r in rows}
  self.assertTrue({('GO','GO:0000001'),('GO','GO:0000002'),('EC','1.1.1.1'),('COG_CATEGORY','A'),('COG_CATEGORY','B')}<=features)

if __name__=='__main__':unittest.main()
