# NGraph Workflow Summary

- Generated: 2026-06-19 07:36:54 UTC
- Seed: `42`
- Branch: `abundance_thresholding`
- Source data: `data/`
- New outputs: `results/ngraph/abundance_thresholding`

## CLR Matrices

|branch|threshold|matrix|abundance_column|samples|taxa|pseudocount|prevalence_min_samples|max_abs_sample_clr_mean|
|---|---|---|---|---|---|---|---|---|
|abundance_thresholding|3|ngraph_clr_global|tax_abund_tad|214|374|0.5|3|0.000000000000000304|
|abundance_thresholding|5|ngraph_clr_global|tax_abund_tad|214|274|0.5|5|0.0000000000000004587|
|abundance_thresholding|10|ngraph_clr_global|tax_abund_tad|214|173|0.5|10|0.0000000000000004313|

## Input QC

Top PC/covariate associations by threshold:

|threshold|PC|covariate|covariate_class|pearson_r|spearman_rho|
|---|---|---|---|---|---|
|3|PC1|detected_taxa_tad|technical|-0.8425|-0.8734|
|3|PC1|log_total_n_reads|technical|-0.6481|-0.8049|
|3|PC1|total_tax_abund_tad|technical|-0.6292|-0.7866|
|3|PC1|total_n_reads|technical|-0.6247|-0.8049|
|3|PC1|library_concentration|technical|-0.5916|-0.694|
|3|PC1|log_total_tax_abund_tad|technical|-0.5234|-0.7866|
|3|PC1|log_total_n_reads_tad|technical|-0.5168|-0.7768|
|3|PC5|age_kyr|biological_proxy|-0.5035|-0.5779|
|5|PC1|detected_taxa_tad|technical|-0.7393|-0.6766|
|5|PC2|log_total_n_reads|technical|0.5737|0.6641|
|5|PC1|log_total_n_reads|technical|-0.5195|-0.5966|
|5|PC4|total_tax_abund_tad|technical|0.5058|-0.01899|
|5|PC1|library_concentration|technical|-0.5037|-0.5683|
|5|PC5|age_kyr|biological_proxy|0.5032|0.5573|
|5|PC2|log_total_tax_abund_tad|technical|0.5029|0.6795|
|5|PC1|total_tax_abund_tad|technical|-0.4961|-0.5637|
|10|PC2|log_total_n_reads|technical|0.7192|0.7995|
|10|PC2|detected_taxa_tad|technical|0.6629|0.876|
|10|PC2|log_total_tax_abund_tad|technical|0.629|0.8143|
|10|PC2|log_total_n_reads_tad|technical|0.6186|0.7923|
|10|PC2|library_concentration|technical|0.5562|0.6782|
|10|PC1|mis|biological_proxy|0.5455|0.6569|
|10|PC2|total_n_reads|technical|0.5428|0.7995|
|10|PC4|total_tax_abund_tad|technical|-0.5364|-0.1329|

## Site Graphs

|threshold|core|method|method_suffix|samples|nodes|edges|density|components|threshold|top_variable_taxa|
|---|---|---|---|---|---|---|---|---|---|---|
|3|ST8|pearson_abs_threshold|pearson|115|374|4318|0.06191|36|0.55|374|
|3|ST8|bicor_abs_threshold|bicor|115|374|63690|0.9131|3|0.55|374|
|3|ST8|spearman_abs_threshold|spearman|115|374|45260|0.6489|12|0.55|374|
|3|ST8|mi_aracne|mi_aracne|115|374|2912|0.04175|1|0|374|
|3|ST13|pearson_abs_threshold|pearson|48|374|6043|0.08664|22|0.55|374|
|3|ST13|bicor_abs_threshold|bicor|48|374|50310|0.7213|11|0.55|374|
|3|ST13|spearman_abs_threshold|spearman|48|374|24600|0.3527|25|0.55|374|
|3|ST13|mi_aracne|mi_aracne|48|374|3832|0.05494|1|0|374|
|3|GeoB25202_R1|pearson_abs_threshold|pearson|26|374|27060|0.388|6|0.55|374|
|3|GeoB25202_R1|bicor_abs_threshold|bicor|26|374|62160|0.8912|2|0.55|374|
|3|GeoB25202_R1|spearman_abs_threshold|spearman|26|374|51090|0.7324|2|0.55|374|
|3|GeoB25202_R1|mi_aracne|mi_aracne|26|374|40190|0.5762|1|0|374|
|3|GeoB25202_R2|pearson_abs_threshold|pearson|25|374|23200|0.3327|7|0.55|374|
|3|GeoB25202_R2|bicor_abs_threshold|bicor|25|374|61010|0.8747|2|0.55|374|
|3|GeoB25202_R2|spearman_abs_threshold|spearman|25|374|49670|0.7122|1|0.55|374|
|3|GeoB25202_R2|mi_aracne|mi_aracne|25|374|39260|0.5629|1|0|374|
|5|ST8|pearson_abs_threshold|pearson|115|274|1757|0.04698|42|0.55|274|
|5|ST8|bicor_abs_threshold|bicor|115|274|33090|0.8848|6|0.55|274|
|5|ST8|spearman_abs_threshold|spearman|115|274|19990|0.5346|12|0.55|274|
|5|ST8|mi_aracne|mi_aracne|115|274|849|0.0227|1|0|274|
|5|ST13|pearson_abs_threshold|pearson|48|274|2623|0.07013|30|0.55|274|
|5|ST13|bicor_abs_threshold|bicor|48|274|21290|0.5693|9|0.55|274|
|5|ST13|spearman_abs_threshold|spearman|48|274|8276|0.2213|24|0.55|274|
|5|ST13|mi_aracne|mi_aracne|48|274|1058|0.02829|1|0|274|
|5|GeoB25202_R1|pearson_abs_threshold|pearson|26|274|10970|0.2934|7|0.55|274|
|5|GeoB25202_R1|bicor_abs_threshold|bicor|26|274|31680|0.847|2|0.55|274|
|5|GeoB25202_R1|spearman_abs_threshold|spearman|26|274|23940|0.64|3|0.55|274|
|5|GeoB25202_R1|mi_aracne|mi_aracne|26|274|17010|0.4549|1|0|274|
|5|GeoB25202_R2|pearson_abs_threshold|pearson|25|274|9720|0.2599|6|0.55|274|
|5|GeoB25202_R2|bicor_abs_threshold|bicor|25|274|30420|0.8133|3|0.55|274|

## Graph-of-Graphs

|threshold|method|core_a|core_b|edge_intersection|edge_union|edge_jaccard|spectral_distance|spectral_similarity|super_weight|
|---|---|---|---|---|---|---|---|---|---|
|3|pearson|GeoB25202_R1|GeoB25202_R2|15560|34710|0.4481|0.07028|0.9343|0.6912|
|3|pearson|GeoB25202_R1|ST13|3219|29890|0.1077|1.16|0.463|0.2853|
|3|pearson|GeoB25202_R1|ST8|2280|29100|0.07834|1.53|0.3953|0.2368|
|3|pearson|GeoB25202_R2|ST13|2789|26460|0.1054|1.134|0.4686|0.287|
|3|pearson|GeoB25202_R2|ST8|2112|25410|0.08312|1.509|0.3986|0.2409|
|3|pearson|ST13|ST8|989|9372|0.1055|0.5073|0.6634|0.3845|
|3|bicor|GeoB25202_R1|GeoB25202_R2|59100|64070|0.9225|0.1426|0.8752|0.8988|
|3|bicor|GeoB25202_R1|ST13|49030|63450|0.7727|0.5756|0.6347|0.7037|
|3|bicor|GeoB25202_R1|ST8|60980|64880|0.9399|0.08909|0.9182|0.929|
|3|bicor|GeoB25202_R2|ST13|48300|63020|0.7664|0.4728|0.679|0.7227|
|3|bicor|GeoB25202_R2|ST8|59020|65680|0.8985|0.06222|0.9414|0.92|
|3|bicor|ST13|ST8|49630|64370|0.771|0.5233|0.6565|0.7137|
|3|spearman|GeoB25202_R1|GeoB25202_R2|47380|53380|0.8876|0.1834|0.845|0.8663|
|3|spearman|GeoB25202_R1|ST13|23800|51890|0.4586|1.268|0.4409|0.4498|
|3|spearman|GeoB25202_R1|ST8|40860|55480|0.7365|0.4777|0.6767|0.7066|
|3|spearman|GeoB25202_R2|ST13|23270|51010|0.4562|1.309|0.433|0.4446|
|3|spearman|GeoB25202_R2|ST8|39070|55860|0.6994|0.4473|0.6909|0.6952|
|3|spearman|ST13|ST8|22980|46890|0.49|1.046|0.4889|0.4894|
|3|mi_aracne|GeoB25202_R1|GeoB25202_R2|34520|44940|0.7682|0.1351|0.8809|0.8246|
|3|mi_aracne|GeoB25202_R1|ST13|3232|40790|0.07923|1.231|0.4483|0.2638|
|3|mi_aracne|GeoB25202_R1|ST8|2249|40860|0.05505|1.381|0.4199|0.2375|
|3|mi_aracne|GeoB25202_R2|ST13|3166|39930|0.07929|1.24|0.4464|0.2628|
|3|mi_aracne|GeoB25202_R2|ST8|2182|39990|0.05456|1.39|0.4183|0.2365|
|3|mi_aracne|ST13|ST8|429|6315|0.06793|0.213|0.8244|0.4462|
|5|pearson|GeoB25202_R1|GeoB25202_R2|5599|15100|0.3709|0.1488|0.8705|0.6207|
|5|pearson|GeoB25202_R1|ST13|1192|12400|0.09609|1.485|0.4025|0.2493|
|5|pearson|GeoB25202_R1|ST8|839|11890|0.07055|1.908|0.3439|0.2072|
|5|pearson|GeoB25202_R2|ST13|1039|11300|0.09191|1.523|0.3964|0.2442|
|5|pearson|GeoB25202_R2|ST8|732|10740|0.06812|1.944|0.3397|0.2039|
|5|pearson|ST13|ST8|506|3874|0.1306|0.6448|0.608|0.3693|

Mean graph-of-graphs similarity by threshold and method:

|threshold|method|mean_edge_jaccard|mean_spectral_similarity|mean_super_weight|
|---|---|---|---|---|
|3|pearson|0.1547|0.5539|0.3543|
|3|bicor|0.8452|0.7842|0.8147|
|3|spearman|0.6214|0.5959|0.6086|
|3|mi_aracne|0.184|0.573|0.3785|
|5|pearson|0.138|0.4935|0.3158|
|5|bicor|0.7616|0.6734|0.7175|
|5|spearman|0.5062|0.5558|0.531|
|5|mi_aracne|0.1498|0.5559|0.3529|
|10|pearson|0.1208|0.4594|0.2901|
|10|bicor|0.4763|0.5443|0.5103|
|10|spearman|0.3409|0.5198|0.4304|
|10|mi_aracne|0.1154|0.5631|0.3392|

## Deep Module Follow-up

The threshold benchmark has been extended into the deep-module phase, with outputs under `results/ngraph/abundance_thresholding/deep_modules/`.

Key deep-module results:

|threshold|method|best_heldout_auc|module_k|module_silhouette|
|---|---|---|---|---|
|prev_3|pearson|0.6608|2|0.6431|
|prev_3|bicor|0.5014|4|0.5593|
|prev_3|spearman|0.5089|2|0.4914|
|prev_3|mi_aracne|0.7140|2|0.7468|
|prev_5|pearson|0.6719|2|0.6195|
|prev_5|bicor|0.5000|7|0.4671|
|prev_5|spearman|0.5000|3|0.4939|
|prev_5|mi_aracne|0.7445|2|0.7278|
|prev_10|pearson|0.5812|2|0.3973|
|prev_10|bicor|0.5000|3|0.5429|
|prev_10|spearman|0.7466|2|0.6292|
|prev_10|mi_aracne|0.7452|2|0.6737|

The primary module snapshot is centered on `prev_5`, with `GeoB25202_R2` used as the validation core.

## Deep Knowledge Discovery

The branch now extends into a local-first discovery layer built on the learned modules and embeddings.

- `10_ngraph_link_prediction.py` ranks absent taxon-taxon and taxon-site hypotheses.
- `11_ngraph_build_evidence_cards.R` creates sample, site, taxon, module, and predicted-link cards.
- `12_ngraph_build_retrieval_index.py` builds TF-IDF and nearest-neighbor indexes.
- `13_ngraph_query_engine.py` runs canonical natural-language questions.

The discovery artifacts live under `results/ngraph/abundance_thresholding/deep_knowledge_discovery/`.

## Output Inventory

|file|bytes|
|---|---|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_ST8_bicor.graphml|28580000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_GeoB25202_R1_bicor.graphml|27470000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_GeoB25202_R2_bicor.graphml|27080000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_GeoB25202_R1_spearman.graphml|22800000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_ST13_bicor.graphml|22740000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_GeoB25202_R2_spearman.graphml|22260000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_ST8_spearman.graphml|20760000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_GeoB25202_R1_mi_aracne.graphml|17520000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_GeoB25202_R2_mi_aracne.graphml|17130000|
|results/ngraph/abundance_thresholding/prev_5/graphs/ngraph_ST8_bicor.graphml|14980000|
|results/ngraph/abundance_thresholding/prev_5/graphs/ngraph_GeoB25202_R1_bicor.graphml|14270000|
|results/ngraph/abundance_thresholding/prev_5/graphs/ngraph_GeoB25202_R2_bicor.graphml|13760000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_GeoB25202_R1_pearson.graphml|11820000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_ST13_spearman.graphml|11520000|
|results/ngraph/abundance_thresholding/prev_5/graphs/ngraph_GeoB25202_R1_spearman.graphml|10930000|
|results/ngraph/abundance_thresholding/prev_5/graphs/ngraph_GeoB25202_R2_spearman.graphml|10460000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_GeoB25202_R2_pearson.graphml|10260000|
|results/ngraph/abundance_thresholding/prev_5/graphs/ngraph_ST13_bicor.graphml|9807000|
|results/ngraph/abundance_thresholding/prev_5/graphs/ngraph_ST8_spearman.graphml|9333000|
|results/ngraph/abundance_thresholding/prev_3/graphs/ngraph_edges_ST8_bicor.tsv|8854000|
