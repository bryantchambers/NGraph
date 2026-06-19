# NGraph Site Graph Report

- Generated: 2026-06-15 10:04:52 CEST
- Branch: `abundance_thresholding`
- Prevalence threshold: `3`
- Pearson/Bicor/Spearman methods: sample-wise CLR, thresholded by absolute association.
- MI/ARACNE method: `minet::build.mim(..., estimator = "spearman")` followed by `minet::aracne(..., eps = 0)`.
- MI/ARACNE available in this run: `TRUE`.

## Graph Summary

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
