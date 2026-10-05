# NGraph Workflow Summary

- Generated: 2026-10-05 15:45:59 CEST
- Seed: `42`
- Branch: `mvp_permissive_mixed_20261005`
- Source data: `data/`
- New outputs: `results/ngraph/mvp_permissive_mixed_20261005`

## CLR Matrices

|branch|threshold|matrix|abundance_column|abundance_mode|min_reads_gate|samples|taxa|pseudocount|prevalence_min_samples|taxa_read_prevalence_only|samples_dropped_empty|max_abs_sample_clr_mean|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|mvp_permissive_mixed_20261005|10|ngraph_clr_global|aggregated_tad_then_read|hybrid_aggregated_tad_then_read|100|214|1797|0.5|10|1359|0|0.0000000000000002302|

## Input QC

Top PC/covariate associations by threshold:

|threshold|PC|covariate|covariate_class|pearson_r|spearman_rho|
|---|---|---|---|---|---|
|10|PC1|detected_taxa_mode|technical|0.858|0.8294|
|10|PC1|log_total_tax_abund_mode|technical|0.785|0.7388|
|10|PC1|log_total_n_reads|technical|0.7729|0.7226|
|10|PC1|log_total_n_reads_tad|technical|0.6545|0.6707|
|10|PC1|total_tax_abund_mode|technical|0.6392|0.7388|
|10|PC1|total_n_reads|technical|0.6102|0.7226|
|10|PC1|age_kyr|biological_proxy|-0.5973|-0.5945|
|10|PC1|library_concentration|technical|0.5944|0.656|

## Site Graphs

|threshold|core|method|method_suffix|samples|nodes|edges|density|components|association_cutoff|top_variable_taxa|
|---|---|---|---|---|---|---|---|---|---|---|
|10|ST8|pearson_abs_threshold|pearson|115|1797|68130|0.04222|282|0.55|1797|
|10|ST13|pearson_abs_threshold|pearson|48|1797|61910|0.03837|125|0.55|1797|
|10|GeoB25202_R1|pearson_abs_threshold|pearson|26|1797|100400|0.06224|2|0.55|1797|
|10|GeoB25202_R2|pearson_abs_threshold|pearson|25|1797|87140|0.054|2|0.55|1797|

## Graph-of-Graphs

|threshold|method|core_a|core_b|edge_intersection|edge_union|edge_jaccard|spectral_distance|spectral_similarity|super_weight|
|---|---|---|---|---|---|---|---|---|---|
|10|pearson|GeoB25202_R1|GeoB25202_R2|27040|160500|0.1684|0.0654|0.9386|0.5535|
|10|pearson|GeoB25202_R1|ST13|14220|148100|0.09598|1.268|0.4409|0.2685|
|10|pearson|GeoB25202_R1|ST8|13370|155200|0.08614|1.828|0.3536|0.2199|
|10|pearson|GeoB25202_R2|ST13|13750|135300|0.1016|1.214|0.4516|0.2766|
|10|pearson|GeoB25202_R2|ST8|11960|143300|0.08349|1.777|0.3601|0.2218|
|10|pearson|ST13|ST8|22580|107500|0.2101|0.9899|0.5025|0.3563|

Mean graph-of-graphs similarity by threshold and method:

|threshold|method|mean_edge_jaccard|mean_spectral_similarity|mean_super_weight|
|---|---|---|---|---|
|10|pearson|0.1243|0.5079|0.3161|

## Output Inventory

|file|bytes|
|---|---|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_GeoB25202_R1_pearson.graphml|48190000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_GeoB25202_R2_pearson.graphml|42260000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_ST8_pearson.graphml|32920000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_ST13_pearson.graphml|30190000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_edges_GeoB25202_R1_pearson.tsv|14350000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_edges_GeoB25202_R2_pearson.tsv|12540000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_edges_ST8_pearson.tsv|9017000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_edges_ST13_pearson.tsv|8182000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/tables/ngraph_taxon_read_support.tsv|5047000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_GeoB25202_R2_pearson.rds|3325000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_GeoB25202_R1_pearson.rds|3217000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_ST8_pearson.rds|2050000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_ST13_pearson.rds|1818000|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/matrices/ngraph_clr_global.rds|943400|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/tables/ngraph_taxa_metadata.tsv|634600|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_nodes_GeoB25202_R1_pearson.tsv|634600|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_nodes_GeoB25202_R2_pearson.tsv|634600|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_nodes_ST13_pearson.tsv|634600|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/graphs/ngraph_nodes_ST8_pearson.tsv|634600|
|results/ngraph/mvp_permissive_mixed_20261005/prev_10/matrices/ngraph_clr_ST8.rds|440000|
