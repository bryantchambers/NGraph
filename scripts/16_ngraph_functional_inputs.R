#!/usr/bin/env Rscript
# Export existing matrices without changing their CLR reference universe.
suppressPackageStartupMessages(library(data.table))
source("config_ngraph.R")
set.seed(42)
LOG <- ng_log_path("16_ngraph_functional_inputs")
ng_start_log(LOG)
ng_log(LOG, "Exporting functional inputs; data.table ", packageVersion("data.table"))
for (threshold in NG_PARAMS$prevalence_thresholds) {
  dirs <- ng_threshold_dirs(threshold)
  out <- file.path(NG$results, "functional_inputs", dirs$label, "tables")
  dir.create(out, recursive = TRUE, showWarnings = FALSE)
  clr <- readRDS(file.path(dirs$matrices, "ngraph_clr_global.rds"))
  abundance <- t(readRDS(file.path(dirs$matrices, "ngraph_tax_abundance_taxa_by_sample.rds")))
  abundance <- abundance[rownames(clr), colnames(clr), drop = FALSE]
  if (!all(is.finite(clr)) || !all(is.finite(abundance)) || any(abundance < 0)) {
    stop("Functional input matrices contain invalid values")
  }
  fwrite(data.table(sample = rownames(clr), as.data.table(clr)),
         file.path(out, "clr_samples_by_taxa.tsv.gz"), sep = "\t", compress = "gzip")
  fwrite(data.table(sample = rownames(abundance), as.data.table(abundance)),
         file.path(out, "abundance_samples_by_taxa.tsv.gz"), sep = "\t", compress = "gzip")
  metadata <- fread(file.path(dirs$tables, "ngraph_sample_qc.tsv"))
  if (!"sample" %in% names(metadata)) metadata[, sample := label]
  metadata <- metadata[match(rownames(clr), sample)]
  stopifnot(identical(metadata$sample, rownames(clr)))
  metadata[, physical_core := sub("_R[12]$", "", core)]
  metadata[, abundance_mode := NG_PARAMS$abundance_mode]
  fwrite(metadata, file.path(out, "sample_metadata.tsv"), sep = "\t")
  fwrite(fread(file.path(dirs$tables, "ngraph_taxa_metadata.tsv")),
         file.path(out, "taxa_metadata.tsv"), sep = "\t")
  ng_log(LOG, dirs$label, ": ", nrow(clr), " samples, ", ncol(clr), " taxa; CLR unchanged")
}
ng_log(LOG, "Functional input export complete")
