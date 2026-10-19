# Constellations interface — 2026-10-06

The discovery web service now presents itself as **Constellations**. The new interface uses the warm cream, restrained gold, card spacing, and left-rail navigation shown in `LEARNING_AND_NOTES/WebInterfaceDesign/`. The product pages are served from `web_assets/constellations/`; `scripts/14_ngraph_local_browser.py` remains the numbered server entry point so existing launch commands and API clients continue to work. Its development-era inline HTML and KG page generator have been removed. Legacy `/kg/*` page URLs redirect to the relevant Constellations view; `/api/*` routes remain available.

## Navigation and data flow

- **Overview** derives counts from the active branch at service start or when watched run artifacts change. It shows KG nodes/relations, module sizes, evidence cards, ontology terms/namespaces, embeddings, link hypotheses, run status, registered sources, four analyzed libraries, 214 samples, the active age range, and three analyzed physical locations for the current mixed run. The source inventory also plots the catalogued ST5 site, clearly marked as outside the analyzed set. GeoB R1/R2 share one physical location. A manual refresh button also updates the snapshot.
- **Knowledge Graph** has clear Graph browser, Metapath search, and Graph schema tabs. The graph canvas is the larger left panel. Search and core selectors set the focus; hop depth, relation, node type and caps control bounded graph rendering. Node selection opens its source/evidence detail. Metapath search has typed source/target suggestions, two saved examples, path count, descriptive degree-weighted score, a selected-path graph and inspectable source values/IDs. Counts marked as lower bounds remain labelled.
- **Query** keeps the existing local query and optional Gemini adapter. Conversation turns remain visible in browser session storage, and the supporting cards/links for the selected answer are shown in a separate right column. The backend still treats each question independently; multi-turn context is future work.
- **Modules** provides the core supergraph, VGAE and DiffPool module explorer, bounded member pages, an embedding view and generated figures. The module dropdown keeps the full module summary while a particular group is selected.
- **Data** contains an indexed, allowlisted file catalogue with source data, KG tables, reports and figures; Markdown report preview; evidence-card search; source inventory and geolocation. File serving is streamed and rejects paths absent from the catalogue.

The new `scripts/ngraph_constellations_catalog.py` computes the Overview and file catalogue. The service reloads its branch data when watched run, KG, card, sample-abundance or module files change; this keeps counts aligned as the MVP is rebuilt. The front end uses the vendored Cytoscape renderer, a single system font stack and no new external runtime dependency.

## Run and validation

Run `bash start_server.sh 10291`; the default workstream is `mvp_permissive_mixed_20261005`, with `prev_10` and Pearson as the active view. Open `http://localhost:10291/`. Set `NG_BRANCH` and `NG_PRIMARY_THRESHOLD` for another output workstream. The historical TAD-only run remains separate.

## Active service and archive status

Port **10291** is the active Constellations service. The legacy browser that served `abundance_thresholding` on port **10289** has been shut down and is archived; do not use it as the current interface. This operational status was confirmed on 2026-10-06.

Validation on the mixed workstream covered Python syntax; JavaScript syntax with Node; the live Overview, module selection, supergraph, cards, local query, downloads and source files; route and asset serving; legacy redirects; bounded, type-diverse KG neighborhoods and typed metapaths; and rejection of an unlisted file. `tests/verify_mvp_http.py --branch mvp_permissive_mixed_20261005 --port 10291` passed. Headless Chromium rendered and visually checked desktop Overview, KG browser, metapath example, Modules, Query, Data, and a mobile Overview. The graph preview was adjusted after that inspection to hide crowded labels and preserve connected node types. Manual point-and-click acceptance remains useful before an external MVP review. This is an interface and service reorganization, not a new scientific validation of modules or KG learning.

Runtime versions observed: Python 3.14.5, pandas 2.3.3, NumPy 2.4.6, NetworkX 3.6.1, and vendored Cytoscape.js 3.30.2. No packages were installed.

## Acceptance follow-up — 2026-10-07

Actual automated Chromium interactions now pass the 13 checks described in [the acceptance/proxy review report](MVP_ACCEPTANCE_AND_PROXY_REVIEW_2026-10-07.md). A RAG card-ID mismatch was repaired; a live Gemini request succeeded with supplied evidence IDs after a transient 503. Scientific answer quality and claim-level citations remain a separate acceptance task. Measurement views now show unit/source provenance and large-gap warnings. The active server runs in tmux session `ngraph-constellations` on 10291; `start_server.sh` also defaults to 10291.

### Enrichment service promotion — 2026-10-08

Constellations **10291** now serves `mvp_functional_20261008`, using the completed `catalog_unweighted_20261008` enrichment snapshot. `bash start_server.sh 10291` defaults to this repaired branch; `NG_BRANCH` still selects a historical run. Port **10289 remains archived**. The loopback 10292 service is a development preview, not the active user-facing endpoint.

Modules → Functions provides unweighted enrichment, permutation Z, empirical p/BH q, paginated carriers and native KO provenance. Modules → Core profiles keeps relative abundance/depth/age summaries separate. Weighted KS/affinity scoring is deferred to the next version. The catalog's original annotation release remains unknown; results describe recorded reference potential rather than measured activity.

Automated acceptance: all 12 interface browser checks and seven focused enrichment checks passed against the promoted build on the 10292 preview. The active 10291 endpoint is checked separately after startup. Reports/screenshots are in `results/ngraph/mvp_functional_20261008/functional_validation/20261008/`. Gemini grounding and biological interpretation still require human review; these checks do not establish those acceptance gates.


### Functional KG integration — 2026-10-09

The combined taxon→module→association→function and reverse searches, same-taxon carrier mode, scoped canonical function lookup, versioned definitions/reference genomes, atomic retained graph snapshots and deterministic proof-producing functional Query are implemented. The active bundle is `functional-ad4cacf8c1ea6bf29e130b66` for `mvp_functional_20261008`/`prev_10`/Pearson/VGAE/`catalog_unweighted_20261008`. Four qualified associations are retained; source enrichment statistics were not recomputed. Full validation passes with 38,218 nodes, 364,315 edges and zero dangling references.

Constellations **10291** serves the integration; **10289 remains archived**, and loopback 10292 is a development preview. Knowledge Graph → Metapath search includes **Example: taxon to function**, carrier/all-member modes and compact/expanded views. Modules → Functions links to the authoritative association and scoped path. Query recognizes explicit taxon/module/KEGG identifiers and supplies inspectable proof IDs, scope and source hashes. It never infers individual activity solely from membership; ordinary retrieval and independently processed conversation turns remain available.

M3/M00091 has 206 community members and 110 supporting carriers. Automated validation comprises 76 functional/catalog tests, 11 focused browser checks and 12 wider interface checks; evidence is saved in `results/ngraph/mvp_functional_20261008/functional_validation/20261009/`. Human/scientific acceptance, general entity resolution and multi-turn Query remain open. Biological label specificity, unknown original annotation release, mixed/TAD-only stability and independent-core generalization still need review. Weighted KS, HMMs, curated ontology mappings and full KG learning remain future work.

See [implementation, acceptance evidence and reproduction commands](FUNCTIONAL_KG_REASONING_PLAN_2026-10-09.md).


### Functional conversational integration 2026-10-12

The technical [functional RAG implementation](FUNCTIONAL_RAG_IMPLEMENTATION_PLAN_2026-10-12.md) is delivered on Constellations **10291**, joint bundle `functional-587688fa942779a82370eb1f`. Its 38,253 nodes, 367,509 edges and 2,602 evidence cards retain four qualified associations and the original enrichment statistics. Functional names, summaries/comparisons, supporting carriers, centrality, core profiles and bounded follow-ups now use shared scoped evidence. Gemini explanations have checked claim-level evidence and deterministic fallback. HTTP POST carries returned context; GET compatibility remains. Reindexing can rebuild the compatible KG/retrieval bundle without retraining or recomputing enrichment.

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
