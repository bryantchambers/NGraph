#!/usr/bin/env Rscript
# 02c_permutation_test.R
# Test whether WGCNA modules survive sample-label permutation.
# If modules in permuted data resemble real data, they are driven by
# the stratigraphic (depth/taphonomy) trend, not biological co-occurrence.
#
# Output: results/main/permutation_test.tsv

suppressPackageStartupMessages({
  library(data.table)
  library(WGCNA)
})
source(file.path("code", "wgcna_hmm", "00_config.R"))
set.seed(PARAMS$seed)
enableWGCNAThreads(nThreads = PARAMS$wgcna_n_threads)

n_perm  <- as.integer(Sys.getenv("WGCNA_HMM_PERMUTATION_N", unset = "20"))
log_msg("Permutation test: ", n_perm, " permutations")

real_mat <- readRDS(file.path(DIRS$main, "rocs_tr_matrix.rds"))
meta_main <- fread(file.path(DIRS$main, "sample_metadata_main.tsv"))
train_ids <- meta_main[core %in% PARAMS$training_cores, label]
train_ids <- intersect(train_ids, rownames(real_mat))
real_expr <- real_mat[train_ids, , drop = FALSE]

# Soft power from real run
sp_path <- file.path(DIRS$main, "soft_power_summary.tsv")
soft_power <- if (file.exists(sp_path)) {
  sp <- fread(sp_path)
  as.integer(sp[1, Power])
} else PARAMS$wgcna_soft_power
log_msg("Soft power: ", soft_power)

# Real module count (non-grey)
real_mods_path <- file.path(DIRS$main, "module_sizes.tsv")
real_mods <- if (file.exists(real_mods_path)) fread(real_mods_path) else NULL
n_real_modules <- if (!is.null(real_mods)) nrow(real_mods[module != "grey"]) else NA_integer_
n_real_grey    <- if (!is.null(real_mods)) real_mods[module == "grey", n_taxa] else NA_integer_
log_msg("Real run: ", n_real_modules, " non-grey modules, grey=", n_real_grey)

run_wgcna_perm <- function(expr_perm) {
  net <- tryCatch(WGCNA::blockwiseModules(
    datExpr        = expr_perm,
    power          = soft_power,
    networkType    = "signed",
    corType        = PARAMS$cor_type,
    maxBlockSize   = 5000,
    minModuleSize  = PARAMS$wgcna_min_module_size,
    deepSplit      = PARAMS$wgcna_deep_split,
    mergeCutHeight = PARAMS$wgcna_merge_cut_height,
    pamStage       = TRUE,
    numericLabels  = FALSE,
    saveTOMs       = FALSE,
    verbose        = 0
  ), error = function(e) NULL)
  if (is.null(net)) return(NULL)
  colors <- net$colors
  tab <- table(colors)
  n_non_grey <- sum(names(tab) != "grey")
  n_grey     <- as.integer(tab["grey"])
  if (is.na(n_grey)) n_grey <- 0L
  list(n_modules = n_non_grey, n_grey = n_grey, n_taxa = length(colors))
}

results <- vector("list", n_perm)
for (i in seq_len(n_perm)) {
  set.seed(PARAMS$seed + i)
  perm_idx  <- sample(nrow(real_expr))
  perm_expr <- real_expr
  rownames(perm_expr) <- rownames(real_expr)[perm_idx]
  res <- run_wgcna_perm(perm_expr)
  if (is.null(res)) {
    log_msg(sprintf("  perm %02d: FAILED", i))
    next
  }
  results[[i]] <- data.table(perm = i, n_modules = res$n_modules,
                              n_grey = res$n_grey, n_taxa = res$n_taxa)
  log_msg(sprintf("  perm %02d: %d non-grey modules, grey=%d",
                  i, res$n_modules, res$n_grey))
}

perm_dt <- rbindlist(results[!sapply(results, is.null)])
perm_dt[, pct_grey := 100 * n_grey / n_taxa]

summary_dt <- data.table(
  metric = c(
    "n_permutations_run",
    "real_n_modules", "real_n_grey",
    "perm_mean_modules", "perm_sd_modules",
    "perm_mean_grey",    "perm_sd_grey",
    "perm_mean_pct_grey","perm_sd_pct_grey",
    "conclusion"
  ),
  value = c(
    nrow(perm_dt),
    n_real_modules, n_real_grey,
    round(mean(perm_dt$n_modules), 2), round(sd(perm_dt$n_modules), 2),
    round(mean(perm_dt$n_grey), 2),    round(sd(perm_dt$n_grey), 2),
    round(mean(perm_dt$pct_grey), 2),  round(sd(perm_dt$pct_grey), 2),
    ifelse(mean(perm_dt$n_modules) >= n_real_modules * 0.7,
           "WARN: permuted modules approach real — possible taphonomic confound",
           "OK: real modules exceed permuted — signal is biological")
  )
)

fwrite(perm_dt,     file.path(DIRS$main, "permutation_test_detail.tsv"),  sep = "\t")
fwrite(summary_dt,  file.path(DIRS$main, "permutation_test_summary.tsv"), sep = "\t")
log_msg("Permutation test done.")
cat("\n=== PERMUTATION TEST SUMMARY ===\n")
print(summary_dt)
