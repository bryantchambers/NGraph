#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(data.table)
})
source(file.path("code", "wgcna_hmm", "00_config.R"))
set.seed(PARAMS$seed)
ensure_dirs(c(DIRS$results, DIRS$main, DIRS$extended, DIRS$reports, DIRS$logs))

log_msg("Loading damage table + metadata...")
tax <- if (grepl("\\.gz$", INPUTS$tax_damage)) {
  fread(cmd = sprintf("gzip -dc %s", shQuote(INPUTS$tax_damage)))
} else {
  fread(INPUTS$tax_damage)
}
meta <- fread(INPUTS$metadata)
retained_taxa <- fread(file.path(
  Sys.getenv("WGCNA_HMM_FILTER_TAXA_DIR",
             file.path(REPO_ROOT, "results", "microbial", "wgcna")),
  "data", "filtered_prokaryotes.tsv"
))

meta <- meta[
  core %in% PARAMS$all_cores &
    !label %in% PARAMS$excluded_samples
]
meta[, age_kyr := y_bp / 1000]

meta_main <- meta[age_kyr <= PARAMS$main_max_age_kyr]

# Per-core extended windows are disabled; k = median(derep) over all samples.
# The Lean depth-invariance/bloom-stability theorems hold for any positive k,
# so this is compatible with the certified spec.
meta_ext <- meta


log_msg("Filtering to damaged prokaryote/viral taxa for selected samples...")
prok <- tax[
  is_dmg == "Damaged" &
    subspecies %in% retained_taxa$taxon &
    label %in% meta_ext$label
]

prok[, abund_val := ifelse(tax_abund_tad > 0, tax_abund_tad, tax_abund_read)]
prok_agg_full <- prok[, .(abundance = sum(abund_val)), by = .(subspecies, label)]

deep_manifest_path <- file.path(DIRS$main, "deep_sediment_excluded_taxa.tsv")
deep_manifest <- data.table(
  taxon = character(),
  exclusion_reason = character(),
  exclusion_detail = character(),
  phylum = character(),
  functional_group = character(),
  display_category = character(),
  ecological_role = character(),
  signal_source = character(),
  confidence_score = numeric(),
  n_samples = integer(),
  total_reads = numeric()
)

n_deep_sediment_candidates <- 0L
n_deep_sediment_excluded_selected <- 0L
n_deep_sediment_excluded_prevalent <- 0L
n_extra_phylum_candidates <- 0L
n_extra_phylum_excluded_selected <- 0L
n_extra_phylum_excluded_prevalent <- 0L
deep_sediment_recovered_group <- list(
  phylum = "p__Chloroflexota",
  class = "c__Anaerolineae",
  order = "o__B4-G1",
  family = "f__B4-G1",
  genus = "g__BS750m-G37"
)

extra_excluded_phyla <- unique(as.character(PARAMS$extra_excluded_phyla))
extra_excluded_phyla <- extra_excluded_phyla[nzchar(extra_excluded_phyla)]
if (isTRUE(PARAMS$exclude_deep_sediment_taxa) || length(extra_excluded_phyla) > 0) {
  log_msg("Sensitivity exclusion filter enabled. Building exclusion set from classification table...")
  class_dt <- fread(INPUTS$prokaryote_function)
  required_cols <- c(
    "taxon", "phylum", "functional_group", "display_category", "ecological_role",
    "signal_source", "confidence_score"
  )
  missing_cols <- setdiff(required_cols, names(class_dt))
  if (length(missing_cols) > 0) {
    stop("Classification table missing required columns: ", paste(missing_cols, collapse = ", "))
  }
  class_dt[, confidence_score := as.numeric(confidence_score)]

  deep_candidates <- data.table(
    taxon = character(), exclusion_reason = character(), exclusion_detail = character(),
    phylum = character(), functional_group = character(), display_category = character(),
    ecological_role = character(), signal_source = character(), confidence_score = numeric()
  )

  if (isTRUE(PARAMS$exclude_deep_sediment_taxa)) {
    deep_candidates <- unique(class_dt[
      display_category == PARAMS$deep_sediment_display_category &
        signal_source %in% PARAMS$deep_sediment_signal_sources &
        confidence_score >= PARAMS$deep_sediment_confidence_min,
      .(
        taxon,
        exclusion_reason = "curated_diagenetic",
        exclusion_detail = sprintf(
          "display_category==%s;signal_source in {%s};confidence_score>=%.2f",
          PARAMS$deep_sediment_display_category,
          paste(PARAMS$deep_sediment_signal_sources, collapse = ","),
          PARAMS$deep_sediment_confidence_min
        ),
        phylum,
        functional_group,
        display_category,
        ecological_role,
        signal_source,
        confidence_score
      )
    ])
    n_deep_sediment_candidates <- uniqueN(deep_candidates$taxon)
  }

  phylum_candidates <- data.table(
    taxon = character(), exclusion_reason = character(), exclusion_detail = character(),
    phylum = character(), functional_group = character(), display_category = character(),
    ecological_role = character(), signal_source = character(), confidence_score = numeric()
  )

  if (length(extra_excluded_phyla) > 0) {
    phylum_candidates <- unique(class_dt[
      phylum %in% extra_excluded_phyla,
      .(
        taxon,
        exclusion_reason = "extra_phylum",
        exclusion_detail = phylum,
        phylum,
        functional_group,
        display_category,
        ecological_role,
        signal_source,
        confidence_score
      )
    ])
    n_extra_phylum_candidates <- uniqueN(phylum_candidates$taxon)
  }

  exclusion_candidates <- unique(rbindlist(list(deep_candidates, phylum_candidates), use.names = TRUE, fill = TRUE))
  recovered_cols <- names(deep_sediment_recovered_group)
  if (all(recovered_cols %in% names(prok))) {
    recovered_taxa <- unique(prok[
      phylum == deep_sediment_recovered_group$phylum &
      class == deep_sediment_recovered_group$class &
      order == deep_sediment_recovered_group$order &
      family == deep_sediment_recovered_group$family &
      genus == deep_sediment_recovered_group$genus,
      subspecies
    ])
    exclusion_candidates <- exclusion_candidates[!taxon %in% recovered_taxa]
  }
  taxa_in_run <- unique(prok$subspecies)
  excluded_taxa <- intersect(unique(exclusion_candidates$taxon), taxa_in_run)

  n_deep_sediment_excluded_selected <- length(intersect(unique(deep_candidates$taxon), taxa_in_run))
  n_extra_phylum_excluded_selected <- length(intersect(unique(phylum_candidates$taxon), taxa_in_run))

  if (length(excluded_taxa) > 0) {
    excl_stats <- prok_agg_full[
      subspecies %in% excluded_taxa,
      .(n_samples = sum(abundance > 0), total_reads = sum(abundance)),
      by = subspecies
    ]

    deep_manifest <- merge(
      exclusion_candidates[taxon %in% excluded_taxa],
      excl_stats[, .(taxon = subspecies, n_samples, total_reads)],
      by = "taxon",
      all.x = TRUE
    )
    deep_manifest[is.na(n_samples), n_samples := 0L]
    deep_manifest[is.na(total_reads), total_reads := 0]

    n_deep_sediment_excluded_prevalent <- prok_agg_full[
      subspecies %in% intersect(unique(deep_candidates$taxon), taxa_in_run) & label %in% meta_main$label & abundance > 0,
      .(n_samples = .N),
      by = subspecies
    ][n_samples >= PARAMS$prevalence_min_samples, uniqueN(subspecies)]

    n_extra_phylum_excluded_prevalent <- prok_agg_full[
      subspecies %in% intersect(unique(phylum_candidates$taxon), taxa_in_run) & label %in% meta_main$label & abundance > 0,
      .(n_samples = .N),
      by = subspecies
    ][n_samples >= PARAMS$prevalence_min_samples, uniqueN(subspecies)]

    prok <- prok[!subspecies %in% excluded_taxa]
  }

  log_msg(
    "Curated-diagenetic candidates: ", n_deep_sediment_candidates,
    "; excluded in selected samples: ", n_deep_sediment_excluded_selected,
    "; excluded meeting prevalence in main window: ", n_deep_sediment_excluded_prevalent,
    "; extra-phylum candidates: ", n_extra_phylum_candidates,
    "; extra-phylum excluded in selected samples: ", n_extra_phylum_excluded_selected,
    "; extra-phylum excluded meeting prevalence in main window: ", n_extra_phylum_excluded_prevalent
  )
} else {
  log_msg("Sensitivity exclusion filter disabled (default).")
}

setcolorder(
  deep_manifest,
  c("taxon", "exclusion_reason", "exclusion_detail", "phylum", "functional_group", "display_category", "ecological_role", "signal_source", "confidence_score", "n_samples", "total_reads")
)
fwrite(deep_manifest[order(-total_reads, taxon)], deep_manifest_path, sep = "\t")

prok_agg <- prok[, .(abund = sum(abund_val)), by = .(subspecies, label)]

# In LOCO mode, restrict prevalence counting to training cores to prevent
# leakage from the held-out core into feature selection.
prevalence_labels <- if (length(PARAMS$training_cores) < length(PARAMS$all_cores)) {
  meta_main[core %in% PARAMS$training_cores, label]
} else {
  meta_main$label
}
keep_taxa <- prok_agg[
  label %in% prevalence_labels & abund > 0,
  .(n_samples = .N),
  by = subspecies
][n_samples >= PARAMS$prevalence_min_samples, subspecies]

prok_agg <- prok_agg[subspecies %in% keep_taxa]

wide <- dcast(prok_agg, subspecies ~ label, value.var = "abund", fill = 0)
taxa <- wide$subspecies
count_mat <- as.matrix(wide[, -1, with = FALSE])
rownames(count_mat) <- taxa
storage.mode(count_mat) <- "integer"

main_ids <- intersect(meta_main$label, colnames(count_mat))
ext_ids <- intersect(meta_ext$label, colnames(count_mat))

derep_vec <- setNames(meta_ext$derep, meta_ext$label)

ext_vst_path <- Sys.getenv("WGCNA_HMM_INPUT_VST_MATRIX", unset = "")
if (nzchar(ext_vst_path)) {
  log_msg("Loading pre-computed VST matrix from: ", ext_vst_path)
  tr_mat <- readRDS(ext_vst_path)
  stopifnot(is.matrix(tr_mat), !is.null(rownames(tr_mat)), !is.null(colnames(tr_mat)))
  log_msg(sprintf("  Loaded: %d samples x %d taxa", nrow(tr_mat), ncol(tr_mat)))
} else {
  tr_ids <- if (PARAMS$transform == "clr_sample") main_ids else ext_ids
  tr_mat <- compute_rocs_tr(
    count_mat_taxa_by_samples = count_mat[, tr_ids, drop = FALSE],
    derep_vec                 = derep_vec
  )
}

meta_main <- meta_main[label %in% rownames(tr_mat)]
meta_ext <- meta_ext[label %in% rownames(tr_mat)]

fwrite(meta_main, file.path(DIRS$main, "sample_metadata_main.tsv"), sep = "\t")
fwrite(meta_ext, file.path(DIRS$extended, "sample_metadata_extended.tsv"), sep = "\t")
fwrite(
  data.table(taxon = colnames(tr_mat)),
  file.path(DIRS$main, "taxa_after_filter.tsv"),
  sep = "\t"
)
saveRDS(tr_mat, file.path(DIRS$main, "rocs_tr_matrix.rds"))

calib_ids <- meta_ext[
  initial / derep < PARAMS$calib_max_dup_ratio &
  library_concentration > PARAMS$calib_min_lib_conc,
  label
]
calib_ids <- intersect(calib_ids, rownames(tr_mat))
calib_taxa <- colnames(tr_mat)[
  colSums(tr_mat[calib_ids, ] > 0) >= PARAMS$prevalence_min_samples
]
tr_mat_calib <- tr_mat[calib_ids, calib_taxa, drop = FALSE]

log_msg(
  "Calibration set: ", length(calib_ids), " samples / ", length(calib_taxa), " taxa",
  " (dup_ratio<", PARAMS$calib_max_dup_ratio,
  ", lib_conc>", PARAMS$calib_min_lib_conc, " ng/ul)"
)

saveRDS(tr_mat_calib[, calib_taxa], file.path(DIRS$main, "rocs_tr_matrix_calib.rds"))
fwrite(
  data.table(taxon = calib_taxa),
  file.path(DIRS$main, "taxa_calib.tsv"), sep = "\t"
)
calib_meta <- meta_ext[label %in% calib_ids]
calib_meta[, saturation_weight := 1 - 1 / (initial / derep)]
fwrite(calib_meta, file.path(DIRS$main, "sample_metadata_calib.tsv"), sep = "\t")

summary_dt <- data.table(
  metric = c(
    "n_samples_main", "n_samples_extended", "n_taxa_final_matrix",
    "n_samples_calib", "n_taxa_calib",
    "calib_max_dup_ratio", "calib_min_lib_conc",
    "deep_sediment_filter_enabled", "deep_sediment_candidates_total",
    "deep_sediment_excluded_selected_samples", "deep_sediment_excluded_prevalent_main_window",
    "extra_excluded_phyla_count", "extra_excluded_phyla_values", "extra_phylum_candidates_total",
    "extra_phylum_excluded_selected_samples", "extra_phylum_excluded_prevalent_main_window",
    "main_max_age_kyr", "st13_max_age_kyr_extended", "geob_max_age_kyr_extended"
  ),
  value = c(
    nrow(meta_main), nrow(meta_ext), ncol(tr_mat),
    length(calib_ids), length(calib_taxa),
    PARAMS$calib_max_dup_ratio, PARAMS$calib_min_lib_conc,
    as.integer(isTRUE(PARAMS$exclude_deep_sediment_taxa)),
    n_deep_sediment_candidates,
    n_deep_sediment_excluded_selected,
    n_deep_sediment_excluded_prevalent,
    length(extra_excluded_phyla),
    if (length(extra_excluded_phyla) > 0) paste(extra_excluded_phyla, collapse = ";") else "",
    n_extra_phylum_candidates,
    n_extra_phylum_excluded_selected,
    n_extra_phylum_excluded_prevalent,
    PARAMS$main_max_age_kyr,
    PARAMS$extended_max_age_kyr[["ST13"]],
    PARAMS$extended_max_age_kyr[["GeoB25202_R1"]]
  )
)
fwrite(summary_dt, file.path(DIRS$main, "data_prep_summary.tsv"), sep = "\t")

log_msg("01_data_prep complete.")
