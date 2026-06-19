#!/usr/bin/env Rscript
# 00_ngraph_import_feedstock.R -- copy NGraph feedstock from Source into /src/data.

suppressPackageStartupMessages({
  library(data.table)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("00_ngraph_import_feedstock")
ng_start_log(LOG)
ng_log(LOG, "Starting NGraph feedstock import")

copy_one <- function(src, dest, required_columns = character()) {
  if (!file.exists(src)) stop("Missing source feedstock: ", src)
  dir.create(dirname(dest), recursive = TRUE, showWarnings = FALSE)
  if (dir.exists(dest)) {
    unlink(dest, recursive = TRUE, force = TRUE)
  }
  if (!file.exists(dest) || file.info(src)$size != file.info(dest)$size) {
    file.copy(src, dest, overwrite = TRUE)
  }
  cols <- names(fread(dest, nrows = 0))
  missing <- setdiff(required_columns, cols)
  if (length(missing)) {
    stop("Imported file missing required columns: ", dest, " missing ", paste(missing, collapse = ", "))
  }
  data.table(
    source = src,
    destination = dest,
    bytes = file.info(dest)$size,
    required_columns = paste(required_columns, collapse = ", "),
    present = file.exists(dest)
  )
}

prov <- rbindlist(list(
  copy_one(
    ROCS$tax_damage,
    NG_DATA$tax_damage,
    c("subspecies", "label", "domain", "is_dmg", "n_reads", "n_reads_tad",
      "tax_abund_tad", "reference_length")
  ),
  copy_one(
    ROCS$metadata,
    NG_DATA$metadata_file,
    c("label", "core", "y_bp", "mis")
  ),
  copy_one(
    ROCS$prokaryote_function,
    NG_DATA$prokaryote_function,
    c("taxon")
  )
), fill = TRUE)

prov[, imported_at := format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z")]
fwrite(prov, file.path(NG_DATA$provenance, "ngraph_feedstock_import.tsv"), sep = "\t")

ng_log(LOG, "Imported ", nrow(prov), " feedstock files")
ng_log(LOG, "Method Validated: feedstock copied into /src/data")
ng_log(LOG, "Complete")
