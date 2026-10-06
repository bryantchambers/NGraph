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

The mixed KG now uses curated XRF, user-confirmed GeoB physical-core aliases, depth matches within 0.5 cm and bracketed linear interpolation without extrapolation. Its schema, source-value reconstruction, coverage accounting and GeoB library consistency checks pass. Unknown native units and large interpolation gaps remain explicit. The current browser is `http://localhost:10291/kg/paths`; port 10290 retains the earlier TAD-only prototype. See [current mixed sensitivity and KG report](LEARNING_AND_NOTES/KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md).

Run a fresh mixed MVP with `bash run_mvp.sh`. To reproduce the TAD-only comparison, use `NG_ABUNDANCE_MODE=hybrid_prevalence_tad_matrix bash run_mvp.sh`. Both commands create a fresh run branch by default.

## Constellations interface — 2026-10-06

The development web UI has been replaced with Constellations at `/`: a left rail for Overview, Knowledge Graph, Query, Modules and Data. The Knowledge Graph has distinct graph-browser, typed-metapath and schema views; Overview derives source/core/sample/age/location and analysis counts from the active workstream. Query shows a conversation with a separate evidence panel; Modules includes bounded member tables, supergraph, embeddings and figures; Data holds reports, evidence cards and downloads. The API remains branch-scoped and old `/kg/*` page routes redirect. Live HTTP checks and headless desktop/mobile rendering pass; manual point-and-click acceptance remains useful before external review. See [LEARNING_AND_NOTES/CONSTELLATIONS_INTERFACE_2026-10-06.md](LEARNING_AND_NOTES/CONSTELLATIONS_INTERFACE_2026-10-06.md).
