# NGraph Deep Knowledge Discovery Workplan

> **Current-state audit (2026-10-05):** The latest code/artifact review is in [REPOSITORY_REVIEW_2026-10-05.md](LEARNING_AND_NOTES/REPOSITORY_REVIEW_2026-10-05.md). The active checkout is `/maps/projects/caeg/people/gfx654/Projects/NGraph`; `/src` is absent here. The graph-learning histories in the threshold benchmark are five-epoch smoke runs, the July file-backed KG needs integrity/schema work, and the dashboard has endpoint probes but no completed browser UI validation. Read the review before treating older “current” labels, module calls, scores, or KG paths as validated.

## Summary

This phase extends the NGraph graph-of-graphs pipeline into local knowledge discovery.
The goal is to connect learned graph structure, functional annotations, and sample/core metadata
to a queryable evidence layer that can answer natural-language questions without depending on
an external API or open network port.

Canonical baseline:
- Primary threshold: `prev_5`
- Primary method: `pearson`
- Learned discovery substrate: `VGAE`
- Module context substrate: `DiffPool`

## Phase Plan

1. Learned link prediction
   - Score absent taxon-taxon and taxon-site relations from the trained embeddings.
   - Keep the output as ranked hypotheses with explicit provenance and validation metrics.

2. Evidence cards
   - Convert samples, sites, taxa, modules, and predicted links into compact cards.
   - Preserve observed, learned, and predicted status on every card.

3. Retrieval index
   - Build a local semantic index over the evidence cards.
   - Build a structural nearest-neighbor index over learned embeddings.

4. Query engine
   - Support natural-language questions over the local cards and learned outputs.
   - Return grounded answers, not free-form speculation.
   - First implement a local RAG orchestrator that packages evidence cards, graph context, and prompt bundles.
   - Keep the future LLM adapter pluggable so a Google API key can be used later for the demo layer.

5. Optional web/app layer
   - Implemented as `scripts/14_ngraph_local_browser.py`.
   - Use `start_server.sh [port]` as the launcher wrapper.
   - Bind the server to `0.0.0.0` so it can be reached across the local network.
   - Treat any port, browser, or API failure as an environment issue that should be reported.
   - For the demo LLM layer, set `NG_LLM_PROVIDER=gemini` and provide `GEMINI_API_KEY` or `GOOGLE_API_KEY` in the environment.

## Implementation Details

- The pipeline stays local-first inside the container.
- No step may assume outbound network access.
- Scripts must write logs under `/src/logs` and use seed `42`.
- Historical outputs under `/src/results/stage1` remain read-only.
- `tax_abund_tad` remains the canonical abundance feature.
- `n_reads` remains QC/read-support only.

## Validation

- Validate link prediction with held-out-core metrics.
- Confirm evidence cards include provenance and stable IDs.
- Confirm retrieval returns the right cards for canonical questions.
- Confirm the query engine can answer:
  - taxa that work together across state transitions
  - top taxa for a specific core/time context
  - functional capabilities of the selected taxa or modules

## Assumptions

- The current container is not guaranteed to expose an external port.
- If an API or service should obviously be reachable but is not, stop and report the blocker.
- CPU execution is acceptable for the first prototype.
- GPU/SLURM is reserved for heavier retraining or local model inference later.
- LLM synthesis is a later plug-in, not a prerequisite for the grounded retrieval layer.
- The first LLM adapter target is Google's API key/free-tier demo path, but only after the local orchestrator is stable.

## Completion Signals

- Phase 1 complete: ranked link predictions and validation summaries exist.
- Phase 2 complete: evidence cards and context tables exist.
- Phase 3 complete: local semantic and structural retrieval indexes exist.
- Phase 4 complete: canonical natural-language queries return grounded answers.
- Phase 5 complete: the local browser serves the discovery artifacts on `0.0.0.0:8000` and the canonical sections load successfully.

## Dated priority update (2026-10-05)

Preserve the phase plan above as the historical workplan. The audited implementation state and detailed acceptance criteria are in [LEARNING_AND_NOTES/REPOSITORY_REVIEW_2026-10-05.md](LEARNING_AND_NOTES/REPOSITORY_REVIEW_2026-10-05.md). Current work should proceed in this order:

1. **P0 — Reproducibility and correctness:** document the `ngraph` runtime and immutable run manifests; fix the VGAE/DiffPool best-checkpoint copy behavior, leakage-prone split/negative sampling, `prevalence_samples` denominator, and runner stage numbering.
2. **P0 — KG integrity:** implement explicit control-site policy, GeoB core alias mapping and dropped-row report; retain observation provenance, units and age/depth uncertainty; validate IDs and zero dangling edges.
3. **P1 — KG search prototype:** specify bounded typed schema and ontology mapping status; implement ordered, domain-valid path counts/DWPC on current relations; add permutation significance only after a degree-preserving null is validated.
4. **P1 — Module evidence:** rerun corrected training, then report stability, functional coherence, null comparisons and independent held-out-core performance before biological interpretation.
5. **P2 — Dashboard:** fix neighborhood traversal, filtering and limits; expose real validation states; run endpoint and browser interaction checks.

Acceptance gates are defined in the linked review. Do not interpret successful artifact generation or HTTP status as scientific validation.


## MVP implementation update — 2026-10-05

A bounded KG/module prototype is now implemented. The requested read-assisted prevalence filter retains 1,797 taxa in a TAD-only CLR matrix across 200 samples. Of these, 438 have positive TAD evidence and form seven exploratory VGAE groups; all retained taxa remain represented in the KG with read support distinguished from TAD abundance. The KG validates identifiers and references, preserves observation provenance and unmatched proxies, and exposes typed connectivity searches at `http://localhost:10290/kg/paths` with two preset demonstration questions.

The runnable entry point is `bash run_mvp.sh`; `NG_ENV_PREFIX` selects an existing environment, and `NG_BRANCH` selects a fresh output branch. See [implementation plan](LEARNING_AND_NOTES/MVP_IMPLEMENTATION_PLAN_2026-10-05.md) and [verified results and limitations](LEARNING_AND_NOTES/MVP_IMPLEMENTATION_RESULTS_2026-10-05.md). Earlier review sections describe the state before these fixes. Proxy units, GeoB aliases and matching tolerances still need scientific review; typed search is implemented, while KG machine learning and publication-level module validation remain future work.


## Current MVP — permissive mixed sensitivity (2026-10-05)

The current MVP launcher uses `hybrid_aggregated_tad_then_read`: damaged source rows pass the >=100-read gate before aggregation; aggregated TAD values take precedence, with read abundance as fallback for both prevalence (>=10 samples) and the CLR matrix. The mixed run retains 1,797 taxa and 214 samples and learns six exploratory VGAE modules over all retained taxa. The TAD-only run remains a separate comparison. Generic mixed abundance and native TAD-only matrices are saved separately.

The mixed KG now uses curated XRF, user-confirmed GeoB physical-core aliases, depth matches within 0.5 cm and bracketed linear interpolation without extrapolation. Its schema, source-value reconstruction, coverage accounting and GeoB library consistency checks pass. Unknown native units and large interpolation gaps remain explicit. At the time of the 2026-10-05 review, the older browser ran at `http://localhost:10289/`; this service has since been archived and shut down. Port 10291 runs the current Constellations interface. See [current mixed sensitivity and KG report](LEARNING_AND_NOTES/KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md).

Run a fresh mixed MVP with `bash run_mvp.sh`. To reproduce the TAD-only comparison, use `NG_ABUNDANCE_MODE=hybrid_prevalence_tad_matrix bash run_mvp.sh`. Both commands create a fresh run branch by default.

## Constellations interface — 2026-10-06

The development web UI has been replaced with Constellations at `/`: a left rail for Overview, Knowledge Graph, Query, Modules and Data. The Knowledge Graph has distinct graph-browser, typed-metapath and schema views; Overview derives source/core/sample/age/location and analysis counts from the active workstream. Query shows a conversation with a separate evidence panel; Modules includes bounded member tables, supergraph, embeddings and figures; Data holds reports, evidence cards and downloads. The API remains branch-scoped and old `/kg/*` page routes redirect. Live HTTP checks and headless desktop/mobile rendering pass; manual point-and-click acceptance remains useful before external review. See [LEARNING_AND_NOTES/CONSTELLATIONS_INTERFACE_2026-10-06.md](LEARNING_AND_NOTES/CONSTELLATIONS_INTERFACE_2026-10-06.md).

Operational status: Constellations on port 10291 is the active service. The legacy service on port 10289 has been stopped and archived.

## MVP acceptance and proxy review — 2026-10-07

Thirteen actual Chromium interaction checks passed, including node/zoom/metapath flows, module pagination, local/Gemini queries, evidence, reports/downloads and mobile navigation. A semantic-card-ID retrieval defect was fixed and covered by a prompt-level regression. Measurement views now show units/provenance and large-gap warnings. Gemini succeeded after one transient 503 but claim-level citation presentation and conservative scientific wording still need acceptance review. The proxy audit distinguishes 606 catalogued contexts from 214 analyzed samples, exports all 625 gap flags (561 in the analyzed input), and confirms that all missing-depth requests concern controls. Source/instrument units/calibration records, the `mis` field meaning, gap decisions and depth-tie policy review remain open. See [acceptance and proxy evidence report](LEARNING_AND_NOTES/MVP_ACCEPTANCE_AND_PROXY_REVIEW_2026-10-07.md).

## TO DO — return to the MVP workstream (2026-10-07)

The user is temporarily switching direction. Preserve this backlog and resume it when returning to the KG/module MVP. Start with items 1 and 2 below, using the [acceptance and proxy evidence report](LEARNING_AND_NOTES/MVP_ACCEPTANCE_AND_PROXY_REVIEW_2026-10-07.md); the first implementation and audit pass is complete, but scientific acceptance remains open. This checkpoint does not change the completed repairs or approve unresolved proxy interpretations.

1. [ ] **Finish MVP acceptance.** Complete a human walkthrough of graph search, node selection, metapaths, module views, evidence and downloads. Review several Gemini questions and insufficient-evidence cases for grounding, claim-level citations and conservative wording. Headless visual/API checks and 13 automated browser interaction checks have passed; the semantic card-ID retrieval bug is fixed, and one Gemini synthesis succeeded with supplied evidence IDs. Detected-taxon counts must not be presented as validated biological diversity.
2. [ ] **Review proxy evidence.** Obtain source/instrument units, normalization and calibration records, especially for XRF, plus GeoB clay/source sums, ambiguous foraminifera fields and SST variants; clarify the metadata `mis` definition. Review unmatched coverage, all 625 large-gap values (561 within the analyzed sample set), and the deterministic shallower-level choice for 1,857 depth ties. Decide on any conservative interpolation sensitivity explicitly; retain original values and provenance. GeoB physical-core aliases and the 0.5-cm tolerance are already confirmed. Active inputs are in `data/metadata/` and `data/kg_feedstock/`; review exports are in `results/ngraph/mvp_permissive_mixed_20261005/knowledge_graph/review_20261007/`.
3. [ ] **Strengthen the two KG demonstrations.** Refine taxon→sample→SST and core→module→core examples with selected taxa/proxies, understandable results and traceable evidence. Keep truncated counts and descriptive scores explicit. Allow selection of module system; the current bridge traverses VGAE and DiffPool modules. Distinguish metadata SST from independently depth-matched calibration variants.
4. [ ] **Validate and annotate the six exploratory VGAE modules.** Compare mixed-abundance and TAD-only runs; examine detection/read-support sensitivity, graph/bootstrap stability, functional enrichment and null/baseline comparisons. Keep the annotations exploratory until these checks support interpretation.
5. [ ] **Test independent generalization.** Implement genuine site/core holdouts and suitable baselines. Current transductive reconstruction scores do not establish unseen-core performance or biological probabilities.
6. [ ] **Connect Query to the KG.** Route appropriate questions through typed graph searches with inspectable evidence, and add multi-turn context. Current retrieval handles each question independently and does not execute the KG searches.
7. [ ] **Prepare KG learning.** Curate ontology mappings and introduce relation-specific KG learning with baseline comparisons. Current module/VGAE learning does not consume the full KG.
8. [ ] **Tighten reproducibility and documentation.** Record complete staged/resumed commands in manifests, keep current status distinct from dated historical reports, and keep this checklist synchronized. Review and commit the uncommitted acceptance/proxy-review changes when that work is ready.

Resume context: active run `mvp_permissive_mixed_20261005`, 1,797 taxa, 214 analyzed samples and six exploratory VGAE modules. Constellations uses port 10291; the legacy port-10289 service is archived. No new scientific validation or matching-policy change is implied by the temporary change of direction.

Parallel research inputs: proxy unit/calibration documentation, preferred taxa/functions for module annotation, and expected biological connections for the two demonstrations. The concise return checklist is [TODO.md](TODO.md); keep it synchronized with this dated checkpoint.

### Functional annotation implementation checkpoint — 2026-10-08

The repaired branch `mvp_functional_20261008` completed discovery and base KG import, retaining 1,797 inventory taxa and assigning 1,717 to six exploratory modules; 80 remain explicitly unassigned. A completed `legacy_20261008` functional analysis provides descriptive reference support, 200-replicate fixed-membership centrality and core profiles, but no statistically qualified enrichment associations. Fresh annotation, enrichment sensitivity validation, browser acceptance and promotion remain open. See [the detailed implementation checkpoint](LEARNING_AND_NOTES/FUNCTIONAL_MODULE_ENRICHMENT_2026-10-08.md) and the additive [TODO checklist](TODO.md). The active established service remains 10291; the repaired-branch preview is loopback 10292. Existing MVP acceptance, proxy scientific review and independent generalization tasks are not superseded.

### Enrichment background and statistical validation — 2026-10-08

The `legacy_background_20261008` snapshot completed with explicit independent-reference background/coverage/QC exports. Statistical code now preserves all declared modules in primary correction, rejects unknown/background misalignment, moves complete annotation rows under a fixed conditional null, reports BH plus separate BY and Monte Carlo uncertainty, and computes tie-preserving vectorized KS. Separate partial-support, annotation-burden/quality and KO-level baseline paths are implemented but unexecuted on fresh real data. Annotation selection verifies raw outputs, execution/database/proteome identities and native sequence IDs; eggNOG transfer parsing retains GO/EC/COG features. Synthetic validation ran 100,000 permutations and 100 null datasets; focused tests reached 55 passes. KG integrity validation after the new legacy projection passed with zero dangling references and zero statistical functional associations. Fresh annotation remains blocked by missing tools/database paths, with an explicit isolated-installation question pending; do not report the enrichment work as scientifically complete. Details and artifact locations are in the functional checkpoint.

### Current enrichment status — 2026-10-08 (supersedes earlier pilot prerequisites)

- [x] Implement primary unweighted broad-catalog KEGG enrichment; 1,577 independent references, 954 tests, 381,600 matched permutations.
- [x] Add empirical-null Z, p/BH q, separate BY/Monte Carlo diagnostics and native carrier provenance; 61 focused tests pass.
- [x] Project four gated catalog associations; KG integrity passes with zero dangling references. Eight results pass primary q <= 0.05 before additional gates.
- [x] Keep abundance/depth/age profiles separate from primary enrichment; update the runner to the broad-catalog route.
- [ ] Review biological label specificity and original database provenance, especially the CAM enzyme framework; catalog support is not activity.
- [ ] Next version: weighted KS/ranked-affinity scoring, separate correction family and sensitivity evaluation. No weighted KS or affinity results are claimed for the current snapshot.
- [ ] Preserve the original ordered eight-action MVP backlog above, including independent-core holdout and mixed/TAD-only module validation.

See [current enrichment evidence](LEARNING_AND_NOTES/FUNCTIONAL_MODULE_ENRICHMENT_2026-10-08.md). The fresh 32-reference pilot is historical and optional, not an analysis prerequisite.

- [x] Complete automated interface/enrichment browser checks and promote the repaired enrichment branch to Constellations **10291**. Current branch: `mvp_functional_20261008`; current snapshot: `catalog_unweighted_20261008`. The previous browser/promotion checkbox is historical. Human MVP/Gemini/biological acceptance stays open.


### Functional KG integration — 2026-10-09

The combined taxon→module→association→function and reverse searches, same-taxon carrier mode, scoped canonical function lookup, versioned definitions/reference genomes, atomic retained graph snapshots and deterministic proof-producing functional Query are implemented. The active bundle is `functional-ad4cacf8c1ea6bf29e130b66` for `mvp_functional_20261008`/`prev_10`/Pearson/VGAE/`catalog_unweighted_20261008`. Four qualified associations are retained; source enrichment statistics were not recomputed. Full validation passes with 38,218 nodes, 364,315 edges and zero dangling references.

Constellations **10291** serves the integration; **10289 remains archived**, and loopback 10292 is a development preview. Knowledge Graph → Metapath search includes **Example: taxon to function**, carrier/all-member modes and compact/expanded views. Modules → Functions links to the authoritative association and scoped path. Query recognizes explicit taxon/module/KEGG identifiers and supplies inspectable proof IDs, scope and source hashes. It never infers individual activity solely from membership; ordinary retrieval and independently processed conversation turns remain available.

M3/M00091 has 206 community members and 110 supporting carriers. Automated validation comprises 76 functional/catalog tests, 11 focused browser checks and 12 wider interface checks; evidence is saved in `results/ngraph/mvp_functional_20261008/functional_validation/20261009/`. Human/scientific acceptance, general entity resolution and multi-turn Query remain open. Biological label specificity, unknown original annotation release, mixed/TAD-only stability and independent-core generalization still need review. Weighted KS, HMMs, curated ontology mappings and full KG learning remain future work.

See [implementation, acceptance evidence and reproduction commands](LEARNING_AND_NOTES/FUNCTIONAL_KG_REASONING_PLAN_2026-10-09.md).

### Functional RAG implementation plan 2026-10-12

The [new implementation plan](LEARNING_AND_NOTES/FUNCTIONAL_RAG_IMPLEMENTATION_PLAN_2026-10-12.md) extends the completed KG integration into the shared retrieval/synthesis infrastructure. First deliver compatible functional evidence indexes, recorded-name resolution and Gemini explanations with checked citations. Then add central supporting members, relative core profiles, backend follow-ups and selected reviewed semantic links. The plan defines code locations, dependencies and acceptance tests; implementation of these extensions has not started. The matching checklist is in [TODO.md](TODO.md).

The active service remains Constellations on 10291; 10289 remains archived. Unweighted enrichment remains primary, and the independent-core/module-validation/proxy-review backlog is preserved. Weighted KS, HMM niches and full KG learning are outside this integration delivery.


### Functional conversational integration 2026-10-12

The technical [functional RAG implementation](LEARNING_AND_NOTES/FUNCTIONAL_RAG_IMPLEMENTATION_PLAN_2026-10-12.md) is delivered on Constellations **10291**, joint bundle `functional-587688fa942779a82370eb1f`. Its 38,253 nodes, 367,509 edges and 2,602 evidence cards retain four qualified associations and the original enrichment statistics. Functional names, summaries/comparisons, supporting carriers, centrality, core profiles and bounded follow-ups now use shared scoped evidence. Gemini explanations have checked claim-level evidence and deterministic fallback. HTTP POST carries returned context; GET compatibility remains. Reindexing can rebuild the compatible KG/retrieval bundle without retraining or recomputing enrichment.

The KG adds selected native KO and recorded-category links. Reviewed semantic mapping infrastructure is present, but the GO/EC registry is empty pending supported curation. No biological equivalence, measured activity, fresh proteome remapping, weighted KS, HMM or KG-learning claim is implied. Biological specificity and original annotation release still require review.

Acceptance: 92 focused tests, 33 browser checks, full KG integrity/proxy validation and bounded HTTP/Gemini checks pass. Reports are in `results/ngraph/mvp_functional_20261008/functional_validation/20261012/`. Port 10289 remains archived; 10292 is a preview. Existing dated checkpoints are historical; the original scientific/proxy/generalization backlog remains open.


### Gemini console diagnosis and repair — 2026-10-19

Live API and browser reproduction found that general queries used a 512-token output budget. The same prompt returned `MAX_TOKENS` with invalid JSON at 512 and `STOP` with valid JSON at 2,048. The adapter previously marked both as `ok`, and general synthesis displayed incomplete JSON as prose. The default is now 2,048 (explicit overrides remain supported); finish reasons, empty/invalid responses and the general answer contract are checked before displaying synthesis. Functional claim validation is retained.

The console now explains synthesis failures while showing local evidence, bounds requests to 90 seconds, and retains answers in memory if session storage is blocked/full. Storage failure was reproduced with an injected quota error; the user's actual browser storage condition is not established. POST requests now log model/status/finish reason without credentials. No failed authentication or provider outage was reproduced during this diagnosis.

Regression checks: 8 response-integrity tests, 88 functional tests and the existing retrieval regression pass. The new `tests/verify_gemini_console.cjs` exercises live general/functional Gemini answers plus controlled truncation and storage-failure display. Diagnosis artifacts and browser acceptance reports are under `logs/rag_diagnosis_20261019/`. Constellations remains on 10291; 10289 remains archived. These are response-delivery checks, not biological acceptance.


### Scoped conversation and climate semantics repair — 2026-10-19

This supersedes earlier claims that successful Gemini delivery establishes scientific grounding. Query now resolves community module identity separately from annotation availability. `M24`, `module 24`, and `DiffPool M24` identify the same recorded DiffPool module; the response explicitly reports that this system has no enrichment analysis in the current snapshot. Scoped follow-ups retain the selection, and an explicit `VGAE module 3` switches to its available annotations. Canonical IDs supply scope where legacy node columns are null. General retrieval selects one module system instead of mixing VGAE and DiffPool records. Service and CLI share the functional routing contract; broad key-findings requests use the bounded functional KG overview.

General Gemini responses now constrain evidence IDs to the exact supplied IDs, check citations and selected module identities, validate referenced module/function pairs and rounded statistics, and reject unsupported positive cooperation/climate/causal interpretations. Typed functional answers use the same interpretation guard plus their graph-proof checks. UI labels distinguish citation/scope checks from typed functional evidence checks, show the selected analysis, and mark older unscoped answers as historical. These bounded programmatic checks do not establish arbitrary semantic entailment or replace human scientific acceptance.

The legacy median-`mis` transition analysis is retired from active query execution. All 548 comparable metadata rows match linear interpolation of the local LR04 benthic delta18O stack at `y_bp / 1000`, with maximum absolute error approximately 6.22e-15. Another 58 rows are unassessed because values/ages are missing or outside the stack range. Historical scripts explicitly use `d18O = mis`. The field is therefore a continuous age-derived LR04 isotope proxy, not an integer MIS stage or an independent local isotope measurement. The LR04 dataset documents isotope units as per mil: https://doi.org/10.1594/PANGAEA.701576 . Provenance, source hashes, examples and exclusions are recorded in `data/reference/metadata_semantics_20261019.json`; reproduce with the ngraph Python interpreter and `scripts/ngraph_climate_context.py`. Source metadata, frozen enrichment results and KG snapshots are preserved.

Climate questions now return source evidence and an explicit unavailable-analysis explanation. No stage boundaries, glacial/interglacial classes, transition windows or MIS–function association tests were invented. Those remain subsequent analysis work. Generalization, biological annotation review, XRF/proxy calibration, module robustness, weighted KS and the original MVP acceptance backlog remain open.

Acceptance for the 2026-10-19 scope/climate repair: 121 tests and 11 browser checks passed. The final five-question HTTP replay on 10291 returned explicit climate-analysis unavailability, identified DiffPool M24 under both spellings, and validated the VGAE M3 and bounded key-findings syntheses. Source hashes and reports: `logs/query_semantics_20261019/validation_summary.json`. Port 10289 remains archived; the temporary 10293 preview has been stopped.
