# NGraph KG MVP implementation plan — 2026-10-05

The MVP prioritizes a usable knowledge graph with explainable connectivity search and reasonable, explicitly exploratory module annotations. Historical outputs remain reference comparisons. The new run uses its own output workstream and records the actual retained taxon count; approximately 1,784 taxa is a comparison target, not a forced count.

## Delivery sequence

1. Implement the requested damage/read gate, aggregate observations, use TAD/read fallback for prevalence only, build a TAD-only abundance matrix, remove empty samples, then compute CLR. Compare the retained taxa and information content with the existing TAD-only and abundance-fallback runs.
2. Fix the prevalence denominator, model checkpoint copies, feature scales, DiffPool assignment normalization, and evaluation negative sampling. Export explicit split/task descriptions. Produce a demonstration partition selected from 6–8 groups, labeled as a constrained exploratory annotation rather than biological validation. Report group sizes and functional reference coverage.
3. Repair the KG substrate: distinguish control contexts from sediment sites; preserve observations and import coverage; account for GeoB aliases, matching tolerances and unit status; scope module IDs; enforce endpoint/type/ID integrity.
4. Add a reusable KG connectivity engine with ordered predicates, explicit inverse traversal, simple paths, degree-weighted path counts, source/target lookup and evidence details. Biological paths exclude ontology/dataset/provenance hubs. No significance claim is made without a validated null model.
5. Integrate connectivity search into the browser, fix neighborhood/filter/limit defects, and expose artifact/run validation status. Add a reproducible launch command and run manifest. Run the new workstream and exercise the demonstration through HTTP and browser interactions when browser tooling is available.

## Acceptance checks

- A synthetic filtering example distinguishes fallback-for-prevalence from fallback-in-the-matrix, handles duplicate observations and empty samples, and proves sample-centered CLR.
- The real dataset comparison records retention counts, zero-TAD taxa, unique profiles, sample counts and graph input coverage without replacing historical results.
- Checkpoint tensors are independent copies; numeric transformations are finite and recorded; negatives exclude known positives and split membership is reproducible. Evaluation is described according to the information actually available to the model.
- Module output has 6–8 occupied groups for the demonstration, coverage and size tables, reference annotations, and an explicit exploratory/constrained status. Identical or unsupported taxa are not presented as independently learned biological evidence.
- KG validation reports unique IDs, no dangling endpoints, declared endpoint types, retained observations, unit status and matched/unmatched import counts. Missing scientific metadata stays explicit.
- Toy graphs establish exact path counts, inverse traversal, degree weighting and path evidence; limits expose truncation rather than silently claiming complete counts.
- HTTP checks cover connectivity, neighborhood depth, taxon/site links, limits, empty results and validation status. A saved manifest records commands, settings, package versions and code/input hashes.

## Research requested from the user

- Confirm whether GeoB25202 proxy chronology can be linked to both R1 and R2, and supply acceptable age/depth matching tolerances.
- Identify authoritative proxy units and age uncertainty metadata; unknown values remain marked unknown.
- Choose two demonstration questions and any preferred taxa, proxy variables or biological functions.

These questions do not block filtering, model corrections, schema validation or metapath implementation. Unconfirmed alias links will remain marked provisional or unmatched.

## Progress

- Plan created; implementation started. Package and runtime availability will be checked from the installed `ngraph` environment without installing packages.

## Implemented MVP status (2026-10-05)

The bounded `mvp_permissive_tad` run now provides the filtering/matrix comparison, corrected VGAE/DiffPool training path, structurally validated file-backed KG, typed connectivity queries and browser API. Its result and evidence are documented in [MVP_IMPLEMENTATION_RESULTS_2026-10-05.md](MVP_IMPLEMENTATION_RESULTS_2026-10-05.md). The HTTP validation artifact is present and API checks passed; visual browser inspection is still pending. Unit/regression and structural checks do not establish biological validity. Proxy units, GeoB alias policy, provisional age/depth tolerances, module stability/coherence and independent site/core generalization remain open scientific gates. Preserve the original plan and acceptance criteria above as the record of intended work.

## Fresh-run verification (2026-10-05)

The command `NG_BRANCH=mvp_permissive_tad_20261005 bash run_mvp.sh` completed successfully; its run manifest records `status: completed`. Stages 00–13 and 15 completed, including KG endpoint domain/range checks against `config_kg_schema.json`, real-artifact/demo validation and independent raw-to-CLR regression. The full results and limits are recorded in [MVP_IMPLEMENTATION_RESULTS_2026-10-05.md](MVP_IMPLEMENTATION_RESULTS_2026-10-05.md). The HTTP/browser checks passed on the existing development branch served at port 10290; a fresh-run visual browser check remains pending.

## User-selected mixed matrix and KG substrate update (2026-10-05)

Add the `mvp_permissive_mixed_20261005` sensitivity alongside the earlier TAD-only MVP: apply the read gate on source rows before duplicate aggregation, then use post-aggregation TAD/read fallback in the matrix and prevalence. Its learner includes all 1,797 threshold-retained taxa; preserve the earlier 438-TAD-supported learner as a separate comparison. The KG substrate now uses canonical hashed feedstock, physical-core/depth matching, bounded interpolation, explicit unit status and retained source/interpolation provenance. Details, artifact evidence, current manifest status and remaining acceptance work are in [KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md](KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md). Component checks passed; the earlier failed `--stop 09` checkpoint came from an interrupted inefficient validator. The validator was optimized, all later stages/audits passed, and the final manifest now reports completion. Visual UI inspection is still pending.

## Mixed-matrix and proxy-substrate sensitivity (2026-10-05)

User-approved sensitivity: `run_mvp.sh` defaults to `hybrid_aggregated_tad_then_read`, applying the `n_reads >= 100` source-row gate before duplicate aggregation, then fallback after aggregation for both the matrix and prevalence. Keep the earlier TAD-only-matrix path as a separate comparison (`NG_ABUNDANCE_MODE=hybrid_prevalence_tad_matrix` on a fresh branch; `tad_only` changes the prevalence policy). The newer KG uses physical-core/depth matching, retains native/interpolation provenance, and leaves unknown units explicit. See [KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md](KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md) for metrics and coverage. Component validations passed, including API checks on port 10291. An interim manifest checkpoint was marked failed after an inefficient validator was interrupted; the optimized validator and all later stages/audits passed, and the final manifest now records `completed`.

## Final mixed-run and proxy decisions (2026-10-05)

The mixed branch now has final `run_manifest.json` status `completed`. All stages 00–09 and 10–15 completed, followed by independent KG/module audits, proxy-matching and unit tests, mixed raw-to-CLR regression, HTTP/new-label checks and rendered-JavaScript syntax checks. The interim failed checkpoint was an interrupted inefficient validator; optimization and all subsequent checks passed. The current manifest's command field still names the earlier `--stop 09` invocation, so use its final status together with the subsequent validator artifacts/logs. See [KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md](KG_SUBSTRATE_AND_MIXED_SENSITIVITY_2026-10-05.md).

The user confirmed the 0.5 cm depth matching rule; physical-core/depth GeoB matching and the 2,929 same-depth comparisons resolve the former alias question without age-only joins. Open proxy review is limited to unresolved source/instrument units/calibration and the 625 flagged large-gap interpolations. The TAD-only matrix comparator is `NG_ABUNDANCE_MODE=hybrid_prevalence_tad_matrix`; `tad_only` would change the prevalence policy and is not the same comparator. The launcher defaults to `hybrid_aggregated_tad_then_read` and automatically sets `NG_TAD_SUPPORTED_ONLY=false`; the TAD-only-matrix comparator automatically defaults that flag to `true`.
