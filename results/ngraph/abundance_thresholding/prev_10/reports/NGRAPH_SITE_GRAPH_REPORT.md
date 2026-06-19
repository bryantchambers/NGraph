# NGraph Site Graph Report

- Generated: 2026-06-15 10:05:10 CEST
- Branch: `abundance_thresholding`
- Prevalence threshold: `10`
- Pearson/Bicor/Spearman methods: sample-wise CLR, thresholded by absolute association.
- MI/ARACNE method: `minet::build.mim(..., estimator = "spearman")` followed by `minet::aracne(..., eps = 0)`.
- MI/ARACNE available in this run: `TRUE`.

## Graph Summary

|threshold|core|method|method_suffix|samples|nodes|edges|density|components|threshold|top_variable_taxa|
|---|---|---|---|---|---|---|---|---|---|---|
|10|ST8|pearson_abs_threshold|pearson|115|173|749|0.05034|40|0.55|173|
|10|ST8|bicor_abs_threshold|bicor|115|173|12180|0.8186|4|0.55|173|
|10|ST8|spearman_abs_threshold|spearman|115|173|5171|0.3476|13|0.55|173|
|10|ST8|mi_aracne|mi_aracne|115|173|272|0.01828|1|0|173|
|10|ST13|pearson_abs_threshold|pearson|48|173|617|0.04147|37|0.55|173|
|10|ST13|bicor_abs_threshold|bicor|48|173|1578|0.1061|14|0.55|173|
|10|ST13|spearman_abs_threshold|spearman|48|173|1242|0.08348|23|0.55|173|
|10|ST13|mi_aracne|mi_aracne|48|173|327|0.02198|1|0|173|
|10|GeoB25202_R1|pearson_abs_threshold|pearson|26|173|2511|0.1688|5|0.55|173|
|10|GeoB25202_R1|bicor_abs_threshold|bicor|26|173|11410|0.7666|3|0.55|173|
|10|GeoB25202_R1|spearman_abs_threshold|spearman|26|173|6763|0.4546|3|0.55|173|
|10|GeoB25202_R1|mi_aracne|mi_aracne|26|173|4017|0.27|1|0|173|
|10|GeoB25202_R2|pearson_abs_threshold|pearson|25|173|3267|0.2196|5|0.55|173|
|10|GeoB25202_R2|bicor_abs_threshold|bicor|25|173|10930|0.7346|4|0.55|173|
|10|GeoB25202_R2|spearman_abs_threshold|spearman|25|173|6326|0.4252|5|0.55|173|
|10|GeoB25202_R2|mi_aracne|mi_aracne|25|173|4381|0.2945|1|0|173|
