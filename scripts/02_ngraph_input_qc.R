#!/usr/bin/env Rscript
# 02_ngraph_input_qc.R -- ordination and PC/covariate QC for each threshold.

suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("02_ngraph_input_qc")
ng_start_log(LOG)
ng_log(LOG, "Starting NGraph input QC")

all_assoc <- list()
all_core_r2 <- list()
for (thr in NG_PARAMS$prevalence_thresholds) {
  dirs <- ng_threshold_dirs(thr)
  clr <- readRDS(file.path(dirs$matrices, "ngraph_clr_global.rds"))
  sample_qc <- fread(file.path(dirs$tables, "ngraph_sample_qc.tsv"))
  sample_qc[, sample := label]

  common <- intersect(rownames(clr), sample_qc$sample)
  clr <- clr[common, , drop = FALSE]
  sample_qc <- sample_qc[match(common, sample)]

  keep <- apply(clr, 2, var, na.rm = TRUE) > 0
  pc <- prcomp(clr[, keep, drop = FALSE], center = TRUE, scale. = FALSE)
  n_pc <- min(5L, ncol(pc$x))
  scores <- as.data.table(pc$x[, seq_len(n_pc), drop = FALSE])
  scores[, sample := rownames(pc$x)]
  scores <- merge(scores, sample_qc, by = "sample", all.x = TRUE, sort = FALSE)
  fwrite(scores, file.path(dirs$tables, "ngraph_input_pc_scores.tsv"), sep = "\t")

  variance <- data.table(
    threshold = thr,
    PC = paste0("PC", seq_len(min(10L, length(pc$sdev)))),
    variance_explained = (pc$sdev^2 / sum(pc$sdev^2))[seq_len(min(10L, length(pc$sdev)))]
  )
  fwrite(variance, file.path(dirs$tables, "ngraph_input_pc_variance.tsv"), sep = "\t")

  covariates <- intersect(
    c("log_total_tax_abund_tad", "total_tax_abund_tad", "detected_taxa_tad",
      "log_total_n_reads", "total_n_reads", "log_total_n_reads_tad",
      "library_concentration", "avg_leng_initial", "avg_len_derep", "age_kyr", "mis", "sst"),
    names(scores)
  )
  assoc <- rbindlist(lapply(paste0("PC", seq_len(n_pc)), function(pc_col) {
    rbindlist(lapply(covariates, function(covar) {
      data.table(
        threshold = thr,
        PC = pc_col,
        covariate = covar,
        covariate_class = ifelse(covar %in% c("age_kyr", "mis", "sst"), "biological_proxy", "technical"),
        pearson_r = ng_safe_cor(scores[[pc_col]], scores[[covar]], "pearson"),
        spearman_rho = ng_safe_cor(scores[[pc_col]], scores[[covar]], "spearman")
      )
    }))
  }))
  assoc[, abs_pearson := abs(pearson_r)]
  fwrite(assoc, file.path(dirs$tables, "ngraph_input_pc_associations.tsv"), sep = "\t")
  all_assoc[[length(all_assoc) + 1]] <- assoc

  core_r2 <- rbindlist(lapply(paste0("PC", seq_len(n_pc)), function(pc_col) {
    fit <- lm(scores[[pc_col]] ~ core, data = scores)
    data.table(threshold = thr, PC = pc_col, covariate = "core", covariate_class = "core_or_site", r2 = summary(fit)$r.squared)
  }))
  fwrite(core_r2, file.path(dirs$tables, "ngraph_input_pc_core_r2.tsv"), sep = "\t")
  all_core_r2[[length(all_core_r2) + 1]] <- core_r2

  top_assoc <- assoc[order(-abs_pearson)][1:min(.N, 20)]
  fwrite(top_assoc, file.path(dirs$tables, "ngraph_input_pc_top_associations.tsv"), sep = "\t")

  p_core <- ggplot(scores, aes(PC1, PC2, color = core)) +
    geom_point(size = 2.4, alpha = 0.9) +
    labs(title = paste("NGraph CLR ordination by core: prevalence", thr), x = "PC1", y = "PC2") +
    theme_minimal(base_size = 11)
  ggsave(file.path(dirs$figures, "ngraph_ordination_by_core.png"), p_core, width = 7.5, height = 5.4, dpi = 160)

  p_reads <- ggplot(scores, aes(PC1, PC2, color = log_total_n_reads, shape = core)) +
    geom_point(size = 2.4, alpha = 0.9) +
    scale_color_viridis_c(option = "magma") +
    labs(title = paste("NGraph CLR ordination by raw reads: prevalence", thr), color = "log10 reads", x = "PC1", y = "PC2") +
    theme_minimal(base_size = 11)
  ggsave(file.path(dirs$figures, "ngraph_ordination_by_raw_reads.png"), p_reads, width = 7.5, height = 5.4, dpi = 160)

  p_abund <- ggplot(scores, aes(PC1, PC2, color = log_total_tax_abund_tad, shape = core)) +
    geom_point(size = 2.4, alpha = 0.9) +
    scale_color_viridis_c(option = "cividis") +
    labs(title = paste("NGraph CLR ordination by TAD abundance: prevalence", thr), color = "log10 TAD", x = "PC1", y = "PC2") +
    theme_minimal(base_size = 11)
  ggsave(file.path(dirs$figures, "ngraph_ordination_by_tad_abundance.png"), p_abund, width = 7.5, height = 5.4, dpi = 160)

  heat <- assoc[PC %in% paste0("PC", 1:3)]
  heat[, label := sprintf("%.2f", pearson_r)]
  p_heat <- ggplot(heat, aes(covariate, PC, fill = pearson_r)) +
    geom_tile(color = "white") +
    geom_text(aes(label = label), size = 3) +
    scale_fill_gradient2(low = "#2166ac", mid = "white", high = "#b2182b", midpoint = 0, limits = c(-1, 1), na.value = "grey90") +
    labs(title = paste("NGraph CLR PC associations: prevalence", thr), x = NULL, y = NULL) +
    theme_minimal(base_size = 10) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1), panel.grid = element_blank())
  ggsave(file.path(dirs$figures, "ngraph_pc_covariate_heatmap.png"), p_heat, width = 10.5, height = 4.8, dpi = 160)

  report <- file.path(dirs$reports, "NGRAPH_INPUT_QC_REPORT.md")
  sink(report)
  cat("# NGraph Input QC Report\n\n")
  cat("- Generated: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), "\n", sep = "")
  cat("- Branch: `", NG$branch, "`\n", sep = "")
  cat("- Prevalence threshold: `", thr, "`\n", sep = "")
  cat("- Feature abundance: `", NG_PARAMS$abundance_column, "`\n\n", sep = "")
  cat("## Top PC Associations\n\n")
  cat(ng_md_table(top_assoc[, .(threshold, PC, covariate, covariate_class, pearson_r, spearman_rho)]))
  cat("\n## Core/Site R2\n\n")
  cat(ng_md_table(core_r2))
  sink()

  ng_log(LOG, "Threshold ", thr, ": QC plots and report written")
}

fwrite(rbindlist(all_assoc), file.path(NG$tables, "ngraph_all_threshold_pc_associations.tsv"), sep = "\t")
fwrite(rbindlist(all_core_r2), file.path(NG$tables, "ngraph_all_threshold_core_r2.tsv"), sep = "\t")
ng_log(LOG, "Method Validated: QC plots and reports written")
ng_log(LOG, "Complete")
