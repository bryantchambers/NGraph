"""Verify KG types, coverage, units and native-source-to-proxy provenance."""
import argparse, hashlib, json, logging
from pathlib import Path
import numpy as np
import pandas as pd
from ngraph_kg_snapshots import active_directory, verify_active, verify_directory
from ngraph_validate_functional_graph import validate_functional_graph
ROOT=Path(__file__).resolve().parents[1]
def validate(branch, snapshot=None):
    kg=ROOT/'results/ngraph'/branch/'knowledge_graph'
    if snapshot and Path(snapshot).name!=snapshot:raise ValueError('Invalid snapshot ID')
    directory=kg/'snapshots'/snapshot if snapshot else active_directory(kg)
    verify_directory(directory)
    tables=directory/'tables'
    def read(name):return pd.read_csv(tables/name,sep='\t',low_memory=False)
    nodes,edges=read('kg_nodes.tsv'),read('kg_edges.tsv')
    assert nodes.node_id.is_unique and edges.edge_id.is_unique
    kinds=nodes.set_index('node_id').node_type
    assert edges.source_id.isin(kinds.index).all() and edges.target_id.isin(kinds.index).all()
    assert edges.source_id.map(kinds).equals(edges.source_node_type)
    assert edges.target_id.map(kinds).equals(edges.target_node_type)
    schema=json.loads((ROOT/'config_kg_schema.json').read_text())
    for predicate,part in edges.groupby('edge_type'):
        rule=schema['relations'][predicate]
        assert part.source_node_type.isin(rule['source']).all() and part.target_node_type.isin(rule['target']).all()
    if schema["schema_version"] == "mvp-3" and (nodes.node_type == "FunctionalConcept").any():
        validate_functional_graph(nodes, edges)
    obs=read('kg_observations.tsv');raw=read('kg_proxy_source_observations.tsv');coverage=read('kg_proxy_matching_coverage.tsv')
    assert raw.source_observation_id.is_unique
    proxy=obs[obs.match_method.isin(['exact_depth','within_depth_tolerance','linear_depth_interpolation'])].copy()
    assert len(proxy)>0 and proxy.unit.notna().all() and proxy.unit_status.notna().all()
    grid=raw.set_index('source_observation_id').value
    known_source_ids=set(grid.index)
    def source_value(ids):
        tokens=str(ids).split(',');assert set(tokens)<=known_source_ids
        values=grid.loc[tokens];assert np.isfinite(values).all();return values.mean()
    # Cache repeated brackets: each source level can serve many samples/libraries.
    cache={}
    for ids in pd.concat([proxy.source_observation_ids_left,proxy.source_observation_ids_right]).unique():
        cache[ids]=source_value(ids)
    left=proxy.source_observation_ids_left.map(cache);right=proxy.source_observation_ids_right.map(cache)
    assert np.allclose(left,proxy.value_left,rtol=1e-12,atol=1e-12)
    assert np.allclose(right,proxy.value_right,rtol=1e-12,atol=1e-12)
    expected=left*(1-proxy.interpolation_fraction)+right*proxy.interpolation_fraction
    assert np.allclose(expected,proxy.value,rtol=1e-12,atol=1e-12)
    interpolated=proxy[proxy.match_method=='linear_depth_interpolation']
    assert (interpolated.depth_left_cm<interpolated.depth_in_core_cm).all()
    assert (interpolated.depth_right_cm>interpolated.depth_in_core_cm).all()
    assert np.allclose(interpolated.bracket_width_cm,interpolated.depth_right_cm-interpolated.depth_left_cm)
    matched=proxy[proxy.match_method!='linear_depth_interpolation'];assert (matched.match_delta<=.5000000001).all()
    assert not proxy.match_method.str.contains('age').any()
    assert not proxy.variable.str.contains('(^|_)count$',regex=True).where(proxy.match_method=='linear_depth_interpolation',False).any()
    shared=proxy[proxy.core=='GeoB25202_R1'].merge(proxy[proxy.core=='GeoB25202_R2'],on=['source_table','variable','depth_in_core_cm'],suffixes=('_r1','_r2'))
    assert len(shared)>0 and np.allclose(shared.value_r1,shared.value_r2,rtol=0,atol=0)
    assert coverage[['source_table','sample_id','variable']].duplicated().sum()==0
    valid=coverage[coverage.matched==True]
    assert len(valid)==len(proxy)
    counts=coverage.groupby('source_table').agg(requested=('matched','size'),matched=('matched','sum'));counts['unmatched']=counts.requested-counts.matched
    native_counts=raw.groupby('source_table').agg(source_cells=('value','size'),finite_cells=('value',lambda x:np.isfinite(x).sum()),source_rows=('source_row','nunique'))
    provenance=json.loads((ROOT/'data/provenance/kg_feedstock_import.json').read_text())
    for record in provenance:
        assert hashlib.sha256((ROOT/record['canonical']).read_bytes()).hexdigest()==record['sha256']
    functional_nodes=nodes[nodes.node_type.isin(['ModuleFunctionalAssociation','ReferenceFunctionalAnnotation','FunctionalFeature'])]
    associations=nodes[nodes.node_type=='ModuleFunctionalAssociation']
    if len(associations):
        assert (pd.to_numeric(associations.q_value,errors='coerce')<=.05).all()
        assert associations.test_method.eq('matched_permutation').all()
        assert (pd.to_numeric(associations.prevalence_difference,errors='coerce')>=.10).all()
        assert (pd.to_numeric(associations.odds_ratio,errors='coerce')>=1.5).all()
        assert (pd.to_numeric(associations.carrier_count,errors='coerce')>=5).all()
        assert (pd.to_numeric(associations.module_annotated_count,errors='coerce')>=20).all()
        assert (pd.to_numeric(associations.annotation_coverage,errors='coerce')>=.70).all()
        assert (pd.to_numeric(associations.exchangeable_fraction,errors='coerce')>=.50).all()
        assert not associations.annotation_status.fillna('').str.contains('legacy',case=False).any()
    report={'kg_snapshot_id':tables.parent.name,'status':'passed','branch':branch,'schema':schema['schema_version'],'dangling_references':0,
      'functional_projected_nodes':len(functional_nodes),'functional_associations':len(associations),
      'nodes':len(nodes),'edges':len(edges),'source_cells':len(raw),'matched_proxy_values':len(proxy),
      'geoB_same_depth_library_comparisons':len(shared),'geoB_same_depth_values_identical':True,
      'source_to_derived_values_reconstructed':True,'age_only_matching':False,'interpolation_extrapolations':0,
      'depth_tolerance_cm':.5,'large_gap_values':int(proxy.large_gap.sum()),
      'large_gap_rule':'Bracket width > 3 times within-core/variable median source spacing; review flag, not exclusion',
      'unit_status_counts':proxy.unit_status.value_counts().to_dict(),
      'units_limitation':'Unspecified native units are explicit; inferred units are not promoted to confirmed',
      'coverage_by_dataset':counts.to_dict('index'),'native_source_coverage':native_counts.to_dict('index'),
      'matching_status_counts':coverage.status.value_counts().to_dict(),'curated_xrf_used':bool(proxy[proxy.source_table=='xrf_geochemistry'].source_file.str.endswith('combined_xrf_geochemistry_curated.csv').all())}
    assert report['curated_xrf_used']
    output=kg/'validation_history'/f'{snapshot}.json' if snapshot else kg/'tables/kg_substrate_validation.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    logging.info('KG substrate validation passed: %s',report)
    print(json.dumps(report,indent=2));return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--branch',required=True);ap.add_argument('--snapshot');args=ap.parse_args()
    log=ROOT/'logs'/args.branch/'kg_substrate_validation.log';log.parent.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=log,level=logging.INFO)
    validate(args.branch,args.snapshot)
