#!/usr/bin/env Rscript
suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
})

options(stringsAsFactors = FALSE)
set.seed(42)

script_args <- commandArgs(trailingOnly = FALSE)
file_arg <- script_args[grepl("^--file=", script_args)]
script_path <- if (length(file_arg)) sub("^--file=", "", file_arg[1]) else normalizePath("scripts/11_ngraph_vgae_glacial_interglacial_plots.R")
project_root <- normalizePath(file.path(dirname(script_path), ".."))

deep_root <- file.path(project_root, "results", "ngraph", "abundance_thresholding", "deep_modules")
log_path <- file.path(project_root, "logs", "11_ngraph_vgae_glacial_interglacial_plots.log")
summary_path <- file.path(deep_root, "vgae_state_plot_summary.tsv")

dir.create(dirname(log_path), recursive = TRUE, showWarnings = FALSE)
dir.create(deep_root, recursive = TRUE, showWarnings = FALSE)
if (file.exists(log_path)) invisible(file.remove(log_path))

log_msg <- function(...) {
  line <- sprintf("[%s] %s", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), paste0(...))
  cat(line, "\n", file = log_path, append = TRUE)
  message(line)
}

metadata_path <- file.path(project_root, "Source", "ROCS", "data", "metadata_v5.tsv")
if (!file.exists(metadata_path)) {
  metadata_path <- file.path(project_root, "data", "metadata", "metadata_v5.tsv")
}
if (!file.exists(metadata_path)) stop("Could not locate metadata_v5.tsv in Source/ROCS or data/metadata")

meta <- fread(metadata_path)
meta[, mis := as.numeric(mis)]
meta[, core_mis := median(mis, na.rm = TRUE), by = core]
meta[, glacial_class := fifelse(core_mis >= 4.0, "glacial_like", "interglacial_like")]

core_summary <- unique(meta[, .(core, core_mis, glacial_class)])
core_summary <- core_summary[order(core)]

discover_combos <- function(root) {
  thr_dirs <- list.dirs(root, recursive = FALSE, full.names = TRUE)
  thr_dirs <- thr_dirs[grepl("^prev_", basename(thr_dirs))]
  combos <- list()
  for (thr in sort(thr_dirs)) {
    methods <- list.dirs(thr, recursive = FALSE, full.names = TRUE)
    methods <- methods[file.info(methods)$isdir %in% TRUE]
    for (method_dir in sort(methods)) {
      combos[[length(combos) + 1L]] <- list(
        threshold = basename(thr),
        method = basename(method_dir),
        path = method_dir
      )
    }
  }
  combos
}

bh_adjust <- function(p) {
  ok <- is.finite(p)
  out <- rep(NA_real_, length(p))
  if (!any(ok)) return(out)
  out[ok] <- p.adjust(p[ok], method = "BH")
  out
}

make_taxon_enrichment <- function(abund_mat, sample_qc) {
  sample_qc <- copy(sample_qc)
  if (!"sample" %in% names(sample_qc)) {
    if ("label" %in% names(sample_qc)) {
      sample_qc[, sample := as.character(label)]
    } else {
      stop("Sample QC table does not contain sample or label columns")
    }
  }
  sample_qc[, mis := as.numeric(mis)]
  sample_qc <- sample_qc[is.finite(mis)]
  sample_qc[, sample_class := fifelse(mis >= 4.0, "glacial_like", "interglacial_like")]
  sample_order <- intersect(colnames(abund_mat), sample_qc$sample)
  if (!length(sample_order)) stop("No overlapping samples between abundance matrix and sample QC")
  sample_qc <- sample_qc[match(sample_order, sample)]
  sample_qc <- sample_qc[!is.na(sample_class)]
  sample_qc <- sample_qc[order(match(sample, sample_order))]
  abund_mat <- abund_mat[, sample_order, drop = FALSE]
  glacial_total <- sum(sample_qc$sample_class == "glacial_like")
  inter_total <- sum(sample_qc$sample_class == "interglacial_like")
  taxa <- rownames(abund_mat)
  res <- vector("list", length(taxa))
  for (i in seq_along(taxa)) {
    tx <- taxa[i]
    values <- as.numeric(abund_mat[tx, ])
    glacial_vals <- values[sample_qc$sample_class == "glacial_like"]
    inter_vals <- values[sample_qc$sample_class == "interglacial_like"]
    glacial_present <- sum(glacial_vals > 0, na.rm = TRUE)
    inter_present <- sum(inter_vals > 0, na.rm = TRUE)
    glacial_absent <- glacial_total - glacial_present
    interglacial_absent <- inter_total - inter_present
    tab <- matrix(c(glacial_present, glacial_absent, inter_present, interglacial_absent), nrow = 2, byrow = TRUE)
    ft <- suppressWarnings(fisher.test(tab))
    glacial_mean <- mean(glacial_vals, na.rm = TRUE)
    inter_mean <- mean(inter_vals, na.rm = TRUE)
    if (!is.finite(glacial_mean)) glacial_mean <- 0
    if (!is.finite(inter_mean)) inter_mean <- 0
    log2fc <- log2((glacial_mean + 1e-6) / (inter_mean + 1e-6))
    res[[i]] <- data.table(
      taxon = tx,
      glacial_present = glacial_present,
      interglacial_present = inter_present,
      glacial_absent = glacial_absent,
      interglacial_absent = interglacial_absent,
      odds_ratio = unname(ft$estimate),
      p_value = ft$p.value,
      glacial_mean_abund = glacial_mean,
      interglacial_mean_abund = inter_mean,
      log2fc = log2fc
    )
  }
  out <- rbindlist(res, fill = TRUE)
  out[, fdr := bh_adjust(p_value)]
  out[, enrichment_class := fifelse(
    is.finite(fdr) & fdr < 0.1 & log2fc > 0,
    "glacial_enriched",
    fifelse(is.finite(fdr) & fdr < 0.1 & log2fc < 0, "interglacial_enriched", "neither")
  )]
  out
}

make_site_embedding_plot <- function(site_dt) {
  z_cols <- grep("^z_[0-9]+$", names(site_dt), value = TRUE)
  if (length(z_cols) < 2) stop("Site embeddings do not contain enough latent dimensions")
  site_dt <- merge(site_dt, core_summary, by.x = "node_id", by.y = "core", all.x = TRUE)
  x <- as.matrix(site_dt[, ..z_cols])
  pcs <- prcomp(x, center = TRUE, scale. = TRUE)
  site_dt[, `:=`(pca_1 = pcs$x[, 1], pca_2 = pcs$x[, 2])]
  site_dt
}

combos <- discover_combos(deep_root)
if (!length(combos)) stop("No deep-module combos found under ", deep_root)

rows <- list()

for (combo in combos) {
  tables <- file.path(combo$path, "tables")
  figs <- file.path(combo$path, "figures")
  if (!dir.exists(tables)) {
    log_msg("Skipping ", combo$threshold, "/", combo$method, ": missing tables directory")
    next
  }

  taxon_modules_path <- file.path(tables, "vgae_taxon_modules.tsv")
  embeddings_path <- file.path(tables, "vgae_embeddings.tsv")
  sample_qc_path <- file.path(project_root, "results", "ngraph", "abundance_thresholding", combo$threshold, "tables", "ngraph_sample_qc.tsv")
  sample_abund_path <- file.path(project_root, "results", "ngraph", "abundance_thresholding", combo$threshold, "matrices", "ngraph_tax_abund_tad_taxa_by_sample.rds")
  if (!file.exists(taxon_modules_path) || !file.exists(embeddings_path) || !file.exists(sample_qc_path) || !file.exists(sample_abund_path)) {
    log_msg("Skipping ", combo$threshold, "/", combo$method, ": missing required TSVs")
    next
  }

  taxon_modules <- fread(taxon_modules_path)
  embeddings <- fread(embeddings_path)
  sample_qc <- fread(sample_qc_path)
  abund_mat <- readRDS(sample_abund_path)

  enrichment <- make_taxon_enrichment(abund_mat, sample_qc)
  taxon_plot_dt <- merge(taxon_modules[, .(taxon, pca_1, pca_2)], enrichment, by = "taxon", all.x = TRUE)
  taxon_plot_dt[, enrichment_class := factor(enrichment_class, levels = c("glacial_enriched", "interglacial_enriched", "neither"))]
  taxon_plot_file <- file.path(figs, "vgae_taxon_embedding_enrichment_pca.png")
  site_plot_file <- file.path(figs, "vgae_site_embedding_mis_pca.png")

  p_taxon <- ggplot(taxon_plot_dt, aes(pca_1, pca_2, color = enrichment_class)) +
    geom_point(size = 2.4, alpha = 0.9) +
    scale_color_manual(values = c(
      glacial_enriched = "#2166ac",
      interglacial_enriched = "#b2182b",
      neither = "#bdbdbd"
    ), drop = FALSE) +
    labs(
      title = paste0("VGAE taxon embeddings by glacial/interglacial enrichment: ", combo$threshold, "/", combo$method),
      x = "PCA 1",
      y = "PCA 2",
      color = NULL
    ) +
    theme_bw(base_size = 12) +
    theme(panel.grid = element_blank())
  ggsave(taxon_plot_file, p_taxon, width = 7.4, height = 5.6, dpi = 180)

  site_dt <- embeddings[node_type == "site"]
  site_dt <- make_site_embedding_plot(site_dt)
  p_site <- ggplot(site_dt, aes(pca_1, pca_2, color = core_mis)) +
    geom_point(size = 3.4, alpha = 0.95) +
    geom_text(aes(label = node_id), nudge_y = 0.03, size = 3.2, check_overlap = TRUE) +
    scale_color_gradient2(
      low = "#4575b4",
      mid = "white",
      high = "#d73027",
      midpoint = 4.0
    ) +
    labs(
      title = paste0("VGAE site embeddings by MIS core state: ", combo$threshold, "/", combo$method),
      x = "PCA 1",
      y = "PCA 2",
      color = "core MIS"
    ) +
    theme_bw(base_size = 12) +
    theme(panel.grid = element_blank())
  ggsave(site_plot_file, p_site, width = 7.0, height = 5.4, dpi = 180)

  enrichment[, threshold := combo$threshold]
  enrichment[, method := combo$method]
  enrichment[, taxon_embedding_plot := taxon_plot_file]
  enrichment[, site_embedding_plot := site_plot_file]
  enrichment[, core_mis_midpoint := 4.0]
  fwrite(enrichment, file.path(tables, "vgae_taxon_mis_enrichment.tsv"), sep = "\t")

  rows[[length(rows) + 1L]] <- data.table(
    threshold = combo$threshold,
    method = combo$method,
    taxa_plotted = nrow(taxon_plot_dt),
    glacial_enriched = sum(taxon_plot_dt$enrichment_class == "glacial_enriched", na.rm = TRUE),
    interglacial_enriched = sum(taxon_plot_dt$enrichment_class == "interglacial_enriched", na.rm = TRUE),
    neither = sum(taxon_plot_dt$enrichment_class == "neither", na.rm = TRUE),
    taxon_embedding_plot = taxon_plot_file,
    site_embedding_plot = site_plot_file
  )

  log_msg("Method Validated: ", combo$threshold, "/", combo$method, " enrichment and site plots written")
}

if (length(rows)) {
  summary <- rbindlist(rows, fill = TRUE)
  fwrite(summary, summary_path, sep = "\t")
  log_msg("Wrote summary to ", summary_path)
}
