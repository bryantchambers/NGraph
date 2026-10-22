#!/usr/bin/env Rscript
# 03_ngraph_site_graphs.R -- build threshold-specific site graphs.

suppressPackageStartupMessages({
  library(data.table)
  library(igraph)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("03_ngraph_site_graphs")
ng_start_log(LOG)
ng_log(LOG, "Starting NGraph site graph construction")

minet_available <- requireNamespace("minet", quietly = TRUE)
wgcna_available <- requireNamespace("WGCNA", quietly = TRUE)
if (!wgcna_available) {
  stop("Missing required R package: WGCNA. Update the ngraph Mamba environment; do not install from scripts.")
}
if (minet_available) {
  ng_log(LOG, "minet available: ", as.character(utils::packageVersion("minet")))
} else {
  ng_log(LOG, "Optional method skipped: minet is not installed; MI/ARACNE graphs were not built")
}

# Eligibility uses positive modeled abundance, never variance induced solely by
# the sample-wise CLR denominator. The original global CLR reference is kept.
local_taxon_eligibility <- function(clr, abundance, samples, core_id, min_positive = 5L, min_fraction = 0) {
  if (min_positive < 1L || !is.finite(min_fraction) || min_fraction < 0 || min_fraction > 1) {
    stop("Invalid local positive-abundance eligibility settings")
  }
  if (!all(samples %in% rownames(clr)) || !all(samples %in% colnames(abundance)) ||
      !all(colnames(clr) %in% rownames(abundance))) stop("CLR/abundance identifiers do not align")
  mat <- clr[samples, , drop = FALSE]
  raw <- abundance[colnames(mat), samples, drop = FALSE]
  required <- max(as.integer(min_positive), ceiling(min_fraction * length(samples)))
  finite_clr <- colSums(!is.finite(mat)) == 0L
  finite_raw <- rowSums(!is.finite(raw)) == 0L
  clr_var <- apply(mat, 2, var, na.rm = TRUE)
  raw_var <- apply(raw, 1, var, na.rm = TRUE)
  positive <- rowSums(is.finite(raw) & raw > 0)
  reason <- fifelse(!finite_clr | !finite_raw, "nonfinite_profile",
                    fifelse(positive < required, "insufficient_local_positive_samples",
                            fifelse(!is.finite(clr_var) | clr_var <= 0, "constant_clr_profile", "eligible")))
  data.table(taxon = colnames(mat), core = core_id, n_positive_samples = as.integer(positive),
             n_core_samples = length(samples), min_positive_samples = required,
             clr_variance = as.numeric(clr_var), raw_abundance_variance = as.numeric(raw_var),
             constant_raw_abundance = is.finite(raw_var) & raw_var == 0,
             eligible = reason == "eligible", exclusion_reason = reason,
             selected_for_graph = FALSE)
}

build_correlation_edges <- function(mat, thr, method_suffix, method_label, method_name, threshold_value) {
  if (method_name == "bicor") {
    cor_mat <- suppressWarnings(WGCNA::bicor(
      x = as.matrix(mat),
      use = "pairwise.complete.obs",
      maxPOutliers = NG_PARAMS$bicor_max_p_outliers
    ))
  } else {
    cor_mat <- suppressWarnings(cor(mat, method = method_name, use = "pairwise.complete.obs"))
  }
  diag(cor_mat) <- 0
  idx <- which(abs(cor_mat) >= threshold_value, arr.ind = TRUE)
  idx <- idx[idx[, 1] < idx[, 2], , drop = FALSE]

  if (nrow(idx) == 0) {
    return(data.table(
      threshold = thr,
      from = character(),
      to = character(),
      signed_weight = numeric(),
      weight = numeric(),
      abs_weight = numeric(),
      method = method_label,
      method_suffix = method_suffix
    ))
  }

  data.table(
    threshold = thr,
    from = colnames(cor_mat)[idx[, 1]],
    to = colnames(cor_mat)[idx[, 2]],
    signed_weight = cor_mat[idx],
    weight = abs(cor_mat[idx]),
    abs_weight = abs(cor_mat[idx]),
    method = method_label,
    method_suffix = method_suffix,
    threshold_value = threshold_value
  )
}

write_site_graph <- function(edges, vertices, out_dirs, core_id, method_suffix, method_label, samples_n, threshold_value, top_taxa_n) {
  edge_cols <- c("from", "to", setdiff(names(edges), c("from", "to")))
  edges <- edges[, ..edge_cols]
  g <- graph_from_data_frame(edges, directed = FALSE, vertices = vertices)
  if (ecount(g) > 0) {
    E(g)$weight <- edges$abs_weight
    if ("signed_weight" %in% names(edges)) {
      E(g)$signed_weight <- edges$signed_weight
    }
  }

  edge_path <- file.path(out_dirs$graphs, paste0("ngraph_edges_", core_id, "_", method_suffix, ".tsv"))
  node_path <- file.path(out_dirs$graphs, paste0("ngraph_nodes_", core_id, "_", method_suffix, ".tsv"))
  graphml_path <- file.path(out_dirs$graphs, paste0("ngraph_", core_id, "_", method_suffix, ".graphml"))
  rds_path <- file.path(out_dirs$graphs, paste0("ngraph_", core_id, "_", method_suffix, ".rds"))

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
    association_cutoff = threshold_value,
    top_variable_taxa = top_taxa_n
  )
}

all_summaries <- list()
for (thr in NG_PARAMS$prevalence_thresholds) {
  dirs <- ng_threshold_dirs(thr)
  clr <- readRDS(file.path(dirs$matrices, "ngraph_clr_global.rds"))
  abundance_path <- file.path(dirs$matrices, "ngraph_tax_abundance_taxa_by_sample.rds")
  if (!file.exists(abundance_path)) abundance_path <- file.path(dirs$matrices, "ngraph_tax_abund_tad_taxa_by_sample.rds")
  abundance <- readRDS(abundance_path)
  sample_qc <- fread(file.path(dirs$tables, "ngraph_sample_qc.tsv"))
  taxa_meta <- fread(file.path(dirs$tables, "ngraph_taxa_metadata.tsv"))

  graph_summaries <- list()
  eligibility_summaries <- list()
  for (core_id in NG_PARAMS$all_cores) {
    samples <- intersect(sample_qc[core == core_id, label], rownames(clr))
    eligibility <- local_taxon_eligibility(clr, abundance, samples, core_id,
      min_positive = as.integer(Sys.getenv("NG_LOCAL_MIN_POSITIVE_SAMPLES", "5")),
      min_fraction = as.numeric(Sys.getenv("NG_LOCAL_PREVALENCE_FRACTION", "0")))
    eligibility[, threshold := thr]
    if (length(samples) < NG_PARAMS$graph_min_samples) {
      eligibility[, `:=`(eligible = FALSE, exclusion_reason = "insufficient_core_samples")]
      eligibility_summaries[[length(eligibility_summaries) + 1]] <- eligibility
      ng_log(LOG, "Threshold ", thr, " skipping ", core_id, ": fewer than ", NG_PARAMS$graph_min_samples, " samples")
      next
    }

    mat <- clr[samples, eligibility[eligible == TRUE, taxon], drop = FALSE]
    if (Sys.getenv("NG_TAD_SUPPORTED_ONLY", "false") == "true") {
      tad <- readRDS(file.path(dirs$matrices, "ngraph_tax_abund_tad_taxa_by_sample.rds"))
      supported <- rownames(tad)[rowSums(tad[, samples, drop = FALSE] > 0) > 0]
      mat <- mat[, intersect(colnames(mat), supported), drop = FALSE]
    }
    vars <- apply(mat, 2, var, na.rm = TRUE)
    top_taxa <- names(sort(vars, decreasing = TRUE))[seq_len(min(NG_PARAMS$graph_top_variable_taxa, length(vars)))]
    mat <- mat[, top_taxa, drop = FALSE]
    eligibility[taxon %in% top_taxa, selected_for_graph := TRUE]
    eligibility_summaries[[length(eligibility_summaries) + 1]] <- eligibility
    if (ncol(mat) < 2L) {
      ng_log(LOG, "Threshold ", thr, " skipping ", core_id, ": fewer than two eligible variable taxa")
      next
    }

    vertices <- data.table(name = colnames(mat), taxon = colnames(mat))
    vertices <- merge(vertices, taxa_meta, by = "taxon", all.x = TRUE, sort = FALSE)
    vertices[, name := taxon]

    for (method_suffix in intersect(NG_PARAMS$site_graph_methods, c("pearson", "bicor", "spearman"))) {
      method_label <- paste0(method_suffix, "_abs_threshold")
      edges <- build_correlation_edges(
        mat = mat,
        thr = thr,
        method_suffix = method_suffix,
        method_label = method_label,
        method_name = method_suffix,
        threshold_value = NG_PARAMS$cor_abs_threshold
      )
      edges[, core := core_id]
      graph_summaries[[length(graph_summaries) + 1]] <- cbind(
        data.table(threshold = thr),
        write_site_graph(
          edges = edges,
          vertices = vertices,
          out_dirs = dirs,
          core_id = core_id,
          method_suffix = method_suffix,
          method_label = method_label,
          samples_n = length(samples),
          threshold_value = NG_PARAMS$cor_abs_threshold,
          top_taxa_n = length(top_taxa)
        )
      )
      ng_log(LOG, "Threshold ", thr, " built ", core_id, " ", toupper(method_suffix), " graph: ", nrow(vertices), " nodes, ", nrow(edges), " edges")
    }

    if (minet_available && "mi_aracne" %in% NG_PARAMS$site_graph_methods) {
      mim <- minet::build.mim(dataset = as.data.frame(mat), estimator = NG_PARAMS$minet_estimator)
      aracne_mat <- as.matrix(minet::aracne(mim, eps = NG_PARAMS$aracne_eps))
      diag(aracne_mat) <- 0
      mi_idx <- which(aracne_mat > 0, arr.ind = TRUE)
      mi_idx <- mi_idx[mi_idx[, 1] < mi_idx[, 2], , drop = FALSE]
      mi_edges <- data.table(
        threshold = thr,
        from = colnames(aracne_mat)[mi_idx[, 1]],
        to = colnames(aracne_mat)[mi_idx[, 2]],
        weight = aracne_mat[mi_idx],
        abs_weight = aracne_mat[mi_idx],
        method = "mi_aracne",
        method_suffix = "mi_aracne",
        estimator = NG_PARAMS$minet_estimator,
        aracne_eps = NG_PARAMS$aracne_eps,
        core = core_id
      )
      graph_summaries[[length(graph_summaries) + 1]] <- cbind(
        data.table(threshold = thr),
        write_site_graph(
          edges = mi_edges,
          vertices = vertices,
          out_dirs = dirs,
          core_id = core_id,
          method_suffix = "mi_aracne",
          method_label = "mi_aracne",
          samples_n = length(samples),
          threshold_value = NG_PARAMS$aracne_eps,
          top_taxa_n = length(top_taxa)
        )
      )
      ng_log(LOG, "Threshold ", thr, " built ", core_id, " MI/ARACNE graph: ", nrow(vertices), " nodes, ", nrow(mi_edges), " edges")
    }
  }

  summary_dt <- rbindlist(graph_summaries, fill = TRUE)
  fwrite(rbindlist(eligibility_summaries, fill = TRUE),
         file.path(dirs$tables, "ngraph_taxon_core_eligibility.tsv"), sep = "\t")
  fwrite(summary_dt, file.path(dirs$tables, "ngraph_site_graph_summary.tsv"), sep = "\t")
  all_summaries[[length(all_summaries) + 1]] <- summary_dt

  report <- file.path(dirs$reports, "NGRAPH_SITE_GRAPH_REPORT.md")
  sink(report)
  cat("# NGraph Site Graph Report\n\n")
  cat("- Generated: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), "\n", sep = "")
  cat("- Branch: `", NG$branch, "`\n", sep = "")
  cat("- Prevalence threshold: `", thr, "`\n", sep = "")
  cat("- Pearson/Bicor/Spearman methods: sample-wise CLR, thresholded by absolute association.\n")
  cat("- MI/ARACNE method: `minet::build.mim(..., estimator = \"", NG_PARAMS$minet_estimator, "\")` followed by `minet::aracne(..., eps = ", NG_PARAMS$aracne_eps, ")`.\n", sep = "")
  cat("- MI/ARACNE available in this run: `", minet_available, "`.\n\n", sep = "")
  cat("## Graph Summary\n\n")
  cat(ng_md_table(summary_dt))
  sink()
}

fwrite(rbindlist(all_summaries, fill = TRUE), file.path(NG$tables, "ngraph_all_threshold_site_graph_summary.tsv"), sep = "\t")
ng_log(LOG, "Method Validated: threshold-specific site graphs written")
ng_log(LOG, "Complete")
