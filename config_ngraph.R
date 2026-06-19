#!/usr/bin/env Rscript
# config_ngraph.R -- shared paths and parameters for the NGraph workflow.
#
# Source from NGraph scripts with: source("config_ngraph.R")

BASE <- normalizePath(getwd(), mustWork = TRUE)

NG_BRANCH <- Sys.getenv("NG_BRANCH", "abundance_thresholding")

ROCS <- list(
  base = file.path(BASE, "Source", "ROCS"),
  stage1 = file.path(BASE, "Source", "ROCS", "results", "stage1"),
  stage1_wgcna = file.path(BASE, "Source", "ROCS", "results", "stage1", "wgcna"),
  tax_damage = file.path(BASE, "Source", "ROCS", "results", "microbial", "damage",
                         "damage-classification-depositional",
                         "dmg-summary-ssp-damage-classification-depositional.tsv.gz"),
  metadata = file.path(BASE, "Source", "ROCS", "data", "metadata_v5.tsv"),
  prokaryote_function = file.path(BASE, "Source", "ROCS", "results", "common", "wgcna",
                                  "classification", "prokaryote_function_assigned.tsv")
)

NG_DATA <- list(
  raw = file.path(BASE, "data", "raw"),
  metadata = file.path(BASE, "data", "metadata"),
  reference = file.path(BASE, "data", "reference"),
  provenance = file.path(BASE, "data", "provenance"),
  tax_damage = file.path(BASE, "data", "raw", "dmg-summary-ssp-damage-classification-depositional.tsv.gz"),
  metadata_file = file.path(BASE, "data", "metadata", "metadata_v5.tsv"),
  prokaryote_function = file.path(BASE, "data", "reference", "prokaryote_function_assigned.tsv")
)

NG <- list(
  branch = NG_BRANCH,
  results = file.path(BASE, "results", "ngraph", NG_BRANCH),
  deep_modules = file.path(BASE, "results", "ngraph", NG_BRANCH, "deep_modules"),
  deep_knowledge = file.path(BASE, "results", "ngraph", NG_BRANCH, "deep_knowledge_discovery"),
  matrices = file.path(BASE, "results", "ngraph", NG_BRANCH, "matrices"),
  tables = file.path(BASE, "results", "ngraph", NG_BRANCH, "tables"),
  figures = file.path(BASE, "results", "ngraph", NG_BRANCH, "figures"),
  graphs = file.path(BASE, "results", "ngraph", NG_BRANCH, "graphs"),
  reports = file.path(BASE, "results", "ngraph", NG_BRANCH, "reports"),
  logs = file.path(BASE, "logs")
)

for (d in c(
  NG,
  NG_DATA[c("raw", "metadata", "reference", "provenance")]
)) {
  dir.create(d, recursive = TRUE, showWarnings = FALSE)
}

NG_PARAMS <- list(
  seed = 42L,
  max_age_kyr = 150,
  all_cores = c("ST8", "ST13", "GeoB25202_R1", "GeoB25202_R2"),
  training_cores = c("ST8", "ST13", "GeoB25202_R1"),
  validation_core = "GeoB25202_R2",
  excluded_samples = c("LV3003046968"),
  abundance_column = "tax_abund_tad",
  raw_read_column = "n_reads",
  clr_pseudocount = 0.5,
  prevalence_thresholds = c(3L, 5L, 10L),
  site_graph_methods = c("pearson", "bicor", "spearman", "mi_aracne"),
  deep_module_methods = c("pearson", "bicor", "spearman", "mi_aracne"),
  deep_module_primary_threshold = 5L,
  deep_module_primary_method = "pearson",
  deep_module_validation_core = "GeoB25202_R2",
  deep_knowledge_methods = c("pearson", "bicor", "spearman", "mi_aracne"),
  deep_knowledge_primary_threshold = 5L,
  deep_knowledge_primary_method = "pearson",
  deep_knowledge_validation_core = "GeoB25202_R2",
  deep_knowledge_top_n = 100L,
  retrieval_top_k = 20L,
  query_batch_size = 10L,
  graph_min_samples = 8L,
  graph_top_variable_taxa = 500L,
  cor_abs_threshold = 0.55,
  bicor_max_p_outliers = 1,
  minet_estimator = "spearman",
  aracne_eps = 0,
  spectral_k = 30L
)

ng_threshold_label <- function(threshold) {
  paste0("prev_", as.integer(threshold))
}

ng_threshold_dirs <- function(threshold) {
  label <- ng_threshold_label(threshold)
  dirs <- list(
    label = label,
    root = file.path(NG$results, label),
    matrices = file.path(NG$results, label, "matrices"),
    tables = file.path(NG$results, label, "tables"),
    figures = file.path(NG$results, label, "figures"),
    graphs = file.path(NG$results, label, "graphs"),
    reports = file.path(NG$results, label, "reports")
  )
  for (d in dirs[setdiff(names(dirs), "label")]) {
    dir.create(d, recursive = TRUE, showWarnings = FALSE)
  }
  dirs
}

ng_knowledge_dirs <- function(threshold, method) {
  label <- ng_threshold_label(threshold)
  dirs <- list(
    threshold = label,
    method = method,
    root = file.path(NG$deep_knowledge, label, method),
    tables = file.path(NG$deep_knowledge, label, method, "tables"),
    figures = file.path(NG$deep_knowledge, label, method, "figures"),
    reports = file.path(NG$deep_knowledge, label, method, "reports"),
    indexes = file.path(NG$deep_knowledge, label, method, "indexes"),
    models = file.path(NG$deep_knowledge, label, method, "models"),
    logs = file.path(NG$deep_knowledge, label, method, "logs")
  )
  for (d in dirs[c("root", "tables", "figures", "reports", "indexes", "models", "logs")]) {
    dir.create(d, recursive = TRUE, showWarnings = FALSE)
  }
  dirs
}

ng_deep_dirs <- function(threshold, method) {
  label <- ng_threshold_label(threshold)
  dirs <- list(
    threshold = label,
    method = method,
    root = file.path(NG$deep_modules, label, method),
    tables = file.path(NG$deep_modules, label, method, "tables"),
    figures = file.path(NG$deep_modules, label, method, "figures"),
    reports = file.path(NG$deep_modules, label, method, "reports"),
    models = file.path(NG$deep_modules, label, method, "models"),
    logs = file.path(NG$deep_modules, label, method, "logs")
  )
  for (d in dirs[c("root", "tables", "figures", "reports", "models", "logs")]) {
    dir.create(d, recursive = TRUE, showWarnings = FALSE)
  }
  dirs
}

ng_log_path <- function(step_name) {
  file.path(NG$logs, paste0(step_name, ".log"))
}

ng_start_log <- function(log_file) {
  dir.create(dirname(log_file), recursive = TRUE, showWarnings = FALSE)
  if (file.exists(log_file)) {
    unlink(log_file)
  }
}

ng_log <- function(log_file, ...) {
  line <- sprintf("[%s] %s", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), paste0(...))
  cat(line, "\n", file = log_file, append = TRUE)
  message(line)
}

ng_require <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    stop("Missing required R package: ", pkg, ". Update the ngraph Mamba environment; do not install from scripts.")
  }
}

ng_safe_cor <- function(x, y, method = "pearson") {
  x <- as.numeric(x)
  y <- as.numeric(y)
  ok <- is.finite(x) & is.finite(y)
  if (sum(ok) < 3) {
    return(NA_real_)
  }
  suppressWarnings(cor(x[ok], y[ok], method = method))
}

ng_md_table <- function(dt, max_rows = 30L) {
  if (nrow(dt) == 0) {
    return("No rows.\n")
  }
  dt <- as.data.frame(head(dt, max_rows))
  out <- c(
    paste0("|", paste(names(dt), collapse = "|"), "|"),
    paste0("|", paste(rep("---", ncol(dt)), collapse = "|"), "|")
  )
  for (i in seq_len(nrow(dt))) {
    vals <- vapply(dt[i, ], function(x) {
      if (is.numeric(x)) {
        ifelse(is.na(x), "NA", format(signif(x, 4), scientific = FALSE))
      } else {
        gsub("\\|", "/", as.character(x))
      }
    }, character(1))
    out <- c(out, paste0("|", paste(vals, collapse = "|"), "|"))
  }
  paste0(paste(out, collapse = "\n"), "\n")
}
