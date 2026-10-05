# NGraph MVP implementation results — 2026-10-05

This report records the bounded `mvp_permissive_tad` development prototype and the completed fresh run `mvp_permissive_tad_20261005` on 2026-10-05. It complements, and does not replace, the [implementation plan](MVP_IMPLEMENTATION_PLAN_2026-10-05.md) and the broader [repository review](REPOSITORY_REVIEW_2026-10-05.md). The result is a runnable technical MVP for a TAD-supported module layer, file-backed KG validation, and explainable typed connectivity queries. Its model scores and module assignments remain exploratory.

## Run and input construction

`run_mvp.sh` isolates each run under a fresh output workstream name, uses `NG_ENV_PREFIX` to select the installed `ngraph` runtime, sets seed 42 and prototype thresholds, and scopes logs to that workstream. The development artifacts are under `results/ngraph/mvp_permissive_tad/` with logs under `logs/mvp_permissive_tad/`. A full fresh run completed with `NG_BRANCH=mvp_permissive_tad_20261005 bash run_mvp.sh`; its manifest at `results/ngraph/mvp_permissive_tad_20261005/run_manifest.json` reports `status: completed`. Pipeline stages 00–13 and 15 completed, including domain/range validation against the tracked `config_kg_schema.json`, real-artifact/demo validation, and the independent raw-to-CLR regression. The manifest records Python 3.14.5, package versions, settings, source and input hashes; no packages were installed. VGAE/DiffPool run summaries and taxon-to-module assignments match the development run exactly. Embedding/PCA values differ by at most 9e-7; the full module files are not byte-identical.

The filtering policy applies the requested read gate (`n_reads >= 100`) to source rows **before duplicate aggregation**. It then sums duplicate taxon/sample records and uses TAD/read fallback **after aggregation and for prevalence eligibility only**. The modeled abundance matrix itself remains `tax_abund_tad` only; read fallback values are never inserted into it. With threshold 10 and pseudocount 0.5, the exported global matrix has 1,797 taxa by 200 samples. Fourteen empty samples were removed from the 214-sample input. Of the retained taxa, 1,359 are read-prevalence-only and 438 have TAD support. The independent raw-input-to-CLR reconstruction passed and confirmed the 1,797 × 200 dimensions, 438 TAD-supported taxa, and sample-centered CLR.

The graph learner is restricted to the 438 TAD-supported taxa. Site graphs exclude taxa without local TAD support. The new KG includes all 1,797 retained taxa and separately records their TAD/read evidence, so the KG taxon count must not be reported as the learned-module taxon count.

## Module learning and evaluation

The primary output is the seven-group VGAE partition over 438 taxa:

| Group | Taxa |
|---|---:|
| M3 | 88 |
| M2 | 84 |
| M4 | 84 |
| M5 | 78 |
| M1 | 52 |
| M6 | 36 |
| M7 | 16 |

The VGAE run used 30 epochs and selected its checkpoint by validation-only AUC. Its evaluation is a **transductive unique-taxon-pair reconstruction** task: fixed 80/10/10 train/validation/test pairs, fixed disjoint negatives excluding all known positive pairs, seed 42. The held-out test AUC is 0.9467 and AP is 0.9472; validation AUC is 0.9353. Node/context features remain visible across splits, so this is not held-out-site generalization and does not support ecological interaction claims. The seven groups have silhouette 0.2613. Repeated KMeans assignment on the same learned embeddings yielded ARI 0.9910 and 0.9851 across the two seed comparisons; this is assignment stability conditional on fixed embeddings, not graph/bootstrap stability.

DiffPool is retained as a secondary method comparison and now produces ten occupied consensus groups rather than one collapsed group. This is a correction of the earlier double-softmax, checkpoint-copy and feature-scale issues, but it does not establish biological validity. The current prototype design treats VGAE as the primary annotation and DiffPool as supplementary evidence.

## Knowledge graph and provenance

Before the R KG importer runs, `run_mvp.sh` calls `scripts/ngraph_import_kg_feedstock.py` to copy feedstock into `data/kg_feedstock/` and record hashes. `scripts/15_kg_import_site_sample_proxies.R` then reads those canonical copies for the branch-scoped KG. For this run the KG contains 34,625 nodes, 246,099 edges, 32,070 measurement summaries and 1,797 taxon nodes. The validation artifact reports structural validation passed, zero dangling references, and no duplicate node or edge IDs. It distinguishes negative/control material as `ControlContext`, avoiding dangling fake sediment-site edges.

Historical note for the earlier TAD-only run: its KG had 413,709 source observations referenced by the measurement summaries, unconfirmed proxy units, exact-core-only GeoB matching, and provisional 500-year/1-cm tolerances. The later mixed-branch substrate supersedes that matching policy with the user-confirmed 0.5-cm physical-core/depth workflow described below. Unit and source/calibration documentation and flagged interpolation gaps still need review. The namespace/ontology entries remain placeholders without verified grounding. The descriptive annotation counts are available in `deep_modules/prev_10/pearson/tables/mvp_module_function_counts.tsv`; these summarize reference annotations and do not validate module function.

Key development-run evidence: `results/ngraph/mvp_permissive_tad/knowledge_graph/tables/kg_validation.json`, `mvp_validation_and_demo.json`, `mvp_http_validation.json`, `kg_observations.tsv`, `kg_unmatched_proxy_observations.tsv`, and `knowledge_graph/kg_manifest.json`. Fresh-run structural/demo evidence is under `results/ngraph/mvp_permissive_tad_20261005/knowledge_graph/`; the completed run manifest is `results/ngraph/mvp_permissive_tad_20261005/run_manifest.json`. The schema definition is `config_kg_schema.json`.

## Typed connectivity and dashboard

The development browser on port 10290 serves `mvp_permissive_tad`; the fresh end-to-end run did not replace that server or receive a separate browser session. Its KG path interface exposes four typed metapaths: `site_taxon`, `taxon_proxy`, `site_module_bridge`, and `shared_module`. Search returns path counts, degree-weighted path counts (DWPC) using damping 0.5, typed node/edge evidence, and truncation status. It does not compute a significance value or p-value; no null calibration is implemented.

Two demonstration queries are recorded in `mvp_validation_and_demo.json`:

- Taxon to SST proxy: 185 paths, DWPC 0.02007, exact path count; the displayed evidence paths are truncated to the configured limit.
- ST8 to ST13 through a module: the search reached its 10,000-path cap, so 10,000 is a lower bound, DWPC is 0.0001935, and both path count and evidence are marked truncated.

The development-branch HTTP validation artifact at `results/ngraph/mvp_permissive_tad/knowledge_graph/tables/mvp_http_validation.json` is present. It records an `ok` health response, metapath catalog, both connectivity responses, neighborhood depth expansion (120 nodes at depth 1; 480 at depth 2), the 15-node cap, taxon-site link filtering, embedding limit, missing-source and invalid-metapath behavior, and the served connectivity page. Those development-branch API checks passed. The artifact explicitly leaves **visual browser inspection pending**. The fresh run passed structural schema and real-artifact/demo validation, but no fresh HTTP/browser smoke or visual UI session is claimed. The local Gemini key/config was detected by health, but external Gemini synthesis was not part of this validation.

## Checks completed and remaining work

Six MVP unit tests passed. The development run’s HTTP/API checks passed and the completed fresh run’s manifest records stages 00–13/15, schema endpoint-domain/range validation against `config_kg_schema.json`, real-artifact/demo validation and independent raw-to-CLR reconstruction as passed. Structural KG validation passed with zero dangling references. No fresh browser server/UI validation is claimed. These checks support implementation and data-flow correctness within the tested scope; they do not demonstrate biological validity, cross-site generalization, or significance of paths/modules.

The exact fresh TAD-only run command was `NG_BRANCH=mvp_permissive_tad_20261005 bash run_mvp.sh`. The two user-approved demonstration questions are “Which samples connect this taxon to an SST proxy?” and “Which taxa link these two cores through a module?” The earlier TAD-only plan had left GeoB matching and tolerance questions open; subsequent physical-core/depth matching addresses the alias issue, and the user confirmed the 0.5-cm tolerance. Current proxy review is limited to source/instrument unit and calibration records plus the 625 large-gap flags.

The next validation priorities are:

1. Review authoritative proxy units and uncertainty using source/instrument calibration records; review the 625 large-gap flags. The physical-core/depth policy and 0.5-cm tolerance are confirmed.
2. Test module coherence and stability with graph/bootstrap resampling, functional enrichment, null comparisons and an independent site/core holdout.
3. Calibrate or replace transductive link/reconstruction scores before using them as support for biological claims.
4. Complete a visual browser interaction pass and keep observed evidence, learned annotations and predictions visibly distinct.

Do not infer causality, direct taxon cooperation, ecosystem seeding requirements, validated function, proxy significance, or sediment-compression correction from this MVP. Its contribution is a reproducible, typed and inspectable prototype that makes these later scientific gates concrete.


### Additional interface check

HTTP/API checks passed, and both rendered JavaScript blocks passed syntax checking for the TAD-only page and mixed page on port 10291. Node.js worked after setting `LD_LIBRARY_PATH` to include the existing `nodejs/lib`; no packages were installed. Visual browser interaction remains pending.

## Later mixed-abundance and KG-substrate update (2026-10-05)

The user-selected mixed matrix and depth-matched proxy substrate are documented separately in [KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md](KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md). This later sensitivity applies `n_reads >= 100` to source rows before duplicate aggregation, then uses TAD/read fallback after aggregation in the matrix as well as prevalence. It includes all 1,797 taxa in learning (1,359 read-fallback-only; 438 TAD-supported) and must not be conflated with the earlier TAD-only run over 438 taxa. The new KG matches proxies by physical core and depth with explicit unit status, observation provenance, interpolation bounds and unmatched coverage.

The mixed branch passed component validation, including unit tests, a proxy-matching fixture, mixed-matrix raw-to-CLR reconstruction and KG substrate validation. Its final run manifest now records `completed`; the earlier failed checkpoint came from an interrupted inefficient validator and was followed by the optimized validation and complete stage rerun. Port 10291 serves the mixed branch; port 10290 remains the TAD-only development server. Visual browser inspection remains pending.

## User-selected mixed sensitivity and updated KG substrate (2026-10-05)

The subsequent mixed abundance sensitivity and physical-core/depth proxy substrate are documented in [KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md](KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md). This branch applies the read threshold before duplicate aggregation, then uses post-aggregation TAD/read fallback in both the abundance matrix and prevalence filter. It includes 1,797 learners, while the earlier TAD-only run retains its separate 438-TAD-supported learner. The updated KG records native/interpolated observation provenance, explicit units status, bounded depth matching and unmatched coverage.

The mixed KG validation and branch API checks passed; the final manifest now reports completion after an interim validator interruption and optimized recheck. The visual browser check remains pending.
