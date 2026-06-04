# NGraph Input QC Report

- Generated: 2026-06-04 13:22:22 CEST
- Input: sample-wise CLR matrix from `results/ngraph/matrices/ngraph_clr_global.rds`
- Log: `logs/02_ngraph_input_qc.log`

## Main QC Result

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
|PC5|avg_len_derep|technical|0.3258|0.3122|
|PC4|log_total_reads|technical|-0.3238|-0.3485|
|PC1|avg_leng_initial|technical|0.3191|0.3229|
|PC3|avg_len_derep|technical|0.313|0.3516|
|PC2|mis|biological_proxy|0.3103|0.3123|
|PC4|avg_leng_initial|technical|0.2903|0.2618|
|PC3|mis|biological_proxy|-0.2872|-0.226|
|PC4|avg_len_derep|technical|0.2704|0.282|

Core/site R2 by PC:

|PC|covariate|covariate_class|r2|
|---|---|---|---|
|PC1|core|core_or_site|0.1011|
|PC2|core|core_or_site|0.06858|
|PC3|core|core_or_site|0.08887|
|PC4|core|core_or_site|0.08246|
|PC5|core|core_or_site|0.1148|

## Interpretation Guardrail

If PC1 or PC2 remains strongly associated with read depth, detected taxa, or core identity, graph similarity must be interpreted as a sensitivity result rather than direct ecological interaction evidence.

## Figures

- `results/ngraph/figures/ngraph_ordination_by_core.png`
- `results/ngraph/figures/ngraph_ordination_by_depth.png`
- `results/ngraph/figures/ngraph_ordination_by_age.png`
- `results/ngraph/figures/ngraph_pc_covariate_heatmap.png`
