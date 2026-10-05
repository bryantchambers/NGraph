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
    "data/metadata/metadata_v5.tsv",
    "data/kg_feedstock/combined_sst_proxies_separate_columns.csv",
    "data/kg_feedstock/combined_foraminifera_geochem.tsv",
    "data/kg_feedstock/geob25202_clean_proxies.tsv",
    "data/kg_feedstock/combined_xrf_geochemistry_curated.csv",
    "data/kg_feedstock/sample-baselines.tsv",
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

sample_meta <- read_src("data/metadata/metadata_v5.tsv")
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
  source_file = "data/metadata/metadata_v5.tsv",
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
  dt[, source_row := seq_len(.N)]
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
    id.vars = intersect(c("source_row", "sample_id", "site_id", "core", "label", "y_bp", "depth_in_core_cm", "age_kyr", "mis"), names(dt)),
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

source("scripts/ngraph_proxy_matching.R")
proxy_matching_results <- list()
nearest_sample_match <- function(proxy, match_col, source_table, source_file, value_cols, sample_key = sample_lookup) {
  # Compatibility wrapper: all source tables now match physical core and depth.
  result <- match_proxy_depth(proxy, sample_key, value_cols, source_table, source_file,
    tolerance_cm = 0.5, gap_factor = as.numeric(Sys.getenv("NG_KG_LARGE_GAP_FACTOR", "3")))
  proxy_matching_results[[source_table]] <<- result
  result$values
}

long_measurements <- list()

meta_numeric <- c("depth_in_core_cm", "y_bp", "library_concentration", "temp", "mis", "initial", "avg_leng_initial", "derep", "avg_len_derep", "sst")
meta_meas <- direct_measurements(sample_meta, "sample_id", meta_numeric, "metadata_v5", "data/metadata/metadata_v5.tsv")
meta_meas[, measurement_group := "sample_metadata"]
long_measurements[[length(long_measurements) + 1]] <- meta_meas

sst <- read_src("data/kg_feedstock/combined_sst_proxies_separate_columns.csv")
sst_meas <- nearest_sample_match(
  sst,
  "depth_in_core_cm",
  "sst_proxies",
  "data/kg_feedstock/combined_sst_proxies_separate_columns.csv",
  c("sst_uk37_alkenone", "sst_mgca_jonkers_2013", "sst_mgca_kozdon_2009")
)
sst_meas[, measurement_group := "sst_proxy"]
long_measurements[[length(long_measurements) + 1]] <- sst_meas

foram <- read_src("data/kg_feedstock/combined_foraminifera_geochem.tsv")
foram_value_cols <- setdiff(names(foram), c("core", "depth_in_core_cm", "y_bp"))
foram_meas <- nearest_sample_match(
  foram,
  "y_bp",
  "foraminifera_geochem",
  "data/kg_feedstock/combined_foraminifera_geochem.tsv",
  foram_value_cols
)
foram_meas[, measurement_group := "foraminifera"]
long_measurements[[length(long_measurements) + 1]] <- foram_meas

geob <- read_src("data/kg_feedstock/geob25202_clean_proxies.tsv")
geob_value_cols <- setdiff(names(geob), c("core", "depth_in_core_cm", "y_bp"))
geob_meas <- nearest_sample_match(
  geob,
  "y_bp",
  "geob25202_proxies",
  "data/kg_feedstock/geob25202_clean_proxies.tsv",
  geob_value_cols
)
geob_meas[, measurement_group := "geob25202"]
long_measurements[[length(long_measurements) + 1]] <- geob_meas

xrf <- read_src("data/kg_feedstock/combined_xrf_geochemistry_curated.csv")
# Preserve curated native measurements and ratios; do not regenerate uncurated ratios.
xrf_value_cols <- setdiff(names(xrf), c("core", "depth_in_core_cm", "y_bp"))
xrf_meas <- nearest_sample_match(
  xrf,
  "y_bp",
  "xrf_geochemistry",
  "data/kg_feedstock/combined_xrf_geochemistry_curated.csv",
  intersect(xrf_value_cols, names(xrf))
)
xrf_meas[, measurement_group := "xrf_geochemistry"]
long_measurements[[length(long_measurements) + 1]] <- xrf_meas

dmg <- read_src("data/kg_feedstock/sample-baselines.tsv")
dmg_meas <- direct_measurements(
  dmg,
  "label",
  c("sample_A_b_median", "sample_A_b_iqr", "sample_Zfit_median", "sample_Zfit_iqr", "sample_rho_median", "sample_rho_iqr", "sample_local_fixed_rate", "low_damage_index"),
  "damage_baselines",
  "data/kg_feedstock/sample-baselines.tsv"
)
dmg_meas[, measurement_group := "damage_baseline"]
long_measurements[[length(long_measurements) + 1]] <- dmg_meas

measurement_dt <- rbindlist(long_measurements, fill = TRUE, use.names = TRUE)
measurement_dt <- measurement_dt[!is.na(value) & is.finite(as.numeric(value))]
measurement_dt[, value := as.numeric(value)]

measurement_dt[, observation_id := paste0("observation:", NG$branch, ":", seq_len(.N))]
unit_registry <- fread("config_kg_units.tsv")
measurement_dt[, `:=`(unit = "unspecified_native_unit", unit_status = "unresolved", unit_evidence = "No unit declaration in source")]
measurement_dt[unit_registry, on = "variable", `:=`(unit = i.unit, unit_status = i.unit_status, unit_evidence = i.unit_evidence)]
measurement_dt[, matching_policy_status := fifelse(match_method == "direct_sample", "direct_sample", "user_confirmed_depth_policy")]
coverage <- rbindlist(lapply(proxy_matching_results, function(x) x$coverage), fill = TRUE)
raw_proxy <- rbindlist(lapply(proxy_matching_results, function(x) x$source_observations), fill = TRUE)
raw_proxy[, `:=`(unit = "unspecified_native_unit", unit_status = "unresolved")]
raw_proxy[unit_registry, on = "variable", `:=`(unit = i.unit, unit_status = i.unit_status)]
fwrite(raw_proxy, file.path(kg_dirs$tables, "kg_proxy_source_observations.tsv"), sep = "\t")
fwrite(coverage, file.path(kg_dirs$tables, "kg_proxy_matching_coverage.tsv"), sep = "\t")
fwrite(coverage[matched == FALSE], file.path(kg_dirs$tables, "kg_unmatched_proxy_observations.tsv"), sep = "\t")
fwrite(unit_registry, file.path(kg_dirs$tables, "kg_variable_units.tsv"), sep = "\t")
coverage_summary <- coverage[, .(requested = .N, matched = sum(matched), unmatched = sum(!matched)), by = .(source_table, physical_core, variable)]
fwrite(coverage_summary, file.path(kg_dirs$tables, "kg_import_coverage.tsv"), sep = "\t")
fwrite(measurement_dt, file.path(kg_dirs$tables, "kg_observations.tsv"), sep = "\t")

for (col in c("bracket_width_cm", "large_gap", "source_observation_ids_left", "source_observation_ids_right")) {
  if (!col %in% names(measurement_dt)) measurement_dt[, (col) := NA]
}
measurement_summary <- measurement_dt[, .(
  observation_ids = paste(observation_id, collapse = ","),
  unit = unit[1], unit_status = unit_status[1], unit_evidence = unit_evidence[1],
  bracket_width_cm = if (all(is.na(bracket_width_cm))) NA_real_ else max(bracket_width_cm, na.rm = TRUE),
  large_gap = any(large_gap %in% TRUE),
  source_observation_ids = paste(unique(unlist(strsplit(paste(na.omit(c(source_observation_ids_left, source_observation_ids_right)), collapse = ","), ","))), collapse = ","),
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
  unit, unit_status, unit_evidence,
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
full_taxa_path <- file.path(ng_threshold_dirs(as.integer(sub("prev_", "", kg_threshold_label)))$tables, "ngraph_taxa_metadata.tsv")
retention_path <- file.path(dirname(full_taxa_path), "ngraph_taxon_retention.tsv")
if (file.exists(full_taxa_path)) taxon_meta <- unique(rbindlist(list(taxon_meta, fread(full_taxa_path)), fill = TRUE), by = "taxon")
taxon_meta[, evidence_status := "tad_supported"]
if (file.exists(retention_path)) {
  retention <- fread(retention_path)
  taxon_meta[retention, on = c(taxon = "subspecies"), evidence_status := i.evidence_status]
}

if (!"taxon" %in% names(taxon_meta)) {
  stop("Taxon metadata table lacks expected taxon column.")
}

taxon_nodes <- unique(taxon_meta[, .(
  node_id = paste0("taxon:", taxon),
  node_type = "Taxon",
  label = taxon,
  evidence_status,
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
  node_id = paste("module", NG$branch, kg_threshold_label, kg_method_label, "vgae", module_kmeans, sep = ":"),
  node_type = "Module",
  label = paste("VGAE", module_kmeans),
  module_id = module_kmeans,
  module_system = "vgae",
  branch = NG$branch
)], by = "node_id")

diffpool_nodes <- unique(diffpool_modules[, .(
  node_id = paste("module", NG$branch, kg_threshold_label, kg_method_label, "diffpool", consensus_module, sep = ":"),
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
  edge_id = paste("edge", "taxon_member_of_module", NG$branch, "vgae", taxon, module_kmeans, sep = ":"),
  edge_type = "taxon_member_of_module",
  source_id = paste0("taxon:", taxon),
  target_id = paste("module", NG$branch, kg_threshold_label, kg_method_label, "vgae", module_kmeans, sep = ":"),
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
  edge_id = paste("edge", "taxon_member_of_module", NG$branch, "diffpool", taxon, consensus_module, sep = ":"),
  edge_type = "taxon_member_of_module",
  source_id = paste0("taxon:", taxon),
  target_id = paste("module", NG$branch, kg_threshold_label, kg_method_label, "diffpool", consensus_module, sep = ":"),
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
support_file <- file.path(dirname(retention_path), "ngraph_taxon_read_support.tsv")
sample_taxon[, `:=`(abundance_tad = NA_real_, abundance_read = NA_real_)]
if (file.exists(support_file)) {
  support <- fread(support_file)
  sample_taxon[support, on = c("sample", "taxon"), `:=`(abundance_tad = i.abundance_tad, abundance_read = i.abundance_read)]
}
if (!"abundance_mode" %in% names(sample_taxon)) sample_taxon[, abundance_mode := "historical_unspecified"]
sample_taxon[, abundance_basis := fifelse(is.na(abundance_tad), "unspecified", fifelse(abundance_tad > 0, "TAD", "read_fallback"))]
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
  sample_id = sample_id,
  taxon = taxon,
  abundance_mode, abundance_basis, abundance_tad, abundance_read,
  analysis = "sample_taxon_abundance"
)]

control_contexts <- unique(sample_nodes[!site_id %in% site_lookup$site_id, .(site_id)])
control_nodes <- control_contexts[, .(node_id = paste0("control:", site_id), node_type = "ControlContext", label = site_id, branch = NG$branch)]
sample_site_edges <- sample_nodes[, .(
  edge_id = paste("edge", "site_has_sample", site_id, node_id, sep = ":"),
  edge_type = fifelse(site_id %in% site_lookup$site_id, "site_has_sample", "control_has_sample"),
  source_id = paste0(fifelse(site_id %in% site_lookup$site_id, "site:", "control:"), site_id),
  target_id = node_id,
  source_node_type = fifelse(site_id %in% site_lookup$site_id, "Site", "ControlContext"),
  target_node_type = "Sample",
  weight = 1,
  source_table = "metadata_v5.tsv",
  source_file = "data/metadata/metadata_v5.tsv",
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
  observation_ids,
  unit,
  unit_status,
  unit_evidence,
  bracket_width_cm,
  large_gap,
  source_observation_ids,
  match_method,
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
  control_nodes,
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

read_support_path <- file.path(dirname(retention_path), "ngraph_taxon_read_support.tsv")
read_support_edges <- data.table()
if (file.exists(read_support_path)) {
  rs <- fread(read_support_path)[abundance_read > 0 & sample %in% sample_nodes$node_id & taxon %in% taxon_nodes$taxon]
  read_support_edges <- rs[, .(edge_id = paste("edge", "sample_read_supported_taxon", sample, taxon, sep = ":"),
    edge_type = "sample_read_supported_taxon", source_id = sample, target_id = paste0("taxon:", taxon),
    source_node_type = "Sample", target_node_type = "Taxon", weight = 1, abundance_read, abundance_tad, n_reads,
    source_table = "ngraph_taxon_read_support.tsv", source_file = read_support_path, branch = NG$branch,
    evidence = "Damaged classification; >=100 reads per source row; read support distinct from TAD abundance")]
}
kg_edges <- rbindlist(list(
  read_support_edges,
  sample_site_edges,
  sample_taxon_edges,
  taxon_module_edges_vgae,
  taxon_module_edges_diffpool,
  site_module_edges,
  measurement_edges,
  ontology_edges
), fill = TRUE, use.names = TRUE)
kg_edges <- unique(kg_edges, by = "edge_id")
dangling <- kg_edges[!source_id %in% kg_nodes$node_id | !target_id %in% kg_nodes$node_id]
if (nrow(dangling)) stop("KG contains ", nrow(dangling), " dangling references")
if (anyDuplicated(names(kg_edges))) {
  for (col in unique(names(kg_edges)[duplicated(names(kg_edges))])) {
    idx <- which(names(kg_edges) == col)
    for (j in idx[-1]) if (!identical(kg_edges[[idx[1]]], kg_edges[[j]])) stop("Conflicting duplicate KG column: ", col)
  }
  kg_edges <- kg_edges[, !duplicated(names(kg_edges)), with = FALSE]
}
write_json(list(status = "structural_validation_passed", dangling_references = nrow(dangling),
  duplicate_node_ids = anyDuplicated(kg_nodes$node_id), duplicate_edge_ids = anyDuplicated(kg_edges$edge_id),
  units = "explicit_registry_with_unresolved_native_units", proxy_alias_policy = "GeoB25202_R1_and_R2_share_physical_core_by_depth",
  matching_policy = list(primary_key = "physical_core_and_depth_cm", within_level_tolerance_cm = 0.5,
    interpolation = "linear_between_bracketing_finite_continuous_values", extrapolation = FALSE,
    age_matching = "disabled_no_universal_age_tolerance", large_gap_factor = as.numeric(Sys.getenv("NG_KG_LARGE_GAP_FACTOR", "3")))),
  file.path(kg_dirs$tables, "kg_validation.json"), auto_unbox = TRUE, pretty = TRUE)

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
    sample_matching = "physical core and depth; within 0.5 cm or bracketed interpolation; no extrapolation",
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
  "- Proxy measurements use physical core/depth matching within 0.5 cm or bracketed interpolation without extrapolation; R1/R2 share a GeoB physical core. Large gaps and unresolved units are explicit.",
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
