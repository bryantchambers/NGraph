#!/usr/bin/env Rscript
# 09_ngraph_deep_module_summary.R -- summarize deep-module exports and model outputs.

suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("09_ngraph_deep_module_summary")
ng_start_log(LOG)
ng_log(LOG, "Writing deep-module summary")
ng_log(LOG, "Package versions: data.table ", as.character(utils::packageVersion("data.table")),
       ", ggplot2 ", as.character(utils::packageVersion("ggplot2")))

dir.create(file.path(NG$deep_modules, "reports"), recursive = TRUE, showWarnings = FALSE)

safe_fread <- function(path) {
  if (!file.exists(path)) return(NULL)
  fread(path)
}

safe_read_dir <- function(path, file_name) {
  if (!file.exists(file.path(path, file_name))) return(NULL)
  fread(file.path(path, file_name))
}

export_summary <- safe_fread(file.path(NG$deep_modules, "heterograph_export_summary.tsv"))
vgae_summary <- safe_fread(file.path(NG$deep_modules, "vgae_run_summary.tsv"))
diffpool_summary <- safe_fread(file.path(NG$deep_modules, "diffpool_run_summary.tsv"))

files <- list.files(NG$deep_modules, recursive = TRUE, full.names = TRUE)
inventory <- data.table(
  file = sub(paste0("^", gsub("([.])", "\\\\\\1", BASE), "/"), "", files),
  bytes = file.info(files)$size
)
inventory <- inventory[order(-bytes)]
fwrite(inventory, file.path(NG$deep_modules, "deep_module_output_inventory.tsv"), sep = "\t")

primary_dirs <- ng_deep_dirs(NG_PARAMS$deep_module_primary_threshold, NG_PARAMS$deep_module_primary_method)
primary_export <- safe_fread(file.path(primary_dirs$tables, "heterograph_export_summary.tsv"))
primary_vgae <- safe_fread(file.path(primary_dirs$tables, "vgae_taxon_modules.tsv"))
primary_consensus <- safe_fread(file.path(primary_dirs$tables, "diffpool_consensus_modules.tsv"))

taxa_meta_primary <- safe_fread(file.path(
  ng_threshold_dirs(NG_PARAMS$deep_module_primary_threshold)$tables,
  "ngraph_taxa_metadata.tsv"
))

report <- file.path(NG$deep_modules, "reports", "NGRAPH_DEEP_MODULE_SUMMARY.md")
sink(report)
cat("# NGraph Deep Module Summary\n\n")
cat("- Generated: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), "\n", sep = "")
cat("- Seed: `", NG_PARAMS$seed, "`\n", sep = "")
cat("- Branch: `", NG$branch, "`\n", sep = "")
cat("- Primary threshold: `", ng_threshold_label(NG_PARAMS$deep_module_primary_threshold), "`\n", sep = "")
cat("- Primary method: `", NG_PARAMS$deep_module_primary_method, "`\n", sep = "")
cat("- Validation core: `", NG_PARAMS$deep_module_validation_core, "`\n\n", sep = "")

cat("## Export Coverage\n\n")
if (!is.null(export_summary)) {
  cat(ng_md_table(export_summary, max_rows = 24))
} else {
  cat("No heterograph exports found.\n\n")
}

cat("\n## VGAE Runs\n\n")
if (!is.null(vgae_summary)) {
  cat(ng_md_table(vgae_summary, max_rows = 24))
} else {
  cat("No VGAE summaries found yet.\n\n")
}

cat("\n## DiffPool Runs\n\n")
if (!is.null(diffpool_summary)) {
  cat(ng_md_table(diffpool_summary, max_rows = 24))
} else {
  cat("No DiffPool summaries found yet.\n\n")
}

cat("\n## Primary Module Snapshot\n\n")
if (!is.null(primary_vgae) && !is.null(taxa_meta_primary)) {
  primary_snapshot <- merge(primary_vgae, taxa_meta_primary, by = "taxon", all.x = TRUE, sort = FALSE)
  enrich_cols <- intersect(
    c("functional_group", "ecological_role", "tea_primary", "guild_tier", "kegg_state", "domain", "phylum", "class"),
    names(primary_snapshot)
  )
  for (col in enrich_cols) {
    freq <- primary_snapshot[, .N, by = c("module_kmeans", col)][order(module_kmeans, -N)]
    cat("### ", col, "\n\n", sep = "")
    cat(ng_md_table(freq, max_rows = 18))
    cat("\n")
  }
} else {
  cat("Primary VGAE module table is not yet available.\n\n")
}

cat("\n## Core Stability\n\n")
if (!is.null(primary_consensus)) {
  core_stability <- primary_consensus[, .(
    taxa = .N,
    mean_assignment_entropy = mean(mean_assignment_entropy, na.rm = TRUE),
    median_sites_present = median(sites_present, na.rm = TRUE)
  )]
  cat(ng_md_table(core_stability))
} else if (!is.null(primary_vgae)) {
  core_stability <- primary_vgae[, .(
    taxa = .N,
    mean_assignment_entropy = mean(assignment_entropy, na.rm = TRUE),
    mean_sites_present = mean(sites_present, na.rm = TRUE)
  )]
  cat(ng_md_table(core_stability))
} else {
  cat("No module assignments available yet.\n\n")
}

cat("\n## Method Agreement\n\n")
if (!is.null(primary_vgae) && !is.null(primary_consensus)) {
  agreed <- merge(
    primary_vgae[, .(taxon, vgae_module = module_kmeans)],
    primary_consensus[, .(taxon, diffpool_module = consensus_module)],
    by = "taxon",
    all = TRUE
  )
  agreed[, same_module := vgae_module == diffpool_module]
  agreement <- agreed[, .(
    taxa = sum(!is.na(vgae_module) & !is.na(diffpool_module)),
    same_module = sum(same_module, na.rm = TRUE),
    agreement_rate = mean(same_module, na.rm = TRUE)
  )]
  cat(ng_md_table(agreement))
} else {
  cat("No overlap between VGAE and DiffPool assignments yet.\n\n")
}

cat("\n## Output Inventory\n\n")
cat(ng_md_table(inventory, max_rows = 20))
sink()

plot_dt <- NULL
plot_kind <- NULL
if (!is.null(vgae_summary) && nrow(vgae_summary) > 0) {
  plot_dt <- rbind(
    vgae_summary[, .(threshold, method, metric = "VGAE held-out AUC", value = best_heldout_auc)],
    vgae_summary[, .(threshold, method, metric = "VGAE module k", value = module_k)]
  )
  if (!is.null(diffpool_summary) && nrow(diffpool_summary) > 0) {
    plot_dt <- rbind(
      plot_dt,
      diffpool_summary[, .(threshold, method, metric = "DiffPool best loss", value = best_loss)]
    )
  }
  plot_kind <- "model"
} else if (!is.null(export_summary) && nrow(export_summary) > 0) {
  plot_dt <- melt(
    export_summary,
    id.vars = c("threshold", "method"),
    measure.vars = c("taxon_nodes", "site_nodes", "taxon_taxon_edges", "site_site_edges", "taxon_site_edges"),
    variable.name = "metric",
    value.name = "value"
  )
  plot_kind <- "export"
}

if (!is.null(plot_dt) && nrow(plot_dt) > 0) {
  p <- ggplot(plot_dt, aes(x = method, y = value, fill = metric)) +
    geom_col(position = position_dodge(width = 0.75), width = 0.65) +
    facet_wrap(~ threshold, nrow = 1, scales = "free_y") +
    labs(
      title = if (identical(plot_kind, "model")) "Deep module model summary" else "Heterograph export inventory",
      x = "Method",
      y = "Value",
      fill = "Metric"
    ) +
    theme_minimal(base_size = 11) +
    theme(panel.grid.major.x = element_blank())
  ggsave(file.path(NG$deep_modules, "deep_module_summary.png"), p, width = 11, height = 4.5, dpi = 180)
  ng_log(LOG, "Method Validated: deep-module summary plot written")
}

ng_log(LOG, "Summary report written: ", report)
ng_log(LOG, "Complete")
