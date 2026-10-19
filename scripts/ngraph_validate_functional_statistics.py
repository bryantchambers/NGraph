"""Save synthetic statistical validation, explicitly separate from biology."""
import argparse,json,logging,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import beta
from ngraph_functional_statistics import enrich_capabilities,ks_enrichment,ks_high_affinity,ks_statistics_matrix,bh_adjust
ROOT=Path(__file__).resolve().parents[1]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--branch',required=True);ap.add_argument('--permutations',type=int,default=100000);ap.add_argument('--null-replicates',type=int,default=100);args=ap.parse_args()
 output=ROOT/'results/ngraph'/args.branch/'functional_statistics_validation';output.mkdir(parents=True,exist_ok=True)
 log=ROOT/'logs'/args.branch/'functional_statistics_validation.log';log.parent.mkdir(parents=True,exist_ok=True)
 logging.basicConfig(level=logging.INFO,handlers=[logging.FileHandler(log),logging.StreamHandler()])
 rng=np.random.default_rng(42);n=120;labels=np.array(['M1']*60+['M2']*60)
 meta=pd.DataFrame(dict(domain=['B']*n,phylum=['P']*n,tad_support=['tad']*n,prevalence_samples=[20]*n,physical_core_count=[3]*n))
 cap=pd.DataFrame({'planted':[True]*55+[False]*5+[True]*5+[False]*55,'duplicate_planted':[True]*55+[False]*5+[True]*5+[False]*55,'balanced':[True,False]*60})
 started=time.monotonic();result,manifest=enrich_capabilities(cap,labels,meta,permutations=args.permutations,progress=lambda done,total:logging.info('Synthetic primary %s/%s',done,total))
 result.to_csv(output/'synthetic_signal.tsv',sep='\t',index=False)
 assert result.loc[result.module_id.eq('M1') & result.function_id.eq('planted'),'publish_kg'].all()
 for _,group in result[result.function_id.isin(['planted','duplicate_planted'])].groupby('module_id'):assert group.p_value.nunique()==1
 signal_seconds=time.monotonic()-started
 confounded=meta.copy();confounded['phylum']=labels
 negative,_=enrich_capabilities(cap,labels,confounded,permutations=999)
 assert negative.p_value.eq(1).all() and not negative.publish_kg.any()
 negative.to_csv(output/'synthetic_taxonomy_confounding.tsv',sep='\t',index=False)
 null_records=[]
 for replicate in range(args.null_replicates):
  neutral=pd.DataFrame(rng.random((n,4))<.3,columns=[f'null_{i}' for i in range(4)])
  tested,_=enrich_capabilities(neutral,labels,meta,permutations=999,seed=1000+replicate)
  null_records.append(dict(replicate=replicate,any_bh_rejection=bool(tested.q_value.le(.05).any()),minimum_p=float(tested.p_value.min())))
 null=pd.DataFrame(null_records);null.to_csv(output/'synthetic_null.tsv',sep='\t',index=False)
 discoveries=int(null.any_bh_rejection.sum());replicates=len(null)
 interval=[0 if discoveries==0 else float(beta.ppf(.025,discoveries,replicates-discoveries+1)),1 if discoveries==replicates else float(beta.ppf(.975,discoveries+1,replicates-discoveries))]
 assert interval[0]<=.05,'Synthetic null shows material anti-conservative family rejection rate'
 scores=rng.integers(0,15,n);matrix=rng.random((n,40))<.4
 np.testing.assert_allclose(ks_statistics_matrix(scores,matrix),[ks_high_affinity(scores,matrix[:,i]) for i in range(40)],atol=1e-15)
 affinity=pd.DataFrame({'M1':np.arange(n)},index=cap.index)
 started=time.monotonic();ks=ks_enrichment(cap,affinity,meta,permutations=args.permutations,progress=lambda module,done,total:logging.info('Synthetic KS %s/%s',done,total))
 ks.to_csv(output/'synthetic_ks.tsv',sep='\t',index=False)
 ks_seconds=time.monotonic()-started
 report=dict(status='passed',scope='synthetic_algorithm_validation_not_real_data_enrichment_or_phylogenetic_validation',seed=42,permutations=args.permutations,
  synthetic_signal_detected=True,whole_annotation_row_dependence_preserved=True,taxonomy_confounding_rejected=True,ks_vectorized_ties_agree_with_scalar=True,
  null_replicates=replicates,null_family_rejections=discoveries,null_family_rejection_rate=discoveries/replicates,null_95_percent_interval=interval,
  primary_family_hypotheses=manifest['hypotheses'],primary_seconds=signal_seconds,ks_seconds=ks_seconds,packages=dict(numpy=np.__version__,pandas=pd.__version__),runtime_command=sys.argv)
 (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
