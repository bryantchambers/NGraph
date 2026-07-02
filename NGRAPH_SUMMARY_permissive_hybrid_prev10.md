# NGraph Workflow Summary

- Generated: 2026-06-24 16:02:46 CEST
- Seed: `42`
- Branch: `permissive_hybrid_prev10`
- Source data: `data/`
- New outputs: `results/ngraph/permissive_hybrid_prev10`

## CLR Matrices

|branch|threshold|matrix|abundance_column|abundance_mode|min_reads_gate|samples|taxa|pseudocount|prevalence_min_samples|max_abs_sample_clr_mean|
|---|---|---|---|---|---|---|---|---|---|---|
|permissive_hybrid_prev10|10|ngraph_clr_global|tax_abund_tad|hybrid_tad_then_read|100|214|1797|0.5|10|0.0000000000000002302|

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

|threshold|core|method|method_suffix|samples|nodes|edges|density|components|threshold|top_variable_taxa|
|---|---|---|---|---|---|---|---|---|---|---|
|10|ST8|pearson_abs_threshold|pearson|115|500|3843|0.03081|180|0.55|500|
|10|ST8|bicor_abs_threshold|bicor|115|500|8031|0.06438|108|0.55|500|
|10|ST8|spearman_abs_threshold|spearman|115|500|5017|0.04022|152|0.55|500|
|10|ST8|mi_aracne|mi_aracne|115|500|937|0.007511|1|0|500|
|10|ST13|pearson_abs_threshold|pearson|48|500|2078|0.01666|147|0.55|500|
|10|ST13|bicor_abs_threshold|bicor|48|500|5039|0.04039|86|0.55|500|
|10|ST13|spearman_abs_threshold|spearman|48|500|3438|0.02756|107|0.55|500|
|10|ST13|mi_aracne|mi_aracne|48|500|1365|0.01094|1|0|500|
|10|GeoB25202_R1|pearson_abs_threshold|pearson|26|500|5529|0.04432|12|0.55|500|
|10|GeoB25202_R1|bicor_abs_threshold|bicor|26|500|7810|0.06261|13|0.55|500|
|10|GeoB25202_R1|spearman_abs_threshold|spearman|26|500|8303|0.06656|13|0.55|500|
|10|GeoB25202_R1|mi_aracne|mi_aracne|26|500|1351|0.01083|1|0|500|
|10|GeoB25202_R2|pearson_abs_threshold|pearson|25|500|4578|0.0367|14|0.55|500|
|10|GeoB25202_R2|bicor_abs_threshold|bicor|25|500|9016|0.07227|7|0.55|500|
|10|GeoB25202_R2|spearman_abs_threshold|spearman|25|500|7086|0.0568|6|0.55|500|
|10|GeoB25202_R2|mi_aracne|mi_aracne|25|500|1391|0.01115|1|0|500|

## Graph-of-Graphs

|threshold|method|core_a|core_b|edge_intersection|edge_union|edge_jaccard|spectral_distance|spectral_similarity|super_weight|
|---|---|---|---|---|---|---|---|---|---|
|10|pearson|GeoB25202_R1|GeoB25202_R2|1021|9086|0.1124|0.2151|0.823|0.4677|
|10|pearson|GeoB25202_R1|ST13|423|7184|0.05888|2.329|0.3004|0.1796|
|10|pearson|GeoB25202_R1|ST8|535|8837|0.06054|2.492|0.2864|0.1735|
|10|pearson|GeoB25202_R2|ST13|339|6317|0.05366|2.166|0.3158|0.1847|
|10|pearson|GeoB25202_R2|ST8|418|8003|0.05223|2.367|0.297|0.1746|
|10|pearson|ST13|ST8|496|5425|0.09143|0.8057|0.5538|0.3226|
|10|bicor|GeoB25202_R1|GeoB25202_R2|1590|15240|0.1044|0.224|0.817|0.4607|
|10|bicor|GeoB25202_R1|ST13|433|12420|0.03487|1.56|0.3907|0.2128|
|10|bicor|GeoB25202_R1|ST8|758|15080|0.05026|1.735|0.3656|0.2079|
|10|bicor|GeoB25202_R2|ST13|320|13740|0.0233|1.607|0.3835|0.2034|
|10|bicor|GeoB25202_R2|ST8|1197|15850|0.07552|1.788|0.3587|0.2171|
|10|bicor|ST13|ST8|516|12550|0.0411|0.5736|0.6355|0.3383|
|10|spearman|GeoB25202_R1|GeoB25202_R2|1804|13580|0.1328|0.1334|0.8823|0.5076|
|10|spearman|GeoB25202_R1|ST13|542|11200|0.0484|1.925|0.3419|0.1951|
|10|spearman|GeoB25202_R1|ST8|634|12690|0.04998|2.296|0.3034|0.1767|
|10|spearman|GeoB25202_R2|ST13|400|10120|0.03951|1.921|0.3424|0.191|
|10|spearman|GeoB25202_R2|ST8|544|11560|0.04706|2.3|0.3031|0.1751|
|10|spearman|ST13|ST8|642|7813|0.08217|0.8507|0.5403|0.3113|
|10|mi_aracne|GeoB25202_R1|GeoB25202_R2|70|2672|0.0262|0.04689|0.9552|0.4907|
|10|mi_aracne|GeoB25202_R1|ST13|43|2673|0.01609|0.09519|0.9131|0.4646|
|10|mi_aracne|GeoB25202_R1|ST8|40|2248|0.01779|0.2316|0.812|0.4149|
|10|mi_aracne|GeoB25202_R2|ST13|35|2721|0.01286|0.05576|0.9472|0.48|
|10|mi_aracne|GeoB25202_R2|ST8|33|2295|0.01438|0.2694|0.7878|0.4011|
|10|mi_aracne|ST13|ST8|46|2256|0.02039|0.3111|0.7627|0.3916|

Mean graph-of-graphs similarity by threshold and method:

|threshold|method|mean_edge_jaccard|mean_spectral_similarity|mean_super_weight|
|---|---|---|---|---|
|10|pearson|0.07152|0.4294|0.2505|
|10|bicor|0.0549|0.4918|0.2734|
|10|spearman|0.06665|0.4522|0.2594|
|10|mi_aracne|0.01795|0.863|0.4405|

## Output Inventory

|file|bytes|
|---|---|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_GeoB25202_R2_bicor.graphml|4787000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_GeoB25202_R1_spearman.graphml|4514000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_ST8_bicor.graphml|4270000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_GeoB25202_R1_bicor.graphml|4244000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_GeoB25202_R2_spearman.graphml|3937000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_GeoB25202_R1_pearson.graphml|3236000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_ST8_spearman.graphml|2967000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_ST13_bicor.graphml|2954000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_GeoB25202_R2_pearson.graphml|2802000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_ST8_pearson.graphml|2433000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_ST13_spearman.graphml|2264000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_ST13_pearson.graphml|1649000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_GeoB25202_R2_mi_aracne.graphml|1308000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_edges_GeoB25202_R2_bicor.tsv|1307000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_GeoB25202_R1_mi_aracne.graphml|1292000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_ST13_mi_aracne.graphml|1288000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_edges_GeoB25202_R1_spearman.tsv|1215000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_edges_GeoB25202_R1_bicor.tsv|1126000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_edges_ST8_bicor.tsv|1113000|
|results/ngraph/permissive_hybrid_prev10/prev_10/graphs/ngraph_ST8_mi_aracne.graphml|1107000|
