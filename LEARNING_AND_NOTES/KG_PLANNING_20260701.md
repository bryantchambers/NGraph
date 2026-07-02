# Knowledge Graph Prototype: Site/Sample/Taxon/Proxy Foundation

## Summary

Build the first KG prototype as a file-backed, reproducible extension of the current NGraph system. The first milestone is not a database migration; it is a typed node/edge export with provenance, proxy metadata, site coordinates, module membership, and ontology-ready fields. This keeps the prototype lightweight while leaving a clean path to DuckDB, RDF, or a property graph once the schema stabilizes.

The central KG objective should be dated and added to `/src/AGENTS.md` as of `2026-07-01`: build a learnable paleo-ecosystem KG that links sites, sediment samples, aeDNA taxa, modules, genes/BGCs, environmental proxies, climate state, ontology terms, and learned/inferred relationships.

## Metadata Inventory From `Source/Misc/01_proxies.r`

Accessible local source tables:

- `Source/ROCS/data/metadata_v5.tsv`: 606 rows, sample/core metadata, `label`, `core`, depth, `y_bp`, library concentration, temperature, MIS, initial/dereplicated read counts, SST.
- `Source/ROCS/data/combined_sst_proxies_separate_columns.csv`: 236 rows, SST proxies: `sst_uk37_alkenone`, `sst_mgca_jonkers_2013`, `sst_mgca_kozdon_2009`.
- `Source/ROCS/data/combined_foraminifera_geochem.tsv`: 237 rows, foraminifera groups/species, concentrations, Mg/Ca SST, `d13c`, `d18o`, P/B ratio.
- `Source/ROCS/data/geob25202_clean_proxies.tsv`: 113 rows, GeoB-specific `d13c`, TOC, clay groups, Greenland/Iceland source indicators.
- `Source/ROCS/data/combined_xrf_geochemistry_not_normalized.csv`: 20,588 rows, XRF elements and derived ratios for productivity, terrigenous input, and redox.
- `Source/ROCS/results/microbial/damage/damage-classification-depositional/sample-baselines.tsv`: 528 rows, sample-level damage summaries.

Not accessible from the old script paths:

- `/projects/fernandezguerra/people/ngm902/scripts/r-miscellaneous.R`: plotting/theme helper only, not needed for KG import.
- Old absolute `/projects/caeg/...` copies of GeoB/damage tables; equivalent repo-local copies are available.
- `data/combined_xrf_not_normalized.tsv` is referenced by the script, but the available local file is the CSV `combined_xrf_geochemistry_not_normalized.csv`; normalize this path in the import.

## Key Changes

- Add a KG objective section to `/src/AGENTS.md` dated `2026-07-01`, correcting the active project direction from only NGraph/deep discovery toward a learnable paleo-ecosystem KG.
- Create a KG build stage that writes branch-scoped artifacts under `results/ngraph/<branch>/knowledge_graph/`:
  - `kg_nodes.tsv`
  - `kg_edges.tsv`
  - `kg_measurements.tsv`
  - `kg_ontology_terms.tsv`
  - `kg_manifest.json`
  - `reports/KG_SCHEMA_AND_IMPORT_REPORT.md`
- Add a first import script, likely `scripts/15_kg_import_site_sample_proxies.R`, that reads the accessible proxy tables, standardizes core names, joins on nearest sample/depth/age where appropriate, and records provenance for every imported value.
- Add a schema draft note in `LEARNING_AND_NOTES/` describing v0 node types, edge predicates, ontology strategy, storage decision, and future GPU/learning checkpoints.
- Add a new browser tab named `Knowledge Graph` that reads KG artifacts and exposes:
  - site/sample browser
  - proxy measurement summaries
  - node/edge counts by type
  - module membership links
  - provenance table
  - simple KG path lookup from site/sample/taxon/module

## V0 Schema

Node types:

- `Site`: ST5, ST8, ST13, GeoB25202, with user-supplied latitude/longitude and site aliases.
- `Sample`: sediment slice/sample label tied to site, depth, local age grid, MIS, SST.
- `Taxon`: current NGraph retained taxa.
- `Module`: VGAE/DiffPool/module summary entities from the active branch.
- `ProxyMeasurement`: environmental/geochemical/isotopic measurements.
- `ProxyVariable`: normalized variables such as SST, Ca/Ti, Ba/Ti, d13C, d18O, TOC, Mn/Fe.
- `OntologyTerm`: external controlled vocabulary term.
- `Dataset` and `AnalysisRun`: provenance anchors.
- Future placeholders: `Gene`, `Allele`, `BGC`, `Pathway`, `Compound`, `Trait`.

Edge predicates:

- `site_has_sample`
- `sample_from_site`
- `sample_has_measurement`
- `measurement_of_variable`
- `sample_observed_taxon`
- `taxon_member_of_module`
- `site_has_module_enrichment`
- `taxon_predicted_link`
- `entity_has_ontology_term`
- `measurement_derived_from_dataset`
- `edge_generated_by_analysis`
- future: `taxon_encodes_bgc`, `bgc_produces_compound`, `gene_part_of_pathway`, `allele_observed_in_sample`.

Ontology defaults:

- Use Relation Ontology for reusable predicates such as `part_of` and related biological relations.
- Use ENVO for environments and environmental processes.
- Use MIxS for sample/contextual sequencing metadata.
- Use PROV-O for provenance.
- Use NCBI Taxonomy plus GTDB for taxa, with GTDB preferred for bacterial/archaeal phylogenomic normalization where available.
- Use GO for gene/function terms and ChEBI for compounds/metabolites.

## Storage Decision

Use flat, versioned TSV/JSON artifacts now. Do not introduce Neo4j, RDF triplestore, or a required local database in v0.

Reason:

- the schema is still changing
- the first goal is reproducible import and visible provenance
- the current pipeline already works well with branch-scoped TSV artifacts
- a database migration is easier after node/edge types stabilize

Checkpoint for database adoption:

- add DuckDB first when joins and browser queries become too slow
- add RDF/OWL export when ontology reasoning becomes central
- add Neo4j or another property graph only when interactive path traversal becomes a bottleneck

## Test Plan

- Validate all proxy source files exist or report missing files clearly.
- Confirm imported site coordinates for ST5, ST8, ST13, and GeoB25202 match the user-provided values.
- Confirm every `Sample` node links to exactly one `Site`.
- Confirm proxy measurements preserve source file, source column, units when known, age/depth basis, and import method.
- Confirm no measurement silently overwrites another measurement with the same sample/variable/source.
- Confirm current NGraph module memberships link to `Taxon` and `Module` nodes.
- Confirm browser `/api/health` reports KG artifact status and the KG tab renders non-empty node/edge/measurement summaries.
- Confirm all new scripts write logs under `/src/logs` and use seed `42` where stochastic behavior exists.

## Assumptions

- The implementation should update `/src/AGENTS.md`; the user’s `AGENT.md` reference means the project instruction file already present as `AGENTS.md`.
- v0 imports proxy metadata and existing NGraph module/taxon artifacts only; BGC, gene, allele, and pathway data are schema placeholders until real tables are available.
- The first KG build targets the live exploratory branch `permissive_hybrid_prev10`, while keeping branch support generic.
- Ontology linking starts as identifier columns and mapping tables, not full OWL reasoning.
- Sources for ontology choices: OBO Relation Ontology, ENVO, MIxS/GSC, W3C PROV-O, NCBI Taxonomy, GTDB, GO, and ChEBI. See official references: RO `https://obofoundry.org/ontology/ro.html`, ENVO `https://obofoundry.org/ontology/envo.html`, MIxS `https://github.com/genomicsStandardsConsortium/mixs`, PROV-O `https://www.w3.org/TR/prov-o/`, NCBI Taxonomy `https://www.ncbi.nlm.nih.gov/taxonomy`, GTDB `https://gtdb.ecogenomic.org/`, GO `https://geneontology.org/`, ChEBI `https://www.ebi.ac.uk/chebi/`.
