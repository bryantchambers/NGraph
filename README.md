# NGraph

NGraph builds site-specific microbial taxon graphs from ancient marine sedaDNA and links those graphs into a graph-of-graphs. The working goal is to reduce bias from uneven sediment compression, uneven age coverage, and unequal sample counts before downstream module discovery.

## Resume Snapshot

- Last updated: 2026-06-19 07:36:54 UTC
- Active branch/workstream: `abundance_thresholding`
- Current execution root: `/src`
- Current canonical input root: `data/`
- Current output root: `results/ngraph/abundance_thresholding`
- Detailed run summary: `results/ngraph/abundance_thresholding/deep_modules/reports/NGRAPH_DEEP_MODULE_SUMMARY.md`
- Workflow diagram: `current_workflow_2026-06-15.md`
- Workplan: `WORKPLAN.md`

Current state: the abundance-thresholding workflow has been rerun from site-graph construction through the deep-module phase with all four Level-1 graph methods: `pearson`, `bicor`, `spearman`, and `mi_aracne`.

## Current Direction

The active NGraph workflow now lives in `/src` and follows the ROCS-style structure:

- Scripts: `scripts/`
- Shared parameters: `config_ngraph.R`
- Runner: `run_pipeline.sh`
- Logs: `logs/`
- Outputs: `results/ngraph/`
- Canonical feedstock: `data/`

`Source/ROCS` and `Source/MinNet` are seed/reference projects. They are no longer the intended long-term execution root for NGraph.

## Input Decision

The NGraph feature matrix is built from normalized abundance, not raw read counts.

- Primary abundance column: `tax_abund_tad`
- Raw read support column: `n_reads`
- Use of `n_reads`: QC/read-support only
- CLR transform: sample-centered, not taxon-centered
- Pseudocount: `0.5`
- Random seed: `42`

Historical ROCS/MinNet stage-1 WGCNA feedstock used `n_reads` and taxon-centered log values. Those remain useful historical context, but they are not the intended NGraph production input.

## Prevalence Decision

Using `tax_abund_tad > 0` is substantially stricter than using raw `n_reads > 0`.

Current stage-1 comparison showed:

| Rule | Taxa Kept |
|---|---:|
| `n_reads > 0` in at least 10 samples | 1797 |
| `tax_abund_tad > 0` in at least 10 samples | 173 |
| `tax_abund_tad > 0` in at least 5 samples | 274 |
| `tax_abund_tad > 0` in at least 3 samples | 374 |

Current threshold interpretation:

- Primary production candidate: `tax_abund_tad > 0` in at least 5 samples
- Discovery sensitivity: `tax_abund_tad > 0` in at least 3 samples
- Strict core-community sensitivity: `tax_abund_tad > 0` in at least 10 samples

Scientific rationale: `tax_abund_tad` positivity already encodes a stronger normalized-abundance criterion than raw read detection. A strict `>=10` rule risks removing episodic, site-specific, or state-specific taxa that may matter biologically.

## Method Comparison Plan

The active prevalence benchmark is not just a threshold test. It is a cross-threshold, cross-method network comparison.

For each prevalence threshold `3`, `5`, and `10`, the pipeline should build four Level-1 site graph families from the same sample-centered CLR matrix:

1. `pearson`
2. `bicor`
3. `spearman`
4. `mi_aracne`

Method roles:

- `pearson`: preserves quantitative linear structure and aligns with historical ROCS correlation logic
- `bicor`: robust alternative to Pearson for outlier-sensitive CLR profiles
- `spearman`: rank-based monotonic baseline; useful, but it discards quantitative distance information
- `mi_aracne`: non-linear/direct-dependency comparator using `minet`

This branch is not intended to run full WGCNA. The goal is to compare alternative site-level graph builders on the same inputs.

## Threshold Selection Framework

Threshold choice should be decided with both input QC and network QC.

Input QC:

- ordination on threshold-specific CLR matrices
- PC association with `detected_taxa_tad`
- PC association with `total_tax_abund_tad`
- PC association with `total_n_reads`
- PC association with core/site and age-related covariates

Network QC:

- node and edge counts
- density and saturation risk
- connected components
- degree concentration
- cross-core graph-of-graphs similarity
- cross-method concordance

Decision logic:

- reject thresholds that repeatedly produce saturated graphs across correlational methods
- reject thresholds that are too sparse for meaningful graph comparison
- prefer thresholds that remain interpretable across methods and are less dominated by technical structure
- expected default remains `>=5` unless the expanded comparison overturns it

## Self-Contained Data Layout

The reproducible NGraph pipeline is intended to run from `/src/data` rather than live paths under `Source/`.

Canonical local inputs include:

- `data/raw/dmg-summary-ssp-damage-classification-depositional.tsv.gz`
- `data/metadata/metadata_v5.tsv`
- `data/reference/prokaryote_function_assigned.tsv`
- additional functional/classification references as later stages require

Rules:

- normal pipeline scripts read from `data/`
- `Source/` paths are only for historical reference or one-time import/provenance steps
- source data copied into `data/` must retain provenance and validation metadata

## Pipeline Shape

Runner:

```bash
bash run_pipeline.sh
bash run_pipeline.sh --start 03
```

Current numbered workflow:

1. `00_ngraph_import_feedstock.R`
2. `01_ngraph_clr_matrices.R`
3. `02_ngraph_input_qc.R`
4. `03_ngraph_site_graphs.R`
5. `04_ngraph_graph_of_graphs.R`
6. `05_ngraph_summary.R`
7. `06_ngraph_build_heterograph.R`
8. `07_ngraph_train_vgae.py`
9. `08_ngraph_train_diffpool.py`
10. `09_ngraph_deep_module_summary.R`

## Deep Module Phase

The new deep-module phase exports a heterogeneous graph view for each threshold/method combination and trains two baseline module discovery models:

- `VGAE/GAE` for unsupervised taxon embeddings and module clustering
- `DiffPool` for batched per-site graph pooling and soft hierarchical assignments

The exported artifacts live under `results/ngraph/abundance_thresholding/deep_modules/`.

## Deep Knowledge Discovery

The pipeline now continues into a local-first discovery layer:

- `10_ngraph_link_prediction.py` for calibrated absent-edge hypotheses
- `11_ngraph_build_evidence_cards.R` for sample, site, taxon, module, and link cards
- `12_ngraph_build_retrieval_index.py` for TF-IDF evidence-card and embedding-neighbor indexes
- `13_ngraph_query_engine.py` for grounded natural-language answers

The discovery artifacts live under `results/ngraph/abundance_thresholding/deep_knowledge_discovery/`.
## Current State

The `abundance_thresholding` branch now contains threshold-specific CLR, QC, site graph, and graph-of-graphs outputs for `prev_3`, `prev_5`, and `prev_10` across all four intended site-graph methods:

- `pearson`
- `bicor`
- `spearman`
- `mi_aracne`

Current high-level interpretation:

- `prev_5` is the locked production threshold.
- `prev_3` is useful as a broader discovery sensitivity, but shows density risk in permissive graph methods.
- `prev_10` is a strict core-community sensitivity, but is likely too sparse for primary discovery.
- `bicor` is currently behaving as a dense upper-bound sensitivity method rather than a conservative default.
- `pearson` is the sparsest conservative correlational method.
- `spearman` remains an intermediate rank-based sensitivity.
- `mi_aracne` remains the selective non-linear/direct-dependency comparator.
- The new evidence/query layer is local-first and does not assume an open external API port.

## Immediate Next Steps

1. Keep the repo-state summary aligned with the completed abundance-thresholding and deep-module outputs.
2. Use the deep-module outputs to compare VGAE and DiffPool behavior across `prev_3`, `prev_5`, and `prev_10`.
3. Check module stability, functional coherence, and held-out reconstruction behavior before biological interpretation.
4. Validate the deep-knowledge discovery scripts and canonical query report.
5. Keep the post-deep diagnostics in sync with the summary report and plots.
