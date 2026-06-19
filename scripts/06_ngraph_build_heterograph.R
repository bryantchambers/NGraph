#!/usr/bin/env Rscript
# 06_ngraph_build_heterograph.R -- export model-ready heterograph tables.

suppressPackageStartupMessages({
  library(data.table)
  library(igraph)
  library(ggplot2)
  library(jsonlite)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("06_ngraph_build_heterograph")
ng_start_log(LOG)
ng_log(LOG, "Starting NGraph heterograph export")
ng_log(LOG, "Package versions: data.table ", as.character(utils::packageVersion("data.table")),
       ", igraph ", as.character(utils::packageVersion("igraph")),
       ", ggplot2 ", as.character(utils::packageVersion("ggplot2")),
       ", jsonlite ", as.character(utils::packageVersion("jsonlite")))

for (path in c(NG_DATA$tax_damage, NG_DATA$metadata_file, NG_DATA$prokaryote_function)) {
  if (!file.exists(path)) stop("Missing imported feedstock: ", path, ". Run steps 00-01 first.")
}

select_numeric <- function(dt, drop = character()) {
  keep <- names(dt)[vapply(dt, is.numeric, logical(1))]
  setdiff(keep, drop)
}

safe_read <- function(path, ...) {
  if (!file.exists(path)) return(NULL)
  fread(path, ...)
}

write_combo_export <- function(thr, method) {
  dirs <- ng_deep_dirs(thr, method)
  matrix_dirs <- ng_threshold_dirs(thr)

  clr_path <- file.path(matrix_dirs$matrices, "ngraph_clr_global.rds")
  abund_path <- file.path(matrix_dirs$matrices, "ngraph_tax_abund_tad_taxa_by_sample.rds")
  sample_qc_path <- file.path(matrix_dirs$tables, "ngraph_sample_qc.tsv")
  taxa_meta_path <- file.path(matrix_dirs$tables, "ngraph_taxa_metadata.tsv")
  site_summary_path <- file.path(matrix_dirs$tables, "ngraph_site_graph_summary.tsv")
  super_edge_path <- file.path(matrix_dirs$tables, paste0("ngraph_super_graph_edges_", method, ".tsv"))

  required <- c(clr_path, abund_path, sample_qc_path, taxa_meta_path, site_summary_path, super_edge_path)
  if (!all(file.exists(required))) {
    ng_log(LOG, "Skipping ", dirs$threshold, "/", method, ": missing source artifacts")
    return(NULL)
  }

  clr <- readRDS(clr_path)
  abund <- readRDS(abund_path)
  sample_qc <- fread(sample_qc_path)
  taxa_meta <- fread(taxa_meta_path)
  site_summary <- fread(site_summary_path)
  super_edges <- fread(super_edge_path)
  taxa_meta <- unique(taxa_meta, by = "taxon")

  if (!identical(rownames(clr), colnames(abund)[match(rownames(clr), colnames(abund))])) {
    abund <- abund[, rownames(clr), drop = FALSE]
  }

  sample_qc[, sample := as.character(sample)]
  sample_qc[, core := as.character(core)]
  sample_qc <- sample_qc[order(match(sample, rownames(clr)))]

  taxa <- colnames(clr)
  taxa_meta <- merge(
    data.table(taxon = taxa),
    taxa_meta,
    by = "taxon",
    all.x = TRUE,
    sort = FALSE
  )

  taxon_presence_samples <- rowSums(abund > 0, na.rm = TRUE)
  taxon_presence_cores <- vapply(NG_PARAMS$all_cores, function(core_id) {
    samples <- sample_qc[core == core_id, sample]
    if (length(samples) == 0) return(rep(FALSE, length(taxa)))
    rowSums(abund[, samples, drop = FALSE] > 0, na.rm = TRUE) > 0
  }, logical(length(taxa)))
  colnames(taxon_presence_cores) <- NG_PARAMS$all_cores

  taxon_nodes <- copy(taxa_meta)
  taxon_nodes[, `:=`(
    threshold = thr,
    taxon_index = seq_len(.N),
    mean_clr = colMeans(clr, na.rm = TRUE),
    sd_clr = apply(clr, 2, sd, na.rm = TRUE),
    mean_abs_clr = colMeans(abs(clr), na.rm = TRUE),
    max_abs_clr = apply(abs(clr), 2, max, na.rm = TRUE),
    mean_abundance = rowMeans(abund, na.rm = TRUE),
    prevalence_samples = taxon_presence_samples / nrow(abund),
    n_samples = taxon_presence_samples,
    n_cores = rowSums(taxon_presence_cores, na.rm = TRUE),
    prevalence_cores = rowSums(taxon_presence_cores, na.rm = TRUE) / length(NG_PARAMS$all_cores)
  )]

  numeric_taxon_cols <- select_numeric(taxon_nodes, drop = c("threshold", "taxon_index"))
  taxon_nodes <- taxon_nodes[, c("taxon", "threshold", "taxon_index", setdiff(names(taxon_nodes), c("taxon", "threshold", "taxon_index"))), with = FALSE]

  site_graph_summary <- site_summary[method_suffix == method]
  if ("threshold" %in% names(site_graph_summary)) {
    site_graph_summary[, graph_threshold := threshold]
    site_graph_summary[, threshold := NULL]
  }
  if ("method" %in% names(site_graph_summary)) {
    site_graph_summary[, graph_method := method]
    site_graph_summary[, method := NULL]
  }
  site_nodes <- merge(
    data.table(core = NG_PARAMS$all_cores),
    site_graph_summary,
    by = "core",
    all.x = TRUE,
    sort = FALSE
  )
  site_nodes <- merge(
    site_nodes,
    sample_qc[, .(
      samples = .N,
      age_min_kyr = min(age_kyr, na.rm = TRUE),
      age_max_kyr = max(age_kyr, na.rm = TRUE),
      age_mean_kyr = mean(age_kyr, na.rm = TRUE),
      total_tax_abund_tad = sum(total_tax_abund_tad, na.rm = TRUE),
      detected_taxa_tad = mean(detected_taxa_tad, na.rm = TRUE),
      total_n_reads = sum(total_n_reads, na.rm = TRUE),
      total_n_reads_tad = sum(total_n_reads_tad, na.rm = TRUE)
    ), by = core],
    by = "core",
    all.x = TRUE,
    suffixes = c("", "_site")
  )
  if ("threshold" %in% names(site_nodes)) {
    site_nodes[, graph_threshold := threshold]
    site_nodes[, threshold := NULL]
  }
  if ("method" %in% names(site_nodes)) {
    site_nodes[, graph_method := method]
    site_nodes[, method := NULL]
  }
  site_nodes[, `:=`(
    threshold = thr,
    method = method
  )]
  site_nodes <- site_nodes[order(match(core, NG_PARAMS$all_cores))]

  taxon_taxon_edges <- list()
  for (core_id in NG_PARAMS$all_cores) {
    edge_path <- file.path(matrix_dirs$graphs, paste0("ngraph_edges_", core_id, "_", method, ".tsv"))
    if (!file.exists(edge_path)) next
    edges <- fread(edge_path)
    if (nrow(edges) == 0) next
    if (!"signed_weight" %in% names(edges)) {
      edges[, signed_weight := weight]
    }
    edges[, `:=`(
      threshold = thr,
      method = method,
      source_core = core_id,
      relation = fifelse(signed_weight >= 0, "positive", "negative"),
      edge_type = paste0("taxon_taxon__", core_id, "__", fifelse(signed_weight >= 0, "positive", "negative"))
    )]
    taxon_taxon_edges[[length(taxon_taxon_edges) + 1]] <- edges[, .(
      threshold, method, source_core, relation, edge_type,
      from, to, signed_weight, weight, abs_weight
    )]
  }
  taxon_taxon_edges <- rbindlist(taxon_taxon_edges, fill = TRUE)
  setnames(taxon_taxon_edges, c("from", "to"), c("taxon_from", "taxon_to"))

  site_site_edges <- copy(super_edges)
  if (nrow(site_site_edges) > 0) {
    site_site_edges[, `:=`(
      threshold = thr,
      method = method,
      edge_type = "site_similarity"
    )]
    setnames(site_site_edges, c("from", "to"), c("site_from", "site_to"))
  }

  taxon_site_edges <- list()
  for (core_id in NG_PARAMS$all_cores) {
    samples <- sample_qc[core == core_id, sample]
    if (length(samples) == 0) next
    clr_core <- clr[samples, , drop = FALSE]
    abund_core <- abund[, samples, drop = FALSE]
    edge_dt <- data.table(
      threshold = thr,
      method = method,
      core = core_id,
      taxon = taxa,
      mean_clr = colMeans(clr_core, na.rm = TRUE),
      sd_clr = apply(clr_core, 2, sd, na.rm = TRUE),
      mean_abs_clr = colMeans(abs(clr_core), na.rm = TRUE),
      max_abs_clr = apply(abs(clr_core), 2, max, na.rm = TRUE),
      temporal_var_clr = apply(clr_core, 2, var, na.rm = TRUE),
      prevalence = rowMeans(abund_core > 0, na.rm = TRUE),
      mean_tax_abund_tad = rowMeans(abund_core, na.rm = TRUE)
    )
    edge_dt <- edge_dt[is.finite(prevalence) & prevalence > 0]
    edge_dt[, edge_type := "taxon_site_context"]
    taxon_site_edges[[length(taxon_site_edges) + 1]] <- edge_dt
  }
  taxon_site_edges <- rbindlist(taxon_site_edges, fill = TRUE)

  fwrite(taxon_nodes, file.path(dirs$tables, "hetero_taxon_nodes.tsv"), sep = "\t")
  fwrite(site_nodes, file.path(dirs$tables, "hetero_site_nodes.tsv"), sep = "\t")
  fwrite(taxon_taxon_edges, file.path(dirs$tables, "hetero_taxon_taxon_edges.tsv"), sep = "\t")
  fwrite(site_site_edges, file.path(dirs$tables, "hetero_site_site_edges.tsv"), sep = "\t")
  fwrite(taxon_site_edges, file.path(dirs$tables, "hetero_taxon_site_edges.tsv"), sep = "\t")

  manifest <- list(
    generated = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
    branch = NG$branch,
    threshold = thr,
    method = method,
    seed = NG_PARAMS$seed,
    source_files = list(
      clr = clr_path,
      abundance = abund_path,
      sample_qc = sample_qc_path,
      taxa_metadata = taxa_meta_path,
      site_summary = site_summary_path,
      super_graph_edges = super_edge_path
    ),
    nodes = list(
      taxon = nrow(taxon_nodes),
      site = nrow(site_nodes)
    ),
    edges = list(
      taxon_taxon = nrow(taxon_taxon_edges),
      site_site = nrow(site_site_edges),
      taxon_site = nrow(taxon_site_edges)
    ),
    feature_columns = list(
      taxon_numeric = numeric_taxon_cols,
      site_numeric = select_numeric(site_nodes, drop = c("threshold", "method"))
    ),
    direct_relations = c("taxon_taxon", "site_similarity", "taxon_site_context")
  )
  write_json(manifest, file.path(dirs$tables, "heterograph_manifest.json"), auto_unbox = TRUE, pretty = TRUE)

  combo_summary <- data.table(
    threshold = thr,
    method = method,
    taxon_nodes = nrow(taxon_nodes),
    site_nodes = nrow(site_nodes),
    taxon_taxon_edges = nrow(taxon_taxon_edges),
    site_site_edges = nrow(site_site_edges),
    taxon_site_edges = nrow(taxon_site_edges),
    taxon_taxon_positive = taxon_taxon_edges[relation == "positive", .N],
    taxon_taxon_negative = taxon_taxon_edges[relation == "negative", .N]
  )

  p <- ggplot(
    melt(
      combo_summary,
      id.vars = c("threshold", "method"),
      variable.name = "artifact",
      value.name = "count"
    ),
    aes(x = method, y = count, fill = artifact)
  ) +
    geom_col(position = position_dodge(width = 0.75), width = 0.65) +
    facet_wrap(~ threshold, nrow = 1, scales = "free_y") +
    labs(title = "NGraph deep-module export inventory", x = "Graph method", y = "Count", fill = "Artifact") +
    theme_minimal(base_size = 11) +
    theme(panel.grid.major.x = element_blank())
  ggsave(file.path(NG$deep_modules, "heterograph_export_inventory.png"), p, width = 11, height = 4.5, dpi = 180)

  report <- file.path(dirs$reports, "NGRAPH_HETEROGRAPH_EXPORT_REPORT.md")
  sink(report)
  cat("# NGraph Heterograph Export Report\n\n")
  cat("- Generated: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), "\n", sep = "")
  cat("- Branch: `", NG$branch, "`\n", sep = "")
  cat("- Threshold: `", thr, "`\n", sep = "")
  cat("- Method: `", method, "`\n", sep = "")
  cat("- Seed: `", NG_PARAMS$seed, "`\n\n", sep = "")
  cat("## Export Inventory\n\n")
  cat(ng_md_table(combo_summary))
  cat("\n## Source Files\n\n")
  cat(ng_md_table(data.table(
    artifact = names(manifest$source_files),
    path = unlist(manifest$source_files, use.names = FALSE)
  )))
  sink()

  ng_log(LOG, "Exported heterograph tables for ", dirs$threshold, "/", method,
         ": taxon nodes=", nrow(taxon_nodes),
         ", site nodes=", nrow(site_nodes),
         ", taxon-taxon edges=", nrow(taxon_taxon_edges),
         ", site-site edges=", nrow(site_site_edges),
         ", taxon-site edges=", nrow(taxon_site_edges))

  combo_summary
}

summaries <- list()
for (thr in NG_PARAMS$prevalence_thresholds) {
  for (method in NG_PARAMS$deep_module_methods) {
    out <- tryCatch(write_combo_export(thr, method), error = function(e) {
      ng_log(LOG, "Export failed for ", ng_threshold_label(thr), "/", method, ": ", conditionMessage(e))
      NULL
    })
    if (!is.null(out)) summaries[[length(summaries) + 1]] <- out
  }
}

summary_dt <- rbindlist(summaries, fill = TRUE)
if (nrow(summary_dt) > 0) {
  fwrite(summary_dt, file.path(NG$deep_modules, "heterograph_export_summary.tsv"), sep = "\t")
}

ng_log(LOG, "Method Validated: heterograph export tables written")
ng_log(LOG, "Complete")
