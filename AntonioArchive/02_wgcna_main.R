#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(data.table)
  library(WGCNA)
  library(tidyverse)
  library(furrr)
})
source(file.path("code", "wgcna_hmm", "00_config.R"))
set.seed(PARAMS$seed)
allowWGCNAThreads(PARAMS$wgcna_n_threads)
options(stringsAsFactors = FALSE)

args <- commandArgs(trailingOnly = TRUE)
run_mode <- PARAMS$wgcna_run_mode
if (length(args) > 0) {
  mode_arg <- sub("^--mode=", "", args[grep("^--mode=", args)][1])
  if (!is.na(mode_arg) && nzchar(mode_arg)) run_mode <- mode_arg
}
if (!run_mode %in% c("build", "final")) {
  stop("Invalid WGCNA mode: ", run_mode, ". Use --mode=build or --mode=final.")
}
preservation_perms <- if (run_mode == "final") {
  PARAMS$wgcna_preservation_permutations_final
} else {
  PARAMS$wgcna_preservation_permutations_build
}
log_msg(sprintf("WGCNA mode: %s; preservation permutations: %d", run_mode, preservation_perms))

rocs_tr_mat_full <- readRDS(file.path(DIRS$main, "rocs_tr_matrix.rds"))
meta_main <- fread(file.path(DIRS$main, "sample_metadata_main.tsv"))
main_ids <- intersect(meta_main$label, rownames(rocs_tr_mat_full))
rocs_tr_mat_full <- rocs_tr_mat_full[main_ids, , drop = FALSE]
prev_ok <- colSums(rocs_tr_mat_full != 0) >= PARAMS$prevalence_min_samples
rocs_tr_mat <- rocs_tr_mat_full[, prev_ok, drop = FALSE]
log_msg(sprintf("Main-window input: %d samples x %d taxa (prevalence >= %d within main window)",
                nrow(rocs_tr_mat), ncol(rocs_tr_mat), PARAMS$prevalence_min_samples))

expr_by_core <- lapply(PARAMS$all_cores, function(core_id) {
  ids <- meta_main[core == core_id, label]
  ids <- intersect(ids, rownames(rocs_tr_mat))
  rocs_tr_mat[ids, , drop = FALSE]
})
names(expr_by_core) <- PARAMS$all_cores

train_expr <- do.call(rbind, lapply(PARAMS$training_cores, function(c) expr_by_core[[c]]))

powers <- c(1:10, seq(12, 20, by = 2))
sft_dt <- {
  sft <- pickSoftThreshold(train_expr, powerVector = powers, networkType = "signed", verbose = 0)
  dt <- as.data.table(sft$fitIndices)
  dt[, core := "joint_calib"]
  dt
}
sft_dt[, signedR2 := ifelse(slope < 0, SFT.R.sq, 0)]

scale01 <- function(x) {
  rng <- range(x, na.rm = TRUE)
  if (!all(is.finite(rng)) || diff(rng) == 0) {
    return(rep(0.5, length(x)))
  }
  (x - rng[1]) / diff(rng)
}
sft_power_summary <- sft_dt[, .(
  median_signedR2 = signedR2,
  min_signedR2 = signedR2,
  median_mean_k = mean.k.,
  min_mean_k = mean.k.,
  median_slope = slope
), by = Power][order(Power)]
# Scale-free R² unreliable at n=159 taxa; weight connectivity (mean_k 5-15) over fit.
# Require negative slope (signed scale-free) and mean_k >= 4 to avoid degenerate low-power solutions.
sft_power_summary[, fit_score := 0.6 * scale01(median_signedR2) + 0.4 * scale01(min_signedR2)]
sft_power_summary[, connectivity_score := 0.7 * scale01(log1p(median_mean_k)) + 0.3 * scale01(log1p(min_mean_k))]
sft_power_summary[, simplicity_score := 1 - scale01(Power)]
sft_power_summary[, balance_score := 0.35 * fit_score + 0.50 * connectivity_score + 0.15 * simplicity_score]
soft_power <- sft_power_summary[median_slope < 0 & median_mean_k >= 4][which.max(balance_score), Power]
if (length(soft_power) == 0 || is.na(soft_power)) soft_power <- 8L
soft_power_selection <- "dynamic_balance_connectivity_fit_simplicity_joint"
if (!is.na(PARAMS$wgcna_soft_power) && PARAMS$wgcna_soft_power > 0L) {
  soft_power <- as.integer(PARAMS$wgcna_soft_power)
  soft_power_selection <- "manual_config"
}
log_msg(sprintf("WGCNA soft power: %d (%s)", soft_power, soft_power_selection))

multiExpr <- lapply(PARAMS$training_cores, function(core_id) list(data = expr_by_core[[core_id]]))
names(multiExpr) <- PARAMS$training_cores

if (identical(PARAMS$module_method, "consensus")) {
  sft_per_core <- rbindlist(lapply(PARAMS$training_cores, function(core_id) {
    s <- pickSoftThreshold(expr_by_core[[core_id]], powerVector = powers,
                           networkType = "signed", verbose = 0)
    dt <- as.data.table(s$fitIndices)
    dt[, core := core_id]
    dt[, signedR2 := ifelse(slope < 0, SFT.R.sq, 0)]
    dt
  }))
  passing_cores <- sft_per_core[signedR2 >= 0.80, .(min_pass = min(Power)), by = core]
  if (nrow(passing_cores) == length(PARAMS$training_cores)) {
    soft_power <- max(passing_cores$min_pass)
    soft_power_selection <- "per_core_consensus_max"
  }
  sft_dt <- sft_per_core
  log_msg(sprintf("Consensus per-core soft power: %d (%s)", soft_power, soft_power_selection))
}

if (identical(PARAMS$module_method, "wgcna")) {
  net <- WGCNA::blockwiseModules(
    datExpr = train_expr,
    power = soft_power,
    networkType = "signed",
    corType = PARAMS$cor_type,
    maxBlockSize = 5000,
    minModuleSize = PARAMS$wgcna_min_module_size,
    deepSplit = PARAMS$wgcna_deep_split,
    mergeCutHeight = PARAMS$wgcna_merge_cut_height,
    pamStage = TRUE,
    pamRespectsDendro = PARAMS$wgcna_pam_respects_dendro,
    numericLabels = FALSE,
    saveTOMs = FALSE,
    verbose = 2
  )
  module_colors <- net$colors
  leiden_backend <- NA_character_
} else if (identical(PARAMS$module_method, "consensus")) {
  net <- blockwiseConsensusModules(
    multiExpr          = multiExpr,
    power              = soft_power,
    networkType        = "signed",
    corType            = "pearson",
    maxBlockSize       = 5000,
    minModuleSize      = PARAMS$wgcna_min_module_size,
    deepSplit          = PARAMS$wgcna_deep_split,
    mergeCutHeight     = PARAMS$wgcna_merge_cut_height,
    pamStage           = TRUE,
    pamRespectsDendro  = PARAMS$wgcna_pam_respects_dendro,
    numericLabels      = FALSE,
    saveTOMs           = FALSE,
    verbose            = 2
  )
  module_colors  <- net$colors
  leiden_backend <- NA_character_
} else if (identical(PARAMS$module_method, "leiden")) {
  if (!requireNamespace("igraph", quietly = TRUE)) {
    stop("Leiden module method requested but igraph is not installed in this R environment.")
  }
  if (!("cluster_leiden" %in% getNamespaceExports("igraph"))) {
    stop("Leiden module method requested but igraph::cluster_leiden is unavailable in this R environment.")
  }

  # Build a WGCNA consensus network from the same training-core expressions,
  # then run Leiden only for module partitioning of that consensus graph.
  cons <- consensusDissTOMandTree(multiExpr = multiExpr, softPower = soft_power)
  consensus_matrix <- cons$consensusTOM
  if (is.null(consensus_matrix)) {
    stop("WGCNA consensusDissTOMandTree did not return consensusTOM; cannot run Leiden on consensus network.")
  }
  consensus_matrix[!is.finite(consensus_matrix)] <- 0
  consensus_matrix <- (consensus_matrix + t(consensus_matrix)) / 2
  diag(consensus_matrix) <- 0

  matrix_mode <- PARAMS$leiden_consensus_matrix_interpretation
  if (identical(matrix_mode, "auto")) {
    med_val <- stats::median(consensus_matrix[upper.tri(consensus_matrix)], na.rm = TRUE)
    matrix_mode <- if (is.finite(med_val) && med_val > 0.5) "dissimilarity" else "similarity"
  }
  if (identical(matrix_mode, "dissimilarity")) {
    consensus_sim <- 1 - consensus_matrix
  } else if (identical(matrix_mode, "similarity")) {
    consensus_sim <- consensus_matrix
  } else {
    stop("Unsupported consensus matrix interpretation: ", matrix_mode)
  }
  consensus_sim[!is.finite(consensus_sim)] <- 0
  consensus_sim[consensus_sim < 0] <- 0
  consensus_sim[consensus_sim > 1] <- 1
  diag(consensus_sim) <- 0

  # Build a sparse graph from consensus TOM to avoid complete-graph collapse in modularity optimization.
  k_neighbors <- min(as.integer(PARAMS$leiden_graph_k_neighbors), ncol(consensus_sim) - 1L)
  sparse_adj <- matrix(0, nrow = nrow(consensus_sim), ncol = ncol(consensus_sim),
                       dimnames = dimnames(consensus_sim))
  for (i in seq_len(nrow(consensus_sim))) {
    ord <- order(consensus_sim[i, ], decreasing = TRUE)
    ord <- ord[ord != i]
    keep <- ord[seq_len(k_neighbors)]
    sparse_adj[i, keep] <- consensus_sim[i, keep]
  }
  # Symmetrize either by union-kNN (max weight) or true mutual-kNN (intersection of retained neighbors).
  graph_sym <- PARAMS$leiden_graph_symmetrization
  if (identical(graph_sym, "union")) {
    sparse_adj <- pmax(sparse_adj, t(sparse_adj))
  } else if (identical(graph_sym, "mutual")) {
    sparse_adj <- ifelse((sparse_adj > 0) & (t(sparse_adj) > 0), consensus_sim, 0)
  } else {
    stop("Unsupported Leiden graph symmetrization: ", graph_sym)
  }
  diag(sparse_adj) <- 0

  g <- igraph::graph_from_adjacency_matrix(sparse_adj, mode = "undirected", weighted = TRUE, diag = FALSE)

  leiden_formals <- names(formals(igraph::cluster_leiden))
  run_leiden <- function(resolution_value) {
    leiden_args <- list(graph = g, weights = igraph::E(g)$weight)
    if ("objective_function" %in% leiden_formals) leiden_args$objective_function <- "modularity"
    if ("resolution" %in% leiden_formals) {
      leiden_args$resolution <- resolution_value
    } else if ("resolution_parameter" %in% leiden_formals) {
      leiden_args$resolution_parameter <- resolution_value
    }
    if ("n_iterations" %in% leiden_formals) leiden_args$n_iterations <- 100

    cl <- do.call(igraph::cluster_leiden, leiden_args)
    memb <- igraph::membership(cl)
    memb_tab <- as.data.table(table(memb))
    setnames(memb_tab, c("community", "n_taxa"))
    memb_tab[, community := as.character(community)]
    kept <- memb_tab[n_taxa >= PARAMS$wgcna_min_module_size, community]
    list(membership = memb, membership_table = memb_tab, kept_communities = kept)
  }

  requested_resolution <- PARAMS$leiden_resolution
  chosen_resolution <- requested_resolution
  auto_adjusted <- FALSE

  if (!isTRUE(PARAMS$leiden_resolution_strict)) {
    resolution_candidates <- unique(c(
      requested_resolution,
      requested_resolution * 1.5,
      requested_resolution * 2,
      requested_resolution * 3
    ))
    leiden_trials <- lapply(resolution_candidates, run_leiden)
    n_non_grey_by_trial <- vapply(leiden_trials, function(x) length(x$kept_communities), integer(1))

    chosen_idx <- which(n_non_grey_by_trial >= 3)[1]
    if (is.na(chosen_idx)) chosen_idx <- which.max(n_non_grey_by_trial)

    chosen_resolution <- resolution_candidates[chosen_idx]
    chosen <- leiden_trials[[chosen_idx]]
    auto_adjusted <- !identical(chosen_resolution, requested_resolution)
  } else {
    chosen <- run_leiden(requested_resolution)
    n_non_grey_by_trial <- integer(0)
    resolution_candidates <- numeric(0)
  }

  memb <- chosen$membership
  memb_tab <- chosen$membership_table
  kept_communities <- chosen$kept_communities
  small_communities <- setdiff(memb_tab$community, kept_communities)

  if (auto_adjusted) {
    log_msg(
      "Leiden resolution adjusted from ", requested_resolution,
      " to ", chosen_resolution,
      " to satisfy downstream minimum module count (>=3 non-grey modules)."
    )
  }

  module_labels <- rep("grey", length(memb))
  names(module_labels) <- names(memb)
  if (length(kept_communities) > 0) {
    kept_idx <- match(as.character(memb), kept_communities)
    module_labels[!is.na(kept_idx)] <- paste0("leiden", kept_idx[!is.na(kept_idx)])
  }

  merge_threshold <- PARAMS$leiden_merge_eigengene_cor
  merge_applied <- FALSE
  merge_n_steps <- 0L
  if (is.finite(merge_threshold)) {
    if (merge_threshold <= 0 || merge_threshold > 1) {
      stop("WGCNA_HMM_LEIDEN_MERGE_EIGENGENE_COR must be in (0, 1].")
    }
    repeat {
      non_grey_modules <- sort(unique(module_labels[module_labels != "grey"]))
      if (length(non_grey_modules) < 2) break

      MEs_tmp <- moduleEigengenes(train_expr, module_labels)$eigengenes
      if (ncol(MEs_tmp) < 2) break

      me_cor <- suppressWarnings(cor(MEs_tmp, use = "pairwise.complete.obs"))
      diag(me_cor) <- NA_real_
      max_cor <- suppressWarnings(max(me_cor, na.rm = TRUE))
      if (!is.finite(max_cor) || max_cor < merge_threshold) break

      idx <- which(me_cor == max_cor, arr.ind = TRUE)[1, ]
      me_i <- colnames(me_cor)[idx[1]]
      me_j <- colnames(me_cor)[idx[2]]
      mod_i <- sub("^ME", "", me_i)
      mod_j <- sub("^ME", "", me_j)
      if (!identical(mod_i, mod_j)) {
        module_labels[module_labels == mod_j] <- mod_i
        merge_applied <- TRUE
        merge_n_steps <- merge_n_steps + 1L
      }
      if (merge_n_steps >= as.integer(PARAMS$leiden_merge_max_iter)) {
        warning("Reached WGCNA_HMM_LEIDEN_MERGE_MAX_ITER; stopping module merge loop.")
        break
      }
    }

    post_merge_tab <- as.data.table(table(module_labels))
    setnames(post_merge_tab, c("module", "n_taxa"))
    kept_after_merge <- post_merge_tab[module != "grey" & n_taxa >= PARAMS$wgcna_min_module_size, module]
    module_labels[!(module_labels %in% c("grey", kept_after_merge))] <- "grey"
  }

  module_colors <- module_labels[colnames(train_expr)]
  names(module_colors) <- colnames(train_expr)

  net <- list(
    method = "leiden",
    backend = "igraph::cluster_leiden",
    soft_power = soft_power,
    resolution_parameter_requested = requested_resolution,
    resolution_parameter_used = chosen_resolution,
    resolution_strict = PARAMS$leiden_resolution_strict,
    resolution_auto_adjusted = auto_adjusted,
    min_module_size = PARAMS$wgcna_min_module_size,
    network_type = "wgcna_consensus_tom",
    consensus_network_constructor = "WGCNA::consensusDissTOMandTree",
    leiden_graph_representation = sprintf("%s kNN sparse graph from interpreted consensus matrix (k=%d)", graph_sym, k_neighbors),
    leiden_consensus_matrix_interpretation = matrix_mode,
    leiden_graph_k_neighbors = k_neighbors,
    leiden_graph_symmetrization = graph_sym,
    leiden_merge_eigengene_cor = if (is.finite(merge_threshold)) merge_threshold else NA_real_,
    leiden_merge_applied = merge_applied,
    leiden_merge_n_steps = merge_n_steps,
    consensus_tree = cons$consTree,
    communities_raw = memb,
    module_labels = module_colors,
    n_communities_raw = uniqueN(memb),
    n_modules_non_grey = uniqueN(module_colors[module_colors != "grey"]),
    n_modules_non_grey_by_resolution_trial = as.list(stats::setNames(n_non_grey_by_trial, as.character(resolution_candidates))),
    graph_weight_summary = list(
      n_taxa = ncol(train_expr),
      edge_weight_min = min(sparse_adj[upper.tri(sparse_adj)][sparse_adj[upper.tri(sparse_adj)] > 0], na.rm = TRUE),
      edge_weight_median = stats::median(sparse_adj[upper.tri(sparse_adj)][sparse_adj[upper.tri(sparse_adj)] > 0], na.rm = TRUE),
      edge_weight_max = max(sparse_adj[upper.tri(sparse_adj)], na.rm = TRUE),
      graph_edges_nonzero = sum(sparse_adj[upper.tri(sparse_adj)] > 0)
    )
  )
  leiden_backend <- "igraph::cluster_leiden"
} else if (identical(PARAMS$module_method, "propr")) {
  # Proportionality ρ as WGCNA similarity — fully library-size independent.
  # train_expr: samples × taxa (log_only transform, per-taxon floored).
  log_mat <- t(train_expr)  # taxa × samples

  rho_mat <- compute_propr_rho(log_mat)
  # Shift ρ ∈ [-1,1] → [0,1]; pmax() strips matrix class so clamp in-place
  sim_mat <- (1 + rho_mat) / 2
  sim_mat[sim_mat < 0] <- 0
  diag(sim_mat) <- 1

  # Re-run soft power selection on the ρ similarity matrix
  if (requireNamespace("WGCNA", quietly = TRUE) &&
      "pickSoftThresholdFromSimilarity" %in% getNamespaceExports("WGCNA")) {
    sft_rho <- WGCNA::pickSoftThresholdFromSimilarity(
      similarity    = sim_mat,
      powerVector   = powers,
      networkType   = "unsigned",
      verbose       = 0
    )
    sft_dt_rho <- as.data.table(sft_rho$fitIndices)
    sft_dt_rho[, signedR2 := ifelse(slope < 0, SFT.R.sq, 0)]
    bal_rho <- sft_dt_rho[, .(
      Power    = Power,
      bal_score = signedR2 - 0.1 * connectivity.truncated.mean
    )]
    propr_soft_power <- bal_rho[which.max(bal_score), Power]
    if (bal_rho[Power == propr_soft_power, signedR2] >= 0.80) {
      passing <- sft_dt_rho[signedR2 >= 0.80][which.min(Power), Power]
      propr_soft_power <- passing
    }
    soft_power <- as.integer(propr_soft_power)
    soft_power_selection <- "propr_rho_balance_score"
    log_msg(sprintf("Propr soft power (ρ similarity): %d (%s)", soft_power, soft_power_selection))
    fwrite(sft_dt_rho, file.path(DIRS$main, "soft_threshold_propr_rho.tsv"), sep = "\t")
  } else {
    log_msg("pickSoftThresholdFromSimilarity unavailable; using precomputed soft_power=", soft_power)
  }

  adj_mat  <- WGCNA::adjacency.fromSimilarity(sim_mat, power = soft_power, type = "unsigned")
  tom      <- WGCNA::TOMsimilarity(adj_mat, TOMType = "unsigned", verbose = 0)
  dissTOM  <- 1 - tom
  colnames(dissTOM) <- rownames(dissTOM) <- colnames(train_expr)
  geneTree <- hclust(as.dist(dissTOM), method = "average")

  dynamicMods <- dynamicTreeCut::cutreeDynamic(
    dendro      = geneTree,
    distM       = dissTOM,
    deepSplit   = PARAMS$wgcna_deep_split,
    minClusterSize = PARAMS$wgcna_min_module_size,
    method      = "hybrid",
    verbose     = 0
  )
  module_colors_raw <- WGCNA::labels2colors(dynamicMods)
  names(module_colors_raw) <- colnames(train_expr)

  merged <- WGCNA::mergeCloseModules(
    train_expr,
    module_colors_raw,
    cutHeight = PARAMS$wgcna_merge_cut_height,
    verbose   = 0
  )
  module_colors <- merged$colors
  names(module_colors) <- colnames(train_expr)

  net <- list(
    method          = "propr",
    soft_power      = soft_power,
    n_taxa          = ncol(train_expr),
    rho_range       = range(rho_mat[upper.tri(rho_mat)]),
    sim_range       = range(sim_mat[upper.tri(sim_mat)])
  )
  leiden_backend <- NA_character_
} else {
  stop("Unsupported module method in PARAMS$module_method: ", PARAMS$module_method)
}
MEs_train <- moduleEigengenes(train_expr, module_colors)$eigengenes
MEs_train <- orderMEs(MEs_train)

project_to_training_basis <- function(expr_train, expr_new, module_colors, me_train_df) {
  modules <- sort(unique(module_colors))
  valid_scores <- vector("list", length(modules))
  names(valid_scores) <- paste0("ME", modules)
  basis_rows <- vector("list", length(modules))
  for (i in seq_along(modules)) {
    mod <- modules[i]
    me_name <- paste0("ME", mod)
    genes <- names(module_colors)[module_colors == mod]
    x_train <- as.matrix(expr_train[, genes, drop = FALSE])
    x_new <- as.matrix(expr_new[, genes, drop = FALSE])

    mu <- colMeans(x_train, na.rm = TRUE)
    sdv <- apply(x_train, 2, sd, na.rm = TRUE)
    sdv[is.na(sdv) | sdv == 0] <- 1

    z_train <- sweep(sweep(x_train, 2, mu, "-"), 2, sdv, "/")
    z_new <- sweep(sweep(x_new, 2, mu, "-"), 2, sdv, "/")

    if (ncol(z_train) == 1) {
      train_pc1 <- as.numeric(z_train[, 1])
      new_pc1 <- as.numeric(z_new[, 1])
      var_expl <- 1
    } else {
      pca_mod <- prcomp(z_train, center = FALSE, scale. = FALSE)
      load1 <- pca_mod$rotation[, 1]
      train_pc1 <- as.numeric(z_train %*% load1)
      new_pc1 <- as.numeric(z_new %*% load1)
      var_expl <- summary(pca_mod)$importance[2, 1]
    }

    sign_cor <- suppressWarnings(cor(train_pc1, me_train_df[[me_name]], use = "pairwise.complete.obs"))
    sign_flip <- is.finite(sign_cor) && sign_cor < 0
    if (sign_flip) new_pc1 <- -new_pc1

    valid_scores[[me_name]] <- new_pc1
    basis_rows[[i]] <- data.table(
      module = mod,
      eigengene = me_name,
      n_taxa = length(genes),
      pc1_variance_explained = var_expl,
      train_pc1_vs_ME_cor = sign_cor,
      sign_flipped = sign_flip
    )
  }
  list(new_me = as.data.table(valid_scores), basis = rbindlist(basis_rows))
}

valid_expr <- expr_by_core[[PARAMS$validation_core]]
if (identical(PARAMS$module_method, "consensus")) {
  me_v       <- moduleEigengenes(valid_expr, module_colors)$eigengenes
  me_v       <- orderMEs(me_v)
  MEs_valid  <- me_v[, intersect(names(MEs_train), colnames(me_v)), drop = FALSE]
  proj_valid <- NULL
} else {
  proj_valid <- project_to_training_basis(train_expr, valid_expr, module_colors, MEs_train)
  MEs_valid  <- proj_valid$new_me[, names(MEs_train), with = FALSE]
}

MEs_train_dt <- as.data.table(MEs_train)
MEs_train_dt[, sample := rownames(train_expr)]
MEs_valid_dt <- as.data.table(MEs_valid)
MEs_valid_dt[, sample := rownames(valid_expr)]

setcolorder(MEs_train_dt, c("sample", setdiff(names(MEs_train_dt), "sample")))
setcolorder(MEs_valid_dt, c("sample", setdiff(names(MEs_valid_dt), "sample")))
MEs_main_all <- rbindlist(list(MEs_train_dt, MEs_valid_dt), use.names = TRUE)

# Project non-calib samples in the main window so the HMM covers all ≤main_max_age_kyr samples.
# Modules are defined on calib only; eigengenes for other samples are projected via the same
# per-module PCA loadings used for the validation core.
rocs_tr_full    <- readRDS(file.path(DIRS$main, "rocs_tr_matrix.rds"))
meta_all_main   <- fread(file.path(DIRS$main, "sample_metadata_main.tsv"))
calib_sample_ids <- rownames(rocs_tr_mat)
noncalib_main_ids <- setdiff(
  intersect(meta_all_main$label, rownames(rocs_tr_full)),
  calib_sample_ids
)
if (length(noncalib_main_ids) > 0) {
  calib_taxa_names <- colnames(rocs_tr_mat)
  expr_noncalib <- rocs_tr_full[noncalib_main_ids, calib_taxa_names, drop = FALSE]
  missing_taxa <- setdiff(colnames(train_expr), colnames(expr_noncalib))
  if (length(missing_taxa) > 0) {
    fill_mat <- matrix(0, nrow(expr_noncalib), length(missing_taxa),
                       dimnames = list(rownames(expr_noncalib), missing_taxa))
    expr_noncalib <- cbind(expr_noncalib, fill_mat)[, colnames(train_expr), drop = FALSE]
  } else {
    expr_noncalib <- expr_noncalib[, colnames(train_expr), drop = FALSE]
  }
  if (identical(PARAMS$module_method, "consensus")) {
    me_nc           <- moduleEigengenes(expr_noncalib, module_colors)$eigengenes
    MEs_noncalib_dt <- as.data.table(me_nc[, intersect(names(MEs_train), colnames(me_nc)), drop = FALSE])
    MEs_noncalib_dt[, sample := rownames(expr_noncalib)]
  } else {
    proj_noncalib   <- project_to_training_basis(train_expr, expr_noncalib, module_colors, MEs_train)
    MEs_noncalib_dt <- proj_noncalib$new_me[, names(MEs_train), with = FALSE]
    MEs_noncalib_dt[, sample := rownames(expr_noncalib)]
  }
  setcolorder(MEs_noncalib_dt, c("sample", setdiff(names(MEs_noncalib_dt), "sample")))
  MEs_main_all <- rbindlist(list(MEs_main_all, MEs_noncalib_dt), use.names = TRUE)
  log_msg(sprintf("Projected %d non-calib main-window samples; MEs_main_all now %d rows",
                  length(noncalib_main_ids), nrow(MEs_main_all)))
}
rm(rocs_tr_full)

module_counts <- data.table(module = unique(module_colors))[order(module)]
module_counts[, n_taxa := as.integer(table(module_colors)[module])]

fwrite(data.table(taxon = names(module_colors), module = module_colors), file.path(DIRS$main, "module_assignments.tsv"), sep = "\t")
fwrite(MEs_main_all, file.path(DIRS$main, "module_eigengenes_main.tsv"), sep = "\t")
fwrite(MEs_train_dt, file.path(DIRS$main, "module_eigengenes_training.tsv"), sep = "\t")
fwrite(MEs_valid_dt, file.path(DIRS$main, "module_eigengenes_validation_projection.tsv"), sep = "\t")
if (!is.null(proj_valid)) fwrite(proj_valid$basis, file.path(DIRS$main, "eigengene_projection_basis_main.tsv"), sep = "\t")
fwrite(sft_dt, file.path(DIRS$main, "soft_power_scan.tsv"), sep = "\t")
if (exists("sft_power_summary")) fwrite(sft_power_summary, file.path(DIRS$main, "soft_power_summary.tsv"), sep = "\t")
fwrite(module_counts, file.path(DIRS$main, "module_sizes.tsv"), sep = "\t")
saveRDS(net, file.path(DIRS$main, "consensus_wgcna_main.rds"))

n_boot        <- PARAMS$wgcna_stability_bootstrap_build
bio_modules   <- sort(unique(module_colors[module_colors != "grey"]))
threads_each  <- PARAMS$wgcna_n_threads
n_workers     <- if (PARAMS$wgcna_bootstrap_workers > 0L) {
  as.integer(PARAMS$wgcna_bootstrap_workers)
} else {
  max(1L, floor(parallel::detectCores() / threads_each))
}
log_msg(sprintf(
  "Bootstrap stability: %d resamples, %d parallel workers, %d WGCNA threads/worker",
  n_boot, n_workers, threads_each
))
dir.create(DIRS$wgcna_stability, recursive = TRUE, showWarnings = FALSE)

run_bootstrap <- function(b) {
  suppressPackageStartupMessages(library(WGCNA))
  allowWGCNAThreads(threads_each)
  idx  <- sample(nrow(train_expr), nrow(train_expr), replace = TRUE)
  bnet <- WGCNA::blockwiseModules(
    datExpr       = train_expr[idx, , drop = FALSE],
    power         = soft_power,
    networkType   = "signed",
    corType       = PARAMS$cor_type,
    maxBlockSize  = 5000,
    minModuleSize = PARAMS$wgcna_min_module_size,
    deepSplit     = PARAMS$wgcna_deep_split,
    mergeCutHeight = PARAMS$wgcna_merge_cut_height,
    pamStage         = TRUE,
    pamRespectsDendro = PARAMS$wgcna_pam_respects_dendro,
    numericLabels    = FALSE,
    saveTOMs         = FALSE,
    verbose          = 0
  )
  bc        <- bnet$colors
  boot_mods <- setdiff(unique(bc), "grey")
  purrr::map(bio_modules, \(mod) {
    orig   <- names(module_colors)[module_colors == mod]
    best_j <- if (length(boot_mods) == 0) 0 else max(purrr::map_dbl(
      boot_mods,
      \(bm) { bt <- names(bc)[bc == bm]; length(intersect(orig, bt)) / length(union(orig, bt)) }
    ))
    tibble::tibble(bootstrap = b, module = mod, jaccard = best_j)
  }) |> purrr::list_rbind()
}

boot_dt <- (if (n_workers <= 1L) {
  lapply(seq_len(n_boot), run_bootstrap)
} else {
  parallel::mclapply(seq_len(n_boot), run_bootstrap,
                     mc.cores = n_workers, mc.set.seed = TRUE)
}) |> purrr::list_rbind()

allowWGCNAThreads(PARAMS$wgcna_n_threads)

stability_summary <- boot_dt |>
  dplyr::group_by(module) |>
  dplyr::summarise(
    mean_jaccard = mean(jaccard, na.rm = TRUE),
    sd_jaccard   = sd(jaccard,   na.rm = TRUE),
    n_boot       = dplyr::n(),
    .groups      = "drop"
  )

fwrite(as.data.table(boot_dt),           file.path(DIRS$wgcna_stability, "bootstrap_jaccard_raw.tsv"),       sep = "\t")
fwrite(as.data.table(stability_summary), file.path(DIRS$wgcna_stability, "bootstrap_stability_summary.tsv"), sep = "\t")
log_msg("Bootstrap stability: ", paste(
  sprintf("%s=%.2f±%.2f", stability_summary$module, stability_summary$mean_jaccard, stability_summary$sd_jaccard),
  collapse = ", "
))

var_r1 <- apply(expr_by_core[["GeoB25202_R1"]], 2, var)
var_r2 <- apply(expr_by_core[[PARAMS$validation_core]], 2, var)
good <- names(which(var_r1 > 0 & var_r2 > 0))

mp <- modulePreservation(
  multiData = list(
    GeoB_R1 = list(data = expr_by_core[["GeoB25202_R1"]][, good, drop = FALSE]),
    GeoB_R2 = list(data = expr_by_core[[PARAMS$validation_core]][, good, drop = FALSE])
  ),
  multiColor = list(GeoB_R1 = module_colors[good]),
  referenceNetworks = 1,
  testNetworks = 2,
  nPermutations = preservation_perms,
  randomSeed = PARAMS$seed,
  verbose = 0
)

pres_raw <- mp$preservation$Z[[1]][[2]]
has_pres <- !is.null(pres_raw) && nrow(pres_raw) > 0 && !is.null(rownames(pres_raw))
if (has_pres) {
  has_z <- "Zsummary.pres" %in% colnames(pres_raw)
  pres_dt <- data.table(
    module        = rownames(pres_raw),
    Zsummary      = if (has_z) pres_raw$Zsummary.pres      else NA_real_,
    Zdensity      = if (has_z) pres_raw$Zdensity.pres      else NA_real_,
    Zconnectivity = if (has_z) pres_raw$Zconnectivity.pres else NA_real_
  )
  pres_dt[, preserved  := fcase(!is.finite(Zsummary), "no_perms",
                                Zsummary > 10,         "strong",
                                Zsummary > 2,          "moderate",
                                default =              "weak")]
  pres_dt[, module_type := fifelse(module %in% c("grey", "gold"), "technical", "biological")]
} else {
  pres_dt <- data.table(module = character(), Zsummary = numeric(),
                        Zdensity = numeric(), Zconnectivity = numeric(),
                        preserved = character(), module_type = character())
}
pres_bio_dt <- pres_dt[module_type == "biological"]

age_aligned_concordance <- function(me_all, meta, r1_core, r2_core, validation_core, age_grid_points) {
  me_cols <- grep("^ME", names(me_all), value = TRUE)
  me_cols <- me_cols[me_cols != "MEgrey"]   # grey is the unassigned bin — not a biological module
  r1_samps <- rownames(expr_by_core[[r1_core]])
  r2_samps <- rownames(expr_by_core[[validation_core]])

  r1_dt <- merge(
    data.table(sample = r1_samps),
    meta[, .(label, y_bp)],
    by.x = "sample",
    by.y = "label",
    all.x = TRUE
  )
  r2_dt <- merge(
    data.table(sample = r2_samps),
    meta[, .(label, y_bp)],
    by.x = "sample",
    by.y = "label",
    all.x = TRUE
  )
  r1_dt[, age_kyr := y_bp / 1000]
  r2_dt[, age_kyr := y_bp / 1000]

  me_r1 <- me_all[sample %in% r1_samps]
  me_r2 <- me_all[sample %in% r2_samps]

  rbindlist(lapply(me_cols, function(me) {
    d1 <- merge(r1_dt[, .(sample, age_kyr)], me_r1[, .(sample, value = get(me))], by = "sample")
    d2 <- merge(r2_dt[, .(sample, age_kyr)], me_r2[, .(sample, value = get(me))], by = "sample")
    d1 <- d1[is.finite(age_kyr) & is.finite(value)][order(age_kyr)]
    d2 <- d2[is.finite(age_kyr) & is.finite(value)][order(age_kyr)]
    if (nrow(d1) < 3 || nrow(d2) < 3) {
      return(data.table(module = me, pearson_r = NA_real_, spearman_rho = NA_real_, rmse = NA_real_))
    }
    age_min <- max(min(d1$age_kyr), min(d2$age_kyr))
    age_max <- min(max(d1$age_kyr), max(d2$age_kyr))
    if (!is.finite(age_min) || !is.finite(age_max) || age_max <= age_min) {
      return(data.table(module = me, pearson_r = NA_real_, spearman_rho = NA_real_, rmse = NA_real_))
    }
    # Linear grid (kept for RMSE and backwards compatibility)
    xout_lin <- seq(age_min, age_max, length.out = age_grid_points)
    y1_lin   <- approx(d1$age_kyr, d1$value, xout = xout_lin, rule = 2)$y
    y2_lin   <- approx(d2$age_kyr, d2$value, xout = xout_lin, rule = 2)$y

    # Log-spaced grid: equalises point density across the 580 kyr range.
    # Requires age_min > 0; clamp to 0.01 kyr (~10 years) for core-top samples.
    age_min_log <- max(age_min, 0.01)
    xout_log <- exp(seq(log(age_min_log), log(age_max), length.out = age_grid_points))
    y1_log   <- approx(d1$age_kyr, d1$value, xout = xout_log, rule = 2)$y
    y2_log   <- approx(d2$age_kyr, d2$value, xout = xout_log, rule = 2)$y

    # Use log-spaced grid as the default y1/y2 for all downstream metrics
    y1 <- y1_log
    y2 <- y2_log

    # Active-interval metrics: robust for sparse/episodic modules where floor noise
    # dominates Spearman rank order but the signal itself is well-preserved.
    q75      <- quantile(c(y1, y2), 0.75, na.rm = TRUE)
    active1  <- y1 > q75
    active2  <- y2 > q75
    n_union  <- sum(active1 | active2)
    active_jaccard  <- if (n_union > 0) sum(active1 & active2) / n_union else NA_real_
    active_mask     <- active1 | active2
    active_pearson  <- if (sum(active_mask, na.rm = TRUE) >= 3)
      suppressWarnings(cor(y1[active_mask], y2[active_mask], method = "pearson", use = "complete.obs"))
    else NA_real_

    peak_age_r1  <- d1$age_kyr[which.max(d1$value)]
    peak_age_r2  <- d2$age_kyr[which.max(d2$value)]
    peak_kyr_diff <- abs(peak_age_r1 - peak_age_r2)

    # Excess kurtosis of pooled interpolated signal: high value flags episodic modules
    # where Pearson/Spearman diverge and active-interval metrics are more informative.
    pool    <- c(y1, y2)
    mu_p    <- mean(pool, na.rm = TRUE)
    sd_p    <- sd(pool, na.rm = TRUE)
    signal_kurtosis <- if (is.finite(sd_p) && sd_p > 0)
      mean(((pool - mu_p) / sd_p)^4, na.rm = TRUE) - 3
    else NA_real_

    data.table(
      module               = me,
      age_min              = age_min,
      age_max              = age_max,
      n_grid               = age_grid_points,
      pearson_r            = as.numeric(suppressWarnings(cor(y1,     y2,     method = "pearson",  use = "complete.obs"))),
      spearman_rho         = as.numeric(suppressWarnings(cor(y1,     y2,     method = "spearman", use = "complete.obs"))),
      spearman_rho_lingrid = as.numeric(suppressWarnings(cor(y1_lin, y2_lin, method = "spearman", use = "complete.obs"))),
      rmse                 = sqrt(mean((y1_lin - y2_lin)^2, na.rm = TRUE)),
      active_jaccard  = active_jaccard,
      active_pearson  = as.numeric(active_pearson),
      peak_age_r1     = peak_age_r1,
      peak_age_r2     = peak_age_r2,
      peak_kyr_diff   = peak_kyr_diff,
      signal_kurtosis = signal_kurtosis
    )
  }), fill = TRUE)
}

concordance_dt <- age_aligned_concordance(
  me_all = MEs_main_all,
  meta = meta_main,
  r1_core = "GeoB25202_R1",
  r2_core = PARAMS$validation_core,
  validation_core = PARAMS$validation_core,
  age_grid_points = PARAMS$wgcna_stability_age_grid_points
)

fwrite(data.table(taxon = names(module_colors), module = module_colors), file.path(DIRS$main, "module_assignments.tsv"), sep = "\t")
fwrite(MEs_main_all, file.path(DIRS$main, "module_eigengenes_main.tsv"), sep = "\t")
fwrite(MEs_train_dt, file.path(DIRS$main, "module_eigengenes_training.tsv"), sep = "\t")
fwrite(MEs_valid_dt, file.path(DIRS$main, "module_eigengenes_validation_projection.tsv"), sep = "\t")
if (!is.null(proj_valid)) fwrite(proj_valid$basis, file.path(DIRS$main, "eigengene_projection_basis_main.tsv"), sep = "\t")
fwrite(pres_dt, file.path(DIRS$main, "module_preservation_validation.tsv"), sep = "\t")
fwrite(pres_bio_dt, file.path(DIRS$main, "module_preservation_validation_biological.tsv"), sep = "\t")
fwrite(concordance_dt, file.path(DIRS$main, "eigengene_concordance_age_aligned.tsv"), sep = "\t")

log_msg("02_wgcna_main complete.")
