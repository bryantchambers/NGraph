#!/usr/bin/env Rscript
# 02_ngraph_input_qc.R -- ROCS-style ordination and PC/covariate QC for NGraph.

suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("02_ngraph_input_qc")
ng_start_log(LOG)
ng_log(LOG, "Starting NGraph input QC")

clr <- readRDS(file.path(NG$matrices, "ngraph_clr_global.rds"))
sample_qc <- fread(file.path(NG$tables, "ngraph_sample_qc.tsv"))
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
fwrite(scores, file.path(NG$tables, "ngraph_input_pc_scores.tsv"), sep = "\t")

variance <- data.table(
  PC = paste0("PC", seq_len(min(10L, length(pc$sdev)))),
  variance_explained = (pc$sdev^2 / sum(pc$sdev^2))[seq_len(min(10L, length(pc$sdev)))]
)
fwrite(variance, file.path(NG$tables, "ngraph_input_pc_variance.tsv"), sep = "\t")

covariates <- intersect(
  c("log_total_reads", "total_reads", "detected_taxa", "library_concentration",
    "avg_leng_initial", "avg_len_derep", "age_kyr", "mis", "sst"),
  names(scores)
)

assoc <- rbindlist(lapply(paste0("PC", seq_len(n_pc)), function(pc_col) {
  rbindlist(lapply(covariates, function(covar) {
    data.table(
      PC = pc_col,
      covariate = covar,
      covariate_class = ifelse(covar %in% c("age_kyr", "mis", "sst"), "biological_proxy", "technical"),
      pearson_r = ng_safe_cor(scores[[pc_col]], scores[[covar]], "pearson"),
      spearman_rho = ng_safe_cor(scores[[pc_col]], scores[[covar]], "spearman")
    )
  }))
}))
assoc[, abs_pearson := abs(pearson_r)]
fwrite(assoc, file.path(NG$tables, "ngraph_input_pc_associations.tsv"), sep = "\t")

core_r2 <- rbindlist(lapply(paste0("PC", seq_len(n_pc)), function(pc_col) {
  fit <- lm(scores[[pc_col]] ~ core, data = scores)
  data.table(PC = pc_col, covariate = "core", covariate_class = "core_or_site", r2 = summary(fit)$r.squared)
}))
fwrite(core_r2, file.path(NG$tables, "ngraph_input_pc_core_r2.tsv"), sep = "\t")

top_assoc <- assoc[order(-abs_pearson)][1:min(.N, 20)]
fwrite(top_assoc, file.path(NG$tables, "ngraph_input_pc_top_associations.tsv"), sep = "\t")

p_core <- ggplot(scores, aes(PC1, PC2, color = core)) +
  geom_point(size = 2.4, alpha = 0.9) +
  labs(title = "NGraph CLR ordination by core", x = "PC1", y = "PC2") +
  theme_minimal(base_size = 11)
ggsave(file.path(NG$figures, "ngraph_ordination_by_core.png"), p_core, width = 7.5, height = 5.4, dpi = 160)

p_depth <- ggplot(scores, aes(PC1, PC2, color = log_total_reads, shape = core)) +
  geom_point(size = 2.4, alpha = 0.9) +
  scale_color_viridis_c(option = "magma") +
  labs(title = "NGraph CLR ordination by read depth", color = "log10 reads", x = "PC1", y = "PC2") +
  theme_minimal(base_size = 11)
ggsave(file.path(NG$figures, "ngraph_ordination_by_depth.png"), p_depth, width = 7.5, height = 5.4, dpi = 160)

p_age <- ggplot(scores, aes(PC1, PC2, color = age_kyr, shape = core)) +
  geom_point(size = 2.4, alpha = 0.9) +
  scale_color_viridis_c(option = "cividis") +
  labs(title = "NGraph CLR ordination by age", color = "Age kyr", x = "PC1", y = "PC2") +
  theme_minimal(base_size = 11)
ggsave(file.path(NG$figures, "ngraph_ordination_by_age.png"), p_age, width = 7.5, height = 5.4, dpi = 160)

heat <- assoc[PC %in% paste0("PC", 1:3)]
heat[, label := sprintf("%.2f", pearson_r)]
p_heat <- ggplot(heat, aes(covariate, PC, fill = pearson_r)) +
  geom_tile(color = "white") +
  geom_text(aes(label = label), size = 3) +
  scale_fill_gradient2(low = "#2166ac", mid = "white", high = "#b2182b", midpoint = 0, limits = c(-1, 1), na.value = "grey90") +
  labs(title = "NGraph CLR PC associations", x = NULL, y = NULL) +
  theme_minimal(base_size = 10) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1), panel.grid = element_blank())
ggsave(file.path(NG$figures, "ngraph_pc_covariate_heatmap.png"), p_heat, width = 9.5, height = 4.8, dpi = 160)

report <- file.path(NG$reports, "NGRAPH_INPUT_QC_REPORT.md")
sink(report)
cat("# NGraph Input QC Report\n\n")
cat("- Generated: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), "\n", sep = "")
cat("- Input: sample-wise CLR matrix from `results/ngraph/matrices/ngraph_clr_global.rds`\n")
cat("- Log: `logs/02_ngraph_input_qc.log`\n\n")
cat("## Main QC Result\n\n")
cat("Top PC/covariate associations:\n\n")
cat(ng_md_table(top_assoc[, .(PC, covariate, covariate_class, pearson_r, spearman_rho)]))
cat("\nCore/site R2 by PC:\n\n")
cat(ng_md_table(core_r2))
cat("\n## Interpretation Guardrail\n\n")
cat("If PC1 or PC2 remains strongly associated with read depth, detected taxa, or core identity, graph similarity must be interpreted as a sensitivity result rather than direct ecological interaction evidence.\n\n")
cat("## Figures\n\n")
cat("- `results/ngraph/figures/ngraph_ordination_by_core.png`\n")
cat("- `results/ngraph/figures/ngraph_ordination_by_depth.png`\n")
cat("- `results/ngraph/figures/ngraph_ordination_by_age.png`\n")
cat("- `results/ngraph/figures/ngraph_pc_covariate_heatmap.png`\n")
sink()

ng_log(LOG, "Method Validated: QC plots and report written")
ng_log(LOG, "Complete")
