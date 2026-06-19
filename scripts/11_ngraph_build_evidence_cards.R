#!/usr/bin/env Rscript
# 11_ngraph_build_evidence_cards.R -- build evidence cards and long-form context tables.

suppressPackageStartupMessages({
  library(data.table)
  library(jsonlite)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("11_ngraph_build_evidence_cards")
ng_start_log(LOG)
ng_log(LOG, "Starting evidence card generation")
ng_log(LOG, "Package versions: data.table ", as.character(utils::packageVersion("data.table")),
       ", jsonlite ", as.character(utils::packageVersion("jsonlite")))

primary_thr <- NG_PARAMS$deep_knowledge_primary_threshold
primary_method <- NG_PARAMS$deep_knowledge_primary_method
primary_dirs <- ng_deep_dirs(primary_thr, primary_method)
primary_thr_dirs <- ng_threshold_dirs(primary_thr)

discovery_root <- NG$deep_knowledge
dir.create(discovery_root, recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(discovery_root, "reports"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(discovery_root, "tables"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(discovery_root, "cards"), recursive = TRUE, showWarnings = FALSE)

safe_fread <- function(path) {
  if (!file.exists(path)) return(NULL)
  fread(path)
}

fmt_num <- function(x, digits = 2) {
  if (length(x) == 0) return(character())
  out <- ifelse(is.na(x), "NA", format(round(as.numeric(x), digits), nsmall = digits, trim = TRUE))
  out
}

slugify <- function(x) {
  gsub("^_|_$", "", gsub("[^A-Za-z0-9]+", "_", x))
}

top_counts <- function(dt, col, n = 5L) {
  if (!col %in% names(dt)) return("NA")
  vals <- dt[[col]]
  vals <- vals[!is.na(vals) & nzchar(as.character(vals))]
  if (length(vals) == 0) return("NA")
  freq <- sort(table(vals), decreasing = TRUE)
  top <- head(freq, n)
  paste0(names(top), " (", as.integer(top), ")", collapse = "; ")
}

make_card <- function(card_type, entity_id, title, summary, evidence, threshold = NA_character_,
                      method = NA_character_, core = NA_character_, taxon = NA_character_,
                      module = NA_character_, relation_type = NA_character_, score = NA_real_,
                      observed_status = NA_character_, source_tables = character()) {
  data.table(
    card_id = paste(card_type, slugify(entity_id), sep = "::"),
    card_type = card_type,
    entity_id = entity_id,
    title = title,
    summary = summary,
    evidence = evidence,
    threshold = threshold,
    method = method,
    core = core,
    taxon = taxon,
    module = module,
    relation_type = relation_type,
    score = score,
    observed_status = observed_status,
    source_tables = toJSON(source_tables, auto_unbox = TRUE)
  )
}

primary_taxon_nodes <- safe_fread(file.path(primary_dirs$tables, "hetero_taxon_nodes.tsv"))
primary_site_nodes <- safe_fread(file.path(primary_dirs$tables, "hetero_site_nodes.tsv"))
primary_taxon_taxon <- safe_fread(file.path(primary_dirs$tables, "hetero_taxon_taxon_edges.tsv"))
primary_taxon_site <- safe_fread(file.path(primary_dirs$tables, "hetero_taxon_site_edges.tsv"))
primary_site_graphs <- safe_fread(file.path(primary_thr_dirs$tables, "ngraph_site_graph_summary.tsv"))
primary_sample_qc <- safe_fread(file.path(primary_thr_dirs$tables, "ngraph_sample_qc.tsv"))
primary_abund <- readRDS(file.path(primary_thr_dirs$matrices, "ngraph_tax_abund_tad_taxa_by_sample.rds"))
primary_clr <- readRDS(file.path(primary_thr_dirs$matrices, "ngraph_clr_global.rds"))
primary_vgae <- safe_fread(file.path(primary_dirs$tables, "vgae_taxon_modules.tsv"))
primary_diffpool <- safe_fread(file.path(primary_dirs$tables, "diffpool_consensus_modules.tsv"))
primary_vgae_summary <- safe_fread(file.path(primary_dirs$tables, "vgae_run_summary.tsv"))
primary_diffpool_summary <- safe_fread(file.path(primary_dirs$tables, "diffpool_run_summary.tsv"))
link_prediction_summary <- safe_fread(file.path(discovery_root, "link_prediction_summary.tsv"))
link_prediction_top <- safe_fread(file.path(discovery_root, "link_prediction_top_candidates.tsv"))

if (is.null(primary_taxon_nodes) || is.null(primary_site_nodes) || is.null(primary_sample_qc)) {
  stop("Missing primary deep-module artifacts; run steps 06-10 first.")
}

sample_cards <- copy(primary_sample_qc)
if ("threshold" %in% names(sample_cards)) sample_cards[, threshold := NULL]
sample_cards[, `:=`(
  card_id = paste0("sample::", label),
  card_type = "sample",
  entity_id = label,
  title = paste0("Sample ", label, " from ", core),
  summary = paste0(
    "Sample ", label, " in core ", core, " at ", fmt_num(age_kyr, 1), " kya; MIS ", fmt_num(mis, 1),
    ", SST ", fmt_num(sst, 2), ", total TAD abundance ", fmt_num(total_tax_abund_tad, 2),
    ", detected taxa ", detected_taxa_tad, ", total reads ", total_n_reads
  ),
  evidence = paste0(
    "Observed metadata from data/metadata/metadata_v5.tsv and stage-1 QC from ",
    primary_thr_dirs$tables, "/ngraph_sample_qc.tsv"
  ),
  method = NA_character_,
  taxon = NA_character_,
  module = NA_character_,
  relation_type = NA_character_,
  score = NA_real_,
  observed_status = "observed",
  source_tables = toJSON(list(
    metadata = "data/metadata/metadata_v5.tsv",
    sample_qc = file.path(primary_thr_dirs$tables, "ngraph_sample_qc.tsv")
  ), auto_unbox = TRUE)
)]
sample_cards[, threshold := as.character(ng_threshold_label(primary_thr))]
sample_cards <- sample_cards[, .(
  card_id, card_type, entity_id, title, summary, evidence, threshold, method, core, taxon, module,
  relation_type, score, observed_status, source_tables
)]

site_summary <- copy(primary_sample_qc)[, .(
  samples = .N,
  age_min_kyr = min(age_kyr, na.rm = TRUE),
  age_max_kyr = max(age_kyr, na.rm = TRUE),
  age_mean_kyr = mean(age_kyr, na.rm = TRUE),
  mis_mean = mean(mis, na.rm = TRUE),
  mis_sd = sd(mis, na.rm = TRUE),
  sst_mean = mean(sst, na.rm = TRUE),
  sst_sd = sd(sst, na.rm = TRUE),
  total_tax_abund_tad = sum(total_tax_abund_tad, na.rm = TRUE),
  detected_taxa_tad = mean(detected_taxa_tad, na.rm = TRUE),
  total_n_reads = sum(total_n_reads, na.rm = TRUE),
  total_n_reads_tad = sum(total_n_reads_tad, na.rm = TRUE)
), by = core]
site_graph_primary <- primary_site_graphs[method_suffix == primary_method]
if (!is.null(site_graph_primary) && nrow(site_graph_primary) > 0) {
  site_graph_primary <- site_graph_primary[, .(
    core,
    site_nodes = nodes,
    site_edges = edges,
    site_density = density,
    site_components = components,
    site_threshold = threshold,
    site_method = method_suffix,
    top_variable_taxa
  )]
  site_summary <- merge(site_summary, site_graph_primary, by = "core", all.x = TRUE, sort = FALSE)
}

site_cards <- rbindlist(lapply(seq_len(nrow(site_summary)), function(i) {
  row <- site_summary[i]
  card_id <- paste0("site::", row$core)
  title <- paste0("Core ", row$core, " site profile")
  summary <- paste0(
    "Core ", row$core, " spans ", fmt_num(row$age_min_kyr, 1), " to ", fmt_num(row$age_max_kyr, 1),
    " kya (mean ", fmt_num(row$age_mean_kyr, 1), " kya) with ", row$samples,
    " samples, MIS ", fmt_num(row$mis_mean, 1), ", SST ", fmt_num(row$sst_mean, 2),
    ", graph density ", fmt_num(row$site_density, 4), " and ", row$site_components, " components under ",
    ng_threshold_label(primary_thr), "/", primary_method, "."
  )
  evidence <- paste0(
    "Observed site context from sample_qc plus site graph metrics from ",
    file.path(primary_dirs$tables, "ngraph_site_graph_summary.tsv")
  )
  make_card(
    card_type = "site",
    entity_id = row$core,
    title = title,
    summary = summary,
    evidence = evidence,
    threshold = ng_threshold_label(primary_thr),
    method = primary_method,
    core = row$core,
    observed_status = "observed",
    source_tables = c(
      file.path(primary_thr_dirs$tables, "ngraph_sample_qc.tsv"),
      file.path(primary_dirs$tables, "ngraph_site_graph_summary.tsv")
    )
  )
}), fill = TRUE)

taxon_meta <- copy(primary_taxon_nodes)
if (!is.null(primary_vgae)) {
  taxon_meta <- merge(taxon_meta, primary_vgae[, .(taxon, vgae_module = module_kmeans, vgae_entropy = module_entropy_proxy, vgae_module_count = module_count)],
                      by = "taxon", all.x = TRUE, sort = FALSE)
}
if (!is.null(primary_diffpool)) {
  taxon_meta <- merge(taxon_meta, primary_diffpool[, .(taxon, diffpool_module = consensus_module, diffpool_entropy = mean_assignment_entropy, diffpool_sites_present = sites_present)],
                      by = "taxon", all.x = TRUE, sort = FALSE)
}

link_support <- NULL
if (!is.null(link_prediction_top) && nrow(link_prediction_top) > 0) {
  if ("taxon_from" %in% names(link_prediction_top)) {
    from_counts <- link_prediction_top[, .(predicted_link_degree = .N, mean_predicted_link_score = mean(latent_score, na.rm = TRUE)),
                                      by = .(taxon = taxon_from)]
    to_counts <- link_prediction_top[, .(predicted_link_degree = .N, mean_predicted_link_score = mean(latent_score, na.rm = TRUE)),
                                    by = .(taxon = taxon_to)]
    link_support <- rbindlist(list(from_counts, to_counts), fill = TRUE)
    link_support <- link_support[, .(
      predicted_link_degree = sum(predicted_link_degree, na.rm = TRUE),
      mean_predicted_link_score = mean(mean_predicted_link_score, na.rm = TRUE)
    ), by = taxon]
  } else if ("taxon" %in% names(link_prediction_top)) {
    link_support <- link_prediction_top[, .(
      predicted_link_degree = .N,
      mean_predicted_link_score = mean(latent_score, na.rm = TRUE)
    ), by = taxon]
  }
}
if (!is.null(link_support)) {
  taxon_meta <- merge(taxon_meta, link_support, by = "taxon", all.x = TRUE, sort = FALSE)
}

taxon_cards <- rbindlist(lapply(seq_len(nrow(taxon_meta)), function(i) {
  row <- taxon_meta[i]
  functional_bits <- Filter(nzchar, c(
    paste0("functional group ", row$functional_group),
    paste0("ecological role ", row$ecological_role),
    paste0("primary TEA ", row$tea_primary),
    paste0("guild tier ", row$guild_tier),
    paste0("KEGG state ", row$kegg_state)
  ))
  summary <- paste0(
    row$taxon, " spans ", row$domain, " / ", row$phylum, " / ", row$class, "; ",
    paste(functional_bits, collapse = "; "), "; ",
    row$n_samples, " samples, ", row$n_cores, " cores, ",
    "VGAE module ", ifelse(is.na(row$vgae_module), "NA", row$vgae_module),
    ", DiffPool module ", ifelse(is.na(row$diffpool_module), "NA", row$diffpool_module),
    ", predicted-link degree ", ifelse(is.na(row$predicted_link_degree), 0, row$predicted_link_degree), "."
  )
  evidence <- paste0(
    "Observed functional metadata from data/reference/prokaryote_function_assigned.tsv; ",
    "heterograph features from ", file.path(primary_dirs$tables, "hetero_taxon_nodes.tsv"),
    "; module assignments from ", file.path(primary_dirs$tables, "vgae_taxon_modules.tsv"),
    " and ", file.path(primary_dirs$tables, "diffpool_consensus_modules.tsv")
  )
  make_card(
    card_type = "taxon",
    entity_id = row$taxon,
    title = paste0("Taxon ", row$taxon),
    summary = summary,
    evidence = evidence,
    threshold = ng_threshold_label(primary_thr),
    method = primary_method,
    taxon = row$taxon,
    module = row$vgae_module,
    observed_status = "observed+learned",
    source_tables = c(
      "data/reference/prokaryote_function_assigned.tsv",
      file.path(primary_dirs$tables, "hetero_taxon_nodes.tsv"),
      file.path(primary_dirs$tables, "vgae_taxon_modules.tsv"),
      file.path(primary_dirs$tables, "diffpool_consensus_modules.tsv")
    )
  )
}), fill = TRUE)

module_cards <- list()
if (!is.null(primary_vgae) && nrow(primary_vgae) > 0) {
  for (mod in unique(primary_vgae$module_kmeans)) {
    mod_dt <- merge(primary_vgae[module_kmeans == mod], taxon_meta, by = "taxon", all.x = TRUE, sort = FALSE)
    module_cards[[length(module_cards) + 1]] <- make_card(
      card_type = "module",
      entity_id = paste0("vgae:", mod),
      title = paste0("VGAE module ", mod),
      summary = paste0(
        "VGAE module ", mod, " contains ", nrow(mod_dt), " taxa; top functional group ",
        top_counts(mod_dt, "functional_group", 3L), "; top ecological role ",
        top_counts(mod_dt, "ecological_role", 3L), "."
      ),
      evidence = paste0(
        "Module assignments from ", file.path(primary_dirs$tables, "vgae_taxon_modules.tsv"),
        " merged with functional annotations from data/reference/prokaryote_function_assigned.tsv."
      ),
      threshold = ng_threshold_label(primary_thr),
      method = primary_method,
      module = mod,
      observed_status = "learned",
      source_tables = c(
        file.path(primary_dirs$tables, "vgae_taxon_modules.tsv"),
        "data/reference/prokaryote_function_assigned.tsv"
      )
    )
  }
}
if (!is.null(primary_diffpool) && nrow(primary_diffpool) > 0) {
  for (mod in unique(primary_diffpool$consensus_module)) {
    mod_dt <- merge(primary_diffpool[consensus_module == mod], taxon_meta, by = "taxon", all.x = TRUE, sort = FALSE)
    module_cards[[length(module_cards) + 1]] <- make_card(
      card_type = "module",
      entity_id = paste0("diffpool:", mod),
      title = paste0("DiffPool consensus module ", mod),
      summary = paste0(
        "DiffPool consensus module ", mod, " contains ", nrow(mod_dt), " taxa; top functional group ",
        top_counts(mod_dt, "functional_group", 3L), "; top ecological role ",
        top_counts(mod_dt, "ecological_role", 3L), "."
      ),
      evidence = paste0(
        "Consensus assignments from ", file.path(primary_dirs$tables, "diffpool_consensus_modules.tsv"),
        " merged with functional annotations from data/reference/prokaryote_function_assigned.tsv."
      ),
      threshold = ng_threshold_label(primary_thr),
      method = primary_method,
      module = mod,
      observed_status = "learned",
      source_tables = c(
        file.path(primary_dirs$tables, "diffpool_consensus_modules.tsv"),
        "data/reference/prokaryote_function_assigned.tsv"
      )
    )
  }
}
module_cards <- if (length(module_cards) > 0) rbindlist(module_cards, fill = TRUE) else data.table()

link_cards <- NULL
  if (!is.null(link_prediction_top) && nrow(link_prediction_top) > 0) {
  link_cards <- copy(link_prediction_top)
  if ("taxon_from" %in% names(link_cards)) {
    link_cards[, entity_id := paste(relation_type, threshold, method, taxon_from, taxon_to, sep = "::")]
    link_cards[, title := paste0("Predicted ", relation_type, " link ", taxon_from, " -> ", taxon_to)]
    link_cards[, summary := ifelse(
      relation_type == "taxon_taxon",
      paste0("Predicted taxon-taxon link between ", taxon_from, " and ", taxon_to, " with score ", fmt_num(latent_score, 3),
             "; shared cores ", shared_core_count, "; cosine ", fmt_num(cosine_similarity, 3), "."),
      paste0("Predicted taxon-site link between ", taxon_from, " and ", taxon_to, " with score ", fmt_num(latent_score, 3),
             "; taxon prevalence cores ", taxon_prevalence_cores, "; site samples ", site_sample_count, ".")
    )]
    link_cards[, evidence := paste0(
      "Learned from calibrated latent similarity on ", threshold, "/", method,
      " using candidate predictions written by 10_ngraph_link_prediction.py."
    )]
    setnames(link_cards, c("taxon_from", "taxon_to"), c("source_taxon", "target_node"), skip_absent = TRUE)
    link_cards[, card_type := "predicted_link"]
    link_cards[, card_id := slugify(entity_id)]
    link_cards[, source_tables := toJSON(list(
      summary = file.path(discovery_root, "link_prediction_summary.tsv"),
      top_candidates = file.path(discovery_root, "link_prediction_top_candidates.tsv")
    ), auto_unbox = TRUE)]
    link_cards[, observed_status := "predicted"]
  } else if ("taxon" %in% names(link_cards)) {
    link_cards[, entity_id := paste(relation_type, threshold, method, taxon, core, sep = "::")]
    link_cards[, title := paste0("Predicted ", relation_type, " link ", taxon, " -> ", core)]
    link_cards[, summary := paste0("Predicted taxon-site link between ", taxon, " and ", core,
                                   " with score ", fmt_num(latent_score, 3), ".")]
    link_cards[, evidence := paste0(
      "Learned from calibrated latent similarity on ", threshold, "/", method,
      " using candidate predictions written by 10_ngraph_link_prediction.py."
    )]
    link_cards[, card_type := "predicted_link"]
    link_cards[, card_id := slugify(entity_id)]
    link_cards[, source_tables := toJSON(list(
      summary = file.path(discovery_root, "link_prediction_summary.tsv"),
      top_candidates = file.path(discovery_root, "link_prediction_top_candidates.tsv")
    ), auto_unbox = TRUE)]
    link_cards[, observed_status := "predicted"]
    link_cards[, `:=`(
      source_taxon = taxon,
      target_node = core
    )]
  }
  link_cards <- link_cards[, .(
    card_id, card_type, entity_id, title, summary, evidence, threshold, method,
    core = if ("core" %in% names(link_cards)) core else NA_character_,
    taxon = if ("taxon" %in% names(link_cards)) taxon else if ("source_taxon" %in% names(link_cards)) source_taxon else NA_character_,
    source_taxon = if ("source_taxon" %in% names(link_cards)) source_taxon else NA_character_,
    target_node = if ("target_node" %in% names(link_cards)) target_node else NA_character_,
    module = NA_character_,
    relation_type, score = latent_score, observed_status, source_tables
  )]
}

card_sources <- Filter(Negate(is.null), list(sample_cards, site_cards, taxon_cards, module_cards, link_cards))
cards <- rbindlist(card_sources, fill = TRUE)
cards <- cards[order(card_type, entity_id)]
fwrite(cards, file.path(discovery_root, "cards", "evidence_cards.tsv"), sep = "\t")

jsonl_path <- file.path(discovery_root, "cards", "evidence_cards.jsonl")
json_lines <- vapply(seq_len(nrow(cards)), function(i) {
  toJSON(as.list(cards[i]), auto_unbox = TRUE, na = "null")
}, character(1))
writeLines(json_lines, jsonl_path)

sample_abund <- as.data.table(as.table(primary_abund))
setnames(sample_abund, c("taxon", "sample", "abundance"))
sample_abund <- merge(sample_abund, primary_sample_qc[, .(sample = label, core, age_kyr, mis, sst)], by = "sample", all.x = TRUE, sort = FALSE)
fwrite(sample_abund, file.path(discovery_root, "tables", "sample_taxon_abundance_long.tsv"), sep = "\t")

sample_clr <- as.data.table(as.table(primary_clr))
setnames(sample_clr, c("sample", "taxon", "clr"))
sample_clr <- merge(sample_clr, primary_sample_qc[, .(sample = label, core, age_kyr, mis, sst)], by = "sample", all.x = TRUE, sort = FALSE)
fwrite(sample_clr, file.path(discovery_root, "tables", "sample_taxon_clr_long.tsv"), sep = "\t")

inventory <- cards[, .N, by = card_type][order(card_type)]
setnames(inventory, "N", "card_count")
fwrite(inventory, file.path(discovery_root, "tables", "evidence_card_inventory.tsv"), sep = "\t")

report <- file.path(discovery_root, "reports", "NGRAPH_DEEP_KNOWLEDGE_DISCOVERY_REPORT.md")
sink(report)
cat("# NGraph Deep Knowledge Discovery Evidence Report\n\n")
cat("- Generated: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), "\n", sep = "")
cat("- Seed: `", NG_PARAMS$seed, "`\n", sep = "")
cat("- Branch: `", NG$branch, "`\n", sep = "")
cat("- Primary threshold: `", ng_threshold_label(primary_thr), "`\n", sep = "")
cat("- Primary method: `", primary_method, "`\n", sep = "")
cat("\n## Card Inventory\n\n")
cat(ng_md_table(inventory, max_rows = 20))
cat("\n## Inputs\n\n")
cat("- Sample abundance long table: `", file.path(discovery_root, "tables", "sample_taxon_abundance_long.tsv"), "`\n", sep = "")
cat("- Sample CLR long table: `", file.path(discovery_root, "tables", "sample_taxon_clr_long.tsv"), "`\n", sep = "")
cat("- Evidence cards TSV: `", file.path(discovery_root, "cards", "evidence_cards.tsv"), "`\n", sep = "")
cat("- Evidence cards JSONL: `", file.path(discovery_root, "cards", "evidence_cards.jsonl"), "`\n", sep = "")
if (!is.null(primary_vgae_summary)) {
  cat("\n## VGAE Summary\n\n")
  cat(ng_md_table(primary_vgae_summary))
}
if (!is.null(primary_diffpool_summary)) {
  cat("\n## DiffPool Summary\n\n")
  cat(ng_md_table(primary_diffpool_summary))
}
sink()

manifest <- list(
  generated = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
  branch = NG$branch,
  threshold = ng_threshold_label(primary_thr),
  method = primary_method,
  seed = NG_PARAMS$seed,
  cards_tsv = file.path(discovery_root, "cards", "evidence_cards.tsv"),
  cards_jsonl = file.path(discovery_root, "cards", "evidence_cards.jsonl"),
  sample_abundance_long = file.path(discovery_root, "tables", "sample_taxon_abundance_long.tsv"),
  sample_clr_long = file.path(discovery_root, "tables", "sample_taxon_clr_long.tsv")
)
write_json(manifest, file.path(discovery_root, "evidence_card_manifest.json"), auto_unbox = TRUE, pretty = TRUE)

ng_log(LOG, "Method Validated: evidence cards and long-form context tables written")
ng_log(LOG, "Report written: ", report)
ng_log(LOG, "Complete")
