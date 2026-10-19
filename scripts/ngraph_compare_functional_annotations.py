"""Compare verified fresh reference KOs with archived module-scoped evidence.

Native gene IDs from different annotation providers are never joined. Agreement
uses genome/KO presence on an explicitly frozen legacy KO universe. This is QA,
not a precision estimate against a gold standard.
"""
import argparse,hashlib,importlib.util,json,logging
from pathlib import Path
import pandas as pd
from ngraph_functional_statistics import ModuleDefinition
ROOT=Path(__file__).resolve().parents[1]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--reference-snapshot',required=True);ap.add_argument('--label',default='pilot_review_20261008');args=ap.parse_args()
 for identifier in [args.reference_snapshot,args.label]:
  if Path(identifier).name!=identifier or identifier in ['.','..']:raise ValueError('Invalid snapshot identifier')
 reference=ROOT/'data/reference/functional'/args.reference_snapshot;output=reference/'comparisons'/args.label
 if (output/'manifest.json').exists():raise SystemExit('Comparison label already exists; choose another immutable label')
 (output/'tables').mkdir(parents=True,exist_ok=True)
 log=ROOT/'logs'/args.reference_snapshot/'annotation_comparison.log';log.parent.mkdir(parents=True,exist_ok=True)
 logging.basicConfig(filename=log,level=logging.INFO)
 spec=importlib.util.spec_from_file_location('functional_analysis_runner',ROOT/'scripts/17_ngraph_module_functions.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
 selected,processed=runner.annotation_selection(reference)
 legacy=runner.read(reference/'tables/reference_annotations.tsv.gz');legacy=legacy[legacy.feature_namespace.eq('KEGG_KO')]
 fresh=selected[selected.source_kind.eq('fresh_reference_kofam') & selected.feature_namespace.eq('KEGG_KO')]
 pilot=runner.read(reference/'tables/pilot_references.tsv');definitions=runner.read(reference/'tables/module_definitions.tsv')
 frozen=set(legacy.feature_id);legacy_sets=legacy.groupby('genome_id').feature_id.apply(set).to_dict();fresh_sets=fresh.groupby('genome_id').feature_id.apply(set).to_dict()
 summaries=[];disagreements=[];modules=[]
 parsed={}
 for row in definitions.itertuples():
  try:parsed[row.module_id]=ModuleDefinition(row.module_definition)
  except ValueError:continue
 for row in pilot.itertuples():
  old=legacy_sets.get(row.genome_id,set());new=fresh_sets.get(row.genome_id)
  record=dict(taxon=row.taxon,genome_id=row.genome_id,legacy_kos=len(old),frozen_legacy_ko_universe=len(frozen),fresh_status='verified_full_proteome' if row.genome_id in processed else 'not_computed_no_fresh_annotations')
  if new is not None:
   common_old=old&frozen;common_new=new&frozen
   record.update(fresh_kos=len(new),shared_frozen_kos=len(common_old&common_new),legacy_only_kos=len(common_old-common_new),fresh_only_frozen_kos=len(common_new-common_old),fresh_outside_frozen_universe=len(new-frozen),frozen_jaccard=len(common_old&common_new)/max(1,len(common_old|common_new)))
   for ko in sorted(old|new):
    if (ko in old)!=(ko in new):disagreements.append(dict(taxon=row.taxon,genome_id=row.genome_id,ko_id=ko,legacy_present=ko in old,fresh_present=ko in new,within_frozen_universe=ko in frozen))
  summaries.append(record)
  for definition in definitions.itertuples():
   if definition.module_id not in parsed:continue
   old_score=parsed[definition.module_id].evaluate(old)
   result=dict(taxon=row.taxon,genome_id=row.genome_id,function_id=definition.module_id,function_namespace=definition.module_namespace,legacy_reconstructed_completeness=old_score['completeness'],legacy_reconstructed_complete=old_score['is_complete'],legacy_unknown_route=old_score['unresolved_definition'],fresh_status=record['fresh_status'])
   if new is not None:
    score=parsed[definition.module_id].evaluate(new)
    result.update(fresh_completeness=score['completeness'],fresh_complete=score['is_complete'],fresh_unknown_route=score['unresolved_definition'],complete_disagreement=score['is_complete']!=old_score['is_complete'])
   modules.append(result)
 pd.DataFrame(summaries).to_csv(output/'tables/reference_comparison.tsv',sep='\t',index=False)
 pd.DataFrame(disagreements,columns=['taxon','genome_id','ko_id','legacy_present','fresh_present','within_frozen_universe']).to_csv(output/'tables/ko_disagreements.tsv',sep='\t',index=False)
 pd.DataFrame(modules).to_csv(output/'tables/module_completeness_comparison.tsv.gz',sep='\t',index=False)
 status='computed_reference_QA' if processed else 'not_computed_no_fresh_annotations'
 manifest=dict(status=status,reference_snapshot=args.reference_snapshot,pilot_references=len(pilot),fresh_pilot_references=sum(pilot.genome_id.isin(processed)),frozen_legacy_ko_universe=len(frozen),native_gene_ids_joined=False,diagnostic_markers='not_reviewed_no_curated_marker_set',scope='KO_presence_and_frozen_module_definitions; archive_not_gold_standard',seed=42)
 manifest['sha256']={str(p.relative_to(reference)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [reference/'tables/reference_annotations.tsv.gz',reference/'tables/module_definitions.tsv',reference/'tables/pilot_references.tsv']}
 (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (output/'report.md').write_text('# Annotation pilot comparison\n\n'+f'Status: **{status}**. Pilot references: {len(pilot)}; freshly annotated pilot references: {manifest["fresh_pilot_references"]}.\n\n'+'Archived module-scoped KO evidence is not a gold standard and missing archived KOs are not known absences. Native gene IDs from different providers are not joined. Comparison uses the frozen legacy KO universe; newly observed KOs outside it are reported separately. Module completeness uses the same frozen definitions in both arms. Curated diagnostic-marker acceptance remains open.\n')
 print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
