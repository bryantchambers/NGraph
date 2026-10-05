# NGraph Workflow Summary

- Generated: 2026-10-05 14:34:07 CEST
- Seed: `42`
- Branch: `mvp_permissive_tad`
- Source data: `data/`
- New outputs: `results/ngraph/mvp_permissive_tad`

## CLR Matrices

|branch|threshold|matrix|abundance_column|abundance_mode|min_reads_gate|samples|taxa|pseudocount|prevalence_min_samples|taxa_read_prevalence_only|samples_dropped_empty|max_abs_sample_clr_mean|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|mvp_permissive_tad|10|ngraph_clr_global|tax_abund_tad|hybrid_prevalence_tad_matrix|100|200|1797|0.5|10|1359|14|0.00000000000000006611|

## Input QC


## Site Graphs

|threshold|core|method|method_suffix|samples|nodes|edges|density|components|association_cutoff|top_variable_taxa|
|---|---|---|---|---|---|---|---|---|---|---|
|10|ST8|pearson_abs_threshold|pearson|102|360|3841|0.05944|31|0.55|360|
|10|ST13|pearson_abs_threshold|pearson|48|336|4445|0.07898|13|0.55|336|
|10|GeoB25202_R1|pearson_abs_threshold|pearson|25|165|1906|0.1409|6|0.55|165|
|10|GeoB25202_R2|pearson_abs_threshold|pearson|25|181|2893|0.1776|7|0.55|181|

## Graph-of-Graphs

|threshold|method|core_a|core_b|edge_intersection|edge_union|edge_jaccard|spectral_distance|spectral_similarity|super_weight|
|---|---|---|---|---|---|---|---|---|---|
|10|pearson|GeoB25202_R1|GeoB25202_R2|1037|3762|0.2757|0.5134|0.6607|0.4682|
|10|pearson|GeoB25202_R1|ST13|382|5969|0.064|0.3921|0.7183|0.3912|
|10|pearson|GeoB25202_R1|ST8|407|5340|0.07622|0.6931|0.5906|0.3334|
|10|pearson|GeoB25202_R2|ST13|779|6559|0.1188|0.4782|0.6765|0.3976|
|10|pearson|GeoB25202_R2|ST8|785|5949|0.132|0.9328|0.5174|0.3247|
|10|pearson|ST13|ST8|1106|7180|0.154|0.5811|0.6325|0.3933|

Mean graph-of-graphs similarity by threshold and method:

|threshold|method|mean_edge_jaccard|mean_spectral_similarity|mean_super_weight|
|---|---|---|---|---|
|10|pearson|0.1368|0.6327|0.3847|

## Output Inventory

|file|bytes|
|---|---|
|results/ngraph/mvp_permissive_tad/deep_modules/prev_10/pearson/tables/ngraph_taxon_taxon_link_predictions.tsv|17860000|
|results/ngraph/mvp_permissive_tad/prev_10/graphs/ngraph_ST13_pearson.graphml|2472000|
|results/ngraph/mvp_permissive_tad/deep_modules/prev_10/pearson/tables/hetero_taxon_taxon_edges.tsv|2233000|
|results/ngraph/mvp_permissive_tad/prev_10/graphs/ngraph_ST8_pearson.graphml|2232000|
|results/ngraph/mvp_permissive_tad/prev_10/graphs/ngraph_GeoB25202_R2_pearson.graphml|1577000|
|results/ngraph/mvp_permissive_tad/prev_10/graphs/ngraph_GeoB25202_R1_pearson.graphml|1105000|
|results/ngraph/mvp_permissive_tad/prev_10/tables/ngraph_taxa_metadata.tsv|634600|
|results/ngraph/mvp_permissive_tad/prev_10/graphs/ngraph_edges_ST13_pearson.tsv|626700|
|results/ngraph/mvp_permissive_tad/prev_10/graphs/ngraph_edges_ST8_pearson.tsv|535100|
|results/ngraph/mvp_permissive_tad/deep_modules/prev_10/pearson/tables/diffpool_site_taxon_assignments.tsv|494300|
|results/ngraph/mvp_permissive_tad/prev_10/graphs/ngraph_edges_GeoB25202_R2_pearson.tsv|438200|
|results/ngraph/mvp_permissive_tad/deep_modules/prev_10/pearson/models/vgae_model.pt|331700|
|results/ngraph/mvp_permissive_tad/deep_modules/prev_10/pearson/models/vgae_pair_splits.npz|310500|
|results/ngraph/mvp_permissive_tad/prev_10/graphs/ngraph_edges_GeoB25202_R1_pearson.tsv|284200|
|results/ngraph/mvp_permissive_tad/prev_10/graphs/ngraph_ST13_pearson.rds|238700|
|results/ngraph/mvp_permissive_tad/deep_modules/prev_10/pearson/tables/hetero_taxon_nodes.tsv|198800|
|results/ngraph/mvp_permissive_tad/deep_modules/prev_10/pearson/tables/hetero_taxon_site_edges.tsv|178700|
|results/ngraph/mvp_permissive_tad/deep_modules/prev_10/pearson/tables/vgae_embeddings.tsv|173100|
|results/ngraph/mvp_permissive_tad/prev_10/graphs/ngraph_nodes_ST8_pearson.tsv|130700|
|results/ngraph/mvp_permissive_tad/prev_10/graphs/ngraph_nodes_ST13_pearson.tsv|122400|
