#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(data.table)
})

env_flag <- function(name, default = FALSE) {
  raw <- Sys.getenv(name, unset = "")
  if (!nzchar(raw)) return(default)
  val <- tolower(trimws(raw))
  if (val %in% c("1", "true", "t", "yes", "y", "on")) return(TRUE)
  if (val %in% c("0", "false", "f", "no", "n", "off")) return(FALSE)
  warning(sprintf("Unrecognized boolean env var %s='%s'; using default=%s", name, raw, default))
  default
}

env_csv <- function(name, default = character()) {
  raw <- Sys.getenv(name, unset = "")
  if (!nzchar(raw)) return(default)
  vals <- trimws(unlist(strsplit(raw, ",", fixed = TRUE)))
  vals <- vals[nzchar(vals)]
  unique(vals)
}

env_string <- function(name, default = "") {
  raw <- Sys.getenv(name, unset = "")
  if (!nzchar(raw)) return(default)
  trimws(raw)
}

env_numeric <- function(name, default) {
  raw <- Sys.getenv(name, unset = "")
  if (!nzchar(raw)) return(default)
  val <- suppressWarnings(as.numeric(raw))
  if (!is.finite(val)) {
    warning(sprintf("Unrecognized numeric env var %s='%s'; using default=%s", name, raw, as.character(default)))
    return(default)
  }
  val
}

env_integer <- function(name, default) {
  val <- env_numeric(name, default = default)
  if (!is.finite(val)) return(default)
  as.integer(round(val))
}

env_choice <- function(name, choices, default) {
  raw <- tolower(env_string(name, default = default))
  if (!raw %in% choices) {
    warning(sprintf("Unrecognized %s='%s'; using default='%s'", name, raw, default))
    return(default)
  }
  raw
}

REPO_ROOT <- getwd()

if (!file.exists(file.path(REPO_ROOT, "data", "metadata_v5.tsv"))) {
  stop("Run scripts from repo root so relative paths resolve (expected data/metadata_v5.tsv).")
}

results_root_env <- env_string("WGCNA_HMM_RESULTS_ROOT", default = "")
results_suffix_env <- env_string("WGCNA_HMM_RESULTS_SUFFIX", default = "")
if (nzchar(results_root_env) && nzchar(results_suffix_env)) {
  warning("Both WGCNA_HMM_RESULTS_ROOT and WGCNA_HMM_RESULTS_SUFFIX set; using WGCNA_HMM_RESULTS_ROOT.")
}

RESULTS_ROOT <- if (nzchar(results_root_env)) {
  if (grepl("^/", results_root_env)) results_root_env else file.path(REPO_ROOT, results_root_env)
} else if (nzchar(results_suffix_env)) {
  file.path(REPO_ROOT, "results", paste0("wgcna_hmm_", results_suffix_env))
} else {
  file.path(REPO_ROOT, "results", "wgcna")
}

DIRS <- list(
  code = file.path(REPO_ROOT, "code", "wgcna_hmm"),
  results = RESULTS_ROOT,
  main = file.path(RESULTS_ROOT, "main"),
  main_tea = file.path(RESULTS_ROOT, "main", "tea"),
  extended = file.path(RESULTS_ROOT, "extended"),
  reports = file.path(RESULTS_ROOT, "reports"),
  qc = file.path(RESULTS_ROOT, "qc"),
  wgcna_stability = file.path(RESULTS_ROOT, "main", "wgcna_stability"),
  logs = file.path(RESULTS_ROOT, "logs")
)

module_method_env <- tolower(env_string("WGCNA_HMM_MODULE_METHOD", default = "wgcna"))
if (!module_method_env %in% c("wgcna", "leiden", "consensus", "propr")) {
  warning(sprintf("Unrecognized WGCNA_HMM_MODULE_METHOD='%s'; using 'wgcna'.", module_method_env))
  module_method_env <- "wgcna"
}

# Data root: shared upstream pipeline outputs (microbial damage, eukaryotes, etc.)
# Default: our symlink dir; override with WGCNA_HMM_DATA_ROOT env var.
DATA_ROOT <- env_string(
  "WGCNA_HMM_DATA_ROOT",
  default = "/projects/caeg/scratch/kbd606/rocs/data"
)

INPUTS <- list(
  tax_damage = env_string(
    "WGCNA_HMM_INPUT_TAX_DAMAGE",
    default = file.path(DATA_ROOT, "microbial/damage/damage-classification-depositional/dmg-summary-ssp-damage-classification-depositional.tsv.gz")
  ),
  metadata = env_string(
    "WGCNA_HMM_INPUT_METADATA",
    default = file.path(REPO_ROOT, "data", "metadata_v5.tsv")
  ),
  xrf = env_string(
    "WGCNA_HMM_INPUT_XRF",
    default = file.path(REPO_ROOT, "data", "combined_xrf_not_normalized.tsv")
  ),
  kegg_mods = env_string(
    "WGCNA_HMM_INPUT_KEGG_MODS",
    default = file.path(DATA_ROOT, "functional/kegg-modules-summary-rocs.tsv.gz")
  ),
  prokaryote_function = env_string(
    "WGCNA_HMM_INPUT_PROK_FUNCTION",
    default = file.path(DATA_ROOT, "microbial/prokaryote_function_assigned.tsv")
  ),
  euk_species = env_string(
    "WGCNA_HMM_INPUT_EUK_SPECIES",
    default = file.path(DATA_ROOT, "eukaryotes/taxonomy/species_level_data.tsv")
  ),
  euk_genus = env_string(
    "WGCNA_HMM_INPUT_EUK_GENUS",
    default = file.path(DATA_ROOT, "eukaryotes/taxonomy/genus_level_data.tsv")
  ),
  euk_family = env_string(
    "WGCNA_HMM_INPUT_EUK_FAMILY",
    default = file.path(DATA_ROOT, "eukaryotes/taxonomy/family_level_data.tsv")
  ),
  euk_species_dmg = env_string(
    "WGCNA_HMM_INPUT_EUK_SPECIES_DMG",
    default = file.path(DATA_ROOT, "eukaryotes/taxonomy/species_level_data_dmg.tsv")
  )
)

PARAMS <- list(
  seed = 42,
  excluded_samples = c("LV3003046968"),
  all_cores = c("ST8", "ST13", "GeoB25202_R1", "GeoB25202_R2"),
  training_cores = env_csv("WGCNA_LOCO_TRAINING_CORES",
                           default = c("ST8", "ST13", "GeoB25202_R1")),
  validation_core = env_string("WGCNA_LOCO_VALIDATION_CORE",
                               default = "GeoB25202_R2"),
  main_max_age_kyr = 150,
  extended_max_age_kyr = c(
    ST8 = 150,
    ST13 = 300,
    GeoB25202_R1 = 600,
    GeoB25202_R2 = 600
  ),
  prevalence_min_samples = 10,
  calib_max_dup_ratio = 4.0,
  calib_min_lib_conc  = 30.0,

  # Bryant/networkQC-selected production WGCNA setting: exp3.
  # exp3 balanced low grey assignment, bootstrap stability, preservation,
  # age-aligned R1/R2 concordance, kME, and TOM topology better than baseline.
  wgcna_min_module_size = env_integer("WGCNA_HMM_MIN_MODULE_SIZE", default = 20L),
  wgcna_deep_split     = env_integer("WGCNA_HMM_DEEP_SPLIT",      default = 3L),
  wgcna_merge_cut_height = env_numeric("WGCNA_HMM_MERGE_CUT_HEIGHT", default = 0.25),
  wgcna_n_threads        = env_integer("WGCNA_HMM_THREADS",           default = 8L),
  wgcna_bootstrap_workers = env_integer("WGCNA_HMM_BOOTSTRAP_WORKERS", default = -1L),
  wgcna_soft_power = env_integer("WGCNA_HMM_WGCNA_SOFT_POWER", default = 12L),
  soft_power_target_r2 = 0.80,
  wgcna_pam_respects_dendro = TRUE,
  wgcna_run_mode = env_choice("WGCNA_HMM_WGCNA_MODE", choices = c("build", "final"), default = "build"),
  wgcna_preservation_permutations_build = env_integer("WGCNA_HMM_PRESERVATION_PERMUTATIONS_BUILD", default = 200L),
  wgcna_preservation_permutations_final = env_integer("WGCNA_HMM_PRESERVATION_PERMUTATIONS_FINAL", default = 700L),
  wgcna_stability_bootstrap_build = env_integer("WGCNA_HMM_STABILITY_BOOTSTRAP_BUILD", default = 100L),
  wgcna_stability_bootstrap_final = env_integer("WGCNA_HMM_STABILITY_BOOTSTRAP_FINAL", default = 120L),
  wgcna_stability_age_grid_points = env_integer("WGCNA_HMM_STABILITY_AGE_GRID_POINTS", default = 100L),
  module_method = module_method_env,
  leiden_resolution = env_numeric("WGCNA_HMM_LEIDEN_RESOLUTION", default = 1.0),
  leiden_resolution_strict = env_flag("WGCNA_HMM_LEIDEN_RESOLUTION_STRICT", default = FALSE),
  leiden_graph_k_neighbors = max(5L, env_integer("WGCNA_HMM_LEIDEN_K_NEIGHBORS", default = 25)),
  leiden_graph_symmetrization = env_choice("WGCNA_HMM_LEIDEN_GRAPH_SYMMETRIZATION", choices = c("union", "mutual"), default = "union"),
  leiden_consensus_matrix_interpretation = env_choice("WGCNA_HMM_LEIDEN_CONSENSUS_MATRIX_INTERPRETATION", choices = c("auto", "similarity", "dissimilarity"), default = "auto"),
  leiden_merge_eigengene_cor = env_numeric("WGCNA_HMM_LEIDEN_MERGE_EIGENGENE_COR", default = NA_real_),
  leiden_merge_max_iter = max(1L, env_integer("WGCNA_HMM_LEIDEN_MERGE_MAX_ITER", default = 1000L)),
  hmm_n_pcs = env_integer("WGCNA_HMM_N_PCS", default = 4L),
  hmm_k_min = env_integer("WGCNA_HMM_K_MIN", default = 2L),
  hmm_k_max = env_integer("WGCNA_HMM_K_MAX", default = 7L),
  hmm_k_preferred = env_integer("WGCNA_HMM_K_PREFERRED", default = 5L),
  hmm_n_iter = 500,
  hmm_n_start = 10,
  extended_anchor_older_validation_core = TRUE,
  extended_anchor_core = "GeoB25202_R2",
  xrf_half_width_cm = 0.5,
  q_threshold = 0.10,
  core_proxy_panel = c(
    "ca_ti_z", "ba_ti_z", "rb_sr_z", "k_ti_z", "mn_fe_z", "ti_al_z", "zr_rb_z",
    "library_concentration_z", "derep_z", "temp_harmonized_z"
  ),
  oap_completeness_threshold = 0.30,
  exclude_deep_sediment_taxa = env_flag("WGCNA_HMM_EXCLUDE_DEEP_SEDIMENT_TAXA", default = FALSE),
  extra_excluded_phyla = env_csv("WGCNA_HMM_EXTRA_EXCLUDED_PHYLA", default = character()),
  deep_sediment_display_category = "Diagenetic",
  deep_sediment_signal_sources = c("diagenetic_in_situ", "benthic_resident"),
  deep_sediment_confidence_min = 0.85
)

TEA <- list(
  oap_modules = list(
    M00155 = list(class = "O2", eo_mv = 820, disc = 1.00),
    M00154 = list(class = "O2", eo_mv = 820, disc = 1.00),
    M00416 = list(class = "O2", eo_mv = 820, disc = 1.00),
    M00417 = list(class = "O2", eo_mv = 820, disc = 1.00),
    M00156 = list(class = "O2", eo_mv = 820, disc = 0.50),
    M00153 = list(class = "O2", eo_mv = 820, disc = 0.25),
    M00529 = list(class = "NO3", eo_mv = 740, disc = 1.00),
    M00530 = list(class = "NO3", eo_mv = 360, disc = 1.00),
    M00973 = list(class = "ANX", eo_mv = 350, disc = 1.00),
    M00596 = list(class = "SO4", eo_mv = -217, disc = 1.00),
    M00567 = list(class = "CH4", eo_mv = -244, disc = 1.00),
    M00357 = list(class = "CH4", eo_mv = -244, disc = 1.00),
    M00356 = list(class = "CH4", eo_mv = -244, disc = 1.00),
    M00563 = list(class = "CH4", eo_mv = -244, disc = 1.00)
  ),
  target_kos = c(
    "K00399", "K00401", "K00402",
    "K14080",
    "K00370",
    "K02305",
    "K00376",
    "K00425",
    "K02274", "K02276",
    "K00394", "K00395",
    "K00958",
    "K11180", "K11181"
  )
)

log_msg <- function(...) {
  message(sprintf("[%s] %s", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), paste0(...)))
}

ensure_dirs <- function(paths) {
  for (d in paths) dir.create(d, recursive = TRUE, showWarnings = FALSE)
}

write_session_info <- function(path) {
  si <- utils::capture.output(sessionInfo())
  writeLines(si, con = path)
}

write_run_metadata <- function(path, script_name, extra = list()) {
  md <- data.table(
    timestamp = format(Sys.time(), "%Y-%m-%d %H:%M:%S"),
    script = script_name,
    repo_root = REPO_ROOT,
    seed = PARAMS$seed
  )
  if (length(extra) > 0) {
    for (nm in names(extra)) {
      val <- extra[[nm]]
      if (length(val) > 1) val <- paste(val, collapse = ";")
      md[[nm]] <- as.character(val)
    }
  }
  fwrite(md, path, sep = "\t")
}

core_group <- function(x) sub("_R[12]$", "", x)

corewise_z_transform <- function(mat, core_ids, feature_names = colnames(mat), variant = "corewise_z") {
  x <- as.matrix(mat)
  storage.mode(x) <- "double"
  if (length(core_ids) != nrow(x)) {
    stop("core_ids length must match number of rows in matrix.")
  }
  if (is.null(feature_names)) {
    feature_names <- paste0("V", seq_len(ncol(x)))
  }
  colnames(x) <- feature_names

  cores <- unique(as.character(core_ids))
  out <- x
  param_rows <- vector("list", length(cores))

  for (i in seq_along(cores)) {
    co <- cores[i]
    idx <- which(core_ids == co)
    x_sub <- x[idx, , drop = FALSE]
    mu <- colMeans(x_sub, na.rm = TRUE)
    sdv <- apply(x_sub, 2, sd, na.rm = TRUE)
    sdv[!is.finite(sdv) | sdv == 0] <- 1
    out[idx, ] <- sweep(sweep(x_sub, 2, mu, "-"), 2, sdv, "/")

    param_rows[[i]] <- data.table(
      core = co,
      feature = feature_names,
      mu = as.numeric(mu),
      sd = as.numeric(sdv),
      variant = variant
    )
  }

  list(
    scaled = out,
    params = rbindlist(param_rows, use.names = TRUE)
  )
}

PARAMS$transform <- env_choice(
  "WGCNA_HMM_TRANSFORM",
  choices = c("clr_taxa", "clr_taxa_rclr", "clr_taxa_adna", "clr_taxa_adna2", "clr_sample", "clr_sample_rclr", "clr_ngm902", "clr_sample_adna", "pflogpf", "rclr", "log_only"),
  default = "clr_taxa"
)
PARAMS$cor_type <- env_choice(
  "WGCNA_HMM_COR_TYPE",
  choices = c("pearson", "bicor"),
  default = "bicor"
)

compute_rocs_tr <- function(count_mat_taxa_by_samples, derep_vec) {
  sample_ids <- colnames(count_mat_taxa_by_samples)
  E_i <- derep_vec[sample_ids]
  missing <- sample_ids[is.na(E_i)]
  if (length(missing) > 0) stop("Missing derep values for: ", paste(missing, collapse = ", "))
  if (any(!is.finite(E_i) | E_i <= 0)) stop("Non-positive or non-finite derep values detected.")
  keep <- apply(count_mat_taxa_by_samples, 1, function(v) stats::var(v, na.rm = TRUE) > 0)
  m <- count_mat_taxa_by_samples[keep, , drop = FALSE]
  tr <- PARAMS$transform
  log_msg("Transform: ", tr, "  (", nrow(m), " taxa x ", ncol(m), " samples)")
  if (tr == "clr_taxa") {
    lm <- log(m + 0.5)
    lm <- lm - rowMeans(lm)
    return(t(lm))
  }
  if (tr == "clr_taxa_rclr") {
    # Taxa-wise rCLR (kept for comparison). NOTE: per-taxon centering is invariant
    # under Pearson/bicor — algebraically equivalent to log(TAD) with zeros=0.
    # Benefit over clr_taxa is zero-handling only, not centering.
    lm <- log(m)
    lm[m == 0] <- NA
    taxa_means <- rowMeans(lm, na.rm = TRUE)
    lm <- lm - taxa_means
    lm[is.na(lm)] <- 0
    return(t(lm))
  }
  if (tr == "clr_ngm902") {
    # Exact replication of ngm902's compute_clr_train_centered:
    # log(TAD + 0.5) then sample-wise centering (subtract per-sample geometric mean).
    # Pseudocount handles zeros; sample-wise centering removes library size.
    lm <- log(m + 0.5)
    lm <- sweep(lm, 2, colMeans(lm), "-")
    return(t(lm))
  }
  if (tr == "clr_sample_adna") {
    # Sample-wise rCLR with aDNA-adapted zero handling:
    # zeros replaced by per-SAMPLE detection floor (min nonzero TAD / 2) before
    # log-transform. This avoids the fixed +0.5 pseudocount bias (which pulls
    # low-library samples toward log(0.5)), and avoids the zero=sample-mean
    # artifact of clr_sample_rclr. After imputation, sample-wise centering
    # removes library size. All taxa get a real value → lower grey rate.
    m_imp <- m
    for (j in seq_len(ncol(m_imp))) {
      nz <- m_imp[m_imp[, j] > 0, j]
      if (length(nz) > 0) m_imp[m_imp[, j] == 0, j] <- min(nz) / 2
    }
    lm <- log(m_imp)
    lm <- sweep(lm, 2, colMeans(lm), "-")
    return(t(lm))
  }
  if (tr == "clr_sample_rclr") {
    # Sample-wise rCLR (Martino 2019): per-sample geometric mean over OBSERVED
    # (non-zero) taxa only, then zeros → 0. Removes library-size confound because
    # log(L_j) appears in every non-zero taxon and is subtracted by colMeans(na).
    # This is the correct direction for library-size removal via compositional centering.
    lm <- log(m)
    lm[m == 0] <- NA
    sample_means <- colMeans(lm, na.rm = TRUE)
    lm <- sweep(lm, 2, sample_means, "-")
    lm[is.na(lm)] <- 0
    return(t(lm))
  }
  if (tr == "clr_taxa_adna") {
    # P3: left-censored imputation — per-sample floor (min nonzero TAD / 2)
    m_imp <- m
    for (j in seq_len(ncol(m_imp))) {
      nz <- m_imp[m_imp[, j] > 0, j]
      if (length(nz) > 0) m_imp[m_imp[, j] == 0, j] <- min(nz) / 2
    }
    lm <- log(m_imp)
    # P4: core-stratified centering
    all_cores <- c(PARAMS$training_cores, PARAMS$validation_core)
    for (co in all_cores) {
      idx <- grep(paste0("^", co, "_"), colnames(lm), fixed = FALSE)
      if (length(idx) > 1) lm[, idx] <- lm[, idx] - rowMeans(lm[, idx, drop = FALSE])
    }
    lm <- lm - rowMeans(lm)
    return(t(lm))
  }
  if (tr == "clr_taxa_adna2") {
    # P3 refined: per-taxon floor — each taxon's detection floor is its own minimum nonzero TAD / 2
    # More stable than per-sample: uses biological signal floor, not library-depth noise
    m_imp <- m
    row_floors <- apply(m_imp, 1, function(r) {
      nz <- r[r > 0]
      if (length(nz) > 0) min(nz) / 2 else NA_real_
    })
    for (i in seq_len(nrow(m_imp))) {
      if (!is.na(row_floors[i]))
        m_imp[i, m_imp[i, ] == 0] <- row_floors[i]
    }
    lm <- log(m_imp)
    # P4: core-stratified centering
    all_cores <- c(PARAMS$training_cores, PARAMS$validation_core)
    for (co in all_cores) {
      idx <- grep(paste0("^", co, "_"), colnames(lm), fixed = FALSE)
      if (length(idx) > 1) lm[, idx] <- lm[, idx] - rowMeans(lm[, idx, drop = FALSE])
    }
    lm <- lm - rowMeans(lm)
    return(t(lm))
  }
  if (tr == "clr_sample") {
    mt <- t(m)  # samples × taxa
    if (any(mt == 0)) {
      if (!requireNamespace("zCompositions", quietly = TRUE))
        stop("WGCNA_HMM_TRANSFORM=clr_sample requires zCompositions (matrix has zeros)")
      mt <- zCompositions::cmultRepl(mt, method = "GBM", output = "p-counts",
                                     z.warning = 1, z.delete = FALSE,
                                     suppress.print = TRUE)
    }
    lm <- log(mt)
    return(lm - rowMeans(lm))
  }
  if (tr == "pflogpf") {
    sp <- Matrix::sparseMatrix(
      i = row(m)[m > 0], j = col(m)[m > 0],
      x = as.numeric(m[m > 0]),
      dims = dim(m), dimnames = dimnames(m)
    )
    res <- scclrR::normalize_matrix(sp, target = "auto", center = TRUE)
    dense <- as.matrix(res$sparse)
    dimnames(dense) <- dimnames(m)
    return(t(sweep(dense, 2, res$center, "-")))
  }
  if (tr == "log_only") {
    # Per-taxon floor: min observed nonzero TAD / 2, so zeros get a taxon-specific detection floor.
    # Returns raw log values without centering — used as input for propr ρ computation.
    row_floors <- apply(m, 1, function(r) {
      nz <- r[r > 0]
      if (length(nz) > 0) min(nz) / 2 else 1e-6
    })
    m_imp <- m
    for (i in seq_len(nrow(m_imp))) {
      m_imp[i, m_imp[i, ] == 0] <- row_floors[i]
    }
    return(t(log(m_imp)))
  }
  # rclr: per-sample centering over non-zero entries using derep as library size
  k <- median(E_i, na.rm = TRUE)
  lm <- log2(1 + k * sweep(m, 2, E_i, "/"))
  lm[m == 0] <- NA
  lm <- sweep(lm, 2, colMeans(lm, na.rm = TRUE), "-")
  lm[is.na(lm)] <- 0
  t(lm)
}

# Proportionality ρ (Quinn 2017): ρ(i,j) = 2·cov(clr_i,clr_j)/(var_i+var_j)
# log_mat: taxa × samples, already log-transformed with per-taxon floor (no zeros).
# CLR-centers per sample first so library size fully cancels.
compute_propr_rho <- function(log_mat) {
  # log_mat: taxa × samples. CLR-center per sample, then standard cov across samples.
  clr_mat <- sweep(log_mat, 2, colMeans(log_mat), "-")
  cov_mat <- cov(t(clr_mat))  # base cov() — always returns plain matrix; t() gives samples × taxa
  var_vec <- diag(cov_mat)
  denom   <- outer(var_vec, var_vec, "+")
  rho_mat <- 2 * cov_mat / denom
  diag(rho_mat) <- 1
  rho_mat[!is.finite(rho_mat)] <- 0
  rho_mat
}
