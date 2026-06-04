#!/usr/bin/env Rscript
# 01_ngraph_clr_matrices.R -- isolate sample-wise CLR matrices for NGraph.

suppressPackageStartupMessages({
  library(data.table)
})

source("config_ngraph.R")
ng_require("DESeq2")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("01_ngraph_clr_matrices")
ng_start_log(LOG)
ng_log(LOG, "Starting NGraph CLR matrix isolation")

dds_path <- file.path(ROCS$stage1, "prokaryotes_dds.rds")
meta_path <- file.path(ROCS$stage1, "sample_metadata_stage1.tsv")
taxa_path <- file.path(ROCS$stage1, "prokaryotes_taxa_metadata.tsv")

if (!file.exists(dds_path)) stop("Missing ROCS DESeq object: ", dds_path)
if (!file.exists(meta_path)) stop("Missing ROCS sample metadata: ", meta_path)
if (!file.exists(taxa_path)) stop("Missing ROCS taxon metadata: ", taxa_path)

dds <- readRDS(dds_path)
counts <- DESeq2::counts(dds)
meta <- fread(meta_path)
taxa_meta <- fread(taxa_path)

meta[, age_kyr := y_bp / 1000]
meta <- meta[
  core %in% NG_PARAMS$all_cores &
    age_kyr <= NG_PARAMS$max_age_kyr &
    label %in% colnames(counts)
]

counts <- counts[, meta$label, drop = FALSE]
prev <- rowSums(counts > 0)
keep_taxa <- prev >= NG_PARAMS$prevalence_min_samples
counts <- counts[keep_taxa, , drop = FALSE]

ng_log(LOG, "Counts after filter: ", nrow(counts), " taxa x ", ncol(counts), " samples")

# Sample-wise CLR: each sample is centered by its own geometric mean.
log_counts <- log(t(counts) + NG_PARAMS$clr_pseudocount)
clr <- sweep(log_counts, 1, rowMeans(log_counts), FUN = "-")

taxon_var <- apply(clr, 2, var, na.rm = TRUE)
clr <- clr[, taxon_var > 0, drop = FALSE]
counts <- counts[colnames(clr), , drop = FALSE]

row_mean_abs_max <- max(abs(rowMeans(clr)), na.rm = TRUE)
if (!is.finite(row_mean_abs_max) || row_mean_abs_max > 1e-10) {
  stop("CLR row means are not approximately zero; max abs mean = ", row_mean_abs_max)
}

sample_qc <- data.table(
  sample = colnames(counts),
  total_reads = as.numeric(colSums(counts)),
  detected_taxa = as.integer(colSums(counts > 0))
)
sample_qc[, log_total_reads := log10(total_reads + 1)]
sample_qc <- merge(
  meta,
  sample_qc,
  by.x = "label",
  by.y = "sample",
  all.x = TRUE,
  sort = FALSE
)

taxa_meta_ng <- taxa_meta[taxon %in% colnames(clr)]
if (nrow(taxa_meta_ng) == 0) {
  taxa_meta_ng <- data.table(taxon = colnames(clr))
}

saveRDS(clr, file.path(NG$matrices, "ngraph_clr_global.rds"))
saveRDS(counts, file.path(NG$matrices, "ngraph_counts_taxa_by_sample.rds"))
fwrite(sample_qc, file.path(NG$tables, "ngraph_sample_qc.tsv"), sep = "\t")
fwrite(taxa_meta_ng, file.path(NG$tables, "ngraph_taxa_metadata.tsv"), sep = "\t")

matrix_summary <- data.table(
  matrix = "ngraph_clr_global",
  samples = nrow(clr),
  taxa = ncol(clr),
  pseudocount = NG_PARAMS$clr_pseudocount,
  prevalence_min_samples = NG_PARAMS$prevalence_min_samples,
  max_abs_sample_clr_mean = row_mean_abs_max
)
fwrite(matrix_summary, file.path(NG$tables, "ngraph_matrix_summary.tsv"), sep = "\t")

core_rows <- list()
for (core_id in NG_PARAMS$all_cores) {
  samples <- sample_qc[core == core_id, label]
  samples <- intersect(samples, rownames(clr))
  core_clr <- clr[samples, , drop = FALSE]
  saveRDS(core_clr, file.path(NG$matrices, paste0("ngraph_clr_", core_id, ".rds")))
  core_rows[[length(core_rows) + 1]] <- data.table(
    core = core_id,
    samples = nrow(core_clr),
    taxa = ncol(core_clr),
    age_min_kyr = sample_qc[core == core_id, min(age_kyr, na.rm = TRUE)],
    age_max_kyr = sample_qc[core == core_id, max(age_kyr, na.rm = TRUE)]
  )
}
fwrite(rbindlist(core_rows), file.path(NG$tables, "ngraph_core_matrix_summary.tsv"), sep = "\t")

ng_log(LOG, "Method Validated: CLR matrices written")
ng_log(LOG, "Complete")
