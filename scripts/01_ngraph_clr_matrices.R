#!/usr/bin/env Rscript
# 01_ngraph_clr_matrices.R -- build threshold-specific sample-centered CLR matrices.

suppressPackageStartupMessages({
  library(data.table)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("01_ngraph_clr_matrices")
ng_start_log(LOG)
ng_log(LOG, "Starting NGraph abundance-threshold CLR matrix isolation")

for (path in c(NG_DATA$tax_damage, NG_DATA$metadata_file, NG_DATA$prokaryote_function)) {
  if (!file.exists(path)) stop("Missing imported feedstock: ", path, ". Run step 00 first.")
}

needed_cols <- c(
  "subspecies", "label", "domain", "is_dmg", "n_reads", "n_reads_tad",
  "tax_abund_tad", "tax_abund_read", "tax_abund_aln", "reference_length"
)
tax <- fread(NG_DATA$tax_damage, select = needed_cols)
meta <- fread(NG_DATA$metadata_file)
taxa_meta <- fread(NG_DATA$prokaryote_function)

meta[, age_kyr := y_bp / 1000]
meta <- meta[
  core %in% NG_PARAMS$all_cores &
    age_kyr <= NG_PARAMS$max_age_kyr &
    !label %in% NG_PARAMS$excluded_samples
]

prok <- tax[
  is_dmg == "Damaged" &
    domain %in% c("d__Archaea", "d__Bacteria", "d__Viruses") &
    label %in% meta$label
]

meta <- meta[label %in% unique(prok$label)]

agg <- prok[, .(
  abundance = sum(get(NG_PARAMS$abundance_column), na.rm = TRUE),
  n_reads = sum(n_reads, na.rm = TRUE),
  n_reads_tad = sum(n_reads_tad, na.rm = TRUE),
  tax_abund_read = sum(tax_abund_read, na.rm = TRUE),
  tax_abund_aln = sum(tax_abund_aln, na.rm = TRUE),
  reference_length = mean(reference_length, na.rm = TRUE)
), by = .(subspecies, label)]

ng_log(LOG, "Stage-1 aggregate: ", uniqueN(agg$subspecies), " taxa x ", uniqueN(agg$label), " samples")

threshold_summaries <- list()
for (thr in NG_PARAMS$prevalence_thresholds) {
  dirs <- ng_threshold_dirs(thr)
  keep_taxa <- agg[abundance > 0, .N, by = subspecies][N >= thr, subspecies]
  dt <- agg[subspecies %in% keep_taxa]

  wide_abund <- dcast(dt, subspecies ~ label, value.var = "abundance", fill = 0)
  taxa_ids <- wide_abund$subspecies
  abund_mat <- as.matrix(wide_abund[, -1, with = FALSE])
  rownames(abund_mat) <- taxa_ids
  storage.mode(abund_mat) <- "double"

  abund_mat <- abund_mat[, meta$label, drop = FALSE]

  log_abund <- log(t(abund_mat) + NG_PARAMS$clr_pseudocount)
  clr <- sweep(log_abund, 1, rowMeans(log_abund), FUN = "-")

  taxon_var <- apply(clr, 2, var, na.rm = TRUE)
  clr <- clr[, taxon_var > 0, drop = FALSE]
  abund_mat <- abund_mat[colnames(clr), , drop = FALSE]

  row_mean_abs_max <- max(abs(rowMeans(clr)), na.rm = TRUE)
  if (!is.finite(row_mean_abs_max) || row_mean_abs_max > 1e-10) {
    stop("CLR row means are not approximately zero for threshold ", thr)
  }

  sample_totals <- dt[, .(
    total_tax_abund_tad = sum(abundance, na.rm = TRUE),
    detected_taxa_tad = sum(abundance > 0, na.rm = TRUE),
    total_n_reads = sum(n_reads, na.rm = TRUE),
    total_n_reads_tad = sum(n_reads_tad, na.rm = TRUE),
    total_tax_abund_read = sum(tax_abund_read, na.rm = TRUE),
    total_tax_abund_aln = sum(tax_abund_aln, na.rm = TRUE)
  ), by = label]
  sample_qc <- merge(meta, sample_totals, by = "label", all.x = TRUE, sort = FALSE)
  for (col in c("total_tax_abund_tad", "detected_taxa_tad", "total_n_reads",
                "total_n_reads_tad", "total_tax_abund_read", "total_tax_abund_aln")) {
    sample_qc[is.na(get(col)), (col) := 0]
  }
  sample_qc[, threshold := thr]
  sample_qc[, `:=`(
    sample = label,
    log_total_tax_abund_tad = log10(total_tax_abund_tad + 1),
    log_total_n_reads = log10(total_n_reads + 1),
    log_total_n_reads_tad = log10(total_n_reads_tad + 1)
  )]

  taxa_meta_ng <- taxa_meta[taxon %in% colnames(clr)]
  if (nrow(taxa_meta_ng) == 0) taxa_meta_ng <- data.table(taxon = colnames(clr))

  saveRDS(clr, file.path(dirs$matrices, "ngraph_clr_global.rds"))
  saveRDS(abund_mat, file.path(dirs$matrices, "ngraph_tax_abund_tad_taxa_by_sample.rds"))
  fwrite(sample_qc, file.path(dirs$tables, "ngraph_sample_qc.tsv"), sep = "\t")
  fwrite(taxa_meta_ng, file.path(dirs$tables, "ngraph_taxa_metadata.tsv"), sep = "\t")

  matrix_summary <- data.table(
    branch = NG$branch,
    threshold = thr,
    matrix = "ngraph_clr_global",
    abundance_column = NG_PARAMS$abundance_column,
    samples = nrow(clr),
    taxa = ncol(clr),
    pseudocount = NG_PARAMS$clr_pseudocount,
    prevalence_min_samples = thr,
    max_abs_sample_clr_mean = row_mean_abs_max
  )
  fwrite(matrix_summary, file.path(dirs$tables, "ngraph_matrix_summary.tsv"), sep = "\t")
  threshold_summaries[[length(threshold_summaries) + 1]] <- matrix_summary

  core_summary <- rbindlist(lapply(NG_PARAMS$all_cores, function(core_id) {
    samples <- intersect(sample_qc[core == core_id, label], rownames(clr))
    saveRDS(clr[samples, , drop = FALSE], file.path(dirs$matrices, paste0("ngraph_clr_", core_id, ".rds")))
    data.table(
      threshold = thr,
      core = core_id,
      samples = length(samples),
      taxa = ncol(clr),
      age_min_kyr = sample_qc[core == core_id, min(age_kyr, na.rm = TRUE)],
      age_max_kyr = sample_qc[core == core_id, max(age_kyr, na.rm = TRUE)]
    )
  }))
  fwrite(core_summary, file.path(dirs$tables, "ngraph_core_matrix_summary.tsv"), sep = "\t")
  ng_log(LOG, "Threshold ", thr, ": ", nrow(clr), " samples x ", ncol(clr), " taxa")
}

fwrite(rbindlist(threshold_summaries), file.path(NG$tables, "ngraph_threshold_matrix_summary.tsv"), sep = "\t")
ng_log(LOG, "Method Validated: abundance-threshold CLR matrices written")
ng_log(LOG, "Complete")
