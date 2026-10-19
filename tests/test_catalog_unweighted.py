import importlib.util,sys,unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ngraph_functional_statistics import enrich_capabilities
from ngraph_functional_background import prepare_background
spec=importlib.util.spec_from_file_location('catalog_runner',Path(__file__).resolve().parents[1]/'scripts/18_ngraph_catalog_enrichment.py');catalog=importlib.util.module_from_spec(spec);spec.loader.exec_module(catalog)

class CatalogTests(unittest.TestCase):
 def test_existing_profiles_do_not_require_new_proteomes(self):
  mapping=pd.DataFrame(dict(taxon=['a','b','c'],genome_id=['G1','G2','G3'],domain=['d__Bacteria']*3,mapping_status=['exact_native_mapping']*3))
  members=pd.DataFrame(dict(taxon=['a','b','c'],module_id=['M1','M2','M2']))
  retention=pd.DataFrame(dict(subspecies=['a','b','c'],prevalence_samples=[10]*3,tad_positive_samples=[5]*3))
  abundance=pd.DataFrame([[1,1,1]],columns=['a','b','c'],index=['s'])
  meta=pd.DataFrame(dict(sample=['s'],physical_core=['ST8']))
  bg,inventory,coverage=prepare_background(mapping,members,{'G1','G2'},retention,abundance,meta,evidence_scope='recorded_annotation_catalog')
  self.assertEqual(set(bg.index),{'a','b'});self.assertFalse(inventory.processed_full_proteome.any())
  self.assertEqual(inventory.set_index('taxon').background_status.c,'no_catalog_annotation_profile')
  self.assertIn('independent_catalog_references',coverage)
 def test_catalog_non_support_and_unknown_definition_are_distinct(self):
  cap=pd.DataFrame(dict(taxon=['a','b','a','b'],function_id=['F1','F1','F2','F2'],function_namespace=['KEGG_MODULE']*4,
   status=['recorded_catalog_supported_framework']*3+['unresolved_definition'],is_carrier=[True,False,True,False]))
  matrix,qc=catalog.catalog_matrix(cap,pd.DataFrame(index=['a','b']))
  self.assertEqual(list(matrix.columns),['F1']);self.assertFalse(matrix.loc['b','F1'])
  self.assertFalse(qc.set_index('function_id').eligible_complete_background.F2)
 def statistical_fixture(self):
  cap=pd.DataFrame({'F':[True]*20+[False]*20});labels=np.array(['M1']*20+['M2']*20)
  meta=pd.DataFrame(dict(domain=['B']*40,phylum=['P']*40,tad_support=['tad']*40,prevalence_samples=[10]*40,physical_core_count=[3]*40))
  return cap,labels,meta
 def test_z_uses_actual_null_mean_and_signed_departure(self):
  cap,labels,meta=self.statistical_fixture();result,_=enrich_capabilities(cap,labels,meta,permutations=9999)
  first=result[result.module_id.eq('M1')].iloc[0];second=result[result.module_id.eq('M2')].iloc[0]
  self.assertAlmostEqual(first.null_carrier_count_mean,10,delta=.1)
  self.assertGreater(first.permutation_z_score,5);self.assertLess(second.permutation_z_score,-5)
  self.assertAlmostEqual(first.permutation_z_score,(first.carrier_count-first.null_carrier_count_mean)/first.null_carrier_count_sd)
 def test_constant_null_z_is_undefined_and_not_significant(self):
  cap,labels,meta=self.statistical_fixture();meta['phylum']=labels
  result,_=enrich_capabilities(cap,labels,meta,permutations=999)
  self.assertTrue(result.permutation_z_score.isna().all());self.assertTrue(result.p_value.eq(1).all());self.assertFalse(result.publish_kg.any())

if __name__=='__main__':unittest.main()
