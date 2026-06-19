# NGraph Deep Knowledge Discovery Workplan

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
