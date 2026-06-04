#!/usr/bin/env Rscript
# 03_ngraph_site_graphs.R -- build site-specific taxon association graphs.

suppressPackageStartupMessages({
  library(data.table)
  library(igraph)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("03_ngraph_site_graphs")
ng_start_log(LOG)
ng_log(LOG, "Starting NGraph site graph construction")

clr <- readRDS(file.path(NG$matrices, "ngraph_clr_global.rds"))
sample_qc <- fread(file.path(NG$tables, "ngraph_sample_qc.tsv"))
taxa_meta <- fread(file.path(NG$tables, "ngraph_taxa_metadata.tsv"))

minet_available <- requireNamespace("minet", quietly = TRUE)
if (minet_available) {
  ng_log(LOG, "minet available: ", as.character(utils::packageVersion("minet")))
} else {
  ng_log(LOG, "Optional method skipped: minet is not installed; MI/ARACNE graphs were not built")
}

write_site_graph <- function(edges, vertices, core_id, method_suffix, method_label, samples_n, threshold_value, top_taxa_n) {
  g <- graph_from_data_frame(edges, directed = FALSE, vertices = vertices)
  if (ecount(g) > 0) {
    E(g)$weight <- edges$abs_weight
    if ("signed_weight" %in% names(edges)) {
      E(g)$signed_weight <- edges$signed_weight
    }
  }

  edge_path <- file.path(NG$graphs, paste0("ngraph_edges_", core_id, "_", method_suffix, ".tsv"))
  node_path <- file.path(NG$graphs, paste0("ngraph_nodes_", core_id, "_", method_suffix, ".tsv"))
  graphml_path <- file.path(NG$graphs, paste0("ngraph_", core_id, "_", method_suffix, ".graphml"))
  rds_path <- file.path(NG$graphs, paste0("ngraph_", core_id, "_", method_suffix, ".rds"))

  fwrite(edges, edge_path, sep = "\t")
  fwrite(as.data.table(vertex_attr(g)), node_path, sep = "\t")
  write_graph(g, graphml_path, format = "graphml")
  saveRDS(g, rds_path)

  data.table(
    core = core_id,
    method = method_label,
    method_suffix = method_suffix,
    samples = samples_n,
    nodes = vcount(g),
    edges = ecount(g),
    density = edge_density(g, loops = FALSE),
    components = components(g)$no,
    threshold = threshold_value,
    top_variable_taxa = top_taxa_n
  )
}

graph_summaries <- list()
for (core_id in NG_PARAMS$all_cores) {
  samples <- intersect(sample_qc[core == core_id, label], rownames(clr))
  if (length(samples) < NG_PARAMS$graph_min_samples) {
    ng_log(LOG, "Skipping ", core_id, ": fewer than ", NG_PARAMS$graph_min_samples, " samples")
    next
  }

  mat <- clr[samples, , drop = FALSE]
  vars <- apply(mat, 2, var, na.rm = TRUE)
  top_taxa <- names(sort(vars, decreasing = TRUE))[seq_len(min(NG_PARAMS$graph_top_variable_taxa, length(vars)))]
  mat <- mat[, top_taxa, drop = FALSE]

  vertices <- data.table(name = colnames(mat), taxon = colnames(mat))
  vertices <- merge(vertices, taxa_meta, by = "taxon", all.x = TRUE, sort = FALSE)
  vertices[, name := taxon]

  cor_mat <- suppressWarnings(cor(mat, method = "spearman", use = "pairwise.complete.obs"))
  diag(cor_mat) <- 0
  idx <- which(abs(cor_mat) >= NG_PARAMS$spearman_abs_threshold, arr.ind = TRUE)
  idx <- idx[idx[, 1] < idx[, 2], , drop = FALSE]

  edges <- data.table(
    from = colnames(cor_mat)[idx[, 1]],
    to = colnames(cor_mat)[idx[, 2]],
    signed_weight = cor_mat[idx],
    weight = abs(cor_mat[idx]),
    abs_weight = abs(cor_mat[idx]),
    method = "spearman_abs_threshold",
    core = core_id
  )
  graph_summaries[[length(graph_summaries) + 1]] <- write_site_graph(
    edges = edges,
    vertices = vertices,
    core_id = core_id,
    method_suffix = "spearman",
    method_label = "spearman_abs_threshold",
    samples_n = length(samples),
    threshold_value = NG_PARAMS$spearman_abs_threshold,
    top_taxa_n = length(top_taxa)
  )
  ng_log(LOG, "Built ", core_id, " Spearman graph: ", nrow(vertices), " nodes, ", nrow(edges), " edges")

  if (minet_available) {
    mim <- minet::build.mim(
      dataset = as.data.frame(mat),
      estimator = NG_PARAMS$minet_estimator
    )
    aracne_mat <- minet::aracne(mim, eps = NG_PARAMS$aracne_eps)
    aracne_mat <- as.matrix(aracne_mat)
    diag(aracne_mat) <- 0
    mi_idx <- which(aracne_mat > 0, arr.ind = TRUE)
    mi_idx <- mi_idx[mi_idx[, 1] < mi_idx[, 2], , drop = FALSE]
    mi_edges <- data.table(
      from = colnames(aracne_mat)[mi_idx[, 1]],
      to = colnames(aracne_mat)[mi_idx[, 2]],
      weight = aracne_mat[mi_idx],
      abs_weight = aracne_mat[mi_idx],
      method = "mi_aracne",
      estimator = NG_PARAMS$minet_estimator,
      aracne_eps = NG_PARAMS$aracne_eps,
      core = core_id
    )
    graph_summaries[[length(graph_summaries) + 1]] <- write_site_graph(
      edges = mi_edges,
      vertices = vertices,
      core_id = core_id,
      method_suffix = "mi_aracne",
      method_label = "mi_aracne",
      samples_n = length(samples),
      threshold_value = NG_PARAMS$aracne_eps,
      top_taxa_n = length(top_taxa)
    )
    ng_log(LOG, "Built ", core_id, " MI/ARACNE graph: ", nrow(vertices), " nodes, ", nrow(mi_edges), " edges")
  }
}

summary_dt <- rbindlist(graph_summaries, fill = TRUE)
fwrite(summary_dt, file.path(NG$tables, "ngraph_site_graph_summary.tsv"), sep = "\t")

report <- file.path(NG$reports, "NGRAPH_SITE_GRAPH_REPORT.md")
sink(report)
cat("# NGraph Site Graph Report\n\n")
cat("- Generated: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), "\n", sep = "")
cat("- Spearman method: sample-wise CLR, thresholded by absolute association.\n")
cat("- MI/ARACNE method: `minet::build.mim(..., estimator = \"", NG_PARAMS$minet_estimator, "\")` followed by `minet::aracne(..., eps = ", NG_PARAMS$aracne_eps, ")`.\n", sep = "")
cat("- MI/ARACNE available in this run: `", minet_available, "`.\n\n", sep = "")
cat("## Graph Summary\n\n")
cat(ng_md_table(summary_dt))
cat("\n## Output Files\n\n")
cat("- Edge lists: `results/ngraph/graphs/ngraph_edges_<core>_<method>.tsv`\n")
cat("- Node tables: `results/ngraph/graphs/ngraph_nodes_<core>_<method>.tsv`\n")
cat("- GraphML exports: `results/ngraph/graphs/ngraph_<core>_<method>.graphml`\n")
sink()

ng_log(LOG, "Method Validated: site graphs written")
ng_log(LOG, "Complete")
