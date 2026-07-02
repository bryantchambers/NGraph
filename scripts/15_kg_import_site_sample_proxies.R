#!/usr/bin/env Rscript
# 15_kg_import_site_sample_proxies.R -- build the first branch-scoped KG substrate.

suppressPackageStartupMessages({
  library(data.table)
  library(jsonlite)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("15_kg_import_site_sample_proxies")
ng_start_log(LOG)
ng_log(LOG, "Starting KG import")
ng_log(LOG, "Package versions: data.table ", as.character(utils::packageVersion("data.table")),
       ", jsonlite ", as.character(utils::packageVersion("jsonlite")))

kg_dirs <- ng_kg_dirs()
dir.create(kg_dirs$root, recursive = TRUE, showWarnings = FALSE)

resolve_module_source <- function(base_dir, threshold_label, method_label) {
  preferred <- file.path(base_dir, threshold_label, method_label)
  if (dir.exists(preferred)) {
    return(list(threshold_label = threshold_label, method_label = method_label, root = preferred))
  }
  threshold_dirs <- list.dirs(base_dir, recursive = FALSE, full.names = FALSE)
  threshold_dirs <- threshold_dirs[grepl("^prev_[0-9]+$", threshold_dirs)]
  for (thr in threshold_dirs) {
    candidate <- file.path(base_dir, thr, method_label)
    if (dir.exists(candidate)) {
      return(list(threshold_label = thr, method_label = method_label, root = candidate))
    }
  }
  stop("Unable to resolve module source directory under ", base_dir, " for method ", method_label)
}

module_source <- resolve_module_source(
  NG$deep_modules,
  ng_threshold_label(NG_PARAMS$deep_knowledge_primary_threshold),
  NG_PARAMS$deep_knowledge_primary_method
)
kg_threshold_label <- module_source$threshold_label
kg_method_label <- module_source$method_label
module_root <- module_source$root

core_to_site <- function(core) {
  site <- gsub("_R[12]$", "", core)
  site
}

site_lookup <- data.table(
  site_id = c("ST5", "ST8", "ST13", "GeoB25202"),
  site_label = c("ST5", "ST8", "ST13", "GeoB25202"),
  latitude = c(61.948, 64.5516666666667, 63.2503333333333, 63.2503333333333),
  longitude = c(-19.495, -29.5415, -28.254, -28.254),
  core_aliases = c("ST5", "ST8", "ST13", "GeoB25202_R1,GeoB25202_R2"),
  site_type = c("continental_sediment_core", "ocean_sediment_core", "ocean_sediment_core", "ocean_sediment_core")
)

dataset_sources <- data.table(
  dataset_id = c(
    "dataset:metadata_v5",
    "dataset:sst_proxies",
    "dataset:foraminifera_geochem",
    "dataset:geob25202_proxies",
    "dataset:xrf_geochemistry",
    "dataset:damage_baselines",
    "dataset:sample_taxon_abundance",
    "dataset:sample_taxon_clr",
    "dataset:vgae_modules",
    "dataset:diffpool_modules",
    "dataset:taxon_nodes",
    "dataset:site_nodes"
  ),
  label = c(
    "metadata_v5",
    "sst_proxies",
    "foraminifera_geochem",
    "geob25202_proxies",
    "xrf_geochemistry",
    "damage_baselines",
    "sample_taxon_abundance",
    "sample_taxon_clr",
    "vgae_modules",
    "diffpool_modules",
    "taxon_nodes",
    "site_nodes"
  ),
  source_file = c(
    "Source/ROCS/data/metadata_v5.tsv",
    "Source/ROCS/data/combined_sst_proxies_separate_columns.csv",
    "Source/ROCS/data/combined_foraminifera_geochem.tsv",
    "Source/ROCS/data/geob25202_clean_proxies.tsv",
    "Source/ROCS/data/combined_xrf_geochemistry_not_normalized.csv",
    "Source/ROCS/results/microbial/damage/damage-classification-depositional/sample-baselines.tsv",
    file.path(NG$deep_knowledge, "tables", "sample_taxon_abundance_long.tsv"),
    file.path(NG$deep_knowledge, "tables", "sample_taxon_clr_long.tsv"),
    file.path(module_root, "tables", "vgae_taxon_modules.tsv"),
    file.path(module_root, "tables", "diffpool_consensus_modules.tsv"),
    file.path(module_root, "tables", "hetero_taxon_nodes.tsv"),
    file.path(module_root, "tables", "hetero_site_nodes.tsv")
  ),
  stringsAsFactors = FALSE
)

required_paths <- dataset_sources$source_file[1:12]
missing_paths <- required_paths[!file.exists(required_paths)]
if (length(missing_paths)) {
  stop("Missing KG source files: ", paste(missing_paths, collapse = ", "))
}

read_src <- function(path) {
  if (grepl("\\.csv$", path, ignore.case = TRUE)) {
    fread(path)
  } else {
    fread(path, sep = "\t")
  }
}

sample_meta <- read_src("Source/ROCS/data/metadata_v5.tsv")
sample_meta[, site_id := core_to_site(core)]
sample_meta[, sample_id := label]
sample_meta[, age_kyr := y_bp / 1000]

sample_nodes <- sample_meta[, .(
  node_id = sample_id,
  node_type = "Sample",
  label = sample_id,
  site_id,
  core,
  depth_in_core_cm,
  y_bp,
  age_kyr,
  mis,
  temp,
  temp_method,
  library_concentration,
  initial,
  derep,
  sst,
  source_table = "metadata_v5",
  source_file = "Source/ROCS/data/metadata_v5.tsv",
  branch = NG$branch
)]

sample_lookup <- sample_meta[, .(
  sample_id,
  site_id,
  core,
  y_bp,
  depth_in_core_cm,
  age_kyr
)]

direct_measurements <- function(dt, id_col, value_cols, source_table, source_file, match_method = "direct_sample") {
  dt <- copy(dt)
  dt[, sample_id := get(id_col)]
  if (!"core" %in% names(dt)) {
    dt <- merge(
      dt,
      sample_lookup,
      by = "sample_id",
      all.x = TRUE,
      sort = FALSE,
      allow.cartesian = TRUE
    )
  } else if (!"site_id" %in% names(dt)) {
    dt[, site_id := core_to_site(core)]
  }
  dt[, site_id := fifelse(is.na(site_id), core_to_site(core), site_id)]
  melted <- melt(
    dt,
    id.vars = intersect(c("sample_id", "site_id", "core", "label", "y_bp", "depth_in_core_cm", "age_kyr", "mis"), names(dt)),
    measure.vars = intersect(value_cols, names(dt)),
    variable.name = "variable",
    value.name = "value",
    na.rm = FALSE
  )
  if (!"sample_id" %in% names(melted) && "label" %in% names(melted)) {
    melted[, sample_id := label]
  }
  melted[, dataset_id := paste0("dataset:", source_table)]
  melted[, `:=`(
    source_table = source_table,
    source_file = source_file,
    match_method = match_method,
    match_delta = 0
  )]
  melted[is.finite(as.numeric(value))]
}

nearest_sample_match <- function(proxy, match_col, source_table, source_file, value_cols, sample_key = sample_lookup) {
  proxy <- copy(proxy)
  proxy[, site_id := core_to_site(core)]
  proxy[, match_value := as.numeric(get(match_col))]
  proxy <- proxy[!is.na(match_value) & is.finite(match_value)]
  if (nrow(proxy) == 0) return(data.table())

  pieces <- lapply(split(proxy, by = "core", drop = TRUE), function(part) {
    core_id <- unique(part$core)
    sam <- sample_key[core == core_id]
    if (nrow(sam) == 0) return(NULL)
    target <- as.numeric(sam[[match_col]])
    target <- target[is.finite(target)]
    if (length(target) == 0) return(NULL)
    nearest_idx <- vapply(part$match_value, function(v) {
      which.min(abs(target - v))
    }, integer(1))
    matched <- copy(part)
    matched[, `:=`(
      sample_id = sam$sample_id[nearest_idx],
      site_id = sam$site_id[nearest_idx],
      matched_core = sam$core[nearest_idx],
      sample_match_value = target[nearest_idx],
      match_delta = abs(match_value - target[nearest_idx]),
      y_bp = sam$y_bp[nearest_idx],
      depth_in_core_cm = sam$depth_in_core_cm[nearest_idx],
      age_kyr = sam$age_kyr[nearest_idx]
    )]
    if (length(value_cols) > 0) {
      keep_cols <- intersect(value_cols, names(matched))
      long <- melt(
        matched,
        id.vars = intersect(c("sample_id", "site_id", "core", "y_bp", "depth_in_core_cm", "age_kyr", "match_delta", "sample_match_value"), names(matched)),
        measure.vars = keep_cols,
        variable.name = "variable",
        value.name = "value",
        na.rm = FALSE
      )
    } else {
      long <- data.table()
    }
    if (nrow(long) == 0) return(NULL)
    long[, dataset_id := paste0("dataset:", source_table)]
    long[, `:=`(
      source_table = source_table,
      source_file = source_file,
      match_method = ifelse(match_col == "y_bp", "nearest_age", "nearest_depth"),
      match_delta = match_delta
    )]
    long[is.finite(as.numeric(value))]
  })
  rbindlist(pieces, fill = TRUE)
}

long_measurements <- list()

meta_numeric <- c("depth_in_core_cm", "y_bp", "library_concentration", "temp", "mis", "initial", "avg_leng_initial", "derep", "avg_len_derep", "sst")
meta_meas <- direct_measurements(sample_meta, "sample_id", meta_numeric, "metadata_v5", "Source/ROCS/data/metadata_v5.tsv")
meta_meas[, measurement_group := "sample_metadata"]
long_measurements[[length(long_measurements) + 1]] <- meta_meas

sst <- read_src("Source/ROCS/data/combined_sst_proxies_separate_columns.csv")
sst_meas <- nearest_sample_match(
  sst,
  "depth_in_core_cm",
  "sst_proxies",
  "Source/ROCS/data/combined_sst_proxies_separate_columns.csv",
  c("sst_uk37_alkenone", "sst_mgca_jonkers_2013", "sst_mgca_kozdon_2009")
)
sst_meas[, measurement_group := "sst_proxy"]
long_measurements[[length(long_measurements) + 1]] <- sst_meas

foram <- read_src("Source/ROCS/data/combined_foraminifera_geochem.tsv")
foram_value_cols <- setdiff(names(foram), c("core", "depth_in_core_cm", "y_bp"))
foram_meas <- nearest_sample_match(
  foram,
  "y_bp",
  "foraminifera_geochem",
  "Source/ROCS/data/combined_foraminifera_geochem.tsv",
  foram_value_cols
)
foram_meas[, measurement_group := "foraminifera"]
long_measurements[[length(long_measurements) + 1]] <- foram_meas

geob <- read_src("Source/ROCS/data/geob25202_clean_proxies.tsv")
geob_value_cols <- setdiff(names(geob), c("core", "depth_in_core_cm", "y_bp"))
geob_meas <- nearest_sample_match(
  geob,
  "y_bp",
  "geob25202_proxies",
  "Source/ROCS/data/geob25202_clean_proxies.tsv",
  geob_value_cols
)
geob_meas[, measurement_group := "geob25202"]
long_measurements[[length(long_measurements) + 1]] <- geob_meas

xrf <- read_src("Source/ROCS/data/combined_xrf_geochemistry_not_normalized.csv")
xrf[, `:=`(
  ratio_ca_ti = ca / ti,
  ratio_ba_ti = ba / ti,
  ratio_rb_sr = rb / sr,
  ratio_k_ti = k / ti,
  ratio_mn_fe = mn / fe,
  ratio_ti_al = ti / al,
  ratio_zr_rb = zr / rb,
  ratio_ti_ca = ti / ca,
  ratio_fe_al = fe / al,
  ratio_fe_ca = fe / ca,
  ratio_zr_al = sqrt(zr / al),
  ratio_mn_ti = mn / ti,
  ratio_mo_ti = sqrt(mo) / ti,
  ratio_si_ti = si / ti,
  ratio_br_ti = br / ti,
  ratio_p_ti = p / ti
)]
xrf_value_cols <- c(
  "ag", "al", "ar", "as", "at", "ba", "bi", "br", "ca", "cd", "ce", "cl", "cr", "cu", "er", "eu",
  "fe", "ga", "ge", "hf", "hg", "k", "la", "mg", "mn", "mo", "nb", "nd", "ni", "p", "pb", "rb",
  "rb_sr", "rh", "ru", "s", "sb", "se", "si", "sm", "sn", "sr", "te", "th", "ti", "tm", "u", "v",
  "y", "yb", "zn", "zr",
  "ratio_ca_ti", "ratio_ba_ti", "ratio_rb_sr", "ratio_k_ti", "ratio_mn_fe", "ratio_ti_al",
  "ratio_zr_rb", "ratio_ti_ca", "ratio_fe_al", "ratio_fe_ca", "ratio_zr_al", "ratio_mn_ti",
  "ratio_mo_ti", "ratio_si_ti", "ratio_br_ti", "ratio_p_ti"
)
xrf_meas <- nearest_sample_match(
  xrf,
  "y_bp",
  "xrf_geochemistry",
  "Source/ROCS/data/combined_xrf_geochemistry_not_normalized.csv",
  intersect(xrf_value_cols, names(xrf))
)
xrf_meas[, measurement_group := "xrf_geochemistry"]
long_measurements[[length(long_measurements) + 1]] <- xrf_meas

dmg <- read_src("Source/ROCS/results/microbial/damage/damage-classification-depositional/sample-baselines.tsv")
dmg_meas <- direct_measurements(
  dmg,
  "label",
  c("sample_A_b_median", "sample_A_b_iqr", "sample_Zfit_median", "sample_Zfit_iqr", "sample_rho_median", "sample_rho_iqr", "sample_local_fixed_rate", "low_damage_index"),
  "damage_baselines",
  "Source/ROCS/results/microbial/damage/damage-classification-depositional/sample-baselines.tsv"
)
dmg_meas[, measurement_group := "damage_baseline"]
long_measurements[[length(long_measurements) + 1]] <- dmg_meas

measurement_dt <- rbindlist(long_measurements, fill = TRUE, use.names = TRUE)
measurement_dt <- measurement_dt[!is.na(value) & is.finite(as.numeric(value))]
measurement_dt[, value := as.numeric(value)]

measurement_summary <- measurement_dt[, .(
  value = mean(value, na.rm = TRUE),
  value_sd = sd(value, na.rm = TRUE),
  value_min = min(value, na.rm = TRUE),
  value_max = max(value, na.rm = TRUE),
  match_delta = mean(match_delta, na.rm = TRUE),
  n_observations = .N
), by = .(
  measurement_group,
  dataset_id,
  source_table,
  source_file,
  sample_id,
  site_id,
  core,
  variable,
  match_method
)]
measurement_summary[, `:=`(
  node_id = paste("measurement", measurement_group, sample_id, variable, sep = ":"),
  node_type = "ProxyMeasurement",
  label = paste(variable, "@", sample_id),
  branch = NG$branch
)]

variable_nodes <- unique(measurement_summary[, .(
  node_id = paste("variable", variable, sep = ":"),
  node_type = "ProxyVariable",
  label = variable,
  variable = variable,
  branch = NG$branch
)], by = "node_id")

analysis_nodes <- data.table(
  node_id = c(
    "analysis:kg_import_v0",
    paste("analysis:ngraph", kg_threshold_label, kg_method_label, sep = ":")
  ),
  node_type = c("AnalysisRun", "AnalysisRun"),
  label = c("KG import v0", paste("NGraph deep knowledge", kg_threshold_label, kg_method_label)),
  branch = NG$branch
)

dataset_nodes <- unique(dataset_sources[, .(
  node_id = dataset_id,
  node_type = "Dataset",
  label = label,
  source_file = source_file,
  branch = NG$branch
)], by = "node_id")

ontology_terms <- data.table(
  ontology_term_id = c(
    "ontology:RO",
    "ontology:PROV-O",
    "ontology:ENVO",
    "ontology:MIxS",
    "ontology:NCBI_Taxonomy",
    "ontology:GTDB",
    "ontology:GO",
    "ontology:ChEBI",
    "ontology:KEGG",
    "ontology:MetaCyc"
  ),
  ontology_prefix = c("RO", "PROV-O", "ENVO", "MIxS", "NCBI Taxonomy", "GTDB", "GO", "ChEBI", "KEGG", "MetaCyc"),
  ontology_name = c(
    "Relation Ontology",
    "W3C PROV-O",
    "Environment Ontology",
    "MIxS / GSC metadata",
    "NCBI Taxonomy",
    "Genome Taxonomy Database",
    "Gene Ontology",
    "Chemical Entities of Biological Interest",
    "KEGG",
    "MetaCyc"
  ),
  ontology_scope = c(
    "relational predicates",
    "provenance",
    "environmental context",
    "sample metadata",
    "taxonomy",
    "taxonomy",
    "gene function",
    "compound",
    "pathway/function",
    "pathway/function"
  ),
  mapped_node_types = c(
    "edge predicates",
    "Dataset; AnalysisRun; ProxyMeasurement",
    "Site; Sample; ProxyMeasurement",
    "Sample",
    "Taxon",
    "Taxon",
    "Taxon; Module",
    "ProxyMeasurement; ProxyVariable",
    "Taxon; Module",
    "Taxon; Module"
  ),
  mapping_status = "planned",
  notes = c(
    "Reusable typed relations for future KG predicates.",
    "Capture provenance for imported measurements and learned edges.",
    "Environmental and site descriptors.",
    "Core sequencing and sample context metadata.",
    "Canonical taxonomy reference for taxon nodes.",
    "Alternative genome-centric taxonomic normalization.",
    "Functional and biological process labels.",
    "Compound/metabolite mapping for proxy and future BGC work.",
    "Pathway and function mapping for taxon/module annotations.",
    "Pathway and function mapping for taxon/module annotations."
  ),
  branch = NG$branch
)

ontology_nodes <- ontology_terms[, .(
  node_id = ontology_term_id,
  node_type = "OntologyTerm",
  label = ontology_name,
  ontology_prefix,
  ontology_scope,
  branch = NG$branch
)]

site_nodes <- copy(site_lookup)
site_nodes[, `:=`(
  node_id = paste0("site:", site_id),
  node_type = "Site",
  label = site_label,
  branch = NG$branch
)]

taxon_modules_path <- file.path(module_root, "tables", "vgae_taxon_modules.tsv")
diffpool_modules_path <- file.path(module_root, "tables", "diffpool_consensus_modules.tsv")
taxon_nodes_path <- file.path(module_root, "tables", "hetero_taxon_nodes.tsv")

if (!file.exists(taxon_modules_path) || !file.exists(diffpool_modules_path) || !file.exists(taxon_nodes_path)) {
  stop("Missing branch module artifacts; run the NGraph pipeline first.")
}

vgae_modules <- fread(taxon_modules_path)
diffpool_modules <- fread(diffpool_modules_path)
taxon_meta <- fread(taxon_nodes_path)

if (!"taxon" %in% names(taxon_meta)) {
  stop("Taxon metadata table lacks expected taxon column.")
}

taxon_nodes <- unique(taxon_meta[, .(
  node_id = paste0("taxon:", taxon),
  node_type = "Taxon",
  label = taxon,
  taxon = taxon,
  domain,
  phylum,
  class,
  functional_group,
  ecological_role,
  tea_primary,
  guild_tier,
  branch = NG$branch
)], by = "node_id")

vgae_nodes <- unique(vgae_modules[, .(
  node_id = paste0("module:vgae:", module_kmeans),
  node_type = "Module",
  label = paste("VGAE", module_kmeans),
  module_id = module_kmeans,
  module_system = "vgae",
  branch = NG$branch
)], by = "node_id")

diffpool_nodes <- unique(diffpool_modules[, .(
  node_id = paste0("module:diffpool:", consensus_module),
  node_type = "Module",
  label = paste("DiffPool", consensus_module),
  module_id = consensus_module,
  module_system = "diffpool",
  branch = NG$branch
)], by = "node_id")

taxon_module_edges_vgae <- merge(
  vgae_modules,
  taxon_nodes[, .(taxon, node_id)],
  by = "taxon",
  all.x = TRUE
)
taxon_module_edges_vgae <- taxon_module_edges_vgae[, .(
  edge_id = paste("edge", "taxon_member_of_module", taxon, module_kmeans, sep = ":"),
  edge_type = "taxon_member_of_module",
  source_id = paste0("taxon:", taxon),
  target_id = paste0("module:vgae:", module_kmeans),
  source_node_type = "Taxon",
  target_node_type = "Module",
  weight = 1,
  source_table = "vgae_taxon_modules.tsv",
  source_file = taxon_modules_path,
  branch = NG$branch,
  module_system = "vgae",
  threshold = kg_threshold_label,
  method = kg_method_label,
  evidence = paste("module_kmeans", module_kmeans),
  analysis = "vgae"
)]

taxon_module_edges_diffpool <- diffpool_modules[, .(
  edge_id = paste("edge", "taxon_member_of_module", taxon, consensus_module, sep = ":"),
  edge_type = "taxon_member_of_module",
  source_id = paste0("taxon:", taxon),
  target_id = paste0("module:diffpool:", consensus_module),
  source_node_type = "Taxon",
  target_node_type = "Module",
  weight = 1,
  source_table = "diffpool_consensus_modules.tsv",
  source_file = diffpool_modules_path,
  branch = NG$branch,
  module_system = "diffpool",
  threshold = kg_threshold_label,
  method = kg_method_label,
  evidence = paste("consensus_module", consensus_module),
  analysis = "diffpool"
)]

sample_taxon_path <- file.path(NG$deep_knowledge, "tables", "sample_taxon_abundance_long.tsv")
sample_clr_path <- file.path(NG$deep_knowledge, "tables", "sample_taxon_clr_long.tsv")
if (!file.exists(sample_taxon_path) || !file.exists(sample_clr_path)) {
  stop("Missing sample taxon discovery tables; run the deep knowledge discovery step first.")
}

sample_abund <- fread(sample_taxon_path)
sample_clr <- fread(sample_clr_path)
sample_taxon <- merge(sample_abund, sample_clr[, .(sample, taxon, clr)], by = c("sample", "taxon"), all.x = TRUE)
sample_taxon[, `:=`(
  site_id = core_to_site(core),
  sample_id = sample,
  abundance = as.numeric(abundance),
  clr = as.numeric(clr)
)]
sample_taxon <- sample_taxon[abundance > 0]
sample_taxon_edges <- sample_taxon[, .(
  edge_id = paste("edge", "sample_observed_taxon", sample_id, taxon, sep = ":"),
  edge_type = "sample_observed_taxon",
  source_id = sample_id,
  target_id = paste0("taxon:", taxon),
  source_node_type = "Sample",
  target_node_type = "Taxon",
  weight = pmin(1, log1p(abundance) / 10),
  source_table = "sample_taxon_abundance",
  source_file = sample_taxon_path,
  branch = NG$branch,
  core = core,
  site_id = site_id,
  value = abundance,
  abundance = abundance,
  clr = clr,
  analysis = "sample_taxon_abundance"
), by = .(sample_id, taxon, core, site_id, abundance, clr)]

sample_site_edges <- sample_nodes[, .(
  edge_id = paste("edge", "site_has_sample", site_id, node_id, sep = ":"),
  edge_type = "site_has_sample",
  source_id = paste0("site:", site_id),
  target_id = node_id,
  source_node_type = "Site",
  target_node_type = "Sample",
  weight = 1,
  source_table = "metadata_v5.tsv",
  source_file = "Source/ROCS/data/metadata_v5.tsv",
  branch = NG$branch,
  core = core,
  sample_id = node_id,
  analysis = "metadata_import"
)]

measurement_nodes <- measurement_summary[, .(
  node_id,
  node_type,
  label,
  dataset_id,
  source_table,
  source_file,
  sample_id,
  site_id,
  core,
  variable,
  measurement_group,
  value,
  value_sd,
  value_min,
  value_max,
  match_delta,
  n_observations,
  branch
)]

measurement_edges <- rbindlist(list(
  measurement_summary[, .(
    edge_id = paste("edge", "sample_has_measurement", sample_id, node_id, sep = ":"),
    edge_type = "sample_has_measurement",
    source_id = sample_id,
    target_id = node_id,
    source_node_type = "Sample",
    target_node_type = "ProxyMeasurement",
    weight = 1,
    source_table,
    source_file,
    branch,
    site_id,
    core,
    variable,
    value,
    analysis = "proxy_import"
  )],
  measurement_summary[, .(
    edge_id = paste("edge", "measurement_of_variable", node_id, paste0("variable:", variable), sep = ":"),
    edge_type = "measurement_of_variable",
    source_id = node_id,
    target_id = paste0("variable:", variable),
    source_node_type = "ProxyMeasurement",
    target_node_type = "ProxyVariable",
    weight = 1,
    source_table,
    source_file,
    branch,
    site_id,
    core,
    variable,
    value,
    analysis = "proxy_import"
  )],
  measurement_summary[, .(
    edge_id = paste("edge", "measurement_derived_from_dataset", node_id, source_table, sep = ":"),
    edge_type = "measurement_derived_from_dataset",
    source_id = node_id,
    target_id = dataset_id,
    source_node_type = "ProxyMeasurement",
    target_node_type = "Dataset",
    weight = 1,
    source_table,
    source_file,
    branch,
    site_id,
    core,
    variable,
    value,
    analysis = "proxy_import"
  )]
), fill = TRUE)

site_taxon_presence <- unique(sample_taxon[, .(site_id, taxon)])
module_lookup <- rbindlist(list(
  taxon_module_edges_vgae[, .(taxon = sub("^taxon:", "", source_id), module_id = target_id, module_system)],
  taxon_module_edges_diffpool[, .(taxon = sub("^taxon:", "", source_id), module_id = target_id, module_system)]
), fill = TRUE)
site_taxon_module <- merge(
  site_taxon_presence,
  module_lookup,
  by = "taxon",
  all = FALSE,
  allow.cartesian = TRUE
)
site_taxon_module <- unique(site_taxon_module, by = c("site_id", "taxon", "module_id", "module_system"))
site_totals <- site_taxon_module[, .(site_taxa = uniqueN(taxon)), by = site_id]
site_module_edges <- site_taxon_module[, .(
  taxa_in_module = uniqueN(taxon)
), by = .(site_id, module_id, module_system)]
site_module_edges <- merge(site_module_edges, site_totals, by = "site_id", all.x = TRUE)
site_module_edges[, `:=`(
  edge_id = paste("edge", "site_has_module_enrichment", site_id, module_id, module_system, sep = ":"),
  edge_type = "site_has_module_enrichment",
  source_id = paste0("site:", site_id),
  target_id = module_id,
  source_node_type = "Site",
  target_node_type = "Module",
  weight = pmin(1, taxa_in_module / pmax(1, site_taxa)),
  source_table = "sample_taxon_abundance",
  source_file = sample_taxon_path,
  branch = NG$branch,
  analysis = "site_module_enrichment"
)]

ontology_edges <- rbindlist(list(
  data.table(
    edge_id = paste("edge", "entity_has_ontology_term", site_nodes$node_id, "ontology:ENVO", sep = ":"),
    edge_type = "entity_has_ontology_term",
    source_id = site_nodes$node_id,
    target_id = "ontology:ENVO",
    source_node_type = "Site",
    target_node_type = "OntologyTerm",
    weight = 1,
    branch = NG$branch,
    analysis = "ontology_mapping"
  ),
  data.table(
    edge_id = paste("edge", "entity_has_ontology_term", sample_nodes$node_id, "ontology:MIxS", sep = ":"),
    edge_type = "entity_has_ontology_term",
    source_id = sample_nodes$node_id,
    target_id = "ontology:MIxS",
    source_node_type = "Sample",
    target_node_type = "OntologyTerm",
    weight = 1,
    branch = NG$branch,
    analysis = "ontology_mapping"
  ),
  data.table(
    edge_id = paste("edge", "entity_has_ontology_term", taxon_nodes$node_id, "ontology:NCBI_Taxonomy", sep = ":"),
    edge_type = "entity_has_ontology_term",
    source_id = taxon_nodes$node_id,
    target_id = "ontology:NCBI_Taxonomy",
    source_node_type = "Taxon",
    target_node_type = "OntologyTerm",
    weight = 1,
    branch = NG$branch,
    analysis = "ontology_mapping"
  ),
  data.table(
    edge_id = paste("edge", "entity_has_ontology_term", unique(measurement_nodes$node_id), "ontology:PROV-O", sep = ":"),
    edge_type = "entity_has_ontology_term",
    source_id = unique(measurement_nodes$node_id),
    target_id = "ontology:PROV-O",
    source_node_type = "ProxyMeasurement",
    target_node_type = "OntologyTerm",
    weight = 1,
    branch = NG$branch,
    analysis = "ontology_mapping"
  )
), fill = TRUE)

kg_nodes <- rbindlist(list(
  site_nodes,
  sample_nodes,
  taxon_nodes,
  vgae_nodes,
  diffpool_nodes,
  measurement_nodes,
  variable_nodes,
  dataset_nodes,
  analysis_nodes,
  ontology_nodes
), fill = TRUE, use.names = TRUE)
kg_nodes <- unique(kg_nodes, by = "node_id")

kg_edges <- rbindlist(list(
  sample_site_edges,
  sample_taxon_edges,
  taxon_module_edges_vgae,
  taxon_module_edges_diffpool,
  site_module_edges,
  measurement_edges,
  ontology_edges
), fill = TRUE, use.names = TRUE)
kg_edges <- unique(kg_edges, by = "edge_id")

kg_measurements <- copy(measurement_summary)
kg_measurements[, measurement_id := node_id]

kg_ontology_terms <- copy(ontology_terms)

fwrite(kg_nodes, file.path(kg_dirs$tables, "kg_nodes.tsv"), sep = "\t")
fwrite(kg_edges, file.path(kg_dirs$tables, "kg_edges.tsv"), sep = "\t")
fwrite(kg_measurements, file.path(kg_dirs$tables, "kg_measurements.tsv"), sep = "\t")
fwrite(kg_ontology_terms, file.path(kg_dirs$tables, "kg_ontology_terms.tsv"), sep = "\t")
fwrite(site_lookup, file.path(kg_dirs$tables, "kg_sites.tsv"), sep = "\t")
fwrite(dataset_sources, file.path(kg_dirs$tables, "kg_datasets.tsv"), sep = "\t")

kg_manifest <- list(
  generated = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
  branch = NG$branch,
  seed = NG_PARAMS$seed,
  source_branch = list(
    deep_knowledge_primary_threshold = kg_threshold_label,
    deep_knowledge_primary_method = kg_method_label
  ),
  source_files = dataset_sources[, .(dataset_id, label, source_file)],
  counts = list(
    nodes = nrow(kg_nodes),
    edges = nrow(kg_edges),
    measurements = nrow(kg_measurements),
    ontology_terms = nrow(kg_ontology_terms),
    site_nodes = nrow(site_nodes),
    sample_nodes = nrow(sample_nodes),
    taxon_nodes = nrow(taxon_nodes),
    module_nodes = nrow(vgae_nodes) + nrow(diffpool_nodes)
  ),
  node_types = sort(unique(as.character(kg_nodes$node_type))),
  edge_types = sort(unique(as.character(kg_edges$edge_type))),
  site_ids = site_lookup$site_id,
  import_strategy = list(
    sample_matching = "nearest label/depth/age within core",
    taxon_modules = "current NGraph deep module artifacts",
    ontology = "namespace-level mapping inventory"
  ),
  files = list(
    nodes = "kg_nodes.tsv",
    edges = "kg_edges.tsv",
    measurements = "kg_measurements.tsv",
    ontology_terms = "kg_ontology_terms.tsv"
  )
)
write_json(kg_manifest, file.path(kg_dirs$root, "kg_manifest.json"), auto_unbox = TRUE, pretty = TRUE)

report_path <- file.path(kg_dirs$reports, "KG_SCHEMA_AND_IMPORT_REPORT.md")
report_text <- c(
  "# KG Schema and Import Report",
  "",
  "## Summary",
  "",
  sprintf("- Branch: `%s`", NG$branch),
  sprintf("- Generated: `%s`", kg_manifest$generated),
  sprintf("- Nodes: `%s`", format(nrow(kg_nodes), big.mark = ",")),
  sprintf("- Edges: `%s`", format(nrow(kg_edges), big.mark = ",")),
  sprintf("- Measurements: `%s`", format(nrow(kg_measurements), big.mark = ",")),
  "",
  "## Source Tables",
  "",
  paste0("- `", dataset_sources$source_file, "`"),
  "",
  "## Node Types",
  "",
  paste0("- `", sort(unique(as.character(kg_nodes$node_type))), "`"),
  "",
  "## Edge Types",
  "",
  paste0("- `", sort(unique(as.character(kg_edges$edge_type))), "`"),
  "",
  "## Notes",
  "",
  "- Site coordinates are encoded directly from the trial metadata supplied in the conversation.",
  "- Proxy measurements are linked to the nearest sample within the same core using age or depth, depending on the source table.",
  "- Current NGraph module assignments are imported as `Taxon -> Module` edges.",
  "- Ontology linking is currently namespace-level and remains a planning inventory rather than a full reasoning layer.",
  "- The importer writes branch-scoped TSV/JSON artifacts only; no external database is required for v0."
)
writeLines(report_text, report_path)

ng_log(LOG, "KG nodes: ", nrow(kg_nodes))
ng_log(LOG, "KG edges: ", nrow(kg_edges))
ng_log(LOG, "KG measurements: ", nrow(kg_measurements))
ng_log(LOG, "KG ontology terms: ", nrow(kg_ontology_terms))
ng_log(LOG, "Method Validated: KG import artifacts written")
ng_log(LOG, "Complete")
