#!/usr/bin/env Rscript
# config_ngraph.R -- shared paths and parameters for the NGraph workflow.
#
# Source from NGraph scripts with: source("config_ngraph.R")

BASE <- normalizePath(getwd(), mustWork = TRUE)

ROCS <- list(
  base = file.path(BASE, "Source", "ROCS"),
  stage1 = file.path(BASE, "Source", "ROCS", "results", "stage1"),
  stage1_wgcna = file.path(BASE, "Source", "ROCS", "results", "stage1", "wgcna")
)

NG <- list(
  results = file.path(BASE, "results", "ngraph"),
  matrices = file.path(BASE, "results", "ngraph", "matrices"),
  tables = file.path(BASE, "results", "ngraph", "tables"),
  figures = file.path(BASE, "results", "ngraph", "figures"),
  graphs = file.path(BASE, "results", "ngraph", "graphs"),
  reports = file.path(BASE, "results", "ngraph", "reports"),
  logs = file.path(BASE, "logs")
)

for (d in NG) {
  dir.create(d, recursive = TRUE, showWarnings = FALSE)
}

NG_PARAMS <- list(
  seed = 42L,
  max_age_kyr = 150,
  all_cores = c("ST8", "ST13", "GeoB25202_R1", "GeoB25202_R2"),
  training_cores = c("ST8", "ST13", "GeoB25202_R1"),
  validation_core = "GeoB25202_R2",
  clr_pseudocount = 0.5,
  prevalence_min_samples = 10L,
  graph_min_samples = 8L,
  graph_top_variable_taxa = 500L,
  spearman_abs_threshold = 0.55,
  minet_estimator = "spearman",
  aracne_eps = 0,
  spectral_k = 30L
)

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
