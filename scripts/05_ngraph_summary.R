#!/usr/bin/env Rscript
# 05_ngraph_summary.R -- compact inventory and milestone summary for NGraph.

suppressPackageStartupMessages({
  library(data.table)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("05_ngraph_summary")
ng_start_log(LOG)
ng_log(LOG, "Writing NGraph summary")

safe_fread <- function(path) {
  if (!file.exists(path)) return(NULL)
  fread(path)
}

matrix_summary <- safe_fread(file.path(NG$tables, "ngraph_matrix_summary.tsv"))
core_summary <- safe_fread(file.path(NG$tables, "ngraph_core_matrix_summary.tsv"))
top_pc <- safe_fread(file.path(NG$tables, "ngraph_input_pc_top_associations.tsv"))
site_graphs <- safe_fread(file.path(NG$tables, "ngraph_site_graph_summary.tsv"))
similarity <- safe_fread(file.path(NG$tables, "ngraph_graph_similarity.tsv"))

files <- list.files(NG$results, recursive = TRUE, full.names = TRUE)
inventory <- data.table(
  file = sub(paste0("^", gsub("([.])", "\\\\\\1", BASE), "/"), "", files),
  bytes = file.info(files)$size
)
inventory <- inventory[order(-bytes)]
fwrite(inventory, file.path(NG$tables, "ngraph_output_inventory.tsv"), sep = "\t")

report <- file.path(BASE, "NGRAPH_SUMMARY.md")
sink(report)
cat("# NGraph Workflow Summary\n\n")
cat("- Generated: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), "\n", sep = "")
cat("- Seed: `", NG_PARAMS$seed, "`\n", sep = "")
cat("- Source data: `Source/ROCS/results/stage1`\n")
cat("- New outputs: `results/ngraph`\n\n")

cat("## CLR Matrices\n\n")
if (!is.null(matrix_summary)) cat(ng_md_table(matrix_summary))
if (!is.null(core_summary)) cat("\n", ng_md_table(core_summary), sep = "")

cat("\n## Input QC\n\n")
if (!is.null(top_pc)) {
  cat("Top PC/covariate associations:\n\n")
  cat(ng_md_table(top_pc[, .(PC, covariate, covariate_class, pearson_r, spearman_rho)], max_rows = 12))
}

cat("\n## Site Graphs\n\n")
if (!is.null(site_graphs)) cat(ng_md_table(site_graphs))

cat("\n## Graph-of-Graphs\n\n")
if (!is.null(similarity)) {
  cat(ng_md_table(similarity))
  if ("method" %in% names(similarity)) {
    cat("\nMean graph-of-graphs similarity by method:\n\n")
    cat(ng_md_table(similarity[, .(
      mean_edge_jaccard = mean(edge_jaccard, na.rm = TRUE),
      mean_spectral_similarity = mean(spectral_similarity, na.rm = TRUE),
      mean_super_weight = mean(super_weight, na.rm = TRUE)
    ), by = method]))
  }
}

cat("\n## Output Inventory\n\n")
cat(ng_md_table(inventory, max_rows = 20))
sink()

ng_log(LOG, "Summary written: ", report)
ng_log(LOG, "Complete")
