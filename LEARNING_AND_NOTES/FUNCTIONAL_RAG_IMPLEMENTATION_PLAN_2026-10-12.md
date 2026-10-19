# Functional enrichment integration implementation plan

Date: 2026-10-12. Status: planned implementation. This extends the completed [functional KG integration](FUNCTIONAL_KG_REASONING_PLAN_2026-10-09.md) into ordinary-language retrieval, explanations, contributor questions, profiles and conversation context.

The first delivery should let a user ask which modules support a named function and receive an explanation with statistics and clickable KG evidence. Subsequent deliveries add module comparisons, central supporting members, core profiles, follow-up questions and selected ontology links. Unweighted enrichment remains the primary annotation. Weighted KS, HMM niches and full KG learning remain separate future work.

## Existing foundation

Constellations serves `mvp_functional_20261008` on port 10291. The selected KG bundle is `functional-ad4cacf8c1ea6bf29e130b66`, with annotation snapshot `catalog_unweighted_20261008`. Typed functional paths, same-taxon witnesses, versioned definitions, immutable graph snapshots and conservative deterministic answers are implemented.

The current service intercepts functional questions before the ordinary RAG orchestrator. Explicit IDs work; names such as phosphatidylcholine biosynthesis need resolution. The retrieval index uses existing evidence cards, and the functional runner does not rebuild that index. Contributor centrality and relative depth/age profiles are available through separate APIs, but functional Query does not combine them. Conversation history is displayed without backend follow-up interpretation.

The primary analysis contains 954 hypotheses and four published associations. These are different views of the same analysis: a tested result is not automatically a positive KG assertion. Original annotation release and biological label review remain explicit limitations.

## Shared query and evidence contract

Introduce a versioned structured request/result contract before changing routing. Every functional request carries the question, requested intent, resolved entity IDs, evidence mode and scope. Scope includes discovery branch, prevalence threshold, network method, module system, annotation snapshot and KG snapshot. Core/library and depth/age selections are optional context filters.

Results carry resolution status, the executed template and filters, deterministic claims, association/proof IDs, statistics, source hashes, native witnesses, counts/caps and unknowns. Keep empirical p, BH q, permutation Z, effects and coverage separate. Preserve undefined Z as missing. The original q-values retain their full correction family when a user filters the display.

Use the same contract from the browser and command-line query engine. Keep existing GET queries compatible and add POST for structured context. The graph and frozen analysis tables supply facts; the language model explains only supported claims.

## Ordered implementation

### 1 Unify evidence retrieval and snapshot publication

Extend `scripts/ngraph_rag_orchestrator.py` to accept functional graph proofs and scoped analysis summaries in its retrieval bundle. Add a small reusable functional retrieval utility if necessary; reuse `ngraph_functional_paths.py`, the existing inventory indexes and connectivity implementation.

Build searchable cards for qualified associations, function definitions and module summaries, with stable evidence IDs derived from the assertion/definition and snapshot. Keep carrier expansion bounded and retrieve native annotations on demand. Preserve older cards, while distinguishing historical descriptive labels from the current statistical annotation. Handle all tested results through an explicit descriptive results mode with their status; do not publish them all as positive graph links.

Extend `12_ngraph_build_retrieval_index.py` and `run_functional.sh` so functional output can be indexed without retraining discovery or recomputing enrichment. Reuse TF-IDF and indexed entity lookup initially. Bind the retrieval manifest to KG, annotation, definition and source hashes.

Extend atomic publication to select a compatible KG/retrieval pair only after both validate. This requires staging graph publication, validating a candidate bundle and building its matching index before activation. Reindexing an existing KG remains supported. Serve the previous complete pair during an interrupted build, and reject mismatched indexes rather than silently answering from another analysis. Watch the selection and validation records for service refresh.

Acceptance: a stored association is discoverable by its name, its card reproduces frozen statistics/provenance, and a failed or mismatched rebuild leaves the previous pair usable. Repeated builds are reproducible and retain historical snapshots.

### 2 Resolve names and execute broader query templates

Add a shared entity resolver, proposed as `scripts/ngraph_functional_query.py`, and use it from both `14_ngraph_local_browser.py` and `13_ngraph_query_engine.py`. Resolve explicit IDs first, then exact scoped labels and reviewed aliases. Use text similarity to suggest candidates; ambiguity produces a clarification response rather than an invented mapping. Taxon names must come from recorded metadata/mappings. Distinguish community module M3 from KEGG functional module M00003.

Support an allowlisted set of intents: module functional summary, function-to-modules, taxon support, supporting carriers, all-module overview, and comparison of two selected modules. Reuse existing typed searches and frozen tables. Return all relevant counts even when the evidence display is paginated; expose truncation. Comparisons describe existing results and do not introduce a new significance test.

Return resolved entities and scope in the response so the UI can display and reuse them. Explicitly report modules without qualified results under the selected policy. Selecting another discovery run or annotation snapshot must not silently reuse a same-named module.

Acceptance: name-based and ID-based queries resolve to the same assertion; broad summaries and M3/M4 comparisons work; ambiguous names, unknown taxa and cross-run M3 labels stay separated.

### 3 Add grounded Gemini explanations and citations

Replace the service's early deterministic return with a unified functional execution followed by optional synthesis through `ngraph_rag_orchestrator.py`. Local mode retains the deterministic answer. Gemini receives the actual selected statistics, reviewed definitions, native support, coverage and limitations, rather than a generic statement that a capability table exists.

Add claims with evidence IDs to the structured synthesis response. Validate returned IDs against the supplied bundle, check entity/numeric facts against structured records, and restrict claims to the approved evidence types. Never infer individual function solely from module membership, infer activity from reference potential, equate centrality with causality, or treat an unrecorded function as biological absence. Definition names such as CAM remain recorded enzyme frameworks with their biological review status.

If the provider fails or an answer fails validation, return the deterministic evidence answer with an explicit synthesis status. In the right evidence panel, each citation should open the relevant assertion/proof or source record with its original scope. Automated validation does not substitute for scientific review of the prose.

Acceptance: local and Gemini answers refer to the same evidence; unknown citations, incorrect statistics and prohibited claims fail validation; provider errors preserve a useful answer; citations open the correct proof.

### 4 Retrieve supporting central members and core profiles

Join the selected association's carrier set to existing module centrality exports using taxon, module and analysis scope. Keep positive/negative connectivity and bootstrap summaries explicit. Distinguish all structural hubs from the subset with recorded functional support, and show unmapped taxa separately. Ranking carriers by centrality changes presentation, not the unweighted enrichment test. Describe central taxa as structurally central supporting members, not proven functional drivers.

Add query templates for module and reference-function profiles along core depth or age. Reuse the profile APIs and link answers to the existing plots. Keep sample-wide reference-function profiles distinct from module-restricted profiles; a module filter must not relabel a sample-wide estimate. Preserve physical core/library identity, units, measured range and relative-abundance interpretation. Statistical trend or proxy association claims require a separate implemented analysis.

Primary files: `14_ngraph_local_browser.py`, the shared functional query utility, `ngraph_rag_orchestrator.py` and `web_assets/constellations/app.js`.

Acceptance: central-carrier answers reproduce the carrier/centrality join, and depth/age answers reproduce the selected exported profile with correct units and scope. Missing profiles and unsupported trend claims remain explicit.

### 5 Add bounded conversation context

Extend POST queries with versioned context containing resolved entities, selected scope, prior successful intent and bounded previous turns. Keep MVP state in the existing browser session storage, isolated by tab/session. The backend must consume and revalidate this context; a supplied history cannot create evidence or bypass entity/scope checks.

Resolve follow-ups such as “Which taxa support that?” against the previous resolved function/module. Explicit new selections override inherited context. Ambiguous pronouns require clarification. Clear-session resets displayed history and execution context. Pin evidence to its snapshot; an unavailable or changed analysis produces a visible context reset or an explicit historical selection, not a silent switch.

Update the Query caption and evidence selection only after this behavior works. Full conversation persistence and cross-user history are outside this MVP.

Acceptance: function→carrier→core-profile follow-ups preserve scope, explicit changes override context, clearing resets it, and separate tabs/snapshot changes cannot leak selections.

### 6 Extend selected KG semantics and biological review

Introduce selected KO concepts and typed support links from the existing native evidence, with reference/provider identity and definition completeness retained. Avoid materializing every reference gene. Add a versioned mapping registry for reviewed GO, EC and broader functional categories when source evidence supports them. Record whether a mapping is exact or related; broader categories do not inherit child enrichment q-values.

Extend `config_kg_schema.json`, `ngraph_functional_kg.py` and `ngraph_validate_functional_graph.py` alongside these relations. Return interpretation/review status in retrieval cards and Query. Preserve the unknown original annotation release until source documentation establishes it. No fresh proteome remapping is required for this integration.

Acceptance: selected module→function→KO/category paths retain source evidence, incompatible definitions fail validation, and unsupported mappings create no inferred equivalence or experimental evidence.

### 7 Complete evaluation and service acceptance

Create a fixed question/evidence suite covering explicit IDs, names, summaries, comparisons, qualified versus tested results, carriers versus members, centrality, profiles, ambiguity, missing evidence, follow-ups, source changes and provider failure. Use synthetic fixtures for exact scope/count checks and the existing frozen analysis for artifact agreement.

Run unit/API tests, then actual Chromium navigation/citation/profile/context checks on the development preview. Exercise Gemini against a bounded representative suite and review explanations manually. Save requests, scopes, evidence IDs, validation/provider statuses, versions, timings and screenshots under a dated validation directory. Never log credentials. Measure bounded retrieval/expansion before changing storage technology.

Promote the reviewed build to Constellations 10291 and verify its listener, branch, active pair, cited answers and downloads. Keep 10289 archived. Preserve existing KG integrity checks, source hashes and historical documentation. Scientific module stability, mixed/TAD-only sensitivity and independent-core generalization remain separate acceptance items.

## Delivery sequence

| Delivery | Dependencies | User outcome |
| --- | --- | --- |
| Ordinary-language functional answers | Steps 1–3 and their tests | Ask about a named function or module and receive an explanation with statistics and clickable KG proof. |
| Contributors and environmental context | Steps 1–4 | Identify structurally central supporting taxa and inspect the corresponding relative core profiles. |
| Conversational exploration | Steps 1–5 | Follow up without repeating resolved names, while keeping scope and evidence explicit. |
| Reviewed semantic expansion | Step 6 after the shared evidence contract | Traverse selected KO/category links with reviewed mappings and provenance. |
| MVP acceptance | Step 7 after each relevant delivery | Use the tested build on 10291 with saved acceptance evidence. |

Start with the shared contract and compatible evidence/index publication, then entity resolution and Gemini synthesis. Contributor/profile retrieval and conversation context can extend that foundation. Biological label and mapping review can proceed alongside implementation; only reviewed mappings become ontology assertions.

## Useful research inputs

Provide preferred biological function names and synonyms, a few representative contributor/core questions, and any original KO/database-release documentation. Review the specificity of existing CAM, phosphatidylcholine, heme and nucleotide framework labels. These inputs improve interpretation and the acceptance suite without changing the approved broad-catalog background.

Implementation scripts should use the existing `ngraph` environment, log commands/package versions and source hashes, and use seed 42 for stochastic checks. No new dependency is planned. Implementation will verify installed versions rather than treating an older runtime inventory as current.


## Implementation checkpoint 2026-10-12

The technical integration is implemented and promoted to Constellations **10291**. The active joint KG/retrieval bundle is `functional-587688fa942779a82370eb1f`: 38,253 nodes, 367,509 edges and 2,602 searchable evidence cards. The original `catalog_unweighted_20261008` enrichment tables and their four published associations are unchanged. Port 10289 remains archived; 10292 is the development preview.

Delivered: one functional query contract for HTTP and CLI; recorded-name resolution with ambiguity/unknown handling; module summaries/comparisons; qualified carriers and centrality; relative core profiles with matching plot/source links; backend follow-ups with snapshot resets; claim-validated Gemini synthesis with local fallback; and a TF-IDF index inside the immutable KG bundle. Publication can stage a candidate, validate it, and atomically activate its graph and retrieval together. Source/graph/index hash mismatches fail before activation. Historical bundles and descriptive cards are retained and labelled.

The scope contract rejects foreign discovery/module-system identifiers and stale context. Module IDs are excluded from function-name matching, including the recorded O-glycan definition containing “core M3.” Central-carrier queries use the carrier sets of the published associations. Core restrictions affect connectivity/context; they do not recompute global enrichment. Sample-wide reference-function profiles are explicitly distinct from module profiles. Missing results are not interpreted as biological absence.

Gemini receives the actual proof/statistic bundle. Claims require valid evidence IDs and compatible claim types; association entities must share a proof path, and individual support needs the same-taxon function witness. Incorrect statistics, unsupported activity/causality/probability claims and invalid responses use the deterministic fallback. Missing/non-finite values become JSON null. Functional synthesis defaults to a 2,048-token output budget unless `NG_GEMINI_MAX_OUTPUT_TOKENS` is explicitly configured. Two live examples passed validation and prose review: M00091→M3 and the two M4 framework associations. This bounded review does not establish general scientific answer quality.

Selected KO definition mentions, native reference KO records and recorded category links are now in the KG. Logical AND/OR/optional definitions remain intact; KO/category links are not separate enrichment tests. The reviewed GO/EC/category mapping importer and registry are implemented at `data/reference/functional/semantic_mappings.tsv`, but the registry has **no approved mappings**. Biological label review, original annotation-release recovery and actual GO/EC curation remain open. No new proteome annotation, weighted KS, HMM or KG training was run.

### Acceptance and commands

Acceptance evidence is in `results/ngraph/mvp_functional_20261008/functional_validation/20261012/`; logs are in `logs/functional_rag_20261012/`. Validation covers 88 functional tests plus four catalog/statistics tests, 11 graph-path browser checks, 10 conversational browser checks, 12 wider interface checks, and the real HTTP question suite including two Gemini answers. Full KG/proxy validation passes with zero dangling references. Python/JavaScript syntax, shell syntax and the shared standalone query backend also pass. Live production checks are recorded separately from the preview checks.

Example conversation: “Which modules support phosphatidylcholine biosynthesis?” → “Which taxa support that?” → “Show that along depth in ST8” → “What about ST13?” The M00091 carrier count is 110; its ST8 profile has 115 exported sample records. “Which central taxa support M00091 in ST8?” returns 29 matching structural records. These quantities have different denominators.

HTTP accepts GET for existing clients and POST `/api/query` with `query`, `llm_provider`, optional `context` and optional `scope`. Reuse the returned `context` for functional follow-ups. Clear-session removes that execution context. Context is bounded and validated per request; no shared server conversation store was added.

Reindex the selected frozen functional analysis without retraining or recomputing enrichment:

```bash
PY_NGRAPH=/maps/projects/caeg/people/gfx654/miniforge3/envs/ngraph/bin/python
NG_LOG_SCOPE=functional_rag_20261012 "$PY_NGRAPH" scripts/12_ngraph_build_retrieval_index.py --branch mvp_functional_20261008 --functional-only
"$PY_NGRAPH" scripts/13_ngraph_query_engine.py --branch mvp_functional_20261008 --query 'Which modules support phosphatidylcholine biosynthesis?' --llm-provider local
"$PY_NGRAPH" tests/verify_functional_rag_http.py --port 10291 --output /tmp/ngraph-functional-http
```

`run_functional.sh` now stages projection, builds its bound retrieval index, validates the candidate, and activates the validated pair. Existing statistical analysis snapshots remain immutable. To run a fresh enrichment analysis, supply a new analysis snapshot as previously documented. The explicit `--gemini` HTTP test flag enables the bounded provider checks.

### Open scientific and semantic work

Populate only provenance-backed reviewed semantic mappings, review CAM/other label specificity and recover original annotation documentation where possible. Species-name aliases require recorded metadata; unknown names are not inferred. General unconstrained conversations, statistical trend analysis, full ontology reasoning and independent-core/module-stability acceptance remain outside the implemented bounded query templates. Weighted KS remains the next statistical version. The original ordered MVP backlog is retained.


### Scoped conversation and climate semantics repair — 2026-10-19

This supersedes earlier claims that successful Gemini delivery establishes scientific grounding. Query now resolves community module identity separately from annotation availability. `M24`, `module 24`, and `DiffPool M24` identify the same recorded DiffPool module; the response explicitly reports that this system has no enrichment analysis in the current snapshot. Scoped follow-ups retain the selection, and an explicit `VGAE module 3` switches to its available annotations. Canonical IDs supply scope where legacy node columns are null. General retrieval selects one module system instead of mixing VGAE and DiffPool records. Service and CLI share the functional routing contract; broad key-findings requests use the bounded functional KG overview.

General Gemini responses now constrain evidence IDs to the exact supplied IDs, check citations and selected module identities, validate referenced module/function pairs and rounded statistics, and reject unsupported positive cooperation/climate/causal interpretations. Typed functional answers use the same interpretation guard plus their graph-proof checks. UI labels distinguish citation/scope checks from typed functional evidence checks, show the selected analysis, and mark older unscoped answers as historical. These bounded programmatic checks do not establish arbitrary semantic entailment or replace human scientific acceptance.

The legacy median-`mis` transition analysis is retired from active query execution. All 548 comparable metadata rows match linear interpolation of the local LR04 benthic delta18O stack at `y_bp / 1000`, with maximum absolute error approximately 6.22e-15. Another 58 rows are unassessed because values/ages are missing or outside the stack range. Historical scripts explicitly use `d18O = mis`. The field is therefore a continuous age-derived LR04 isotope proxy, not an integer MIS stage or an independent local isotope measurement. The LR04 dataset documents isotope units as per mil: https://doi.org/10.1594/PANGAEA.701576 . Provenance, source hashes, examples and exclusions are recorded in `data/reference/metadata_semantics_20261019.json`; reproduce with the ngraph Python interpreter and `scripts/ngraph_climate_context.py`. Source metadata, frozen enrichment results and KG snapshots are preserved.

Climate questions now return source evidence and an explicit unavailable-analysis explanation. No stage boundaries, glacial/interglacial classes, transition windows or MIS–function association tests were invented. Those remain subsequent analysis work. Generalization, biological annotation review, XRF/proxy calibration, module robustness, weighted KS and the original MVP acceptance backlog remain open.

Acceptance for the 2026-10-19 scope/climate repair: 121 tests and 11 browser checks passed. The final five-question HTTP replay on 10291 returned explicit climate-analysis unavailability, identified DiffPool M24 under both spellings, and validated the VGAE M3 and bounded key-findings syntheses. Source hashes and reports: `logs/query_semantics_20261019/validation_summary.json`. Port 10289 remains archived; the temporary 10293 preview has been stopped.
