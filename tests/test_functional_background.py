import sys,unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ngraph_functional_background import prepare_background,capability_matrix
from ngraph_functional_statistics import ks_statistics_matrix,ks_high_affinity,ks_enrichment,bh_adjust,matched_groups,enrich_capabilities

class BackgroundTests(unittest.TestCase):
 def fixture(self):
  mapping=pd.DataFrame(dict(taxon=['a','b','c','d','e'],genome_id=['G1','G1','G2','G2','G3'],domain=['d__Bacteria']*5,mapping_status=['exact_native_mapping']*5))
  members=pd.DataFrame(dict(taxon=['a','b','c','d','e'],module_id=['M1','M1','M1','M2','M2']))
  retention=pd.DataFrame(dict(subspecies=list('abcde'),prevalence_samples=[10]*5,tad_positive_samples=[5]*5))
  abundance=pd.DataFrame(np.ones((2,5)),columns=list('abcde'),index=['s1','s2'])
  meta=pd.DataFrame(dict(sample=['s1','s2'],physical_core=['ST8','ST13']))
  return mapping,members,retention,abundance,meta
 def test_reference_dependencies_and_unknown_inventory(self):
  m,l,r,a,s=self.fixture();b,i,c=prepare_background(m,l,{'G1','G2'},r,a,s)
  self.assertEqual(list(b.index),['a'])
  statuses=i.set_index('taxon').background_status
  self.assertEqual(statuses.b,'shared_reference_collapsed_alias')
  self.assertEqual(statuses.c,'shared_reference_conflicting_modules')
  self.assertEqual(statuses.d,'shared_reference_conflicting_modules')
  self.assertEqual(statuses.e,'no_fresh_full_proteome_annotation')
  self.assertFalse(c.coverage_pass.any())
 def test_missing_entire_unit_cannot_disappear(self):
  frame=pd.DataFrame(dict(taxon=['a'],function_id=['F'],function_namespace=['KEGG_MODULE'],status=['fresh_full_proteome_processed'],is_carrier=[True],completeness=[1.]))
  matrix,qc=capability_matrix(frame,pd.DataFrame(index=['a','b']))
  self.assertEqual(list(matrix.index),['a','b']);self.assertEqual(len(matrix.columns),0)
  self.assertFalse(qc.eligible_complete_background.iloc[0])
 def test_unresolved_is_unknown_not_negative(self):
  frame=pd.DataFrame(dict(taxon=['a','b'],function_id=['F','F'],function_namespace=['KEGG_MODULE']*2,status=['fresh_full_proteome_processed','unresolved_definition'],is_carrier=[True,False],completeness=[1.,0.]))
  matrix,_=capability_matrix(frame,pd.DataFrame(index=['a','b']));self.assertEqual(len(matrix.columns),0)
 def test_empty_fresh_background(self):
  m,l,r,a,s=self.fixture();b,i,c=prepare_background(m,l,set(),r,a,s)
  self.assertTrue(b.empty);self.assertTrue(c.independent_fresh_references.eq(0).all())

class StatisticalBoundaryTests(unittest.TestCase):
 def test_unannotated_modules_stay_in_declared_bh_family(self):
  cap=pd.DataFrame({'F':[True]*15+[False]*5+[True]*5+[False]*15})
  labels=np.array(['M1']*20+['M2']*20)
  meta=pd.DataFrame(dict(domain=['B']*40,phylum=['P']*40,tad_support=['tad']*40,prevalence_samples=[10]*40,physical_core_count=[3]*40))
  result,manifest=enrich_capabilities(cap,labels,meta,permutations=99,declared_modules=['M1','M2','M3'])
  self.assertEqual(manifest['hypotheses'],3)
  missing=result[result.module_id.eq('M3')].iloc[0]
  self.assertEqual(missing.p_value,1);self.assertFalse(missing.publish_kg)
  self.assertEqual(missing.module_annotated_count,0)
 def test_vectorized_ks_agrees_with_scalar_including_ties(self):
  rng=np.random.default_rng(42);scores=rng.integers(0,6,60);carriage=rng.random((60,25))>.5
  expected=[ks_high_affinity(scores,carriage[:,i]) for i in range(25)]
  np.testing.assert_allclose(ks_statistics_matrix(scores,carriage),expected,atol=1e-15)
 def test_invalid_p_values_rejected(self):
  for values in [[-.1],[1.1],[np.inf]]:
   with self.assertRaises(ValueError):bh_adjust(values)
 def test_unknown_matching_covariate_is_not_zero(self):
  meta=pd.DataFrame(dict(domain=['B'],phylum=['P'],tad_support=['tad'],prevalence_samples=[np.nan],physical_core_count=[3]))
  with self.assertRaises(ValueError):matched_groups(meta)
 def test_ks_alignment_and_reproducibility(self):
  n=40;cap=pd.DataFrame({'F':[False]*20+[True]*20},index=[f'T{i}' for i in range(n)])
  affin=pd.DataFrame({'M1':np.arange(n)},index=cap.index)
  meta=pd.DataFrame(dict(domain=['B']*n,phylum=['P']*n,tad_support=['tad']*n,prevalence_samples=[10]*n,physical_core_count=[3]*n))
  x=ks_enrichment(cap,affin,meta,permutations=99);y=ks_enrichment(cap,affin,meta,permutations=99)
  pd.testing.assert_frame_equal(x,y);self.assertEqual(x.p_value.iloc[0],.01)
  with self.assertRaises(ValueError):ks_enrichment(cap,affin.iloc[::-1],meta,permutations=99)

if __name__=='__main__':unittest.main()
