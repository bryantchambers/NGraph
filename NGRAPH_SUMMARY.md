# NGraph Workflow Summary

- Generated: 2026-06-04 14:09:41 CEST
- Seed: `42`
- Source data: `Source/ROCS/results/stage1`
- New outputs: `results/ngraph`

## CLR Matrices

|matrix|samples|taxa|pseudocount|prevalence_min_samples|max_abs_sample_clr_mean|
|---|---|---|---|---|---|
|ngraph_clr_global|214|1797|0.5|10|0.000000000000000262|

|core|samples|taxa|age_min_kyr|age_max_kyr|
|---|---|---|---|---|
|ST8|115|1797|1.522|107.7|
|ST13|48|1797|5.659|148.1|
|GeoB25202_R1|26|1797|0.692|147.2|
|GeoB25202_R2|25|1797|0.692|147.2|

## Input QC

Top PC/covariate associations:

|PC|covariate|covariate_class|pearson_r|spearman_rho|
|---|---|---|---|---|
|PC1|detected_taxa|technical|0.8444|0.8145|
|PC1|log_total_reads|technical|0.769|0.7029|
|PC1|age_kyr|biological_proxy|-0.6013|-0.595|
|PC1|total_reads|technical|0.5843|0.7029|
|PC1|library_concentration|technical|0.5813|0.6481|
|PC1|mis|biological_proxy|0.4797|0.5288|
|PC5|age_kyr|biological_proxy|-0.4139|-0.4523|
|PC5|avg_leng_initial|technical|0.4016|0.3458|
|PC2|log_total_reads|technical|-0.3939|-0.2743|
|PC3|total_reads|technical|0.38|0.08062|
|PC3|avg_leng_initial|technical|0.3642|0.3522|
|PC4|total_reads|technical|-0.3391|-0.3485|

## Site Graphs

|core|method|method_suffix|samples|nodes|edges|density|components|threshold|top_variable_taxa|
|---|---|---|---|---|---|---|---|---|---|
|ST8|spearman_abs_threshold|spearman|115|500|3921|0.03143|167|0.55|500|
|ST8|mi_aracne|mi_aracne|115|500|971|0.007784|1|0|500|
|ST13|spearman_abs_threshold|spearman|48|500|2769|0.0222|144|0.55|500|
|ST13|mi_aracne|mi_aracne|48|500|1433|0.01149|1|0|500|
|GeoB25202_R1|spearman_abs_threshold|spearman|26|500|8087|0.06483|11|0.55|500|
|GeoB25202_R1|mi_aracne|mi_aracne|26|500|1355|0.01086|1|0|500|
|GeoB25202_R2|spearman_abs_threshold|spearman|25|500|7126|0.05712|10|0.55|500|
|GeoB25202_R2|mi_aracne|mi_aracne|25|500|1379|0.01105|1|0|500|

## Graph-of-Graphs

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

Mean graph-of-graphs similarity by method:

|method|mean_edge_jaccard|mean_spectral_similarity|mean_super_weight|
|---|---|---|---|
|spearman|0.05709|0.4533|0.2552|
|mi_aracne|0.01433|0.8659|0.4401|

## Output Inventory

|file|bytes|
|---|---|
|results/ngraph/graphs/ngraph_GeoB25202_R1_spearman.graphml|2816000|
|results/ngraph/graphs/ngraph_GeoB25202_R2_spearman.graphml|2491000|
|results/ngraph/graphs/ngraph_ST8_spearman.graphml|1453000|
|results/ngraph/graphs/ngraph_ST13_spearman.graphml|1098000|
|results/ngraph/graphs/ngraph_edges_GeoB25202_R1_spearman.tsv|1036000|
|results/ngraph/matrices/ngraph_clr_global.rds|942300|
|results/ngraph/graphs/ngraph_edges_GeoB25202_R2_spearman.tsv|887700|
|results/ngraph/graphs/ngraph_ST13_mi_aracne.graphml|702600|
|results/ngraph/graphs/ngraph_GeoB25202_R2_mi_aracne.graphml|696200|
|results/ngraph/graphs/ngraph_GeoB25202_R1_mi_aracne.graphml|688100|
|results/ngraph/graphs/ngraph_ST8_mi_aracne.graphml|551400|
|results/ngraph/graphs/ngraph_edges_ST8_spearman.tsv|474400|
|results/ngraph/matrices/ngraph_clr_ST8.rds|440900|
|results/ngraph/graphs/ngraph_edges_ST13_spearman.tsv|336600|
|results/ngraph/matrices/ngraph_counts_taxa_by_sample.rds|313200|
|results/ngraph/matrices/ngraph_clr_ST13.rds|252000|
|results/ngraph/tables/ngraph_taxa_metadata.tsv|207400|
|results/ngraph/graphs/ngraph_GeoB25202_R1_spearman.rds|153800|
|results/ngraph/graphs/ngraph_edges_GeoB25202_R2_mi_aracne.tsv|148700|
|results/ngraph/graphs/ngraph_edges_ST13_mi_aracne.tsv|147200|
