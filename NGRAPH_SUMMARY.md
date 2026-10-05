# NGraph Current Summary

> **Current-state audit (2026-10-05):** The latest code/artifact review is in [REPOSITORY_REVIEW_2026-10-05.md](LEARNING_AND_NOTES/REPOSITORY_REVIEW_2026-10-05.md). The active checkout is `/maps/projects/caeg/people/gfx654/Projects/NGraph`; `/src` is absent here. The graph-learning histories in the threshold benchmark are five-epoch smoke runs, the July file-backed KG needs integrity/schema work, and the dashboard has endpoint probes but no completed browser UI validation. Read the review before treating older “current” labels, module calls, scores, or KG paths as validated.

- Last updated: 2026-06-19 07:36:54 UTC
- Seed: `42`
- Active workstream: `abundance_thresholding`
- Execution root: `/src`
- Canonical input root: `data/`
- Current output root: `results/ngraph/abundance_thresholding`
- Detailed generated run report: `results/ngraph/abundance_thresholding/deep_modules/reports/NGRAPH_DEEP_MODULE_SUMMARY.md`
- Workflow diagram: `current_workflow_2026-06-15.md`
- Workplan: `WORKPLAN.md`

## Purpose

NGraph builds one taxon association graph per sediment core/site, then links those site graphs by graph similarity to create a graph-of-graphs. The goal is to reduce bias from uneven sediment compression, uneven sample counts, and core-specific time distortion before downstream module and driver discovery.

## Current Architecture

The active pipeline is self-contained under `/src`:

- `config_ngraph.R`: shared parameters
- `run_pipeline.sh`: numbered workflow runner
- `scripts/00_ngraph_import_feedstock.R`: copies canonical feedstock into `/src/data`
- `scripts/01_ngraph_clr_matrices.R`: builds threshold-specific CLR matrices
- `scripts/02_ngraph_input_qc.R`: runs ordination and PC/covariate QC
- `scripts/03_ngraph_site_graphs.R`: builds site-level graphs
- `scripts/04_ngraph_graph_of_graphs.R`: builds graph-of-graphs similarity networks
- `scripts/05_ngraph_summary.R`: regenerates summary tables and reports
- `scripts/06_ngraph_build_heterograph.R`: exports heterograph tables for deep-module training
- `scripts/07_ngraph_train_vgae.py`: trains the relation-aware VGAE baseline
- `scripts/08_ngraph_train_diffpool.py`: trains the batched DiffPool baseline
- `scripts/09_ngraph_deep_module_summary.R`: summarizes deep-module outputs

`Source/ROCS` and `Source/MinNet` are now reference projects. The reproducible NGraph pipeline should operate from `/src/data` after import validation.

## Established Data Decisions

- Feature abundance is `tax_abund_tad`, not `n_reads`.
- `n_reads` is used only as a QC/read-support covariate.
- CLR is sample-centered, not taxon-centered.
- CLR uses pseudocount `0.5`.
- Prevalence filtering is applied before graph construction, at the CLR matrix stage.
- The historical June 4 `NGRAPH_SUMMARY` run used an older `n_reads`-derived scaffold and is superseded by the abundance-thresholding workstream.

## Current Threshold Benchmark

The active benchmark compares `tax_abund_tad > 0` prevalence thresholds:

| threshold | retained taxa | interpretation |
|---:|---:|---|
| 3 | 374 | discovery sensitivity |
| 5 | 274 | leading production candidate |
| 10 | 173 | strict core-community sensitivity |

The scientific reason for testing lower thresholds is that `tax_abund_tad > 0` is already a stronger normalized-abundance criterion than raw read detection. Applying the historical raw-read `>=10` rule directly to `tax_abund_tad` removes many episodic or state-specific taxa.

## Current Graph Methods

For each threshold, the pipeline now builds four Level-1 site graph families:

| method | role |
|---|---|
| `pearson` | quantitative linear correlational graph; conservative in current outputs |
| `bicor` | robust correlational graph; currently very dense and best treated as sensitivity |
| `spearman` | rank-based monotonic graph; intermediate density but discards quantitative distance information |
| `mi_aracne` | selective non-linear/direct-dependency comparator using `minet` and ARACNE |

This branch does not run full WGCNA module construction. Pearson and bicor are being used as graph builders on the shared CLR inputs.

## Deep Module Phase

The current branch now extends beyond graph-of-graphs into a heterogeneous graph phase for module discovery.

- Taxa are the module targets.
- Sites remain contextual nodes.
- Taxon-taxon, site-site, and taxon-site relations are exported per threshold and method.
- Primary deep-learning baseline: relation-aware `VGAE/GAE`.
- Secondary deep-learning baseline: `DiffPool` on batched site graphs.

The outputs now live under `results/ngraph/abundance_thresholding/deep_modules/`.

## Deep Knowledge Discovery

The current branch now extends beyond the deep-module checkpoint into a local-first discovery layer.

- `10_ngraph_link_prediction.py` scores absent relations from the learned embeddings.
- `11_ngraph_build_evidence_cards.R` turns samples, sites, taxa, modules, and predicted links into evidence cards.
- `12_ngraph_build_retrieval_index.py` builds TF-IDF and nearest-neighbor indexes.
- `13_ngraph_query_engine.py` runs canonical natural-language queries and writes grounded answers.

The outputs now live under `results/ngraph/abundance_thresholding/deep_knowledge_discovery/`.

## Current Results

The branch has been rerun from step `03` through step `05` with all four graph methods.

Mean graph-of-graphs super-weight by threshold and method:

| threshold | pearson | bicor | spearman | mi_aracne |
|---:|---:|---:|---:|---:|
| 3 | 0.3543 | 0.8147 | 0.6086 | 0.3785 |
| 5 | 0.3158 | 0.7175 | 0.5310 | 0.3529 |
| 10 | 0.2901 | 0.5103 | 0.4304 | 0.3392 |

Current interpretation:

- `prev_5` is the locked production threshold.
- `prev_3` retains more taxa but creates density risk, especially for `bicor` and `spearman`.
- `prev_10` is cleaner as a strict core-community check but likely too sparse for discovery.
- `bicor` is extremely dense relative to Pearson and MI/ARACNE, so it should not be treated as the default graph method without further QC.
- The next task is interpretation and documentation of the deep-module and deep-knowledge results, not more threshold expansion.

## Immediate Next Steps

1. Keep the repo-state summary aligned with the completed abundance-thresholding and deep-module outputs.
2. Use the deep-module outputs to compare VGAE and DiffPool behavior across `prev_3`, `prev_5`, and `prev_10`.
3. Check module stability, functional coherence, and held-out reconstruction behavior before biological interpretation.
4. Validate the deep-knowledge discovery scripts and canonical query report.
5. Keep the post-deep diagnostics in sync with the summary report and plots.

## Audited current state (2026-10-05)

See [the detailed repository review](LEARNING_AND_NOTES/REPOSITORY_REVIEW_2026-10-05.md) for code/artifact evidence and acceptance criteria. This summary preserves earlier run descriptions above. The module-discovery chain and file-backed KG/browser substrate are implemented, but neither establishes a validated biological discovery prototype yet. The twelve `abundance_thresholding` VGAE and DiffPool runs have five-epoch smoke histories; the KG has dangling control edges and missing GeoB proxy rows; dashboard probes found defects in neighborhood traversal, limits and relation filtering. Current modeling and query layers do not consume the KG. The next prototype should fix reproducibility/model/KG-integrity defects, implement explicit evidence-backed metapaths, validate a separate KG learning task on clean holdout, and repair browser/API behavior. No sediment time-warp correction or transition-state learner is implemented.


## MVP implementation update — 2026-10-05

A bounded KG/module prototype is now implemented. The requested read-assisted prevalence filter retains 1,797 taxa in a TAD-only CLR matrix across 200 samples. Of these, 438 have positive TAD evidence and form seven exploratory VGAE groups; all retained taxa remain represented in the KG with read support distinguished from TAD abundance. The KG validates identifiers and references, preserves observation provenance and unmatched proxies, and exposes typed connectivity searches at `http://localhost:10290/kg/paths` with two preset demonstration questions.

The runnable entry point is `bash run_mvp.sh`; `NG_ENV_PREFIX` selects an existing environment, and `NG_BRANCH` selects a fresh output branch. See [implementation plan](LEARNING_AND_NOTES/MVP_IMPLEMENTATION_PLAN_2026-10-05.md) and [verified results and limitations](LEARNING_AND_NOTES/MVP_IMPLEMENTATION_RESULTS_2026-10-05.md). Earlier review sections describe the state before these fixes. Proxy units, GeoB aliases and matching tolerances still need scientific review; typed search is implemented, while KG machine learning and publication-level module validation remain future work.


## Current MVP — permissive mixed sensitivity (2026-10-05)

The current MVP launcher uses `hybrid_aggregated_tad_then_read`: damaged source rows pass the >=100-read gate before aggregation; aggregated TAD values take precedence, with read abundance as fallback for both prevalence (>=10 samples) and the CLR matrix. The mixed run retains 1,797 taxa and 214 samples and learns six exploratory VGAE modules over all retained taxa. The TAD-only run remains a separate comparison. Generic mixed abundance and native TAD-only matrices are saved separately.

The mixed KG now uses curated XRF, user-confirmed GeoB physical-core aliases, depth matches within 0.5 cm and bracketed linear interpolation without extrapolation. Its schema, source-value reconstruction, coverage accounting and GeoB library consistency checks pass. Unknown native units and large interpolation gaps remain explicit. The current browser is `http://localhost:10291/kg/paths`; port 10290 retains the earlier TAD-only prototype. See [current mixed sensitivity and KG report](LEARNING_AND_NOTES/KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md).

Run a fresh mixed MVP with `bash run_mvp.sh`. To reproduce the TAD-only comparison, use `NG_ABUNDANCE_MODE=hybrid_prevalence_tad_matrix bash run_mvp.sh`. Both commands create a fresh run branch by default.
