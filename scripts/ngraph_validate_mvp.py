"""Validate real MVP artifacts and save evidence for the two demonstration questions."""
import argparse, json, logging, os
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score
from ngraph_kg_connectivity import ConnectivityIndex
root=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--branch',required=True);args=ap.parse_args()
    branch=root/'results/ngraph'/args.branch;kg=branch/'knowledge_graph/tables';combo=branch/'deep_modules/prev_10/pearson/tables'
    log=root/'logs'/args.branch/'validate_mvp.log';log.parent.mkdir(parents=True,exist_ok=True);logging.basicConfig(filename=log,level=logging.INFO)
    nodes=pd.read_csv(kg/'kg_nodes.tsv',sep='\t',keep_default_na=False, low_memory=False);edges=pd.read_csv(kg/'kg_edges.tsv',sep='\t',keep_default_na=False, low_memory=False)
    assert nodes.node_id.is_unique and edges.edge_id.is_unique
    lookup=nodes.set_index('node_id').node_type
    assert edges.source_id.isin(lookup.index).all() and edges.target_id.isin(lookup.index).all()
    assert (edges.source_id.map(lookup)==edges.source_node_type).all()
    assert (edges.target_id.map(lookup)==edges.target_node_type).all()
    schema=json.loads((root/'config_kg_schema.json').read_text())
    for predicate,group in edges.groupby('edge_type'):
        assert predicate in schema['relations'],predicate
        rule=schema['relations'][predicate]
        assert group.source_node_type.isin(rule['source']).all(),predicate
        assert group.target_node_type.isin(rule['target']).all(),predicate
    modules=pd.read_csv(combo/'vgae_taxon_modules.tsv',sep='\t');sizes=modules.module_kmeans.value_counts()
    assert 6<=len(sizes)<=8 and sizes.max()/len(modules)<.95
    features=pd.read_csv(combo/'vgae_embeddings.tsv',sep='\t')
    features=features[features.node_type=='taxon'];z=features[[c for c in features if c.startswith('z_')]].to_numpy()
    seed_labels=[KMeans(n_clusters=len(sizes),n_init=10,random_state=seed).fit_predict(z) for seed in [42,43,44]]
    stability=[adjusted_rand_score(seed_labels[0],labels) for labels in seed_labels[1:]]
    partitions=np.load(branch/'deep_modules/prev_10/pearson/models/vgae_pair_splits.npz')
    positives={tuple(p) for k in ['train','validation','test'] for p in partitions[k]}
    negative={tuple(p) for k in ['train_negative','validation_negative','test_negative'] for p in partitions[k]}
    assert not positives&negative
    index=ConnectivityIndex(nodes.to_dict('records'),edges.to_dict('records'));assert not index.invalid_edges
    taxon_edges=edges[(edges.edge_type=='sample_observed_taxon') & (edges.core=='ST8')]
    variables=nodes[(nodes.node_type=='ProxyVariable') & nodes.label.str.contains('sst',case=False)].node_id.tolist()
    result=None
    for taxon in taxon_edges.target_id.value_counts().head(20).index:
        for variable in variables:
            candidate=index.search(taxon,variable,'taxon_proxy')
            if candidate.get('path_count',0):result=candidate;break
        if result:break
    assert result is not None,'No taxon/SST evidence paths'
    bridge=index.search('site:ST8','site:ST13','site_module_bridge',limit=10)
    assert bridge['path_count']>0
    obs=pd.read_csv(kg/'kg_observations.tsv',sep='\t');measurements=pd.read_csv(kg/'kg_measurements.tsv',sep='\t')
    observation_ids=set(obs.observation_id)
    referenced={v for values in measurements.observation_ids.dropna() for v in values.split(',')}
    assert observation_ids==referenced
    annotations=modules.merge(nodes[nodes.node_type=='Taxon'],left_on='taxon',right_on='taxon',suffixes=('','_kg'))
    annotations.groupby(['module_kmeans','functional_group','ecological_role'],dropna=False).size().reset_index(name='taxa').to_csv(combo/'mvp_module_function_counts.tsv',sep='\t',index=False)
    report={'status':'passed' ,'branch':args.branch,'nodes':len(nodes),'edges':len(edges),'dangling_references':0,'declared_endpoint_types':'passed',
      'taxa':int((nodes.node_type=='Taxon').sum()),'taxa_evidence_status':nodes[nodes.node_type=='Taxon'].evidence_status.value_counts().to_dict(),
      'module_sizes':sizes.to_dict(),'assignment_seed_stability_ari':stability,'stability_scope':'Repeated KMeans on fixed learned embeddings; not graph/bootstrap validation',
      'diffpool_sizes':pd.read_csv(combo/'diffpool_consensus_modules.tsv',sep='\t').consensus_module.value_counts().to_dict(),
      'observations':len(obs),'observation_provenance':'all observations referenced by measurement summaries',
      'questions':[{'question':'Which samples connect this taxon to an SST proxy?','answer':result},{'question':'Which taxa link these two cores through a module?','answer':bridge}]}
    (kg/'mvp_validation_and_demo.json').write_text(json.dumps(report,indent=2)+'\n')
    logging.info('PASS: %d nodes, %d edges, modules %s',len(nodes),len(edges),sizes.to_dict())
    print(json.dumps({k:v for k,v in report.items() if k!='questions'},indent=2))
if __name__=='__main__':main()
