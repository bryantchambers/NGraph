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

const nodePalette = {site:"#a77921",sample:"#5b9b87",taxon:"#4b806d",module:"#866b9a",proxymeasurement:"#648ba0",proxyvariable:"#567f9a",dataset:"#8b8b80",ontologyterm:"#bd8b5d",analysisrun:"#656b75",controlcontext:"#9c8e83"};
function graphStyle() {
  const base = [
    {selector:"node",style:{"background-color":"#798d81","label":"data(label)","color":"#373930","font-family":"Inter, Segoe UI, sans-serif","font-size":10,"text-wrap":"ellipsis","text-max-width":"105px","text-valign":"bottom","text-margin-y":5,"width":18,"height":18,"border-width":2,"border-color":"#fffdfa","overlay-opacity":0}},
    {selector:"edge",style:{"line-color":"#c5bba9","width":1.35,"opacity":.72,"curve-style":"bezier","target-arrow-shape":"triangle","target-arrow-color":"#c5bba9","arrow-scale":.65}},
    {selector:"node:selected",style:{"border-width":4,"border-color":"#b8831d","width":26,"height":26}},
    {selector:"edge:selected",style:{"line-color":"#a77921","target-arrow-color":"#a77921","width":3}}
  ];
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
  return `<div class="legend">${[["site","Core"],["sample","Sample"],["taxon","Taxon"],["module","Module"],["proxymeasurement","Measurement"],["proxyvariable","Proxy"],["ontologyterm","Ontology"]].map(([key,label]) => `<span class="legend-item"><span class="legend-dot" style="background:${nodePalette[key]}"></span>${label}</span>`).join("")}</div>`;
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
  $("kg-to-path").addEventListener("click", () => { if (state.selectedNode) { sessionStorage.setItem("constellations-metapath-source",state.selectedNode); location.href="/knowledge-graph?view=metapaths"; } });
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
  if (!node) { $("kg-node-detail").innerHTML = `<div class="empty">Node not found.</div>`; return; }
  $("kg-node-badge").textContent = node.node_type || "Node";
  $("kg-node-detail").innerHTML = `<h3 style="overflow-wrap:anywhere">${esc(node.label || node.node_id)}</h3>${details(node,[["node_id","ID"],["node_type","Type"],["core","Core"],["taxon","Taxon"],["module_id","Module"],["variable","Variable"],["value","Value"],["unit","Unit"],["unit_status","Unit status"],["match_method","Matching"],["source_file","Source"],["evidence_status","Evidence"]])}<p class="small muted" style="margin-top:12px">${numeric((data.incident_edges || []).length)} relations returned · ${numeric((data.measurements || []).length)} measurements returned</p>`;
}

async function renderSchema() {
  const schema = await ensureSchema();
  $("kg-view").innerHTML = `<div class="hero-note">This describes the current graph structure and observed relation types. Structural validation and biological interpretation are separate checks.</div><div class="grid two"><section class="panel"><h2>Node types</h2>${table(schema.node_types || [],["node_type","count"],30)}</section><section class="panel"><h2>Relations</h2>${table(schema.edge_types || [],["edge_type","count"],30)}</section></div><section class="panel" style="margin-top:16px"><h2>Allowed connections in this run</h2>${table(schema.metagraph || [],["source_node_type","edge_type","target_node_type","count"],35)}</section>`;
}

const metapaths = {
  taxon_proxy:{label:"Taxon → sample → measurement → proxy",source:"Taxon",target:"ProxyVariable",help:"Which sampled proxy values connect to this taxon?"},
  site_module_bridge:{label:"Core → taxa → module → taxa → core",source:"Site",target:"Site",help:"Which modules connect taxa observed across two cores?"},
  shared_module:{label:"Taxon → module ← taxon",source:"Taxon",target:"Taxon",help:"Do these two taxa share an exploratory module?"},
  site_taxon:{label:"Core → sample → taxon",source:"Site",target:"Taxon",help:"Which sample observations connect a core to a taxon?"}
};

async function renderMetapaths() {
  await ensureSchema();
  const savedSource = sessionStorage.getItem("constellations-metapath-source") || "";
  $("kg-view").innerHTML = `<div class="hero-note">Metapath counts and degree-weighted path counts describe connectivity. They are exploratory scores, without a significance test.</div><section class="panel" style="margin-bottom:16px"><div class="panel-title"><h2>Choose a connection pattern</h2><span class="badge badge-blue">Typed paths</span></div><div class="filters"><div class="field wide"><label for="path-pattern">Metapath</label><select id="path-pattern">${Object.entries(metapaths).map(([key,value]) => `<option value="${key}">${esc(value.label)}</option>`).join("")}</select></div><div class="field"><label for="path-source-type">From type</label><select id="path-source-type"></select></div><div class="field"><label for="path-target-type">To type</label><select id="path-target-type"></select></div><div class="field suggestion-box wide"><label for="path-source">From node</label><input id="path-source" placeholder="Search or enter a node ID" autocomplete="off" value="${esc(savedSource)}"><div id="path-source-suggestions" class="suggestions"></div></div><div class="field suggestion-box wide"><label for="path-target">To node</label><input id="path-target" placeholder="Search or enter a node ID" autocomplete="off"><div id="path-target-suggestions" class="suggestions"></div></div></div><div class="button-row" style="margin-top:13px"><button id="path-run" class="button" type="button">Find connections</button><button id="path-demo-tax" class="button secondary" type="button">Example: taxon to SST</button><button id="path-demo-core" class="button secondary" type="button">Example: cores through module</button></div><p class="small muted" id="path-help" style="margin:11px 0 0"></p></section><div class="graph-layout"><section class="panel graph-stage"><div class="panel-title"><div><h2>Evidence path</h2><span class="small muted" id="path-graph-caption">Choose two nodes, then run a search.</span></div><button class="button secondary" id="path-fit" type="button">Fit graph</button></div><div class="graph-canvas medium" id="path-canvas" role="img" aria-label="Selected typed evidence path"><div class="empty">A selected path will appear here.</div></div>${graphLegend()}</section><aside class="stack"><section class="panel"><h2>Connectivity</h2><div id="path-summary" class="small muted">No search yet.</div></section><section class="panel"><div class="panel-title"><h2>Inspectable evidence</h2><span id="path-count" class="small muted"></span></div><div class="result-list" id="path-list"><div class="empty">Run a metapath search to see paths.</div></div></section><section class="panel"><h2>Selected path details</h2><div id="path-detail" class="small muted">Choose an evidence path above.</div></section></aside></div>`;
  const availableTypes = (state.schema.node_types || []).map((row) => row.node_type);
  const typeOptions = `<option value="">All types</option>` + availableTypes.map((type) => `<option value="${esc(type)}">${esc(type)}</option>`).join("");
  $("path-source-type").innerHTML = typeOptions; $("path-target-type").innerHTML = typeOptions;
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
  $("path-fit").addEventListener("click",() => state.kgCy?.fit(undefined,36));
  const demo=new URLSearchParams(location.search).get("demo");
  if (demo === "taxon" || demo === "cores") await loadMetapathDemo(demo === "taxon" ? 0 : 1);
}

function updateMetapathTypes() {
  const selected = metapaths[$("path-pattern").value];
  $("path-source-type").value = selected.source;
  $("path-target-type").value = selected.target;
  $("path-help").textContent = selected.help;
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
  if (!source || !target) { notify("Choose both source and target nodes."); return; }
  $("path-summary").textContent="Searching typed connections…";
  const data = await api("/api/kg/connectivity",{source,target,metapath:$("path-pattern").value,limit:20});
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
  $("path-list").innerHTML=(data.paths || []).length ? data.paths.map((path,index) => `<button type="button" class="result-item" data-index="${index}"><strong>Path ${index+1}</strong><span>${esc((path.node_details || []).map((n) => n.label || n.node_id).join(" → "))}</span><span>Weight ${Number(path.weight).toPrecision(3)}</span></button>`).join("") : `<div class="empty">No path of this type connects these nodes.</div>`;
  $("path-list").querySelectorAll("button[data-index]").forEach((button) => button.addEventListener("click",() => showEvidencePath(Number(button.dataset.index))));
  if ((data.paths || []).length) showEvidencePath(0);
  else { destroyGraph("kgCy"); $("path-canvas").innerHTML=`<div class="empty">No connection found for this pattern.</div>`; $("path-detail").textContent=""; }
}

function showEvidencePath(index) {
  const path = state.pathResult?.paths?.[index];
  if (!path) return;
  $("path-list").querySelectorAll("button[data-index]").forEach((button) => button.classList.toggle("active",Number(button.dataset.index)===index));
  const lookup = new Map((path.node_details || []).map((node) => [node.node_id,node]));
  const nodes = (path.nodes || []).map((id,i) => ({data:{id,label:lookup.get(id)?.label || id},position:{x:120+i*210,y:200},classes:String(lookup.get(id)?.node_type || "").toLowerCase()}));
  const edges = (path.edges || []).map((edge,i) => ({data:{id:String(edge.edge_id || `step-${i}`),source:String(edge.source_id),target:String(edge.target_id),label:String(edge.edge_type)}}));
  mountGraph("path-canvas",nodes,edges,"kgCy","preset",(id) => { const node=lookup.get(id); if(node) $("path-detail").innerHTML=details(node,[["node_id","ID"],["node_type","Type"],["value","Value"],["unit","Unit"],["unit_status","Unit status"],["match_method","Match"],["bracket_width_cm","Gap (cm)"],["source_observation_ids","Source records"],["source_file","Source"]]); });
  $("path-graph-caption").textContent=`Path ${index+1} of ${(state.pathResult.paths || []).length} shown · ${path.nodes?.length || 0} nodes`;
  $("path-detail").innerHTML=(path.node_details || []).map((node,i) => `<div class="evidence-card"><strong>${i+1}. ${esc(node.label || node.node_id)}</strong><small>${esc(node.node_type)} · ${esc(node.node_id)}</small>${node.value !== "" && node.value != null ? `<p>Value: ${esc(node.value)} ${esc(node.unit || "")} · ${esc(node.match_method || "observed")}</p>` : ""}${node.source_observation_ids ? `<p>Source records: ${esc(node.source_observation_ids)}</p>` : ""}</div>`).join("");
}

async function renderModules(viewName = null) {
  destroyGraph("moduleCy");
  setPage("modules", "Modules");
  const view = viewName || pathSection("view",["supergraph","modules","embeddings"]);
  $("app-view").innerHTML = pageHead("Learned structure", "Modules and site networks", "Explore core similarity, exploratory taxon groups, embeddings, and their supporting figures.")
    + `<div class="hero-note">These are exploratory groups from the permissive mixed abundance analysis. Assignment and graph scores are evidence for review, not confirmed ecological communities.</div><div class="tabs" id="module-tabs" role="tablist" aria-label="Module views"></div><div id="module-view"></div>`;
  subTabs("module-tabs",{supergraph:"Supergraph",modules:"Taxon modules",embeddings:"Embeddings & figures"},view,(next) => { const url=new URL(location.href); url.pathname="/modules"; url.searchParams.set("view",next); history.pushState({},"",url); renderModules(next); });
  await attempt(async () => { if(view === "supergraph") await renderSupergraph(); else if(view === "modules") await renderModuleExplorer(); else await renderEmbeddings(); },"Modules view failed");
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
  const d=await api("/api/modules",{threshold:state.overview.threshold,method:state.overview.method,kind,module_id:moduleId,limit:1000});
  state.moduleData=d;
  const summary=d.summary || [];
  $("module-select").innerHTML=summary.map((row) => `<option value="${esc(row.module_id)}">${esc(row.module_id)} · ${numeric(row.taxa)} taxa</option>`).join("");
  $("module-select").value=d.module_id || "";
  $("module-title").textContent=`${kind === "vgae" ? "VGAE" : "DiffPool"} ${d.module_id || "module"}`;
  const selected=summary.find((row) => String(row.module_id) === String(d.module_id));
  $("module-subtitle").textContent=`${numeric(selected?.taxa || (d.members || []).length)} assigned taxa · ${state.overview.threshold} / ${state.overview.method}`;
  $("module-size-bars").innerHTML=bars(Object.fromEntries(summary.map((row) => [row.module_id,row.taxa])),9);
  const representative=(d.members || []).slice(0,32);
  const center=`module:${kind}:${d.module_id}`;
  const nodes=[{data:{id:center,label:`${kind.toUpperCase()} ${d.module_id}`},classes:"module"},...representative.map((row) => ({data:{id:String(row.taxon),label:String(row.taxon)},classes:"taxon"}))];
  const edges=representative.map((row,index) => ({data:{id:`member-${index}`,source:center,target:String(row.taxon)}}));
  mountGraph("module-canvas",nodes,edges,"moduleCy","cose",(id) => {
    if(id===center) return;
    const row=representative.find((item) => String(item.taxon)===id) || {};
    $("module-member-detail").innerHTML=`<h3>${esc(id)}</h3>${details(row,[["module_kmeans","VGAE module"],["consensus_module","DiffPool module"],["domain","Domain"],["phylum","Phylum"],["functional_group","Function"]])}<a class="button secondary" style="margin-top:12px" href="/knowledge-graph?view=browser&id=${encodeURIComponent(`taxon:${id}`)}">Open taxon in KG →</a>`;
  });
  state.modulePage=0;
  fillModuleMembers();
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

function readConversation() {
  try {
    const turns=JSON.parse(sessionStorage.getItem("constellations-conversation") || "[]");
    return Array.isArray(turns) ? turns.slice(-12) : [];
  } catch (_) { return []; }
}

function saveConversation(turns) {
  try { sessionStorage.setItem("constellations-conversation",JSON.stringify(turns.slice(-12))); }
  catch (_) { notify("This browser could not save the conversation for this session."); }
}

async function renderQuery() {
  setPage("query", "Query");
  const questions=(await api("/api/summary")).questions || [];
  $("app-view").innerHTML=pageHead("Evidence-led search", "Ask the graph", "Explore evidence cards and learned network results. Select a turn to inspect the records that supported it.")
    + `<div class="query-layout"><section class="panel"><div class="panel-title"><h2>Conversation</h2><button class="button text" id="query-clear" type="button">Clear this session</button></div><div id="conversation" class="conversation"></div><div class="query-compose"><div class="field"><label for="query-input">Your question</label><textarea id="query-input" placeholder="Ask about taxa, cores, modules or evidence…"></textarea></div><div class="button-row" style="justify-content:space-between;margin-top:10px"><div class="field" style="min-width:160px"><label for="query-provider">Answer source</label><select id="query-provider"><option value="local">Local evidence</option><option value="gemini">Gemini synthesis</option></select></div><button class="button" id="query-submit" type="button">Ask question →</button></div><div class="small muted" style="margin-top:10px">Each question currently retrieves independently. Conversation context will be added after the KG learning layer is validated.</div></div></section><aside class="evidence-column stack"><section class="panel"><div class="panel-title"><h2>Evidence for selected answer</h2><span class="badge badge-blue">Source records</span></div><div id="query-evidence" class="scroll-panel"><div class="empty">Ask a question or select a past answer.</div></div></section><section class="panel panel-soft"><h3>Try a question</h3><div id="query-suggestions" class="stack"></div></section></aside></div>`;
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
  box.innerHTML=turns.length ? turns.map((turn,index) => `<div class="chat-turn user"><div class="chat-label">You</div><div class="answer-text">${esc(turn.question)}</div></div><div class="chat-turn"><div class="chat-label">Constellations · ${esc(turn.provider || "local evidence")}</div><div class="answer-text">${esc(turn.answer)}</div><div class="turn-actions"><button class="button text" data-turn="${index}" type="button">View evidence →</button></div></div>`).join("") : `<div class="empty">Start with a question. The answer and its evidence will stay together in this browser session.</div>`;
  box.querySelectorAll("button[data-turn]").forEach((button) => button.addEventListener("click",() => showQueryEvidence(turns[Number(button.dataset.turn)])));
  const latestQuestion=[...box.querySelectorAll(".chat-turn.user")].pop();
  box.scrollTop=latestQuestion ? latestQuestion.offsetTop-box.offsetTop : 0;
  if(turns.length) showQueryEvidence(turns[turns.length-1]);
}

function evidenceItems(turn) {
  const cards=turn.cards || [];
  const links=turn.links || [];
  const cardHtml=cards.map((row) => `<div class="evidence-card"><strong>${esc(row.title || row.entity_id || row.card_id || "Evidence card")}</strong><small>${esc(row.card_type || "card")}${row.entity_id ? ` · ${esc(row.entity_id)}` : ""}</small>${row.summary ? `<p>${esc(String(row.summary).slice(0,380))}</p>` : ""}</div>`).join("");
  const linkHtml=links.map((row) => `<div class="evidence-card"><strong>${esc(row.taxon_from || row.source || "Link")} → ${esc(row.taxon_to || row.target || "")}</strong><small>Learned link hypothesis${row.latent_score == null ? "" : ` · score ${esc(row.latent_score)}`}</small></div>`).join("");
  return cardHtml + linkHtml || `<div class="empty">This answer did not return inspectable cards or links.</div>`;
}

function showQueryEvidence(turn) {
  $("query-evidence").innerHTML=`<p class="small muted">${esc(turn.question)}</p>${evidenceItems(turn)}${turn.status ? `<div class="insight">Synthesis status: ${esc(turn.status)}</div>` : ""}`;
}

async function runQuery() {
  const question=$("query-input").value.trim();
  if(!question) { notify("Enter a question first."); return; }
  const provider=$("query-provider").value;
  const button=$("query-submit");
  button.disabled=true; button.textContent="Searching…";
  try {
    const data=await api("/api/query",{query:question,llm_provider:provider});
    const cardRows=(data.retrieved_cards || []).length ? data.retrieved_cards : (data.semantic_hits || []);
    const linkRows=(data.retrieved_links || []).length ? data.retrieved_links : (data.link_hits || []);
    const localSummary=(data.answer_lines || []).join("\n") || data.markdown || "No answer was returned.";
    const answer=(provider === "gemini" && data.llm_answer ? data.llm_answer : `${localSummary}\n\n${cardRows.length} related records and ${linkRows.length} link candidates are available in the evidence panel.`).slice(0,18000);
    const turn={question,answer,provider:provider === "gemini" ? `Gemini · ${data.llm_status || "unknown"}` : "local evidence",status:data.llm_status || "",cards:cardRows.slice(0,15),links:linkRows.slice(0,8)};
    const turns=readConversation(); turns.push(turn); saveConversation(turns);
    $("query-input").value=""; showConversation();
  } finally { button.disabled=false; button.textContent="Ask question →"; }
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
