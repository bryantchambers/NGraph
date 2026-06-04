# NGraph Graph-of-Graphs Report

- Generated: 2026-06-04 14:09:41 CEST
- Nodes: site-specific taxon graphs.
- Edge weight: mean of edge-Jaccard similarity and normalized-Laplacian spectral-quantile similarity.
- Methods compared: `spearman`, `mi_aracne`.

## Similarity Table

|method|core_a|core_b|edge_intersection|edge_union|edge_jaccard|spectral_distance|spectral_similarity|super_weight|
|---|---|---|---|---|---|---|---|---|
|spearman|GeoB25202_R1|GeoB25202_R2|1686|13530|0.1246|0.1544|0.8663|0.4955|
|spearman|GeoB25202_R1|ST13|338|10520|0.03214|2.301|0.303|0.1676|
|spearman|GeoB25202_R1|ST8|440|11570|0.03804|2.455|0.2895|0.1637|
|spearman|GeoB25202_R2|ST13|261|9634|0.02709|2.255|0.3072|0.1672|
|spearman|GeoB25202_R2|ST8|418|10630|0.03933|2.417|0.2926|0.166|
|spearman|ST13|ST8|503|6187|0.0813|0.5122|0.6613|0.3713|
|mi_aracne|GeoB25202_R1|GeoB25202_R2|49|2685|0.01825|0.02409|0.9765|0.4974|
|mi_aracne|GeoB25202_R1|ST13|42|2746|0.01529|0.09248|0.9153|0.4653|
|mi_aracne|GeoB25202_R1|ST8|35|2291|0.01528|0.2317|0.8119|0.4136|
|mi_aracne|GeoB25202_R2|ST13|18|2794|0.006442|0.1041|0.9057|0.4561|
|mi_aracne|GeoB25202_R2|ST8|31|2319|0.01337|0.2199|0.8197|0.4165|
|mi_aracne|ST13|ST8|41|2363|0.01735|0.305|0.7663|0.3918|

## Outputs

- `results/ngraph/graphs/ngraph_super_graph_<method>.graphml`
- `results/ngraph/tables/ngraph_graph_similarity.tsv`
- `results/ngraph/figures/ngraph_super_graph_<method>.png`
