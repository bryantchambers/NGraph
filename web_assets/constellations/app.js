/* Constellations: small, branch-scoped interface over the existing read-only API. */
"use strict";

const fmt = new Intl.NumberFormat("en-US");
const state = { overview: null, schema: null, catalog: null, kgCy: null, moduleCy: null, selectedNode: "", pathResult: null, cards: [], currentPage: "overview" };
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value == null ? "" : value).replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));
const numeric = (value) => Number.isFinite(Number(value)) ? fmt.format(Number(value)) : "—";
const params = (values) => new URLSearchParams(Object.entries(values).filter(([, value]) => value !== "" && value != null));

async function api(path, values = {}) {
  const query = params(values).toString();
  const response = await fetch(query ? `${path}?${query}` : path, {cache: "no-store"});
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try { const body = await response.json(); detail = body.error || detail; } catch (_) { /* status is enough */ }
    throw new Error(detail);
  }
  return response.json();
}

function notify(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => toast.classList.remove("show"), 5500);
}

async function attempt(work, prefix = "Unable to load data") {
  try { return await work(); }
  catch (error) { notify(`${prefix}: ${error.message}`); throw error; }
}

function pageHead(kicker, title, description, actions = "") {
  return `<div class="page-head page-head-split"><div><div class="eyebrow">${esc(kicker)}</div><h1>${esc(title)}</h1><p>${esc(description)}</p></div>${actions ? `<div class="page-actions">${actions}</div>` : ""}</div>`;
}

function stat(label, value, sub = "") {
  return `<div class="stat"><div class="stat-label">${esc(label)}</div><div class="stat-number">${esc(value)}</div>${sub ? `<div class="stat-sub">${esc(sub)}</div>` : ""}</div>`;
}

function chip(label, tone = "") { return `<span class="chip ${tone}">${esc(label)}</span>`; }

function table(rows, columns, maxRows = 20) {
  if (!rows || !rows.length) return `<div class="empty">No records in this view.</div>`;
  const cols = columns || Object.keys(rows[0]);
  return `<div class="table-frame"><table><thead><tr>${cols.map((col) => `<th>${esc(col.replaceAll("_", " "))}</th>`).join("")}</tr></thead><tbody>${rows.slice(0, maxRows).map((row) => `<tr>${cols.map((col) => `<td>${esc(row[col])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>${rows.length > maxRows ? `<p class="small muted" style="margin:8px 0 0">Showing ${maxRows} of ${numeric(rows.length)} rows. Use the filters to narrow the view.</p>` : ""}`;
}

function bars(counts, cap = 10) {
  const entries = Object.entries(counts || {}).sort((a, b) => b[1] - a[1]).slice(0, cap);
  if (!entries.length) return `<div class="empty">No values available.</div>`;
  const largest = Math.max(...entries.map(([, n]) => Number(n)), 1);
  return `<div class="bar-list">${entries.map(([name, n]) => `<div class="bar-row"><strong title="${esc(name)}">${esc(name)}</strong><div class="bar-track"><div class="bar-fill" style="width:${Math.max(2, Math.round(Number(n) / largest * 100))}%"></div></div><span class="bar-value">${numeric(n)}</span></div>`).join("")}</div>`;
}

function details(record, fields) {
  const rows = fields.filter(([key]) => record && record[key] != null && String(record[key]) !== "");
  return rows.length ? `<dl class="detail-list">${rows.map(([key, label]) => `<div class="detail-row"><dt>${esc(label)}</dt><dd>${esc(record[key])}</dd></div>`).join("")}</dl>` : `<div class="empty">Select a record to see its context.</div>`;
}

function coordinatePlot(locations) {
  const sites = (locations || []).filter((row) => row.latitude != null && row.longitude != null);
  if (!sites.length) return `<div class="empty">No source coordinates recorded.</div>`;
  const bounds = {lonMin:-35, lonMax:-15, latMin:58, latMax:68};
  const x = (lon) => 60 + (Number(lon) - bounds.lonMin) / (bounds.lonMax - bounds.lonMin) * 440;
  const y = (lat) => 220 - (Number(lat) - bounds.latMin) / (bounds.latMax - bounds.latMin) * 170;
  const lines = [-30,-25,-20].map((lon) => `<line class="gridline" x1="${x(lon)}" x2="${x(lon)}" y1="25" y2="220"/><text x="${x(lon)-10}" y="242">${lon}°</text>`).join("") + [60,64,68].map((lat) => `<line class="gridline" x1="60" x2="500" y1="${y(lat)}" y2="${y(lat)}"/><text x="15" y="${y(lat)+4}">${lat}°</text>`).join("");
  const dots = sites.map((row, index) => `<g><circle class="site-dot ${row.active === false ? "inactive" : ""}" cx="${x(row.longitude)}" cy="${y(row.latitude)}" r="${index ? 7 : 8}"/><text class="site-label" x="${x(row.longitude)+11}" y="${y(row.latitude)-9-index*16}">${esc(row.site)}</text><title>${esc(row.site)} · ${esc(row.latitude)}° N, ${esc(row.longitude)}° E · ${row.active === false ? "catalogued" : "analyzed"}</title></g>`).join("");
  return `<div class="map-wrap"><svg viewBox="0 0 540 260" role="img" aria-label="Latitude and longitude of source core locations">${lines}${dots}</svg></div><div class="map-caption">Gold: analyzed sites · gray: catalogued source. GeoB libraries share one physical location.</div>`;
}

function setPage(route, label) {
  state.currentPage = route;
  $("page-crumb").textContent = label;
  document.title = `${label} · Constellations`;
  document.querySelectorAll("#primary-nav a").forEach((link) => {
    if (link.dataset.route === route) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
}

function pathSection(key, choices) {
  const url = new URL(window.location.href);
  const selected = choices.includes(url.searchParams.get(key)) ? url.searchParams.get(key) : choices[0];
  return selected;
}

function subTabs(id, labels, selected, change) {
  const container = $(id);
  container.innerHTML = Object.entries(labels).map(([key, label]) => `<button type="button" role="tab" aria-selected="${key === selected}" data-view="${esc(key)}">${esc(label)}</button>`).join("");
  container.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => change(button.dataset.view)));
}

async function ensureSchema() {
  if (!state.schema) state.schema = await api("/api/kg/schema");
  return state.schema;
}

async function ensureCatalog() {
  if (!state.catalog) state.catalog = (await api("/api/data/catalog")).files || [];
  return state.catalog;
}

function linkToFile(file) { return `/api/data/file?id=${encodeURIComponent(file.id)}`; }

async function renderOverview() {
  setPage("overview", "Overview");
  const view = $("app-view");
  view.innerHTML = pageHead("Research atlas", "Find patterns across deep time", "An at-a-glance view of the active knowledge graph, source cores, evidence, and exploratory module analysis.", `<button class="button secondary" id="refresh-overview">↻ Refresh snapshot</button>`)
    + `<div class="hero-note" id="overview-analysis"></div><div class="stats" id="overview-stats"></div><div class="grid overview"><div class="stack"><section class="panel"><div class="panel-title"><h2>Module structure</h2><a href="/modules" class="button text">Explore modules →</a></div><div id="overview-modules"></div></section><section class="panel"><div class="panel-title"><h2>Knowledge graph composition</h2><a href="/knowledge-graph" class="button text">Open graph →</a></div><div class="grid two"><div><div class="upper" style="margin-bottom:12px">Nodes by type</div><div id="overview-nodes"></div></div><div><div class="upper" style="margin-bottom:12px">Relations by type</div><div id="overview-relations"></div></div></div></section><section class="panel"><div class="panel-title"><h2>Evidence and ontology</h2><a href="/data" class="button text">Browse data →</a></div><div class="grid two"><div><div class="upper" style="margin-bottom:12px">Evidence cards</div><div id="overview-evidence"></div></div><div><div class="upper" style="margin-bottom:12px">Ontology namespaces</div><div id="overview-ontology" class="chips"></div></div></div></section></div><div class="stack"><section class="panel"><h2>Source material</h2><div id="overview-sources"></div></section><section class="panel"><h2>Where the cores come from</h2><div id="overview-map"></div><div id="overview-locations" style="margin-top:14px"></div></section><section class="panel panel-soft"><h2>Run state</h2><div id="overview-state"></div></section></div></div>`;
  $("refresh-overview").addEventListener("click", async () => { state.overview = await attempt(() => api("/api/overview"), "Overview refresh failed"); fillOverview(); notify("Overview rebuilt from the current workstream."); });
  fillOverview();
}

function fillOverview() {
  const data = state.overview;
  const c = data.counts || {};
  $("overview-analysis").textContent = data.analysis_label || "Active exploratory analysis";
  const age = data.age_range_years_bp;
  const ageText = age ? `${(age[0] / 1000).toFixed(1)}–${(age[1] / 1000).toFixed(1)} kyr BP` : "Age range unavailable";
  $("overview-stats").innerHTML = [
    stat("KG nodes", numeric(c.kg_nodes), `${numeric(c.kg_edges)} relations`), stat("Exploratory modules", numeric(c.modules), `${numeric(c.taxa_in_modules)} assigned taxa`),
    stat("Analyzed cores", numeric(c.cores), `${numeric(c.physical_sites)} physical sites`), stat("Samples", numeric(c.samples), ageText),
    stat("Evidence cards", numeric(c.evidence_cards)), stat("Ontology terms", numeric(c.ontology_terms), "linked term records"),
    stat("Embeddings", numeric(c.embeddings)), stat("Link hypotheses", numeric(c.link_hypotheses))
  ].join("");
  $("overview-modules").innerHTML = bars(data.module_sizes);
  $("overview-nodes").innerHTML = bars(data.node_types, 7);
  $("overview-relations").innerHTML = bars(data.edge_types, 7);
  $("overview-evidence").innerHTML = bars(data.card_types, 6);
  $("overview-ontology").innerHTML = (data.ontology_namespaces || []).map((name) => chip(name)).join("") || `<span class="muted small">No ontology namespace recorded.</span>`;
  $("overview-sources").innerHTML = `<p class="small">${numeric(c.data_sources)} registered data sources support this branch. The analyzed age range is ${esc(ageText)}.</p><div class="chips">${Object.entries(data.core_samples || {}).map(([core, n]) => chip(`${core} · ${numeric(n)} samples`)).join("")}</div><div class="table-frame short" style="margin-top:14px"><table><thead><tr><th>Dataset</th><th>Source</th></tr></thead><tbody>${(data.sources || []).map((row) => `<tr><td>${esc(row.name)}</td><td>${esc(row.source_file.split("/").pop())}</td></tr>`).join("")}</tbody></table></div>`;
  $("overview-map").innerHTML = coordinatePlot(data.registered_locations || data.locations);
  $("overview-locations").innerHTML = table((data.registered_locations || data.locations || []).map((row) => ({site: row.site, status: row.active ? "Analyzed" : "Catalogued", coordinates: row.latitude == null ? "unknown" : `${Number(row.latitude).toFixed(3)}° N, ${Number(row.longitude).toFixed(3)}° E`})), ["site", "status", "coordinates"], 8);
  $("overview-state").innerHTML = `<div class="chips">${chip(`Run: ${data.run_status}`)}${chip(`KG audit: ${data.validation?.kg || "unverified"}`)}${chip(`${data.threshold} / ${data.method}`)}</div><p class="small" style="margin:14px 0 0">Counts describe the active branch. Module assignments and link scores remain exploratory; the graph audit checks structure and provenance.</p><div class="upper" style="margin:14px 0 8px">${numeric((data.workstreams || []).length)} recorded workstreams</div><div class="chips">${(data.workstreams || []).map((name) => chip(name,name===data.branch ? "active" : "")).join("")}</div>`;
}

const nodePalette = {site:"#a77921",sample:"#5b9b87",taxon:"#4b806d",module:"#866b9a",proxymeasurement:"#648ba0",proxyvariable:"#567f9a",dataset:"#8b8b80",ontologyterm:"#bd8b5d",analysisrun:"#656b75",controlcontext:"#9c8e83",functionalfeature:"#648c89",functionalconcept:"#648c89",referencegenome:"#8a9a72",referencefunctionalannotation:"#8a9a72",modulefunctionalassociation:"#a47798"};
function graphStyle() {
  const base = [
    {selector:"node",style:{"background-color":"#798d81","label":"data(label)","color":"#373930","font-family":"Inter, Segoe UI, sans-serif","font-size":10,"text-wrap":"ellipsis","text-max-width":"105px","text-valign":"bottom","text-margin-y":5,"width":18,"height":18,"border-width":2,"border-color":"#fffdfa","overlay-opacity":0}},
    {selector:"edge",style:{"line-color":"#c5bba9","width":1.35,"opacity":.72,"curve-style":"bezier","target-arrow-shape":"triangle","target-arrow-color":"#c5bba9","arrow-scale":.65}},
    {selector:"node:selected",style:{"border-width":4,"border-color":"#b8831d","width":26,"height":26}},
    {selector:"edge:selected",style:{"line-color":"#a77921","target-arrow-color":"#a77921","width":3}}
  ];
  base.push({selector:"edge.association",style:{"target-arrow-shape":"none"}});
  base.push({selector:"edge.negative",style:{"line-color":"#bd8173","line-style":"dashed"}});
  Object.entries(nodePalette).forEach(([type, color]) => base.push({selector:`node.${type}`,style:{"background-color":color,"width":type === "site" ? 29 : type === "module" ? 25 : 18,"height":type === "site" ? 29 : type === "module" ? 25 : 18,"shape":type === "module" ? "diamond" : type === "site" ? "round-rectangle" : "ellipse"}}));
  base.push({selector:"node.sample, node.taxon, node.proxymeasurement",style:{"label":""}});
  base.push({selector:"node.sample:selected, node.taxon:selected, node.proxymeasurement:selected",style:{"label":"data(label)"}});
  return base;
}

function destroyGraph(name) { if (state[name]) { state[name].destroy(); state[name] = null; } }
function mountGraph(containerId, nodes, edges, name, layout = "cose", onNode = null) {
  destroyGraph(name);
  const container = $(containerId);
  if (!container || typeof cytoscape !== "function") { if (container) container.innerHTML = `<div class="empty">Graph renderer unavailable.</div>`; return null; }
  if (!nodes || !nodes.length) { container.innerHTML = `<div class="empty">No connected nodes for this selection.</div>`; return null; }
  container.replaceChildren();
  const present = new Set(nodes.map((n) => n.data.id));
  const validEdges = (edges || []).filter((e) => present.has(e.data.source) && present.has(e.data.target));
  const styles=graphStyle();
  if (layout === "preset") styles.push({selector:"node.sample, node.taxon, node.proxymeasurement",style:{"label":"data(label)","text-max-width":"150px"}});
  const cy = cytoscape({container, elements:[...nodes, ...validEdges],style:styles,layout:{name:layout,animate:false,fit:true,padding:38},minZoom:.18,maxZoom:3,wheelSensitivity:.16});
  if (onNode) cy.on("tap","node",(event) => onNode(event.target.id()));
  cy.on("mouseover","node",(event) => event.target.style("label",event.target.data("label")));
  cy.on("mouseout","node",(event) => event.target.removeStyle("label"));
  state[name] = cy;
  requestAnimationFrame(() => { cy.resize(); cy.fit(undefined,36); });
  return cy;
}

function graphLegend() {
  return `<div class="legend">${[["site","Core"],["sample","Sample"],["taxon","Taxon"],["module","Module"],["proxymeasurement","Measurement"],["proxyvariable","Proxy"],["ontologyterm","Ontology"],["functionalfeature","Function"]].map(([key,label]) => `<span class="legend-item"><span class="legend-dot" style="background:${nodePalette[key]}"></span>${label}</span>`).join("")}</div>`;
}

function functionalReview(node) {
  if(!["FunctionalFeature","ReferenceFunctionalAnnotation","ModuleFunctionalAssociation"].includes(node?.node_type)) return "";
  return `<div class="insight" style="margin-top:12px"><strong>Exploratory reference-supported potential</strong><p class="small" style="margin:6px 0">Function support is based on reference annotations; it does not establish measured activity or causality.</p>${details(node,[["function_id","Function"],["function_namespace","Namespace"],["test_method","Test"],["prevalence_difference","Effect"],["p_value","p value"],["q_value","q value"],["permutation_z_score","Permutation Z"],["evidence_scope","Evidence scope"],["threshold","Threshold"],["method","Network"],["module_system","Assignment"],["biological_review_status","Biological review"],["definition_sha256","Definition hash"],["annotation_coverage","Mapped coverage"],["annotation_status","Annotation status"],["db_snapshot","Database snapshot"],["genome_id","Reference genome"],["gene_ids","Native gene IDs"],["ko_ids","KOs"],["source_path","Native source"],["source_row","Native row"],["functional_manifest","Analysis manifest"]])}</div>`;
}

async function renderKnowledgeGraph(viewName = null) {
  destroyGraph("kgCy");
  setPage("knowledge-graph", "Knowledge Graph");
  const view = viewName || pathSection("view", ["browser","metapaths","schema"]);
  $("app-view").innerHTML = pageHead("Connected evidence", "Knowledge Graph", "Follow samples, taxa, modules and measured proxies through a typed, provenance-aware graph.")
    + `<div class="tabs" id="kg-tabs" role="tablist" aria-label="Knowledge graph views"></div><div id="kg-view"></div>`;
  subTabs("kg-tabs", {browser:"Graph browser",metapaths:"Metapath search",schema:"Graph schema"}, view, (next) => { const url = new URL(window.location.href); url.pathname = "/knowledge-graph"; url.searchParams.set("view",next); history.pushState({},"",url); renderKnowledgeGraph(next); });
  await attempt(async () => {
    if (view === "browser") await renderGraphBrowser();
    else if (view === "metapaths") await renderMetapaths();
    else await renderSchema();
  }, "Knowledge graph view failed");
}

async function renderGraphBrowser() {
  const schema = await ensureSchema();
  const initial = new URLSearchParams(location.search).get("id") || state.selectedNode || `site:${state.overview.locations?.[0]?.site || "ST8"}`;
  $("kg-view").innerHTML = `<div class="panel" style="margin-bottom:16px"><div class="filters"><div class="field wide"><label for="kg-search">Find a node</label><input id="kg-search" placeholder="Search a core, taxon, module, sample or proxy" autocomplete="off"></div><div class="field"><label for="kg-search-type">Type</label><select id="kg-search-type"><option value="">All types</option>${(schema.node_types || []).map((row) => `<option value="${esc(row.node_type)}">${esc(row.node_type)} (${numeric(row.count)})</option>`).join("")}</select></div><button class="button" id="kg-search-button" type="button">Search nodes</button></div><div id="kg-search-results" class="result-list" style="display:none;margin-top:12px"></div></div>
    <div class="graph-layout"><section class="panel graph-stage"><div class="panel-title"><div><h2>Network canvas</h2><div class="small muted" id="kg-graph-summary">Choose a core or node to explore.</div></div><div class="button-row"><button type="button" class="button secondary" id="kg-fit">Fit graph</button></div></div><div class="filters" style="margin-bottom:12px"><div class="field"><label for="kg-core">Start at core</label><select id="kg-core"><option value="">Custom node</option>${(state.overview.locations || []).map((row) => `<option value="site:${esc(row.site)}">${esc(row.site)}</option>`).join("")}</select></div><div class="field"><label for="kg-focus">Focus node ID</label><input id="kg-focus" value="${esc(initial)}"></div><div class="field"><label for="kg-depth">Reach</label><select id="kg-depth"><option value="1">1 step</option><option value="2" selected>2 steps</option><option value="3">3 steps</option></select></div><div class="field"><label for="kg-limit">Node cap</label><select id="kg-limit"><option>40</option><option selected>70</option><option>100</option><option>150</option></select></div><div class="field"><label for="kg-edge">Relation</label><select id="kg-edge"><option value="">All relations</option>${(schema.edge_types || []).map((row) => `<option value="${esc(row.edge_type)}">${esc(row.edge_type)}</option>`).join("")}</select></div><div class="field"><label for="kg-node-filter">Show node type</label><select id="kg-node-filter"><option value="">All types</option>${(schema.node_types || []).map((row) => `<option value="${esc(row.node_type)}">${esc(row.node_type)}</option>`).join("")}</select></div><button class="button" id="kg-load" type="button">Draw graph</button></div><div class="graph-canvas" id="kg-canvas" role="img" aria-label="Interactive knowledge graph neighborhood"></div><div class="graph-tools"><span class="small muted">Drag nodes · scroll to zoom · select a node for its evidence</span><span id="kg-truncation" class="small muted"></span></div>${graphLegend()}</section>
    <aside class="stack"><section class="panel"><div class="panel-title"><h2>Selected node</h2><span id="kg-node-badge" class="badge badge-soft">No selection</span></div><div id="kg-node-detail" class="small muted">Click a node in the graph or choose a search result.</div><div class="button-row" style="margin-top:14px"><button type="button" class="button secondary" id="kg-focus-selected">Center on node</button><button type="button" class="button secondary" id="kg-to-path">Use in metapath</button></div></section><section class="panel"><div class="panel-title"><h2>Visible relations</h2><span class="small muted" id="kg-edge-count"></span></div><div id="kg-neighbor-table"></div></section></aside></div>`;
  $("kg-core").value = [...$("kg-core").options].some((opt) => opt.value === initial) ? initial : "";
  $("kg-core").addEventListener("change", () => { if ($("kg-core").value) $("kg-focus").value = $("kg-core").value; });
  $("kg-load").addEventListener("click", () => attempt(loadNeighborhood, "Graph load failed"));
  $("kg-fit").addEventListener("click", () => state.kgCy?.fit(undefined,36));
  $("kg-focus-selected").addEventListener("click", () => { if (state.selectedNode) { $("kg-focus").value = state.selectedNode; attempt(loadNeighborhood, "Graph load failed"); } });
  $("kg-to-path").addEventListener("click", () => {
    const node=state.selectedKgRecord;
    const pattern={Taxon:'taxon_module_function',Module:'module_function',FunctionalFeature:'function_module_taxon',FunctionalConcept:'function_module_taxon',Site:'site_taxon'}[node?.node_type];
    if(!pattern) return notify('Choose a taxon, community module, function or core to start one of the available metapaths.');
    sessionStorage.setItem('constellations-metapath-source',node.node_id);
    const context=params({view:'metapaths',pattern,source:node.node_id,threshold:node.threshold,method:node.method,kind:node.module_system,snapshot:node.db_snapshot});
    location.href=`/knowledge-graph?${context}`;
  });
  $("kg-search-button").addEventListener("click", () => attempt(searchKgNodes, "Node search failed"));
  $("kg-search").addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); attempt(searchKgNodes, "Node search failed"); } });
  await loadNeighborhood();
}

async function searchKgNodes() {
  const query = $("kg-search").value.trim();
  if (!query) { $("kg-search-results").style.display = "none"; return; }
  const data = await api("/api/kg/search",{query,node_type:$("kg-search-type").value,limit:12});
  const box = $("kg-search-results");
  box.style.display = "grid";
  box.innerHTML = (data.rows || []).length ? data.rows.map((row) => `<button class="result-item" data-id="${esc(row.node_id)}"><strong>${esc(row.label || row.node_id)}</strong><span>${esc(row.node_type)} · ${esc(row.node_id)}</span></button>`).join("") : `<div class="empty">No matching nodes. Try a shorter name or another type.</div>`;
  box.querySelectorAll("button[data-id]").forEach((button) => button.addEventListener("click", () => { $("kg-focus").value = button.dataset.id; box.style.display = "none"; attempt(loadNeighborhood,"Graph load failed"); }));
}

async function loadNeighborhood() {
  const focus = $("kg-focus").value.trim();
  const data = await api("/api/kg/neighborhood",{id:focus,depth:$("kg-depth").value,limit:$("kg-limit").value,edge_type:$("kg-edge").value,node_type:$("kg-node-filter").value});
  const elements = data.elements || {nodes:[],edges:[]};
  mountGraph("kg-canvas",elements.nodes || [],elements.edges || [],"kgCy","cose",(id) => attempt(() => showNode(id),"Node details failed"));
  $("kg-graph-summary").textContent = `${numeric((elements.nodes || []).length)} visible nodes · ${numeric((elements.edges || []).length)} relations · ${data.focus || "no focus"}`;
  $("kg-truncation").textContent = data.truncated ? "View capped for responsiveness" : "";
  $("kg-edge-count").textContent = `${numeric((elements.edges || []).length)} visible`;
  const relationCounts={};
  (data.edges || []).forEach((row) => { relationCounts[row.edge_type]=(relationCounts[row.edge_type] || 0)+1; });
  const focusEdges=(data.edges || []).filter((row) => row.source_id===data.focus || row.target_id===data.focus).slice(0,8);
  $("kg-neighbor-table").innerHTML=`<div class="chips" style="margin-bottom:12px">${Object.entries(relationCounts).map(([name,count]) => chip(`${name.replaceAll("_"," ")} · ${count}`)).join("")}</div><div class="upper" style="margin-bottom:7px">From the focus node</div><div class="result-list">${focusEdges.map((row) => { const neighbor=row.source_id===data.focus ? row.target_id : row.source_id; return `<button type="button" class="result-item" data-node="${esc(neighbor)}"><strong>${esc(neighbor)}</strong><span>${esc(row.edge_type.replaceAll("_"," "))}</span></button>`; }).join("") || `<div class="empty">No visible direct relations.</div>`}</div>`;
  $("kg-neighbor-table").querySelectorAll("button[data-node]").forEach((button) => button.addEventListener("click",() => attempt(() => showNode(button.dataset.node),"Node details failed")));
  if (data.status === "ok") await showNode(data.focus);
}

async function showNode(id) {
  if (!id) return;
  state.selectedNode = id;
  if (state.kgCy) { state.kgCy.nodes().unselect(); state.kgCy.getElementById(id).select(); }
  sessionStorage.setItem("constellations-selected-node",id);
  const data = await api("/api/kg/node",{id});
  const node = data.node;
  state.selectedKgRecord=node;
  if (!node) { $("kg-node-detail").innerHTML = `<div class="empty">Node not found.</div>`; return; }
  $("kg-node-badge").textContent = node.node_type || "Node";
  $("kg-node-detail").innerHTML = `<h3 style="overflow-wrap:anywhere">${esc(node.label || node.node_id)}</h3>${details(node,[["node_id","ID"],["node_type","Type"],["core","Core"],["taxon","Taxon"],["module_id","Module"],["variable","Variable"],["value","Value"],["unit","Unit"],["source_file","Source"],["evidence_status","Evidence"]])}${measurementReview(node)}${functionalReview(node)}<p class="small muted" style="margin-top:12px">${numeric((data.incident_edges || []).length)} relations returned · ${numeric((data.measurements || []).length)} measurements returned</p>`;
}

function measurementReview(node) {
  if(node.node_type !== "ProxyMeasurement") return "";
  const flagged=String(node.large_gap).toLowerCase() === "true";
  return `${flagged ? `<div class="insight">Large interpolation gap: this value requires scientific review.</div>` : ""}${details(node,[["unit_status","Unit status"],["unit_evidence","Unit evidence"],["match_method","Matching"],["bracket_width_cm","Interpolation bracket (cm)"],["source_table","Dataset"],["source_file","Source file"],["source_observation_ids","Source records"],["observation_ids","Derived observations"]])}`;
}

async function renderSchema() {
  const schema = await ensureSchema();
  $("kg-view").innerHTML = `<div class="hero-note">This describes the current graph structure and observed relation types. Structural validation and biological interpretation are separate checks.</div><div class="grid two"><section class="panel"><h2>Node types</h2>${table(schema.node_types || [],["node_type","count"],30)}</section><section class="panel"><h2>Relations</h2>${table(schema.edge_types || [],["edge_type","count"],30)}</section></div><section class="panel" style="margin-top:16px"><h2>Allowed connections in this run</h2>${table(schema.metagraph || [],["source_node_type","edge_type","target_node_type","count"],35)}</section>`;
}

let metapaths = {};

async function renderMetapaths() {
  await ensureSchema();
  const config = await api('/api/kg/metapaths');
  metapaths = config.presets;
  const scope = config.functional_scope || {};
  const urlParams = new URLSearchParams(location.search);
  const savedSource = sessionStorage.getItem("constellations-metapath-source") || "";
  $("kg-view").innerHTML = `<div class="hero-note">Metapath counts and degree-weighted path counts describe connectivity. They are exploratory scores, without a significance test.</div><section class="panel" style="margin-bottom:16px"><div class="panel-title"><h2>Choose a connection pattern</h2><span class="badge badge-blue">Typed paths</span></div><div class="filters"><div class="field wide"><label for="path-pattern">Metapath</label><select id="path-pattern">${Object.entries(metapaths).map(([key,value]) => `<option value="${key}">${esc(value.label)}</option>`).join("")}</select></div><div class="field"><label for="path-source-type">From type</label><select id="path-source-type"></select></div><div class="field"><label for="path-target-type">To type</label><select id="path-target-type"></select></div><div class="field suggestion-box wide"><label for="path-source">From node</label><input id="path-source" placeholder="Search or enter a node ID" autocomplete="off" value="${esc(savedSource)}"><div id="path-source-suggestions" class="suggestions"></div></div><div class="field suggestion-box wide"><label for="path-target">To node</label><input id="path-target" placeholder="Search or enter a node ID" autocomplete="off"><div id="path-target-suggestions" class="suggestions"></div></div></div><div class="filters" style="margin-top:12px"><div class="field"><label for="path-threshold">Taxon threshold</label><input id="path-threshold" value="${esc(scope.threshold || state.overview.threshold)}"></div><div class="field"><label for="path-method">Network</label><input id="path-method" value="${esc(scope.method || state.overview.method)}"></div><div class="field"><label for="path-kind">Assignment</label><select id="path-kind"><option>vgae</option><option>diffpool</option></select></div><div class="field wide"><label for="path-snapshot">Annotation snapshot</label><input id="path-snapshot" value="${esc(scope.db_snapshot || "")}"></div><div class="field"><label for="path-core">Core/library context</label><input id="path-core" placeholder="Optional, e.g. ST8"></div><div class="field"><label for="path-carriers">Evidence mode</label><select id="path-carriers"><option value="false">All module members</option><option value="true">Supporting carriers only</option></select></div></div><div class="button-row" style="margin-top:13px"><button id="path-run" class="button" type="button">Find connections</button><button id="path-demo-tax" class="button secondary" type="button">Example: taxon to SST</button><button id="path-demo-core" class="button secondary" type="button">Example: cores through module</button><button id="path-demo-function" class="button secondary" type="button">Example: taxon to function</button></div><p class="small muted" id="path-help" style="margin:11px 0 0"></p></section><div class="graph-layout"><section class="panel graph-stage"><div class="panel-title"><div><h2>Evidence path</h2><span class="small muted" id="path-graph-caption">Choose two nodes, then run a search.</span></div><div class="button-row"><label class="small"><input type="checkbox" id="path-collapse"> Compact module/function view</label><button class="button secondary" id="path-fit" type="button">Fit graph</button></div></div><div class="graph-canvas medium" id="path-canvas" role="img" aria-label="Selected typed evidence path"><div class="empty">A selected path will appear here.</div></div>${graphLegend()}</section><aside class="stack"><section class="panel"><h2>Connectivity</h2><div id="path-summary" class="small muted">No search yet.</div></section><section class="panel"><div class="panel-title"><h2>Inspectable evidence</h2><span id="path-count" class="small muted"></span></div><div class="result-list" id="path-list"><div class="empty">Run a metapath search to see paths.</div></div></section><section class="panel"><h2>Selected path details</h2><div id="path-detail" class="small muted">Choose an evidence path above.</div></section></aside></div>`;
  const availableTypes = (state.schema.node_types || []).map((row) => row.node_type);
  const typeOptions = `<option value="">All types</option>` + availableTypes.map((type) => `<option value="${esc(type)}">${esc(type)}</option>`).join("");
  $("path-source-type").innerHTML = typeOptions; $("path-target-type").innerHTML = typeOptions;
  $('path-pattern').value = urlParams.get('pattern') || 'taxon_module_function';
  $('path-kind').value = scope.module_system || 'vgae';
  if(urlParams.has('carriers_only')) $('path-carriers').value=urlParams.get('carriers_only');
  for (const key of ['threshold','method','snapshot','core','kind']) if(urlParams.has(key)) $('path-'+key).value=urlParams.get(key);
  $("path-pattern").addEventListener("change",updateMetapathTypes);
  updateMetapathTypes();
  for (const side of ["source","target"]) {
    let timer;
    $("path-"+side).addEventListener("input",() => { clearTimeout(timer); timer=setTimeout(() => suggestPathNode(side),250); });
    $("path-"+side).addEventListener("keydown",(event) => { if (event.key === "Escape") $("path-"+side+"-suggestions").innerHTML=""; });
  }
  $("path-run").addEventListener("click",() => attempt(runMetapath,"Connectivity search failed"));
  $("path-demo-tax").addEventListener("click",() => attempt(() => loadMetapathDemo(0),"Demo failed"));
  $("path-demo-core").addEventListener("click",() => attempt(() => loadMetapathDemo(1),"Demo failed"));
  $('path-demo-function').addEventListener('click',()=>attempt(async()=>{
    const data=await api('/api/kg/functional-demo'); if(!data.demo) return notify('No qualified functional demonstration in this graph.');
    $('path-pattern').value=data.demo.metapath;updateMetapathTypes();$('path-source').value=data.demo.source;$('path-target').value=data.demo.target;
    await runMetapath();
  },'Functional demo failed'));
  $('path-collapse').addEventListener('change',()=>showEvidencePath(state.pathIndex || 0));
  $("path-fit").addEventListener("click",() => state.kgCy?.fit(undefined,36));
  const demo=new URLSearchParams(location.search).get("demo");
  if (demo === "taxon" || demo === "cores") await loadMetapathDemo(demo === "taxon" ? 0 : 1);
  else if(urlParams.get('source')) { $('path-source').value=urlParams.get('source');$('path-target').value=urlParams.get('target') || '';await runMetapath(); }
}

function updateMetapathTypes() {
  const selected = metapaths[$("path-pattern").value];
  $("path-source-type").value = selected.source;
  $("path-target-type").value = selected.target;
  $("path-help").textContent = selected.help;
  $('path-carriers').disabled = !['taxon_module_function','function_module_taxon'].includes($('path-pattern').value);
  if($('path-carriers').disabled) $('path-carriers').value='false';
  $('path-target').placeholder = ['taxon_module_function','function_module_taxon','function_module','module_function','taxon_function','module_function_ko'].includes($('path-pattern').value) ? 'Optional: leave blank to list connected results' : 'Search or enter a node ID';
}

async function suggestPathNode(side) {
  const input = $("path-"+side);
  const box = $("path-"+side+"-suggestions");
  const query = input.value.trim();
  if (query.length < 2) { box.innerHTML=""; return; }
  const data = await api("/api/kg/search",{query,node_type:$("path-"+side+"-type").value,limit:8});
  if (input.value.trim() !== query) return;
  box.innerHTML = (data.rows || []).map((row) => `<button type="button" data-id="${esc(row.node_id)}">${esc(row.label || row.node_id)}<small>${esc(row.node_type)} · ${esc(row.node_id)}</small></button>`).join("");
  box.querySelectorAll("button").forEach((button) => button.addEventListener("click",() => { input.value=button.dataset.id; box.innerHTML=""; }));
}

async function loadMetapathDemo(index) {
  const demo = await api("/api/kg/demo");
  const item = (demo.questions || [])[index];
  if (!item) { notify("No saved demo for this branch."); return; }
  $("path-pattern").value=item.metapath;
  updateMetapathTypes();
  $("path-source").value=item.source;
  $("path-target").value=item.target;
  await runMetapath();
}

async function runMetapath() {
  const source = $("path-source").value.trim();
  const target = $("path-target").value.trim();
  const functional=['taxon_module_function','function_module_taxon','function_module','module_function','taxon_function','module_function_ko'].includes($('path-pattern').value);
  if (!source || (!target && !functional)) { notify("Choose source and target nodes for this pattern."); return; }
  $("path-summary").textContent="Searching typed connections…";
  const data = await api("/api/kg/connectivity",{source,target,metapath:$("path-pattern").value,limit:20,
    threshold:functional ? $('path-threshold').value : '',method:functional ? $('path-method').value : '',
    kind:functional ? $('path-kind').value : '',snapshot:functional ? $('path-snapshot').value : '',
    core:functional ? $('path-core').value : '',carriers_only:$('path-carriers').value});
  state.pathResult=data;
  if (data.status !== "ok") {
    $("path-summary").textContent="One or both nodes are absent from this graph. Use the node suggestions to choose existing IDs.";
    $("path-list").innerHTML="";
    $("path-canvas").innerHTML=`<div class="empty">No path to display.</div>`;
    destroyGraph("kgCy");
    return;
  }
  $("path-summary").innerHTML=`<div class="stats" style="grid-template-columns:repeat(2,minmax(0,1fr));margin-bottom:12px">${stat("Paths",numeric(data.path_count),data.count_status === "exact" ? "Complete count" : "Lower bound")}${stat("Degree-weighted",Number(data.dwpc).toPrecision(4),"Descriptive score")}</div><div class="chips">${chip(`${numeric(data.expansions)} expansions`)}${data.truncated ? chip("Enumeration capped","active") : chip("Enumeration complete")}</div><p class="small muted" style="margin:12px 0 0">Counts reflect this selected ordered metapath. No permutation significance or ecological interaction is implied.</p>`;
  $("path-count").textContent=`${numeric((data.paths || []).length)} shown`;
  $("path-list").innerHTML=(data.paths || []).length ? data.paths.map((path,index) => `<button type="button" class="result-item" data-index="${index}"><strong>Path ${index+1}</strong><span>${esc((path.node_details || []).map((n) => n.label || n.node_id).join(" → "))}</span><span>Weight ${Number(path.weight).toPrecision(3)}${path.carrier_status ? ` · ${esc(path.carrier_status)}` : ""}</span></button>`).join("") : `<div class="empty">No path of this type connects these nodes.</div>`;
  $("path-list").querySelectorAll("button[data-index]").forEach((button) => button.addEventListener("click",() => showEvidencePath(Number(button.dataset.index))));
  if ((data.paths || []).length) showEvidencePath(0);
  else { destroyGraph("kgCy"); $("path-canvas").innerHTML=`<div class="empty">No connection found for this pattern.</div>`; $("path-detail").textContent=""; }
}

function showEvidencePath(index) {
  const path = state.pathResult?.paths?.[index];
  if (!path) return;
  state.pathIndex=index;
  $("path-list").querySelectorAll("button[data-index]").forEach((button) => button.classList.toggle("active",Number(button.dataset.index)===index));
  const lookup = new Map((path.node_details || []).map((node) => [node.node_id,node]));
  const compact=$('path-collapse')?.checked;
  const hidden=new Set(compact ? (path.node_details || []).filter(n=>n.node_type==='ModuleFunctionalAssociation').map(n=>n.node_id) : []);
  const nodes = (path.nodes || []).filter(id=>!hidden.has(id)).map((id,i) => {
    const node=lookup.get(id), label=node?.node_type==='FunctionalFeature' ? `${node.function_id} · ${node.label}` : node?.node_type==='ModuleFunctionalAssociation' ? 'Association evidence' : node?.label || id;
    return {data:{id,label},position:{x:120+i*210,y:200},classes:String(node?.node_type || '').toLowerCase()};
  });
  const edges = (path.edges || []).filter(e=>!hidden.has(e.source_id)&&!hidden.has(e.target_id)).map((edge,i) => ({data:{id:String(edge.edge_id || `step-${i}`),source:String(edge.source_id),target:String(edge.target_id),label:String(edge.edge_type)}}));
  for(const association of hidden) {
    const module=(path.edges || []).find(e=>e.target_id===association && e.edge_type==='module_has_functional_association');
    const feature=(path.edges || []).find(e=>e.source_id===association && e.edge_type==='association_with_function');
    if(module&&feature) edges.push({data:{id:'display:'+association,source:module.source_id,target:feature.target_id,label:'functional association',association_id:association}});
  }
  mountGraph("path-canvas",nodes,edges,"kgCy","preset",(id) => { const node=lookup.get(id); if(node) $("path-detail").innerHTML=details(node,[["node_id","ID"],["node_type","Type"],["value","Value"],["unit","Unit"],["source_file","Source"]])+measurementReview(node)+functionalReview(node); });
  $("path-graph-caption").textContent=`Path ${index+1} of ${(state.pathResult.paths || []).length} shown · ${path.nodes?.length || 0} nodes`;
  $("path-detail").innerHTML=(path.membership_context ? `<div class="insight"><strong>Module membership context</strong><p>Individual reference support: ${esc(path.carrier_status)}.</p><p>${esc(path.interpretation)}</p><small>Proof: ${esc(path.proof_id)} · ${esc(path.rule_version)}</small></div>` : '')+(path.node_details || []).map((node,i) => `<div class="evidence-card"><strong>${i+1}. ${esc(node.label || node.node_id)}</strong><small>${esc(node.node_type)} · ${esc(node.node_id)}</small>${node.value !== "" && node.value != null ? `<p>Value: ${esc(node.value)} ${esc(node.unit || "")} · ${esc(node.match_method || "observed")}</p>` : ""}${measurementReview(node)}${functionalReview(node)}</div>`).join("")+(path.witnesses || []).map(w=>`<div class="evidence-card"><strong>Same-taxon supporting witness: ${esc(w.genome_id)}</strong>${details(w.annotation,[["gene_ids","Native genes"],["ko_ids","KOs"],["source_path","Source"],["source_row","Row"],["annotation_source","Annotation source"]])}<small>${esc(w.edge_ids.join(" · "))}</small></div>`).join("");
}

async function renderModules(viewName = null) {
  destroyGraph("moduleCy");
  setPage("modules", "Modules");
  const view = viewName || pathSection("view",["supergraph","modules","functions","profiles","embeddings"]);
  $("app-view").innerHTML = pageHead("Learned structure", "Modules and site networks", "Explore core similarity, exploratory taxon groups, embeddings, and their supporting figures.")
    + `<div class="hero-note">These are exploratory groups from the permissive mixed abundance analysis. Assignment and graph scores are evidence for review, not confirmed ecological communities.</div><div class="tabs" id="module-tabs" role="tablist" aria-label="Module views"></div><div id="module-view"></div>`;
  subTabs("module-tabs",{supergraph:"Supergraph",modules:"Taxon modules",functions:"Functions",profiles:"Core profiles",embeddings:"Embeddings & figures"},view,(next) => { const url=new URL(location.href); url.pathname="/modules"; url.searchParams.set("view",next); history.pushState({},"",url); renderModules(next); });
  await attempt(async () => { if(view === "supergraph") await renderSupergraph(); else if(view === "modules") await renderModuleExplorer(); else if(view === "functions" || view === "profiles") await renderFunctionalExplorer(view); else await renderEmbeddings(); },"Modules view failed");
}

function toGraphElements(nodes,edges) {
  return {
    nodes:(nodes || []).map((node) => ({data:{id:String(node.id),label:String(node.label || node.id)},classes:String(node.type || "").toLowerCase()})),
    edges:(edges || []).map((edge,index) => ({data:{id:`e-${index}`,source:String(edge.source),target:String(edge.target),weight:edge.weight}}))
  };
}

async function renderSupergraph() {
  $("module-view").innerHTML=`<div class="graph-layout"><section class="panel graph-stage"><div class="panel-title"><div><h2>Graph of core graphs</h2><p class="small" style="margin:0">Edges summarize similarity between separately constructed core networks.</p></div><button class="button secondary" id="super-fit" type="button">Fit graph</button></div><div id="super-canvas" class="graph-canvas medium" role="img" aria-label="Interactive core similarity supergraph"></div><div class="small muted" id="super-summary" style="margin-top:10px"></div></section><aside class="stack"><section class="panel"><h2>Selected core</h2><div id="super-detail" class="small muted">Select a core node.</div></section><section class="panel"><h2>Core comparisons</h2><div id="super-table"></div></section></aside></div>`;
  const d=await api("/api/supergraph",{threshold:state.overview.threshold,method:state.overview.method});
  const elements=toGraphElements(d.nodes,d.edges);
  mountGraph("super-canvas",elements.nodes,elements.edges,"moduleCy","cose",(id) => {
    const location=(state.overview.locations || []).find((loc) => loc.cores.includes(id) || loc.site===id);
    $("super-detail").innerHTML=`<h3>${esc(id)}</h3>${location ? details(location,[["site","Physical site"],["latitude","Latitude"],["longitude","Longitude"],["samples","Analyzed samples"]]) : `<p class="small muted">Core context is not recorded in the active source table.</p>`}<a class="button secondary" href="/knowledge-graph?view=browser&id=${encodeURIComponent(`site:${location?.site || id}`)}">Explore in KG →</a>`;
  });
  $("super-fit").addEventListener("click",() => state.moduleCy?.fit(undefined,35));
  $("super-summary").textContent=`${numeric(elements.nodes.length)} core graphs · ${numeric(elements.edges.length)} similarity links · ${state.overview.threshold} / ${state.overview.method}`;
  $("super-table").innerHTML=table((d.rows || []).map((row) => ({core_a:row.core_a || row.from,core_b:row.core_b || row.to,edge_jaccard:row.edge_jaccard,spectral_similarity:row.spectral_similarity})),["core_a","core_b","edge_jaccard","spectral_similarity"],12);
}

async function renderModuleExplorer() {
  $("module-view").innerHTML=`<section class="panel" style="margin-bottom:16px"><div class="filters"><div class="field"><label for="module-kind">Assignment</label><select id="module-kind"><option value="vgae">VGAE + K-means</option><option value="diffpool">DiffPool consensus</option></select></div><div class="field"><label for="module-select">Module</label><select id="module-select"><option value="">Largest available</option></select></div><div class="field"><label for="module-page-size">Members per page</label><select id="module-page-size"><option>10</option><option selected>20</option><option>40</option></select></div><button class="button" id="module-load" type="button">Open module</button></div></section><div class="graph-layout"><section class="panel graph-stage"><div class="panel-title"><div><h2 id="module-title">Taxon module</h2><p id="module-subtitle" class="small" style="margin:0"></p></div><button class="button secondary" id="module-fit" type="button">Fit graph</button></div><div class="graph-canvas medium" id="module-canvas" role="img" aria-label="Selected module and representative taxa"></div><p class="small muted" style="margin:10px 0 0">Representative members are shown for a responsive graph. The member table below provides more context.</p></section><aside class="stack"><section class="panel"><h2>Group sizes</h2><div id="module-size-bars"></div></section><section class="panel"><h2>Selected member</h2><div id="module-member-detail" class="small muted">Choose a taxon in the graph.</div></section></aside></div><section class="panel" style="margin-top:16px"><div class="panel-title"><h2>Taxa in this module</h2><div class="button-row"><button class="button secondary" id="module-prev" type="button">← Previous</button><span id="module-page-label" class="small muted"></span><button class="button secondary" id="module-next" type="button">Next →</button></div></div><div id="module-members"></div></section>`;
  state.modulePage=0;
  $("module-page-size").parentElement.insertAdjacentHTML("beforebegin",`<div class="field"><label for="module-core">Association network</label><select id="module-core"><option value="">First available core/library</option></select></div>`);
  $("module-canvas").nextElementSibling.id="module-network-caption";
  $("module-core").addEventListener("change",() => attempt(loadModule,"Module network failed"));
  $("module-load").addEventListener("click",() => attempt(loadModule,"Module load failed"));
  $("module-kind").addEventListener("change",() => { $("module-select").innerHTML=`<option value="">Largest available</option>`; state.modulePage=0; attempt(loadModule,"Module load failed"); });
  $("module-select").addEventListener("change",() => { state.modulePage=0; attempt(loadModule,"Module load failed"); });
  $("module-page-size").addEventListener("change",() => { state.modulePage=0; fillModuleMembers(); });
  $("module-prev").addEventListener("click",() => { state.modulePage=Math.max(0,state.modulePage-1); fillModuleMembers(); });
  $("module-next").addEventListener("click",() => { state.modulePage++; fillModuleMembers(); });
  $("module-fit").addEventListener("click",() => state.moduleCy?.fit(undefined,35));
  await loadModule();
}

async function loadModule() {
  const kind=$("module-kind").value;
  const moduleId=$("module-select").value;
  const d=await api("/api/modules",{threshold:state.overview.threshold,method:state.overview.method,kind,module_id:moduleId,core:$("module-core").value,limit:1000});
  state.moduleData=d;
  const summary=d.summary || [];
  $("module-select").innerHTML=summary.map((row) => `<option value="${esc(row.module_id)}">${esc(row.module_id)} · ${numeric(row.taxa)} taxa</option>`).join("");
  $("module-select").value=d.module_id || "";
  $("module-title").textContent=`${kind === "vgae" ? "VGAE" : "DiffPool"} ${d.module_id || "module"}`;
  const selected=summary.find((row) => String(row.module_id) === String(d.module_id));
  $("module-subtitle").textContent=`${numeric(selected?.taxa || (d.members || []).length)} assigned taxa · ${state.overview.threshold} / ${state.overview.method}`;
  $('module-subtitle').insertAdjacentHTML('beforeend',` · <a href="/knowledge-graph?view=metapaths&pattern=module_function&source=${encodeURIComponent(d.module_id)}&kind=${encodeURIComponent(kind)}&threshold=${encodeURIComponent(state.overview.threshold)}&method=${encodeURIComponent(state.overview.method)}">Show functional paths →</a>`);
  $("module-size-bars").innerHTML=bars(Object.fromEntries(summary.map((row) => [row.module_id,row.taxa])),9);
  $("module-core").innerHTML=(d.cores || []).map((core) => `<option value="${esc(core)}">${esc(core)}</option>`).join("") || `<option value="">No association network</option>`;
  $("module-core").value=d.core || "";
  const nodes=(d.graph_nodes || []).map((row) => ({data:{id:String(row.id),label:String(row.label),positive_strength:row.positive_strength},classes:"taxon"}));
  const edges=(d.graph_edges || []).map((row,index) => ({data:{id:`association-${index}`,source:String(row.source),target:String(row.target),weight:row.weight},classes:`association ${Number(row.weight)<0 ? "negative" : "positive"}`}));
  const networkRows=new Map((d.graph_nodes || []).map((row) => [String(row.id),row]));
  $("module-network-caption").textContent=`${numeric(d.graph_returned_nodes)} of ${numeric(d.graph_total_nodes)} members · ${numeric(d.graph_returned_edges)} of ${numeric(d.graph_total_edges)} within-module association edges from ${d.core || "no core"}${d.graph_truncated ? " · bounded view" : ""}. Solid: positive; dashed: negative. Structural rank is not causal influence.`;
  mountGraph("module-canvas",nodes,edges,"moduleCy","cose",(id) => {
    const row={...(d.members || []).find((item) => String(item.taxon)===id),...networkRows.get(id)};
    $("module-member-detail").innerHTML=`<h3>${esc(id)}</h3>${details(row,[["positive_strength","Positive weight sum"],["module_kmeans","VGAE module"],["consensus_module","DiffPool module"],["domain","Domain"],["phylum","Phylum"],["functional_group","Reference guild"]])}<div class="button-row" style="margin-top:12px"><a class="button secondary" href="/knowledge-graph?view=browser&id=${encodeURIComponent(`taxon:${id}`)}">Open taxon in KG →</a><button class="button secondary" id="member-inventory-open">Reference annotations</button></div><div id="taxon-inventory" style="margin-top:14px"></div>`;
    state.inventoryTaxon=id;state.inventoryPage=0;
    $("member-inventory-open").addEventListener("click",()=>attempt(loadTaxonInventory,"Reference annotations failed"));
  });
  state.modulePage=0;
  fillModuleMembers();
  let central=$("module-centrality-panel");
  if(!central) {$("module-view").insertAdjacentHTML("beforeend",`<section class="panel" id="module-centrality-panel" style="margin-top:16px"><div class="panel-title"><h2>Structural member ranking</h2><div class="button-row"><button class="button secondary" id="centrality-prev">← Previous</button><span class="small" id="centrality-page"></span><button class="button secondary" id="centrality-next">Next →</button></div></div><p class="small muted">Centrality describes network position. Bootstrap intervals and candidate status remain separate from functional evidence.</p><div id="module-centrality"></div></section>`);$("centrality-prev").addEventListener("click",()=>{state.centralityPage=Math.max(0,state.centralityPage-1);attempt(loadCentrality,"Centrality failed");});$("centrality-next").addEventListener("click",()=>{state.centralityPage++;attempt(loadCentrality,"Centrality failed");});}
  state.centralityPage=0;await loadCentrality();
}

async function loadCentrality() {
  const d=await api("/api/module-centrality",{threshold:state.overview.threshold,method:state.overview.method,kind:$("module-kind").value,module_id:state.moduleData.module_id,core:$("module-core").value,offset:state.centralityPage*40,limit:40});
  $("centrality-page").textContent=`${numeric(d.offset+1)}–${numeric(d.offset+d.returned_count)} of ${numeric(d.total_count)}`;
  $("centrality-prev").disabled=state.centralityPage===0;$("centrality-next").disabled=!d.truncated;
  $("module-centrality").innerHTML=d.status==="not_computed" ? `<div class="empty">${esc(d.message)}</div>` : table(d.rows,["taxon","positive_strength","negative_strength","degree","centrality_percentile","bootstrap_top_decile_frequency","rank_lower","rank_upper","central_candidate"],40);
}

function fillModuleMembers() {
  if (!$("module-members") || !state.moduleData) return;
  const rows=state.moduleData.members || [];
  const pageSize=Number($("module-page-size").value || 20);
  const pages=Math.max(1,Math.ceil(rows.length/pageSize));
  state.modulePage=Math.min(state.modulePage,pages-1);
  const start=state.modulePage*pageSize;
  $("module-members").innerHTML=table(rows.slice(start,start+pageSize),["taxon",...(rows[0] && "functional_group" in rows[0] ? ["functional_group"] : []),...(rows[0] && "sites_present" in rows[0] ? ["sites_present"] : [])],pageSize);
  $("module-page-label").textContent=`Page ${state.modulePage+1} of ${pages} · ${numeric(rows.length)} members`;
  $("module-prev").disabled=state.modulePage===0;
  $("module-next").disabled=state.modulePage>=pages-1;
}

function precision(value) { const n=Number(value); return value == null || value === "" || !Number.isFinite(n) ? "—" : (Math.abs(n)>0 && Math.abs(n)<.001 ? n.toExponential(2) : n.toFixed(3)); }

function functionalFilters() {
  return {threshold:$("functional-threshold").value,method:$("functional-method").value,kind:$("functional-kind").value,
    snapshot:$("functional-snapshot").value,module_id:$("functional-module").value};
}

function functionalScopeControls(data) {
  const scopes=data.scopes || [];
  const options=(values,selected) => [...new Set(values)].sort().map((value) => `<option value="${esc(value)}" ${value===selected ? "selected" : ""}>${esc(value)}</option>`).join("");
  $("functional-threshold").innerHTML=options([state.overview.threshold,...scopes.map((s) => s.threshold)],data.threshold);
  $("functional-method").innerHTML=options([state.overview.method,...scopes.map((s) => s.method)],data.method);
  $("functional-kind").innerHTML=options(["vgae","diffpool"],data.kind);
  $("functional-snapshot").innerHTML=(data.snapshots || []).map((s) => `<option value="${esc(s.snapshot)}" ${s.snapshot===data.snapshot ? "selected" : ""}>${esc(s.snapshot)} · ${esc(s.status)}</option>`).join("") || `<option value="">No annotation snapshot</option>`;
  const selected=$("functional-module").value;
  $("functional-module").innerHTML=`<option value="">All modules</option>`+(data.modules || []).map((id) => `<option value="${esc(id)}" ${id===selected ? "selected" : ""}>${esc(id)}</option>`).join("");
  state.functionalContext=data;
}

async function renderFunctionalExplorer(view) {
  state.functionalPage=0; state.functionalView=view;
  $("module-view").innerHTML=`<div class="hero-note">Reference genome annotations describe functional potential. These results do not measure gene expression, metabolic activity, or causal ecological roles.</div><section class="panel"><div class="filters"><div class="field"><label for="functional-threshold">Taxon threshold</label><select id="functional-threshold"><option>${esc(state.overview.threshold)}</option></select></div><div class="field"><label for="functional-method">Network</label><select id="functional-method"><option>${esc(state.overview.method)}</option></select></div><div class="field"><label for="functional-kind">Assignment</label><select id="functional-kind"><option>vgae</option><option>diffpool</option></select></div><div class="field"><label for="functional-snapshot">Annotation snapshot</label><select id="functional-snapshot"><option value="">Latest completed</option></select></div><div class="field"><label for="functional-module">Module</label><select id="functional-module"><option value="">All modules</option></select></div>${view==="functions" ? `<div class="field"><label for="functional-qualified">Results</label><select id="functional-qualified"><option value="false">All tested results</option><option value="true">Qualifying KG associations</option></select></div>` : `<div class="field"><label for="profile-core">Core/library</label><select id="profile-core"><option value="">All cores</option></select></div><div class="field"><label for="profile-axis">Sediment axis</label><select id="profile-axis"><option value="depth">Depth (cm)</option><option value="age">Age (kyr BP)</option></select></div><div class="field"><label for="profile-function">Profile</label><select id="profile-function"><option value="">Module CLR profile</option></select></div>`}<button class="button" id="functional-load">Refresh analysis</button></div><div id="functional-status" style="margin-top:14px"></div></section><div id="functional-content" style="margin-top:16px"></div>`;
  $("functional-load").addEventListener("click",() => {state.functionalPage=0;attempt(loadFunctionalView,"Functional analysis failed");});
  ["functional-threshold","functional-method","functional-kind"].forEach((id) => $(id).addEventListener("change",() => {$("functional-snapshot").innerHTML=`<option value="">Latest completed</option>`;$("functional-module").innerHTML=`<option value="">All modules</option>`;state.functionalPage=0;attempt(loadFunctionalView,"Functional scope failed");}));
  ["functional-snapshot","functional-module",...(view==="functions" ? ["functional-qualified"] : ["profile-core","profile-function"])].forEach((id) => $(id).addEventListener("change",() => {state.functionalPage=0;attempt(loadFunctionalView,"Analysis selection failed");}));
  if(view==="profiles") $("profile-axis").addEventListener("change",() => drawProfiles(state.profileData));
  await loadFunctionalView();
  const linked=new URLSearchParams(location.search);
  for(const [key,id] of [['module_id','functional-module'],['function_id','profile-function'],['core','profile-core'],['snapshot','functional-snapshot'],['threshold','functional-threshold'],['method','functional-method'],['kind','functional-kind'],['axis','profile-axis']]) {
    if(linked.has(key) && $(id)) $(id).value=linked.get(key);
  }
  if(linked.has('module_id') || linked.has('function_id') || linked.has('core')) await loadFunctionalView();
}

async function loadFunctionalView() {
  const selection=functionalFilters();
  const view=state.functionalView;
  const data=await api("/api/module-functions",{...selection,limit:view==="profiles" ? 500 : 40,offset:view==="functions" ? state.functionalPage*40 : 0,qualified_only:view==="functions" ? $("functional-qualified").value : "false"});
  functionalScopeControls(data);
  const manifest=data.manifest || {};
  $("functional-status").innerHTML=`<div class="chips">${chip(`Analysis: ${data.status}`)}${chip(`Annotation: ${manifest.annotation_status || "not available"}`)}${chip(data.snapshot || "No database snapshot")}</div><p class="small muted" style="margin:10px 0 0">${esc(data.interpretation)}. ${esc(data.message || "Unweighted annotation; abundance profiles are separate. Weighted KS and affinity are planned for the next version.")}</p>${manifest.kg_scope ? `<p class="small muted" style="margin:6px 0 0">KG scope: ${esc(typeof manifest.kg_scope === "string" ? manifest.kg_scope : JSON.stringify(manifest.kg_scope))}</p>` : ""}`;
  if(data.status==="not_computed") {$("functional-content").innerHTML=`<section class="panel"><div class="empty">${esc(data.message)} Taxon modules and their association networks remain available in the Taxon modules tab.</div></section>`;return;}
  if(view==="profiles") {
    const old=$("profile-function").value;
    const functions=[...new Map((data.rows || []).map((r) => [r.function_id,r])).values()];
    $("profile-function").innerHTML=`<option value="">Module CLR profile</option>`+functions.map((r) => `<option value="${esc(r.function_id)}" ${r.function_id===old ? "selected" : ""}>${esc(r.function_name || r.function_id)}</option>`).join("");
    $("functional-module").disabled=!!$("profile-function").value;
    if($("profile-function").value) $("functional-module").value="";
    if(!$("profile-function").value && !$("functional-module").value && (data.modules || []).length) $("functional-module").value=data.modules[0];
    const profile=await api("/api/module-profiles",{...functionalFilters(),function_id:$("profile-function").value,core:$("profile-core").value,limit:500});
    const core=$("profile-core").value;
    $("profile-core").innerHTML=`<option value="">All cores</option>`+(profile.cores || []).map((c) => `<option value="${esc(c)}" ${c===core ? "selected" : ""}>${esc(c)}</option>`).join("");
    state.profileData=profile;drawProfiles(profile);return;
  }
  state.functionalRows=data.rows || [];
  const source={id:data.source_file};
  $("functional-content").innerHTML=`<div class="grid two"><section class="panel"><h2>Module functional associations</h2><div id="functional-dotplot" class="functional-plot"></div><p class="small muted">Circle size: carrier taxa. Gold: positive effect; blue: negative effect. Outlined circles qualify for KG publication. This plot shows the current result page.</p></section><section class="panel"><h2>Selected function evidence</h2><div id="functional-detail" class="small muted">Select a result below to inspect its supporting taxa and annotation provenance.</div></section></div><section class="panel" style="margin-top:16px"><div class="panel-title"><h2>Tested results</h2><div class="button-row"><button class="button secondary" id="functional-prev">← Previous</button><span class="small" id="functional-page"></span><button class="button secondary" id="functional-next">Next →</button><a class="button secondary" href="${linkToFile(source)}">Download full table</a></div></div><div id="functional-results"></div></section><section class="panel" id="functional-contributors-panel" style="margin-top:16px;display:none"><div class="panel-title"><h2>Reference carriers and structural context</h2><div class="button-row"><button class="button secondary" id="contributor-prev">← Previous</button><span class="small" id="contributor-page"></span><button class="button secondary" id="contributor-next">Next →</button></div></div><div id="functional-contributors"></div><div id="functional-contributor-detail" style="margin-top:14px"></div></section>${(data.figures || []).length ? `<section class="panel" style="margin-top:16px"><h2>Generated analysis figures</h2><div class="figure-grid">${data.figures.map((f) => `<figure><a href="${linkToFile(f)}" target="_blank" rel="noopener"><img class="plot-image" src="${linkToFile(f)}" alt="${esc(f.name)}"></a><figcaption>${esc(f.name)}</figcaption></figure>`).join("")}</div></section>` : ""}`;
  $("functional-page").textContent=`${numeric(data.offset+1)}–${numeric(data.offset+data.returned_count)} of ${numeric(data.total_count)}`;
  $("functional-prev").disabled=state.functionalPage===0;$("functional-next").disabled=!data.truncated;
  $("functional-prev").addEventListener("click",() => {state.functionalPage=Math.max(0,state.functionalPage-1);attempt(loadFunctionalView,"Results failed");});
  $("functional-next").addEventListener("click",() => {state.functionalPage++;attempt(loadFunctionalView,"Results failed");});
  $("functional-results").innerHTML=state.functionalRows.length ? `<div class="table-frame"><table><thead><tr><th>Module / function</th><th>Test</th><th>Effect</th><th>Z</th><th>q</th><th>Carriers</th><th>Coverage</th><th>Status</th></tr></thead><tbody>${state.functionalRows.map((r,i) => `<tr><td><button class="result-item" data-function-index="${i}"><strong>${esc(r.module_id)} · ${esc(r.function_name || r.function_id)}</strong><span>${esc(r.function_id)} · ${esc(r.function_namespace)}</span></button></td><td>${esc(r.test_method)}</td><td>${precision(r.prevalence_difference)}</td><td>${precision(r.permutation_z_score)}</td><td>${precision(r.q_value)}</td><td>${numeric(r.carrier_count)} / ${numeric(r.module_annotated_count)}</td><td>${precision(r.annotation_coverage)}</td><td>${esc(r.status)}${String(r.publish_kg).toLowerCase()==="true" ? " · KG qualified" : ""}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty">${esc(data.message || "No tested results for these filters.")}</div>`;
  $("functional-dotplot").innerHTML=functionDotPlot(state.functionalRows);
  document.querySelectorAll("[data-function-index]").forEach((el) => el.addEventListener("click",() => selectFunctionalResult(Number(el.dataset.functionIndex))));
  $("contributor-prev").addEventListener("click",() => {state.contributorPage=Math.max(0,state.contributorPage-1);attempt(loadFunctionalContributors,"Contributors failed");});
  $("contributor-next").addEventListener("click",() => {state.contributorPage++;attempt(loadFunctionalContributors,"Contributors failed");});
}

function functionDotPlot(rows) {
  if(!rows.length) return `<div class="empty">No results on this page.</div>`;
  const features=[...new Map(rows.map((r) => [r.function_id,r.function_name || r.function_id])).entries()].slice(0,18);
  const modules=[...new Set(rows.map((r) => r.module_id))].sort();
  const width=640,height=80+features.length*30,x=(m)=>275+modules.indexOf(m)*Math.min(54,300/Math.max(1,modules.length)),y=(id)=>65+features.findIndex(([f])=>f===id)*30;
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Functional association dot plot">${modules.map((m)=>`<text x="${x(m)}" y="28" text-anchor="middle">${esc(m)}</text>`).join("")}${features.map(([id,name])=>`<text x="12" y="${y(id)+4}">${esc(String(name).slice(0,34))}</text><line x1="265" x2="620" y1="${y(id)}" y2="${y(id)}" stroke="#ece6da"/>`).join("")}${rows.map((r,i)=>features.some(([id])=>id===r.function_id) ? `<circle tabindex="0" role="button" aria-label="Inspect ${esc(r.function_id)} in ${esc(r.module_id)}" data-function-index="${i}" cx="${x(r.module_id)}" cy="${y(r.function_id)}" r="${Math.min(11,3+Math.sqrt(Number(r.carrier_count)||0))}" fill="${Number(r.prevalence_difference)>=0 ? "#ac842e" : "#64869d"}" opacity="${Number(r.q_value)<=.05 ? .95 : .45}" stroke="${String(r.publish_kg).toLowerCase()==="true" ? "#383d32" : "none"}" stroke-width="2"><title>${esc(r.function_name || r.function_id)} · ${esc(r.module_id)} · effect ${precision(r.prevalence_difference)} · Z ${precision(r.permutation_z_score)} · q ${precision(r.q_value)} · ${numeric(r.carrier_count)} carriers</title></circle>` : "").join("")}</svg>`;
}

async function selectFunctionalResult(index) {
  const row=state.functionalRows[index];if(!row) return;
  state.selectedFunction=row;state.contributorPage=0;
  $("functional-detail").innerHTML=`<h3>${esc(row.function_name || row.function_id)}</h3>${details(row,[["module_id","Module"],["function_id","Function"],["test_method","Statistical test"],["capability_threshold","Carrier threshold"],["statistic","Statistic"],["null_carrier_count_mean","Null mean carriers"],["null_carrier_count_sd","Null SD carriers"],["odds_ratio","Odds ratio"],["prevalence_difference","Prevalence difference"],["p_value","p value"],["q_value","q value"],["permutation_z_score","Permutation Z"],["evidence_scope","Evidence scope"],["threshold","Threshold"],["method","Network"],["module_system","Assignment"],["biological_review_status","Biological review"],["definition_sha256","Definition hash"],["annotation_coverage","Mapped coverage"],["exchangeable_fraction","Exchangeable fraction"],["status","Status"],["db_snapshot","Database snapshot"]])}<p class="small muted" style="margin:12px 0 0">Supporting reference annotations identify potential carriers. Shared enzymes can support a named KEGG framework without establishing that biological process; CAM labels in microbial references need specific review. Network centrality is a separate structural measurement.</p>`;
  const context=new URLSearchParams({threshold:row.threshold || state.overview.threshold,method:row.method || state.overview.method,kind:row.module_system || $('functional-kind').value,snapshot:row.db_snapshot});
  $('functional-detail').insertAdjacentHTML('beforeend',`<div class="button-row"><a class="button secondary" href="/knowledge-graph?view=metapaths&pattern=module_function&source=${encodeURIComponent(row.module_id)}&target=${encodeURIComponent(row.function_id)}&${context}">Show module function path →</a>${row.kg_association_id ? `<a class="button secondary" href="/knowledge-graph?view=browser&id=${encodeURIComponent(row.kg_association_id)}">Inspect association in KG →</a>` : ''}</div>`);
  await loadFunctionalContributors();
}

async function loadFunctionalContributors() {
  const row=state.selectedFunction;if(!row) return;
  const d=await api("/api/module-function-members",{...functionalFilters(),module_id:row.module_id,function_id:row.function_id,offset:state.contributorPage*40,limit:40});
  $("functional-contributors-panel").style.display="block";
  $("contributor-page").textContent=`${numeric(d.offset+1)}–${numeric(d.offset+d.returned_count)} of ${numeric(d.total_count)}`;
  $("contributor-prev").disabled=state.contributorPage===0;$("contributor-next").disabled=!d.truncated;
  $("functional-contributors").innerHTML=d.rows.length ? `<div class="table-frame"><table><thead><tr><th>Taxon / reference</th><th>Completeness</th><th>Carrier</th><th>Centrality percentile</th><th>Annotation</th></tr></thead><tbody>${d.rows.map((r,i)=>`<tr><td><button class="result-item" data-carrier-index="${i}"><strong>${esc(r.taxon)}</strong><span>${esc(r.genome_id)}</span></button></td><td>${precision(r.completeness)}</td><td>${esc(r.is_carrier)}</td><td>${precision(r.centrality_percentile)}</td><td>${esc(r.annotation_status)} · ${esc(r.annotation_source)}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty">${esc(d.message || "No carriers available.")}</div>`;
  document.querySelectorAll("[data-carrier-index]").forEach((el)=>el.addEventListener("click",()=>selectFunctionalCarrier(d.rows[Number(el.dataset.carrierIndex)])));
}

function selectFunctionalCarrier(row) {
  state.inventoryTaxon=row.taxon;state.inventoryPage=0;
  $("functional-contributor-detail").innerHTML=details(row,[["taxon","Taxon"],["genome_id","Reference genome"],["gene_ids","Native gene IDs"],["ko_ids","KOs"],["source_path","Source file"],["source_row","Source row"],["db_snapshot","Snapshot"],["core","Centrality core"],["positive_strength","Positive strength"],["negative_strength","Negative strength"],["bootstrap_top_decile_frequency","Bootstrap top-decile frequency"],["rank_lower","Rank lower"],["rank_upper","Rank upper"]])+`<div class="button-row" style="margin-top:12px"><a class="button secondary" href="/knowledge-graph?view=browser&id=${encodeURIComponent(`taxon:${row.taxon}`)}">Open taxon in KG →</a><button class="button secondary" id="inventory-open">Inspect full reference annotations</button></div><div id="taxon-inventory" style="margin-top:14px"></div>`;
  $("inventory-open").addEventListener("click",()=>attempt(loadTaxonInventory,"Reference annotations failed"));
}

async function loadTaxonInventory(namespace="") {
  const selection=$("functional-threshold") ? functionalFilters() : {threshold:state.overview.threshold,method:state.overview.method,kind:$("module-kind")?.value || "vgae"};
  const data=await api("/api/taxon-functions",{...selection,taxon:state.inventoryTaxon,feature_namespace:namespace,offset:state.inventoryPage*40,limit:40});
  $("taxon-inventory").innerHTML=`<h3>Full reference annotation inventory</h3><p class="small muted">${esc(data.message || "No indexed inventory for this snapshot.")}</p><div class="button-row"><div class="field"><label for="inventory-namespace">Feature namespace</label><select id="inventory-namespace"><option value="">All namespaces</option>${(data.feature_namespaces || []).map((n)=>`<option value="${esc(n)}" ${n===namespace ? "selected" : ""}>${esc(n)}</option>`).join("")}</select></div><button class="button secondary" id="inventory-prev">← Previous</button><span class="small">${numeric(data.returned_count ? data.offset+1 : 0)}–${numeric(data.offset+data.returned_count)} of ${numeric(data.total_count)}</span><button class="button secondary" id="inventory-next">Next →</button>${data.download_file ? `<a class="button secondary" href="${linkToFile({id:data.download_file})}">Download full inventory</a>` : ""}</div><div style="margin-top:12px">${table(data.rows || [],["gene_id","feature_namespace","feature_id","source_kind","annotation_status","score","evalue","threshold","source_path","source_row"],40)}</div>`;
  $("inventory-prev").disabled=state.inventoryPage===0;$("inventory-next").disabled=!data.truncated;
  $("inventory-prev").addEventListener("click",()=>{state.inventoryPage=Math.max(0,state.inventoryPage-1);attempt(()=>loadTaxonInventory(namespace),"Inventory failed");});
  $("inventory-next").addEventListener("click",()=>{state.inventoryPage++;attempt(()=>loadTaxonInventory(namespace),"Inventory failed");});
  $("inventory-namespace").addEventListener("change",()=>{state.inventoryPage=0;attempt(()=>loadTaxonInventory($("inventory-namespace").value),"Inventory failed");});
}

function drawProfiles(data) {
  if(!data || !$("functional-content")) return;
  const age=$("profile-axis").value==="age";
  const functionId=$("profile-function").value;
  const raw=data.rows || [];
  const scoreKey=functionId ? "logratio" : "mean_clr";
  const rows=raw.filter((r)=>r[scoreKey]!=null && r[age ? "age_kyr" : "depth_cm"]!=null && Number.isFinite(Number(r[scoreKey])) && Number.isFinite(Number(r[age ? "age_kyr" : "depth_cm"])));
  const physical=[...new Set(rows.map((r)=>r.physical_core || r.core))];
  const panels=physical.map((site)=>{
    const points=rows.filter((r)=>(r.physical_core || r.core)===site);
    const vals=points.map((r)=>Number(r[scoreKey])),levels=points.map((r)=>Number(r[age ? "age_kyr" : "depth_cm"]));
    const lo=Math.min(...vals),hi=Math.max(...vals),top=Math.min(...levels),bottom=Math.max(...levels);
    const x=(v)=>65+(v-lo)/Math.max(hi-lo,1e-9)*260,y=(v)=>42+(v-top)/Math.max(bottom-top,1e-9)*300;
    const libraries=[...new Set(points.map((r)=>r.core))];
    const colors=["#9f741d","#527893","#4b806d"];
    return `<section class="panel"><h3>${esc(site)}</h3><svg viewBox="0 0 400 395" role="img" aria-label="${esc(site)} profile by ${age ? "age" : "depth"}"><line x1="65" x2="65" y1="42" y2="342" stroke="#bfb4a0"/><line x1="65" x2="325" y1="342" y2="342" stroke="#bfb4a0"/>${[0,.25,.5,.75,1].map((f)=>`<text x="58" y="${42+f*300+4}" text-anchor="end">${precision(top+f*(bottom-top))}</text><line x1="65" x2="325" y1="${42+f*300}" y2="${42+f*300}" stroke="#eee8dd"/>`).join("")}${libraries.map((library,i)=>{const p=points.filter((r)=>r.core===library).sort((a,b)=>Number(a[age ? "age_kyr" : "depth_cm"])-Number(b[age ? "age_kyr" : "depth_cm"]));return `<polyline fill="none" stroke="${colors[i%3]}" stroke-width="1.5" points="${p.map((r)=>`${x(Number(r[scoreKey]))},${y(Number(r[age ? "age_kyr" : "depth_cm"]))}`).join(" ")}"/>${p.map((r)=>`<circle cx="${x(Number(r[scoreKey]))}" cy="${y(Number(r[age ? "age_kyr" : "depth_cm"]))}" r="3.5" fill="${colors[i%3]}"><title>${esc(r.sample)} · ${esc(r.core)} · depth ${precision(r.depth_cm)} cm · age ${precision(r.age_kyr)} kyr BP · ${scoreKey} ${precision(r[scoreKey])} · ${esc(r.abundance_mode || r.status || "reference-weighted potential")}</title></circle>`).join("")}`;}).join("")}<text x="65" y="365">${precision(lo)}</text><text x="325" y="365" text-anchor="end">${precision(hi)}</text><text x="195" y="390" text-anchor="middle">${functionId ? "Reference-potential log ratio" : "Mean member CLR"}</text></svg><div class="chips">${libraries.map((l)=>chip(l)).join("")}</div></section>`;
  }).join("");
  $("functional-content").innerHTML=`<p class="small muted">${age ? "Age (kyr BP)" : "Depth (cm)"} increases downward. ${functionId ? "Reference-weighted functional potential, relative to the mapped background; not measured sample KO abundance." : "Mean module-member CLR; relative profile, not absolute abundance."} GeoB libraries remain separate. No smoothing or interpolation. Showing ${numeric(rows.length)} valid points from ${numeric(data.total_count)} records${data.truncated ? " · truncated response" : ""}.</p><div class="grid three profile-grid">${panels || `<section class="panel"><div class="empty">${esc(data.message || "No profile values with valid depth/age are available.")}</div></section>`}</div><section class="panel" style="margin-top:16px"><h2>Profile records</h2>${table(raw,[...(functionId ? ["function_id"] : ["module_id"]),"sample","core","depth_cm","age_kyr",scoreKey],30)}${data.source_file ? `<a class="button secondary" style="margin-top:12px" href="${linkToFile({id:data.source_file})}">Download full profile table</a>` : ""}</section>`;
}

async function renderEmbeddings() {
  const catalog=await ensureCatalog();
  const figureFiles=catalog.filter((file) => file.category === "Figures" && /vgae_taxon_embedding_pca|deep_module_summary|diffpool_assignment_diagnostics|ngraph_super_graph/.test(file.name)).slice(0,6);
  $("module-view").innerHTML=`<section class="panel" style="margin-bottom:16px"><div class="panel-title"><div><h2>Embedding view</h2><p class="small" style="margin:0">A two-dimensional projection of learned taxon positions for inspection.</p></div><span class="badge badge-warning">Exploratory</span></div><div class="filters" style="margin-bottom:13px"><div class="field wide"><label for="embedding-focus">Highlight taxon</label><input id="embedding-focus" placeholder="Optional taxon ID"></div><div class="field"><label for="embedding-limit">Points</label><select id="embedding-limit"><option>300</option><option selected>800</option><option>1500</option></select></div><button class="button" id="embedding-load" type="button">Refresh view</button></div><div id="embedding-svg" class="map-wrap" style="min-height:260px;padding:12px"></div><p id="embedding-caption" class="small muted" style="margin:10px 0 0"></p></section><section class="panel"><h2>Generated figures</h2><div class="figure-grid" id="module-figures"></div></section>`;
  $("module-figures").innerHTML=figureFiles.length ? figureFiles.map((file) => `<figure><a href="${linkToFile(file)}" target="_blank" rel="noopener"><img class="plot-image" loading="lazy" src="${linkToFile(file)}" alt="${esc(file.name)}"></a><figcaption>${esc(file.name.replaceAll("_"," "))}</figcaption></figure>`).join("") : `<div class="empty">No generated figures for this branch.</div>`;
  $("embedding-load").addEventListener("click",() => attempt(loadEmbedding,"Embedding failed"));
  await loadEmbedding();
}

async function loadEmbedding() {
  const data=await api("/api/embedding",{focus:$("embedding-focus").value.trim(),limit:$("embedding-limit").value});
  $("embedding-svg").innerHTML=data.svg || `<div class="empty">No embedding available.</div>`;
  $("embedding-caption").textContent=`${numeric((data.rows || []).length)} plotted records. This projection summarizes an exploratory learned space.`;
}

let conversationFallback=null;

function readConversation() {
  if(conversationFallback !== null) return conversationFallback.slice(-12);
  try {
    const turns=JSON.parse(sessionStorage.getItem("constellations-conversation") || "[]");
    return Array.isArray(turns) ? turns.slice(-12) : [];
  } catch (_) { return []; }
}

function saveConversation(turns) {
  const recent=turns.slice(-12);
  try { sessionStorage.setItem("constellations-conversation",JSON.stringify(recent));conversationFallback=null; }
  catch (_) {
    conversationFallback=recent;
    notify("Conversation storage is unavailable. Answers remain visible until this page is reloaded.");
  }
}

async function renderQuery() {
  setPage("query", "Query");
  const questions=(await api("/api/summary")).questions || [];
  $("app-view").innerHTML=pageHead("Evidence-led search", "Ask the graph", "Explore evidence cards and learned network results. Select a turn to inspect the records that supported it.")
    + `<div class="query-layout"><section class="panel"><div class="panel-title"><h2>Conversation</h2><button class="button text" id="query-clear" type="button">Clear this session</button></div><div id="conversation" class="conversation"></div><div class="query-compose"><div class="field"><label for="query-input">Your question</label><textarea id="query-input" placeholder="Ask about taxa, cores, modules or evidence…"></textarea></div><div class="button-row" style="justify-content:space-between;margin-top:10px"><div class="field" style="min-width:160px"><label for="query-provider">Answer source</label><select id="query-provider"><option value="local">Local evidence</option><option value="gemini">Gemini synthesis</option></select></div><button class="button" id="query-submit" type="button">Ask question →</button></div><div class="small muted" style="margin-top:10px">Functional follow-ups reuse the selected entities and analysis snapshot. Clear this session to reset the context.</div></div></section><aside class="evidence-column stack"><section class="panel"><div class="panel-title"><h2>Evidence for selected answer</h2><span class="badge badge-blue">Source records</span></div><div id="query-evidence" class="scroll-panel"><div class="empty">Ask a question or select a past answer.</div></div></section><section class="panel panel-soft"><h3>Try a question</h3><div id="query-suggestions" class="stack"></div></section></aside></div>`;
  $("query-suggestions").innerHTML=questions.slice(0,3).map((text,index) => `<button type="button" class="result-item" data-question="${index}">${esc(text)}</button>`).join("") || `<div class="small muted">No saved examples for this run.</div>`;
  $("query-suggestions").querySelectorAll("button").forEach((button) => button.addEventListener("click",() => { $("query-input").value=questions[Number(button.dataset.question)]; $("query-input").focus(); }));
  $("query-submit").addEventListener("click",() => attempt(runQuery,"Query failed"));
  $("query-clear").addEventListener("click",() => { saveConversation([]); showConversation(); $("query-evidence").innerHTML=`<div class="empty">No answer selected.</div>`; });
  $("query-input").addEventListener("keydown",(event) => { if(event.key === "Enter" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); attempt(runQuery,"Query failed"); } });
  showConversation();
  const sharedQuestion=new URLSearchParams(location.search).get("question");
  if (sharedQuestion) { const url=new URL(location.href); url.searchParams.delete("question"); history.replaceState({},"",url); $("query-input").value=sharedQuestion; await runQuery(); }
}

function showConversation() {
  const turns=readConversation();
  const box=$("conversation");
  if(!box) return;
  box.innerHTML=turns.length ? turns.map((turn,index) => `<div class="chat-turn user"><div class="chat-label">You</div><div class="answer-text">${esc(turn.question)}</div></div><div class="chat-turn"><div class="chat-label">Constellations · ${esc(turn.provider || "local evidence")}</div>${!turn.scope && !turn.context?.scope ? `<div class="small muted">Earlier answer: analysis scope and evidence checks were not recorded. Re-ask to use the current checks.</div>` : ""}<div class="answer-text">${esc(turn.answer)}</div><div class="turn-actions"><button class="button text" data-turn="${index}" type="button">View evidence →</button></div></div>`).join("") : `<div class="empty">Start with a question. The answer and its evidence will stay together in this browser session.</div>`;
  box.querySelectorAll("button[data-turn]").forEach((button) => button.addEventListener("click",() => showQueryEvidence(turns[Number(button.dataset.turn)])));
  const latestQuestion=[...box.querySelectorAll(".chat-turn.user")].pop();
  box.scrollTop=latestQuestion ? latestQuestion.offsetTop-box.offsetTop : 0;
  if(turns.length) showQueryEvidence(turns[turns.length-1]);
}

function evidenceItems(turn) {
  const cards=turn.cards || [];
  const links=turn.links || [];
  const cardHtml=cards.map((row) => `<div class="evidence-card"><strong>${esc(row.title || row.entity_id || row.card_id || "Evidence card")}</strong><small>${esc(row.card_type || "card")}${row.entity_id ? ` · ${esc(row.entity_id)}` : ""}</small>${row.card_id ? `<small>Evidence ID: ${esc(row.card_id)}</small>` : ""}${row.summary ? `<p>${esc(String(row.summary).slice(0,380))}</p>` : ""}${row.entity_id && String(row.entity_id).startsWith("functionalassociation:") ? `<a href="/knowledge-graph?view=browser&id=${encodeURIComponent(row.entity_id)}">Inspect cited association →</a>` : ""}</div>`).join("");
  const linkHtml=links.map((row) => `<div class="evidence-card"><strong>${esc(row.taxon_from || row.source || "Link")} → ${esc(row.taxon_to || row.target || "")}</strong><small>Learned link hypothesis${row.latent_score == null ? "" : ` · score ${esc(row.latent_score)}`}</small></div>`).join("");
  const proofContext=new URLSearchParams({threshold:turn.graph?.scope?.threshold || '',method:turn.graph?.scope?.method || '',kind:turn.graph?.scope?.module_system || '',snapshot:turn.graph?.scope?.db_snapshot || '',core:turn.graph?.core || '',carriers_only:String(turn.graph?.carriers_only || false)});
  const graphHtml=(turn.graph?.paths || []).map(path=>`<div class="evidence-card"><strong>${esc(path.claim_kind || 'Functional association')}</strong><small>Proof: ${esc(path.proof_id || path.association_id || '')}</small><p>${esc((path.node_details || []).map(n=>n.label || n.node_id).join(' → '))}</p><p>${esc(path.carrier_status || '')}</p>${path.statistics ? details(path.statistics,[["q_value","q"],["permutation_z_score","Permutation Z"],["annotation_status","Annotation confidence"]]) : ''}<a href="/knowledge-graph?view=metapaths&pattern=${encodeURIComponent(turn.graph.metapath)}&source=${encodeURIComponent(turn.graph.source)}&target=${encodeURIComponent(turn.graph.target || '')}&${proofContext}">Inspect proof path →</a></div>`).join('');
  const tableContext=params({view:turn.table?.intent==='profiles' ? 'profiles' : 'functions',module_id:turn.table?.entities?.modules?.[0],function_id:turn.table?.entities?.functions?.[0],core:turn.table?.core,threshold:turn.table?.scope?.threshold,method:turn.table?.scope?.method,kind:turn.table?.scope?.module_system,snapshot:turn.table?.scope?.db_snapshot});
  const tableHtml=turn.table ? `<div class="evidence-card"><strong>${esc(turn.table.intent)}</strong><p>${numeric(turn.table.returned_count)} of ${numeric(turn.table.total_count)} records${turn.table.truncated ? ' · bounded evidence' : ''}</p>${table(turn.table.rows,null,40)}${turn.table.source_file ? `<a href="${linkToFile({id:turn.table.source_file})}">Download source evidence →</a><br>` : ""}${turn.table.intent==='metadata semantics' ? `<a href="https://doi.org/10.1594/PANGAEA.701576" target="_blank" rel="noopener noreferrer">LR04 reference and units →</a>` : `<a href="/modules?${tableContext}">Open full analysis →</a>`}</div>` : '';
  return tableHtml + graphHtml + cardHtml + linkHtml || `<div class="empty">This answer did not return inspectable cards or links.</div>`;
}

function showQueryEvidence(turn) {
  const scope=turn.scope || turn.context?.scope;
  const scopeLabel=scope ? `${String(scope.module_system || '').toUpperCase()} · ${scope.threshold || ''} · ${scope.method || ''}` : '';
  $("query-evidence").innerHTML=`<p class="small muted">${esc(turn.question)}</p>${scopeLabel ? `<div class="insight">Analysis: ${esc(scopeLabel)}</div>` : ''}${evidenceItems(turn)}${turn.status ? `<div class="insight">Answer status: ${esc(turn.status)}</div>` : ""}`;
}

async function runQuery() {
  const question=$("query-input").value.trim();
  if(!question) { notify("Enter a question first."); return; }
  const provider=$("query-provider").value;
  const button=$("query-submit");
  const controller=new AbortController();
  const deadline=setTimeout(()=>controller.abort(),90000);
  button.disabled=true; button.textContent="Searching…";
  try {
    const previous=readConversation().at(-1);
    let response=await fetch('/api/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:question,llm_provider:provider,context:previous?.context || {}}),signal:controller.signal});
    if(response.status===501 || response.status===404) response=await fetch('/api/query?'+params({query:question,llm_provider:provider}),{signal:controller.signal});
    const data=await response.json();if(!response.ok) throw new Error(data.error || 'Query failed');
    const cardRows=(data.retrieved_cards || []).length ? data.retrieved_cards : (data.semantic_hits || []);
    const linkRows=(data.retrieved_links || []).length ? data.retrieved_links : (data.link_hits || []);
    const localSummary=(data.answer_lines || []).join("\n") || data.markdown || "No answer was returned.";
    const fallbackNotice=provider === 'gemini' && !data.llm_answer ? synthesisFallbackNotice(data.llm_status) : '';
    const structured=['functional_kg','climate_context'].includes(data.query_type);
    const answer=(fallbackNotice+(structured ? (data.llm_answer || localSummary) : provider === "gemini" && data.llm_answer ? data.llm_answer : `${localSummary}\n\n${cardRows.length} related records and ${linkRows.length} link candidates are available in the evidence panel.`)).slice(0,18000);
    const sourceLabel=data.llm_status==='validated' ? 'Gemini · typed evidence checked' : data.llm_status==='evidence_checked' ? 'Gemini · citations and scope checked' : structured ? 'KG evidence · '+String(data.llm_status || 'local').replaceAll('_',' ') : provider === 'gemini' ? 'Local evidence · synthesis unavailable' : 'Local evidence';
    const turn={question,answer,provider:sourceLabel,status:data.llm_status || "",scope:data.scope || null,cards:cardRows.slice(0,15),links:linkRows.slice(0,8),graph:data.graph_evidence || null,context:data.context || null,table:data.table_evidence || null,resolution:data.candidates || []};
    const turns=readConversation(); turns.push(turn); saveConversation(turns);
    $("query-input").value=""; showConversation();
  } catch(error) {
    if(error.name==='AbortError') throw new Error('The query timed out. Please retry or choose Local evidence.');
    throw error;
  } finally { clearTimeout(deadline);button.disabled=false; button.textContent="Ask question →"; }
}

function synthesisFallbackNotice(status) {
  const reasons={output_truncated:'Gemini reached its response limit.',invalid_json:'Gemini returned an incomplete or invalid response.',invalid_response:'Gemini returned no usable answer.',empty_response:'Gemini returned no answer.',generation_stopped:'Gemini stopped before completing the answer.',missing_key:'The Gemini API key is not configured.',validation_failed:'The Gemini answer did not pass the evidence checks.',http_error_429:'Gemini is rate limited.',http_error_503:'Gemini is temporarily unavailable.',error:'The Gemini request failed.',provider_error:'The Gemini request failed.'};
  if(['rule_based','needs_entities','context_reset','annotation_unavailable','analysis_unavailable'].includes(status)) return '';
  return `${reasons[status] || 'Gemini synthesis was unavailable.'} Showing local evidence below.\n\n`;
}

async function renderData(viewName = null) {
  setPage("data", "Data");
  const view=viewName || pathSection("view",["files","evidence","sources"]);
  $("app-view").innerHTML=pageHead("Traceable outputs", "Data and evidence", "Browse source files, run artifacts, reports, and the evidence cards used by the discovery tools.")
    + `<div class="tabs" id="data-tabs" role="tablist" aria-label="Data views"></div><div id="data-view"></div>`;
  subTabs("data-tabs",{files:"Files & reports",evidence:"Evidence cards",sources:"Source inventory"},view,(next) => { const url=new URL(location.href); url.pathname="/data"; url.searchParams.set("view",next); history.pushState({},"",url); renderData(next); });
  await attempt(async () => { if(view === "files") await renderFiles(); else if(view === "evidence") await renderCards(); else await renderSources(); },"Data view failed");
}

async function renderFiles() {
  const files=await ensureCatalog();
  const groups=[...new Set(files.map((item) => item.category))];
  $("data-view").innerHTML=`<div class="grid data-layout"><section class="panel"><div class="panel-title"><h2>Available files</h2><span class="small muted">${numeric(files.length)} indexed files</span></div><div class="filters" style="grid-template-columns:minmax(0,1fr) 175px;margin-bottom:14px"><div class="field"><label for="data-search">Search files</label><input id="data-search" placeholder="Name or folder"></div><div class="field"><label for="data-category">Category</label><select id="data-category"><option value="">All categories</option>${groups.map((group) => `<option>${esc(group)}</option>`).join("")}</select></div></div><div id="data-file-list" class="data-list"></div><div class="button-row" style="margin-top:12px"><button id="data-more" class="button secondary" type="button">Show more</button><span id="data-results" class="small muted"></span></div></section><aside class="stack"><section class="panel"><h2>Report preview</h2><p class="small muted">Select a Markdown report to read it here; other files download directly.</p><div id="data-preview" class="report-text">Choose a report from the list.</div></section><section class="panel panel-soft"><h3>What the labels mean</h3><p class="small" style="margin:0">A completed run and a structurally valid graph do not establish biological validity. Check the provenance and unit fields before interpreting proxy values.</p></section></aside></div>`;
  state.dataLimit=22;
  $("data-search").addEventListener("input",() => { state.dataLimit=22; fillFiles(); });
  $("data-category").addEventListener("change",() => { state.dataLimit=22; fillFiles(); });
  $("data-more").addEventListener("click",() => { state.dataLimit+=22; fillFiles(); });
  fillFiles();
}

function fillFiles() {
  const query=$("data-search").value.trim().toLowerCase();
  const category=$("data-category").value;
  const files=(state.catalog || []).filter((file) => (!category || file.category===category) && (!query || `${file.name} ${file.id}`.toLowerCase().includes(query)));
  $("data-file-list").innerHTML=files.slice(0,state.dataLimit).map((file) => `<div class="data-row"><div><strong>${esc(file.name)}</strong><small>${esc(file.category)} · ${esc(file.id)}</small></div><span class="file-size small muted">${numeric(Math.round(file.size/1024))} KB</span>${file.format === "MD" ? `<button class="button secondary" type="button" data-preview="${esc(file.id)}">Preview</button>` : `<a class="button secondary" href="${linkToFile(file)}" ${file.format === "PNG" ? 'target="_blank" rel="noopener"' : ""}>${file.format === "PNG" ? "Open" : "Download"}</a>`}</div>`).join("") || `<div class="empty">No files match this search.</div>`;
  $("data-results").textContent=`Showing ${numeric(Math.min(files.length,state.dataLimit))} of ${numeric(files.length)}`;
  $("data-more").disabled=state.dataLimit>=files.length;
  $("data-file-list").querySelectorAll("button[data-preview]").forEach((button) => button.addEventListener("click",async () => {
    try { const response=await fetch(`/api/data/file?id=${encodeURIComponent(button.dataset.preview)}`); if(!response.ok) throw new Error(`HTTP ${response.status}`); $("data-preview").textContent=await response.text(); }
    catch (error) { notify(`Report preview failed: ${error.message}`); }
  }));
}

async function renderCards() {
  $("data-view").innerHTML=`<section class="panel"><div class="panel-title"><h2>Evidence cards</h2><span class="badge badge-blue">Inspectable records</span></div><div class="filters" style="grid-template-columns:minmax(0,1fr) 190px auto;margin-bottom:14px"><div class="field"><label for="card-search">Find evidence</label><input id="card-search" placeholder="Taxon, site, module or text"></div><div class="field"><label for="card-type">Card type</label><select id="card-type"><option value="">All types</option>${Object.keys(state.overview.card_types || {}).map((type) => `<option value="${esc(type)}">${esc(type)}</option>`).join("")}</select></div><button class="button" id="card-load" type="button">Search cards</button></div><div id="card-list" class="grid three"></div></section>`;
  $("card-load").addEventListener("click",() => attempt(loadCards,"Evidence search failed"));
  $("card-search").addEventListener("keydown",(event) => { if(event.key === "Enter") attempt(loadCards,"Evidence search failed"); });
  await loadCards();
}

async function loadCards() {
  const data=await api("/api/cards",{query:$("card-search").value.trim(),card_type:$("card-type").value,limit:36});
  $("card-list").innerHTML=(data.rows || []).map((row) => `<article class="evidence-card" style="margin:0"><span class="badge badge-neutral">${esc(row.card_type || "evidence")}</span><h3 style="margin:9px 0 4px;overflow-wrap:anywhere">${esc(row.title || row.entity_id || row.card_id)}</h3><div class="tiny muted">${esc(row.entity_id || "")}</div><p>${esc(String(row.summary || row.evidence || "").slice(0,360))}</p>${row.entity_id && /^(taxon:|site:|sample:|module:)/.test(String(row.entity_id)) ? `<a class="button text" href="/knowledge-graph?view=browser&id=${encodeURIComponent(row.entity_id)}">Inspect in graph →</a>` : ""}</article>`).join("") || `<div class="empty">No evidence cards match this filter.</div>`;
}

async function renderSources() {
  const data=state.overview;
  const files=await ensureCatalog();
  const sourceFiles=files.filter((file) => file.category === "Source data");
  $("data-view").innerHTML=`<div class="grid two"><section class="panel"><h2>Registered datasets</h2>${table(data.sources || [],["name","source_file"],35)}<p class="small muted" style="margin:11px 0 0">Source paths reflect the current branch manifest and registered KG datasets.</p></section><section class="panel"><h2>Physical sites and libraries</h2>${coordinatePlot(data.registered_locations || data.locations)}<div style="margin-top:14px">${table((data.registered_locations || data.locations || []).map((row) => ({site:row.site,status:row.active ? "Analyzed" : "Catalogued",cores:row.cores.join(", "),samples:row.samples,latitude:row.latitude,longitude:row.longitude})),["site","status","cores","samples","latitude","longitude"],10)}</div></section></div><section class="panel" style="margin-top:16px"><h2>Source files</h2><div class="data-list">${sourceFiles.map((file) => `<div class="data-row"><div><strong>${esc(file.name)}</strong><small>${esc(file.id)}</small></div><span class="file-size small muted">${numeric(Math.round(file.size/1024))} KB</span><a class="button secondary" href="${linkToFile(file)}">Download</a></div>`).join("") || `<div class="empty">No local source files registered.</div>`}</div></section>`;
}

async function start() {
  const toggle=$("mobile-nav-toggle");
  toggle.addEventListener("click",() => { const open=document.querySelector(".sidebar").classList.toggle("open"); toggle.setAttribute("aria-expanded",String(open)); });
  try {
    state.overview=await api("/api/overview");
    $("sidebar-branch").textContent=state.overview.branch || "Unknown workstream";
    $("sidebar-run").textContent=`● ${state.overview.run_status || "unverified"} run`;
    $("analysis-badge").textContent=state.overview.analysis_label || "Exploratory analysis";
    const route=location.pathname.replace(/^\//,"") || "overview";
    if(route === "knowledge-graph") await renderKnowledgeGraph();
    else if(route === "query") await renderQuery();
    else if(route === "modules") await renderModules();
    else if(route === "data") await renderData();
    else await renderOverview();
  } catch(error) {
    $("app-view").innerHTML=`<div class="panel"><h1>Could not open this workstream</h1><p>${esc(error.message)}</p><button class="button" type="button" onclick="location.reload()">Retry</button></div>`;
    $("service-state").textContent="● Service unavailable";
  }
}

window.addEventListener("popstate",() => location.reload());
window.addEventListener("resize",() => { state.kgCy?.resize(); state.moduleCy?.resize(); });
start();
