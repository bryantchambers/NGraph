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
