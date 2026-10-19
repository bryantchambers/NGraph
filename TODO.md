# TODO — KG and module MVP

Current checkpoint (2026-10-09): functional KG integration is implemented on `mvp_functional_20261008` at port **10291**. The dated checkpoints below preserve the earlier sequence and superseding decisions. The ordered MVP backlog remains open, with functional annotation and explicit-ID functional Query now delivered.

Updated 2026-10-07. This workstream is temporarily deferred at the user's request while another direction is explored. Return to the actions below in this order. Detailed checkpoint: [WORKPLAN.md](WORKPLAN.md). Current evidence: [MVP acceptance and proxy review](LEARNING_AND_NOTES/MVP_ACCEPTANCE_AND_PROXY_REVIEW_2026-10-07.md).

1. [ ] **Finish MVP acceptance.** Complete a human walkthrough of graph search, node selection, metapaths, module views, evidence and downloads. Review Gemini answers for grounding and citation accuracy, including insufficient-evidence cases. Headless visual/API checks and 13 automated Chromium interaction checks passed; these do not replace human acceptance or establish general scientific answer quality.
2. [ ] **Review proxy evidence.** Resolve units and calibration records, especially XRF; review all 625 large-gap interpolation flags and unmatched coverage. GeoB aliases and the 0.5-cm depth rule are settled. Also review the metadata `mis` definition and depth-tie policy. Of the 625 flags, 561 affect analyzed samples.
3. [ ] **Strengthen the two KG demonstrations.** Polish taxon→sample→SST and core→module→core searches with selected taxa/proxies, understandable results and traceable evidence. Keep truncated counts and descriptive scores explicit; distinguish module systems and SST source/calibration variants.
4. [ ] **Validate and annotate the six exploratory modules.** Compare mixed-abundance and TAD-only results; check detection/read-support sensitivity; assess resampling stability, functional enrichment and simple null/baseline comparisons. Aim for defensible MVP annotations.
5. [ ] **Test independent generalization.** Add a genuine site/core holdout. Current reconstruction scores are transductive and do not establish unseen-core performance.
6. [ ] **Connect Query to the KG.** Let questions invoke typed graph searches and return evidence. Functional explicit-ID questions now execute scoped graph templates with proof evidence (2026-10-09). General routing and multi-turn context remain open; conversation history is displayed, but questions are processed independently.
7. [ ] **Prepare the next learning layer.** Curate ontology mappings and introduce relation-specific KG learning with suitable baselines. Current VGAE/module models do not learn the full KG.
8. [ ] **Tighten reproducibility and documentation.** Record staged/resumed commands accurately in manifests and consolidate dated status updates into a clear current checklist. Review and commit the outstanding acceptance/proxy-review changes when ready.

Parallel research inputs: **proxy unit/calibration documentation**, **preferred taxa/functions for module annotation**, and **expected biological connections for the two demonstrations**.

Resume from `mvp_permissive_mixed_20261005`: 1,797 taxa, 214 analyzed samples and six exploratory VGAE modules. Constellations uses port **10291**; port **10289** is archived. The RAG card-ID mismatch is fixed; measurement views expose units, provenance and large-gap warnings. Proxy evidence tables are in `results/ngraph/mvp_permissive_mixed_20261005/knowledge_graph/review_20261007/`. Unknown units and unreviewed interpolations remain unresolved.

## Functional enrichment checkpoint — 2026-10-08

The module annotation direction is now active. Preserve the ordered MVP list above; this work advances item 4 and repairs discovery inputs. Current implementation and remaining gates: [functional enrichment checkpoint](LEARNING_AND_NOTES/FUNCTIONAL_MODULE_ENRICHMENT_2026-10-08.md).

- [x] Repair local eligibility, annotation-feature leakage and unassigned taxon handling; complete the repaired discovery/KG run.
- [x] Audit native KO/reference/module evidence and retrieve a 32-proteome pilot.
- [x] Generate descriptive legacy functional summaries, signed-network centrality with 200 depth-block replicates and native depth/age profiles.
- [x] Implement scoped functional APIs and conservative KG publication gates; verify real-artifact API responses.
- [ ] Install missing tools after the pending explicit installation decision; freeze authorized database snapshots and perform fresh annotation.
- [ ] Compare pilot annotations, validate corrected enrichment and complete sensitivity/secondary scoring work. Zero qualified associations currently exist.
- [ ] Complete browser acceptance and promote the reviewed functional branch to Constellations 10291. The temporary loopback preview is 10292; 10289 stays archived.
- [ ] Complete stricter graph, mixed/TAD-only and module stability comparisons; preserve independent-core holdout as a separate open task.

### Statistical/background follow-up — 2026-10-08

- [x] Freeze explicit independent-reference backgrounds; prevent unknown annotation cells becoming negatives and preserve all declared modules in the correction family.
- [x] Implement fixed whole-row permutations, BH plus separate BY sensitivity, Monte Carlo diagnostics and vectorized tie-preserving KS.
- [x] Add separate partial-support, annotation-burden/quality and individual-KO sensitivity code paths; these await fresh real-data execution.
- [x] Verify fresh-annotation provenance and native sequence identities; preserve GO/EC/COG complementary features.
- [x] Complete 100,000-permutation synthetic signal/confounding checks and a 100-dataset null check; preserve their limited scope.
- [ ] Resolve the pending isolated annotation-environment/Kofam database decision and run the 32-reference fresh pilot; no fresh statistical enrichment has been computed yet.

### Superseding annotation scope correction

The user directs the main workflow to use broad existing mappings for module/function set enrichment. The 32-proteome pilot is **not** a required analysis background or prerequisite; the preceding fresh-pilot dependency items are historical. Current next steps are to audit the existing export's reporting coverage, construct the broad eligible annotated background, run/rank set enrichment with effect sizes and multiple-testing correction, validate conditional permutation sensitivity, and expose supporting taxa in the portal/KG. Preserve unknowns and annotation provenance; HMM modelling remains deferred.

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

### Functional KG paths and reasoning plan — 2026-10-09

Plan: [functional annotation paths and reasoning](LEARNING_AND_NOTES/FUNCTIONAL_KG_REASONING_PLAN_2026-10-09.md). Existing module→association→function and taxon→reference-annotation→function links are implemented; the combined taxon→module→association→function preset and bounded functional reasoning are now implemented. The plan retains its original proposed stages and adds the implementation evidence.

- [x] Add the combined metapath, same-taxon carrier-witness mode, explicit analysis-scope filters, Z/null/provenance path details and reverse function searches.
- [x] Add saved examples and deep links from taxa, modules and functional results; show membership separately from reference support.
- [x] Add stable function concepts/versioned definitions, evidence constraints and atomic retained KG snapshots.
- [x] Implement deterministic proof-producing rules and KG-backed Query; never inherit function/activity solely from module membership.
- [x] Validate positive/member-only/unknown/cross-run fixtures and real browser paths.

Unweighted enrichment remains primary. Weighted KS/ranked affinity stays next-version work; HMM niches and relation-specific KG learning remain later tasks. Preserve the original ordered MVP backlog.


Implementation evidence (2026-10-09): 76 functional/catalog tests, 11 focused and 12 wider browser checks pass; the active bundle `functional-ad4cacf8c1ea6bf29e130b66` has zero dangling references. M3/M00091 reverse search returns 206 members, 110 supporting carriers. No activity claim is inherited from membership. Original KEGG release/biological label review, general entity resolution, multi-turn Query, curated ontology mappings and the original validation/holdout backlog remain open.

### Functional RAG implementation plan 2026-10-12

The next implementation plan is [Functional enrichment integration implementation plan](LEARNING_AND_NOTES/FUNCTIONAL_RAG_IMPLEMENTATION_PLAN_2026-10-12.md). It extends the completed functional KG paths; the technical query and retrieval integration is now implemented; scientific and semantic curation remain open. Preserve the original ordered MVP backlog.

- [x] Define the shared functional query/evidence contract, index functional cards and atomically select compatible KG/retrieval snapshots.
- [x] Resolve recorded names/aliases and add all-module summaries, comparisons and scoped query templates.
- [x] Feed functional proofs/statistics into Gemini with claim-level citations, validation and deterministic fallback.
- [x] Retrieve central supporting carriers and existing relative depth/age profiles through Query.
- [x] Add backend follow-up interpretation with bounded, isolated and snapshot-aware conversation context.
- [x] Add selected KO links and reviewed GO/EC/category mappings with provenance and semantic validation.
- [x] Complete the question/evidence suite, browser/provider/scientific review and promotion checks on 10291.

First delivery: ordinary-language functional questions with cited graph evidence. Weighted KS, HMMs and full KG learning remain subsequent work.


Implementation checkpoint (2026-10-12): active joint bundle `functional-587688fa942779a82370eb1f` on 10291; 38,253 nodes, 367,509 edges, 2,602 cards and four unchanged qualified associations. Acceptance: 92 focused tests, 33 browser checks, full KG integrity and the HTTP/Gemini suite pass. See the plan for examples, commands and saved evidence.

- [ ] Populate approved GO/EC/category mappings; the validated registry/importer exists but no mappings are approved yet.
- [ ] Complete biological label/original-release review and broader human scientific acceptance. Preserve the original module-stability, independent-core and proxy-review backlog.


### Query scope and climate evidence repair — 2026-10-19

- [x] Resolve module-number aliases and preserve module-system identity across follow-ups; explain unavailable DiffPool annotation.
- [x] Apply citation/scope/association/statistic and conservative interpretation checks to synthesis; distinguish checked outputs from provider success.
- [x] Establish the `mis` field's continuous LR04 delta18O meaning with a reproducible all-row source audit. This resolves the earlier field-definition question, not XRF or other proxy calibration questions.
- [x] Retire the median-split transition answer and expose source provenance and missing-analysis limitations in Query.
- [ ] Next: define reviewed MIS-stage boundaries/transition windows and implement core-aware module/function climate-association analyses. Existing enrichment scores do not test climate association.
- [ ] Preserve independent-core/module-stability, biological review and the remaining original MVP checklist.

See the dated repair checkpoint in WORKPLAN.md and the functional RAG plan. Evidence and browser replays are stored under `logs/query_semantics_20261019/`.
