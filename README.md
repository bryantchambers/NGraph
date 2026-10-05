# NGraph

> **Current-state audit (2026-10-05):** The latest code/artifact review is in [REPOSITORY_REVIEW_2026-10-05.md](LEARNING_AND_NOTES/REPOSITORY_REVIEW_2026-10-05.md). The active checkout is `/maps/projects/caeg/people/gfx654/Projects/NGraph`; `/src` is absent here. The graph-learning histories in the threshold benchmark are five-epoch smoke runs, the July file-backed KG needs integrity/schema work, and the dashboard has endpoint probes but no completed browser UI validation. Read the review before treating older “current” labels, module calls, scores, or KG paths as validated.

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

## Audited current state and next prototype (2026-10-05)

The detailed evidence and acceptance gates are in [LEARNING_AND_NOTES/REPOSITORY_REVIEW_2026-10-05.md](LEARNING_AND_NOTES/REPOSITORY_REVIEW_2026-10-05.md). This is an additive update; the dated resume snapshot above records the earlier `/src` setup. The active checkout now runs at `/maps/projects/caeg/people/gfx654/Projects/NGraph`, and `abundance_thresholding` / `permissive_hybrid_prev10` name output workstreams, not Git branches.

- **Graph and modules:** The graph-of-graphs plus heterograph/VGAE and DiffPool artifacts exist. All 12 threshold-benchmark model pairs have five-epoch histories and are smoke runs; the permissive `prev_10` run has 120 VGAE and 160 DiffPool epochs, with all 1,797 taxa assigned to one DiffPool consensus module. No bootstrap stability, functional enrichment, clean held-out-core evaluation or sediment time-warp correction is implemented.
- **Knowledge graph:** A file-backed importer, manifests and browser APIs exist. Schema enforcement and ontology grounding are absent; artifacts have 58 dangling control-site edges, missing GeoB proxy imports due to core aliases, and gaps in units, matching tolerance and observation provenance.
- **Dashboard:** Local API/query routes respond, while neighborhood traversal, relation filters and limits have confirmed defects. No full browser UI validation or live Gemini synthesis was completed. The KG is not used by current module learning or query generation.

**Next prototype sequence:** (1) fix reproducibility, checkpoint/split, prevalence and KG importer defects; (2) define and validate a bounded typed KG schema with provenance and units; (3) implement evidence-backed metapath counts/DWPC on `prev_5`/Pearson; (4) assess a separate KG-learning task with clean holdout; (5) repair and validate dashboard workflows. `scripts/15_kg_import_site_sample_proxies.R` is currently invoked under runner stage label 14, while `scripts/14_ngraph_local_browser.py` is the browser; reconcile this numbering before documenting `--start` behavior.


## MVP implementation update — 2026-10-05

A bounded KG/module prototype is now implemented. The requested read-assisted prevalence filter retains 1,797 taxa in a TAD-only CLR matrix across 200 samples. Of these, 438 have positive TAD evidence and form seven exploratory VGAE groups; all retained taxa remain represented in the KG with read support distinguished from TAD abundance. The KG validates identifiers and references, preserves observation provenance and unmatched proxies, and exposes typed connectivity searches at `http://localhost:10290/kg/paths` with two preset demonstration questions.

The runnable entry point is `bash run_mvp.sh`; `NG_ENV_PREFIX` selects an existing environment, and `NG_BRANCH` selects a fresh output branch. See [implementation plan](LEARNING_AND_NOTES/MVP_IMPLEMENTATION_PLAN_2026-10-05.md) and [verified results and limitations](LEARNING_AND_NOTES/MVP_IMPLEMENTATION_RESULTS_2026-10-05.md). Earlier review sections describe the state before these fixes. Proxy units, GeoB aliases and matching tolerances still need scientific review; typed search is implemented, while KG machine learning and publication-level module validation remain future work.


## Current MVP — permissive mixed sensitivity (2026-10-05)

The current MVP launcher uses `hybrid_aggregated_tad_then_read`: damaged source rows pass the >=100-read gate before aggregation; aggregated TAD values take precedence, with read abundance as fallback for both prevalence (>=10 samples) and the CLR matrix. The mixed run retains 1,797 taxa and 214 samples and learns six exploratory VGAE modules over all retained taxa. The TAD-only run remains a separate comparison. Generic mixed abundance and native TAD-only matrices are saved separately.

The mixed KG now uses curated XRF, user-confirmed GeoB physical-core aliases, depth matches within 0.5 cm and bracketed linear interpolation without extrapolation. Its schema, source-value reconstruction, coverage accounting and GeoB library consistency checks pass. Unknown native units and large interpolation gaps remain explicit. The current browser is `http://localhost:10291/kg/paths`; port 10290 retains the earlier TAD-only prototype. See [current mixed sensitivity and KG report](LEARNING_AND_NOTES/KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md).

Run a fresh mixed MVP with `bash run_mvp.sh`. To reproduce the TAD-only comparison, use `NG_ABUNDANCE_MODE=hybrid_prevalence_tad_matrix bash run_mvp.sh`. Both commands create a fresh run branch by default.
