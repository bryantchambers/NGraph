# NGraph Site Graph Report

- Generated: 2026-06-04 14:08:49 CEST
- Spearman method: sample-wise CLR, thresholded by absolute association.
- MI/ARACNE method: `minet::build.mim(..., estimator = "spearman")` followed by `minet::aracne(..., eps = 0)`.
- MI/ARACNE available in this run: `TRUE`.

## Graph Summary

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

## Output Files

- Edge lists: `results/ngraph/graphs/ngraph_edges_<core>_<method>.tsv`
- Node tables: `results/ngraph/graphs/ngraph_nodes_<core>_<method>.tsv`
- GraphML exports: `results/ngraph/graphs/ngraph_<core>_<method>.graphml`
