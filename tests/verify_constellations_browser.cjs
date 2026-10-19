/* Real Chromium interactions against an existing Constellations service.
 * Set NG_PUPPETEER_PATH and NG_CHROMIUM_PATH to installed runtimes; no install.
 */
const puppeteer = require(process.env.NG_PUPPETEER_PATH || 'puppeteer-core');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const base = process.env.NG_BROWSER_URL || 'http://127.0.0.1:10291';
const output = process.argv[2] || '/tmp/constellations-browser-acceptance';
fs.mkdirSync(output, {recursive:true});

(async () => {
  const browser = await puppeteer.launch({executablePath:process.env.NG_CHROMIUM_PATH,
    headless:true, args:['--no-sandbox','--disable-gpu']});
  const page = await browser.newPage();
  await page.setViewport({width:1600,height:1000});
  page.setDefaultTimeout(25000);
  const errors = [], checks = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', r => {if(r.status() >= 400) errors.push(`${r.status()} ${r.url()}`);});
  async function go(route, selector) {
    await page.goto(base+route,{waitUntil:'networkidle0'});
    await page.waitForSelector(selector);
  }
  async function check(name, work) {
    try { const evidence = await work(); checks.push({name,status:'passed',evidence}); }
    catch(e) { checks.push({name,status:'failed',error:e.message}); }
  }
  async function graphClick(key, canvas, detail) {
    await (await page.$(canvas)).scrollIntoView();
    await page.waitForNetworkIdle();
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    const node = await page.evaluate(key => {
      const cy=state[key], n=cy.nodes().filter(n=>n.id()!==state.selectedNode)[0] || cy.nodes()[0];
      return {id:n.id(),position:n.renderedPosition()};
    },key);
    const box=await (await page.$(canvas)).boundingBox();
    await page.mouse.click(box.x+node.position.x,box.y+node.position.y);
    await page.waitForFunction((selector,id)=>document.querySelector(selector).innerText.includes(id),{},detail,node.id);
    return node.id;
  }
  await check('overview navigation and refresh',async()=>{
    await go('/','#refresh-overview');
    await page.click('#refresh-overview');
    await page.waitForFunction(()=>state.overview.counts.samples===214);
    await page.screenshot({path:path.join(output,'overview.png'),fullPage:true});
    return await page.evaluate(()=>({branch:state.overview.branch,counts:state.overview.counts}));
  });
  await check('graph search, node click, zoom and bounded neighborhood',async()=>{
    await go('/knowledge-graph?view=browser','#kg-canvas canvas');
    await page.type('#kg-search','ST13'); await page.click('#kg-search-button');
    await page.waitForSelector('#kg-search-results button[data-id="site:ST13"]');
    await page.click('#kg-search-results button[data-id="site:ST13"]');
    await page.waitForFunction(()=>state.kgCy?.getElementById('site:ST13').length && state.selectedNode==='site:ST13');
    const id=await graphClick('kgCy','#kg-canvas','#kg-node-detail');
    const box=await (await page.$('#kg-canvas')).boundingBox();
    const old=await page.evaluate(()=>state.kgCy.zoom());
    await page.mouse.move(box.x+box.width/2,box.y+box.height/2); await page.mouse.wheel({deltaY:-180});
    await page.waitForFunction(z=>state.kgCy.zoom()!==z,{},old);
    await page.select('#kg-limit','40'); await page.click('#kg-load');
    await page.waitForFunction(()=>state.kgCy.nodes().length<=40);
    await page.click('#kg-fit');
    await page.screenshot({path:path.join(output,'graph.png'),fullPage:true});
    return {clicked:id,nodes:await page.evaluate(()=>state.kgCy.nodes().length)};
  });
  for (const [name,button] of [['taxon to SST','#path-demo-tax'],['cores through module','#path-demo-core']]) {
    await check(`metapath ${name}`,async()=>{
      await go('/knowledge-graph?view=metapaths','#path-run');
      await page.click(button); await page.waitForSelector('#path-list button[data-index="0"]');
      const count=await page.evaluate(()=>state.pathResult.path_count);
      assert(count>0);
      await page.click('#path-list button[data-index="1"]');
      await page.waitForFunction(()=>document.querySelector('#path-list button[data-index="1"]').classList.contains('active'));
      await page.click('#path-fit');
      await page.screenshot({path:path.join(output,button.includes('tax')?'taxon-sst.png':'core-module.png'),fullPage:true});
      return await page.evaluate(()=>({paths:state.pathResult.path_count,status:state.pathResult.count_status,detail:document.querySelector('#path-detail').innerText}));
    });
  }
  await check('flagged proxy exposes units, bracket width and provenance',async()=>{
    const id='measurement:sst_proxy:LV3003047127:sst_mgca_jonkers_2013';
    await go('/knowledge-graph?view=browser&id='+encodeURIComponent(id),'#kg-node-detail .insight');
    const detail=await page.$eval('#kg-node-detail',el=>el.innerText);
    assert.match(detail,/Large interpolation gap/);assert.match(detail,/inferred_temperature/);
    assert.match(detail,/Interpolation bracket/);assert.match(detail,/Source records/);
    await page.screenshot({path:path.join(output,'flagged-proxy.png'),fullPage:true});
    return detail;
  });
  await check('supergraph node click',async()=>{
    await go('/modules','#super-canvas canvas');
    return await graphClick('moduleCy','#super-canvas','#super-detail');
  });
  await check('module selection and member pagination',async()=>{
    await go('/modules?view=modules','#module-select');
    await page.waitForFunction(()=>document.querySelector('#module-select').options.length>=6);
    await page.select('#module-select','M5');
    await page.waitForNetworkIdle();
    await page.waitForFunction(()=>state.moduleData?.module_id==='M5' && state.moduleData.members?.length>20);
    const memberCount=await page.evaluate(()=>state.moduleData.members.length);
    assert.match(await page.$eval('#module-page-label',el=>el.innerText),new RegExp(String(memberCount)));
    const first=await page.$eval('#module-members',el=>el.innerText);
    await page.click('#module-next');
    await page.waitForFunction(()=>document.querySelector('#module-page-label').innerText.includes('Page 2'));
    assert.notEqual(first,await page.$eval('#module-members',el=>el.innerText));
    await page.waitForNetworkIdle();
    assert.match(await page.$eval('#module-page-label',el=>el.innerText),/Page 2/);
    await page.screenshot({path:path.join(output,'modules.png'),fullPage:true});
    return await page.$eval('#module-page-label',el=>el.innerText);
  });
  await check('embedding and visible figure loading',async()=>{
    await go('/modules?view=embeddings','#embedding-svg svg');
    await page.waitForFunction(()=>[...document.querySelectorAll('#module-figures img')].some(i=>i.complete&&i.naturalWidth>0));
    return await page.$eval('#embedding-caption',el=>el.innerText);
  });
  await check('local query and selected-answer evidence',async()=>{
    await go('/query','#query-input');
    await page.click('#query-clear');
    await page.type('#query-input','Which taxa are associated with ST8?');
    await page.click('#query-submit');
    await page.waitForSelector('#conversation button[data-turn="0"]');
    await page.click('#conversation button[data-turn="0"]');
    await page.waitForSelector('#query-evidence .evidence-card');
    await page.screenshot({path:path.join(output,'query.png'),fullPage:true});
    return {cards:await page.$$eval('#query-evidence .evidence-card',els=>els.length)};
  });
  if(process.env.NG_CHECK_GEMINI === '1') await check('Gemini synthesis receives cards and cites supplied IDs',async()=>{
    await go('/query','#query-input');await page.click('#query-clear');
    await page.select('#query-provider','gemini');
    await page.type('#query-input','Which taxa are associated with ST8, and how strong is the evidence?');
    const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/query'&&r.status()===200,{timeout:65000});
    await page.click('#query-submit');
    const result=await (await response).json();
    assert.equal(result.llm_status,'evidence_checked');assert(result.retrieved_cards.length>0);
    const supplied=new Set(result.retrieved_cards.slice(0,12).map(c=>c.card_id));
    assert(result.llm_evidence_ids.length>0);
    assert(result.llm_evidence_ids.every(id=>supplied.has(id)));
    await page.waitForSelector('#query-evidence .evidence-card');
    await page.screenshot({path:path.join(output,'gemini.png'),fullPage:true});
    return {model:result.llm_model,evidence_ids:result.llm_evidence_ids,answer:result.llm_answer,
      uncertainty:result.llm_uncertainty,observations:result.llm_observations,predictions:result.llm_predictions,
      provided_cards:result.retrieved_cards.length};
  });
  await check('report preview and download endpoint',async()=>{
    await go('/data','#data-category');
    await page.select('#data-category','Reports');
    await page.waitForSelector('#data-file-list button[data-preview]');
    await page.click('#data-file-list button[data-preview]');
    await page.waitForFunction(()=>document.querySelector('#data-preview').innerText.length>100);
    const download=await page.evaluate(async()=>{
      const catalog=await api('/api/data/catalog');
      const f=catalog.files.find(f=>f.category==='Source data');
      const r=await fetch('/api/data/file?id='+encodeURIComponent(f.id));
      return {status:r.status,bytes:(await r.arrayBuffer()).byteLength,name:f.name};
    });
    assert.equal(download.status,200);assert(download.bytes>0);
    return download;
  });
  await check('evidence-card search',async()=>{
    await go('/data?view=evidence','#card-search');
    await page.type('#card-search','ST8');await page.click('#card-load');
    await page.waitForSelector('#card-list article');
    return await page.$$eval('#card-list article',els=>els.length);
  });
  await check('mobile navigation and page width',async()=>{
    await page.setViewport({width:390,height:844});
    await go('/','#mobile-nav-toggle'); await page.click('#mobile-nav-toggle');
    assert.equal(await page.$eval('#mobile-nav-toggle',el=>el.getAttribute('aria-expanded')),'true');
    const width=await page.evaluate(()=>({viewport:innerWidth,content:document.documentElement.scrollWidth}));
    assert(width.content<=width.viewport+1);
    await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
    return width;
  });
  await browser.close();
  const report={base,checked_at:new Date().toISOString(),checks,errors,
    status:checks.every(c=>c.status==='passed') && !errors.length ? 'passed':'failed'};
  fs.writeFileSync(path.join(output,'browser_acceptance.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
  if(report.status!=='passed')process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
