# NGraph Site Graph Report

- Generated: 2026-06-15 10:05:04 CEST
- Branch: `abundance_thresholding`
- Prevalence threshold: `5`
- Pearson/Bicor/Spearman methods: sample-wise CLR, thresholded by absolute association.
- MI/ARACNE method: `minet::build.mim(..., estimator = "spearman")` followed by `minet::aracne(..., eps = 0)`.
- MI/ARACNE available in this run: `TRUE`.

## Graph Summary

|threshold|core|method|method_suffix|samples|nodes|edges|density|components|threshold|top_variable_taxa|
|---|---|---|---|---|---|---|---|---|---|---|
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
|5|GeoB25202_R2|spearman_abs_threshold|spearman|25|274|22780|0.6091|2|0.55|274|
|5|GeoB25202_R2|mi_aracne|mi_aracne|25|274|16470|0.4403|1|0|274|
