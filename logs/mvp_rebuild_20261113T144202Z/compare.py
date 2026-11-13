"""Compare rebuilt artifacts without assuming module labels stay equivalent."""
import json
from pathlib import Path
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from scipy.optimize import linear_sum_assignment
ROOT=Path(__file__).resolve().parents[2]
NEW=Path(__file__).parent.name
OLD='mvp_functional_20261008'

def read(path):return pd.read_csv(path,sep='\t',low_memory=False)
def analysis(branch):
    root=ROOT/'results/ngraph'/branch
    combo=root/'deep_modules/prev_10/pearson/tables'
    modules=read(combo/'vgae_taxon_modules.tsv')
    statuses=read(combo/'vgae_taxon_assignment_status.tsv')
    graph=read(root/'prev_10/tables/ngraph_site_graph_summary.tsv')
    kg=root/'knowledge_graph'
    pointer=json.loads((kg/'active_snapshot.json').read_text())
    active=kg/'snapshots'/pointer['snapshot_id']
    manifest=json.loads((active/'kg_manifest.json').read_text())
    scope=manifest['functional_projection']['scope']
    enrichment=root/'functional_enrichment'/scope['threshold']/scope['method']/scope['model']/scope['db_snapshot']
    funcs=read(enrichment/'tables/module_functions.tsv')
    coverage=read(active/'tables/kg_proxy_matching_coverage.tsv')
    validation=json.loads((kg/'tables/kg_substrate_validation.json').read_text())
    run_manifest=json.loads((root/'run_manifest.json').read_text())
    return dict(modules=modules,statuses=statuses,graph=graph,funcs=funcs,coverage=coverage,
                summary=dict(branch=branch,kg_snapshot_id=pointer['snapshot_id'],functional_snapshot=scope['db_snapshot'],
                assigned_taxa=len(modules),inventory_taxa=len(statuses),assignment_status=statuses.assignment_status.value_counts().to_dict(),
                module_sizes=modules.module_kmeans.value_counts().to_dict(),qualified_associations=int(funcs.publish_kg.sum()),
                tested_associations=len(funcs),proxy_coverage_rows=len(coverage),kg_validation=validation,
                packages=run_manifest.get('packages'),source_git_head=run_manifest.get('git_head')))
old,new=analysis(OLD),analysis(NEW)
shared=old['modules'][['taxon','module_kmeans']].merge(new['modules'][['taxon','module_kmeans']],on='taxon',suffixes=('_old','_new'),validate='one_to_one')
counts=pd.crosstab(shared.module_kmeans_old,shared.module_kmeans_new)
a,b=linear_sum_assignment(-counts.to_numpy())
label_map={counts.columns[j]:counts.index[i] for i,j in zip(a,b)}
def associations(frame,mapping=None):
    q=frame[frame.publish_kg.eq(True)].copy()
    if mapping is not None:q['matched_old_module']=q.module_id.map(mapping)
    return json.loads(q[[c for c in ['module_id','matched_old_module','function_id','q_value','permutation_z_score','carrier_count'] if c in q]].to_json(orient='records'))
report=dict(status='comparison_completed',baseline=old['summary'],candidate=new['summary'],shared_assigned_taxa=len(shared),
            module_membership_ARI=float(adjusted_rand_score(shared.module_kmeans_old,shared.module_kmeans_new)),
            candidate_to_baseline_label_overlap=label_map,
            baseline_associations=associations(old['funcs']),candidate_associations=associations(new['funcs'],label_map),
            baseline_site_graphs=json.loads(old['graph'].to_json(orient='records')),candidate_site_graphs=json.loads(new['graph'].to_json(orient='records')),
            limitations=['Module labels are run-scoped; overlap matching is descriptive.',
                        'Fixed-embedding clustering and repeated pipeline agreement do not establish bootstrap stability or unseen-core generalization.',
                        'Unresolved proxy units/calibration and interpolation flags remain unapproved.'])
output=ROOT/'results/ngraph'/NEW/'reports';output.mkdir(exist_ok=True)
(output/'REBUILD_COMPARISON.json').write_text(json.dumps(report,indent=2)+'\n')
(output/'REBUILD_COMPARISON.md').write_text('# Rebuild comparison\n\n'+f'Baseline: `{OLD}`. Candidate: `{NEW}`.\n\n'+f'{len(shared)} shared assigned taxa; adjusted Rand index {report["module_membership_ARI"]:.6f}. Candidate module sizes: {new["summary"]["module_sizes"]}. Qualified associations: {old["summary"]["qualified_associations"]} baseline, {new["summary"]["qualified_associations"]} candidate.\n\n'+'See REBUILD_COMPARISON.json for scope, label-overlap mapping, graph summaries, proxy coverage and validation. No independent generalization, biological activity or reviewed proxy calibration is implied.\n')
print(json.dumps({k:report[k] for k in ['status','shared_assigned_taxa','module_membership_ARI','candidate_to_baseline_label_overlap']},indent=2))
