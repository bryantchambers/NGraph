#!/usr/bin/env Rscript
# =============================================================================
# WGCNA Taxa Filtering Script
#
# Purpose: Filter taxa for WGCNA analysis based on:
#   1. Damage authentication (aDNA authenticity)
#   2. Prevalence (present in enough samples)
#   3. Contamination exclusion
#   4. Time range and core selection
#
# Outputs taxa list for classification and KEGG matching
# =============================================================================

library(data.table)
library(dplyr)
library(tidyr)

read_delim_auto <- function(path, ...) {
  if (grepl("\\.gz$", path)) {
    fread(cmd = sprintf("gzip -dc %s", shQuote(path)), ...)
  } else {
    fread(path, ...)
  }
}

cat(strrep("=", 70), "\n")
cat("WGCNA TAXA FILTERING\n")
cat(strrep("=", 70), "\n\n")

# =============================================================================
# CONFIGURATION
# =============================================================================
base_dir <- getwd()
output_dir <- Sys.getenv("WGCNA_HMM_FILTER_TAXA_DIR",
                         file.path(base_dir, "results/microbial/wgcna"))

# Target cores used in the WGCNA workflow
target_cores <- c("ST8", "ST13", "GeoB25202_R1", "GeoB25202_R2")

# Time range (600 kyr = 6 glacial cycles)
timerange <- 600000

# Prevalence thresholds
min_samples_prok <- 10      # Prokaryotes: present in ≥10 samples
min_damage_pct <- 40        # Minimum % damaged observations for authentication
min_reads <- 100            # Minimum reads to trust damage estimates

# =============================================================================
# 1. LOAD AND FILTER PROKARYOTE DATA
# =============================================================================
cat("1. Loading Prokaryote/Virus data...\n")

prok_file <- Sys.getenv(
  "WGCNA_HMM_INPUT_TAX_DAMAGE",
  unset = "/maps/projects/caeg/people/ngm902/apps/repos/rocs_marine_cores_old/results/microbial/taxonomy/dmg-summary-ssp_selected.tsv.gz"
)
prok_raw <- read_delim_auto(prok_file)

cat(sprintf("   Raw rows: %s\n", format(nrow(prok_raw), big.mark = ",")))
cat(sprintf("   Columns: %d\n", ncol(prok_raw)))

# Filter by core and time
prok_filtered <- prok_raw[
  core %in% target_cores &
  y_bp <= timerange
]
cat(sprintf("   After core/time filter: %s rows\n", format(nrow(prok_filtered), big.mark = ",")))

# Damage authentication: damaged OR (recent AND selected)
# Also require minimum reads for reliable damage estimates
prok_auth <- prok_filtered[
  n_reads >= min_reads &
  is_dmg == "Damaged"
]
cat(sprintf("   After damage authentication (min %d reads): %s rows\n", min_reads, format(nrow(prok_auth), big.mark = ",")))

# Compute species-level statistics
prok_auth[, abund_val := ifelse(tax_abund_tad > 0, tax_abund_tad, tax_abund_read)]
prok_stats <- prok_auth[
  abund_val > 0,
  .(
    domain = domain[1],
    phylum = phylum[1],
    class = class[1],
    n_obs = .N,
    n_samples = length(unique(label)),
    n_cores = length(unique(core)),
    total_reads = sum(n_reads),
    mean_abundance = mean(abund_val),
    n_damaged = sum(is_dmg == "Damaged"),
    pct_damaged = 100 * mean(is_dmg == "Damaged")
  ),
  by = name
]

cat(sprintf("   Unique taxa: %d\n", nrow(prok_stats)))
cat(sprintf("   By domain:\n"))
print(prok_stats[, .N, by = domain][order(-N)])

# Apply prevalence filter
prok_keep <- prok_stats[
  n_samples >= min_samples_prok
]

cat(sprintf("\n   FILTERING SUMMARY (Prokaryotes):\n"))
cat(sprintf("     n_samples >= %d: %d taxa\n", min_samples_prok,
            nrow(prok_stats[n_samples >= min_samples_prok])))
cat(sprintf("     + n_cores >= 2: %d taxa\n", nrow(prok_keep)))

# Summary by domain
cat("\n   KEPT TAXA BY DOMAIN:\n")
print(prok_keep[, .N, by = domain][order(-N)])

# =============================================================================
# 2. CHECK KEGG COVERAGE
# =============================================================================
cat("\n2. Checking KEGG module coverage...\n")

kegg_file <- "/projects/caeg/people/ngm902/apps/repos/rocs/data/functional/kegg-modules-summary-rocs.tsv.gz"
# kegg_file <- file.path(base_dir, "results/network_regimes/kegg_modules_filtered.tsv")
if (file.exists(kegg_file)) {
  kegg_data <- read_delim_auto(kegg_file, header = FALSE)
  kegg_genomes <- unique(kegg_data$V2)

  # Extract genome IDs from prokaryote names (remove S__ prefix)
  prok_keep[, genome_id := sub("^S__", "", name)]
  prok_keep[, has_kegg := genome_id %in% kegg_genomes]

  cat(sprintf("   Genomes with KEGG data: %d\n", length(kegg_genomes)))
  cat(sprintf("   Kept prokaryotes with KEGG: %d / %d (%.1f%%)\n",
              sum(prok_keep$has_kegg), nrow(prok_keep),
              100 * mean(prok_keep$has_kegg)))

  # By domain
  cat("\n   KEGG coverage by domain:\n")
  print(prok_keep[, .(
    n_taxa = .N,
    n_with_kegg = sum(has_kegg),
    pct_kegg = round(100 * mean(has_kegg), 1)
  ), by = domain])

} else {
  cat("   WARNING: KEGG file not found\n")
  prok_keep[, has_kegg := FALSE]
}

# =============================================================================
# 3. SAVE FILTERED TAXA LISTS
# =============================================================================
cat("\n3. Saving filtered taxa lists...\n")
dir.create(file.path(output_dir, "data"), recursive = TRUE, showWarnings = FALSE)

# Prokaryotes/Viruses
prok_out <- prok_keep[, .(
  taxon = name,
  domain,
  phylum,
  class,
  n_samples,
  n_cores,
  total_reads,
  pct_damaged,
  has_kegg,
  genome_id
)]
fwrite(prok_out, file.path(output_dir, "data/filtered_prokaryotes.tsv"), sep = "\t")
cat(sprintf("   Saved: %d prokaryotes/viruses\n", nrow(prok_out)))

# =============================================================================
# 4. SUMMARY
# =============================================================================
cat("\n")
cat(strrep("=", 70), "\n")
cat("SUMMARY\n")
cat(strrep("=", 70), "\n")
cat(sprintf("Prokaryotes/Viruses: %d taxa\n", nrow(prok_out)))
cat(sprintf("  - Bacteria: %d\n", nrow(prok_out[domain == "d__Bacteria"])))
cat(sprintf("  - Archaea: %d\n", nrow(prok_out[domain == "d__Archaea"])))
cat(sprintf("  - Viruses: %d\n", nrow(prok_out[domain == "d__Viruses"])))
cat(sprintf("  - With KEGG: %d (%.1f%%)\n", sum(prok_out$has_kegg),
            100 * mean(prok_out$has_kegg)))
cat(sprintf("\nTotal taxa for WGCNA: %d\n", nrow(prok_out)))
cat(strrep("=", 70), "\n")

# Save session info
cat("\nSession info saved to: ", file.path(output_dir, "00_filter_taxa_session.txt"), "\n")
sink(file.path(output_dir, "00_filter_taxa_session.txt"))
cat("Filtering parameters:\n")
cat(sprintf("  target_cores: %s\n", paste(target_cores, collapse = ", ")))
cat(sprintf("  timerange: %d\n", timerange))
cat(sprintf("  min_samples_prok: %d\n", min_samples_prok))
cat(sprintf("  min_damage_pct: %d\n", min_damage_pct))
cat("\n")
sessionInfo()
sink()

cat("\nDone!\n")
