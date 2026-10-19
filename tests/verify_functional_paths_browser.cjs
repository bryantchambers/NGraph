/* Real Chromium acceptance for combined paths, witnesses and KG-backed Query. */
const puppeteer=require(process.env.NG_PUPPETEER_PATH || 'puppeteer-core');
const assert=require('node:assert/strict');const fs=require('node:fs');
const base=process.env.NG_BROWSER_URL || 'http://127.0.0.1:10291';
const output=process.argv[2] || '/tmp/ngraph-functional-paths';fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.NG_CHROMIUM_PATH,headless:true,timeout:120000,args:['--no-sandbox','--disable-gpu']});
 const page=await browser.newPage();await page.setViewport({width:1600,height:1100});page.setDefaultTimeout(60000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)errors.push(r.status()+' '+r.url());});
 const checks=[];
 try{
  await page.goto(base+'/knowledge-graph?view=metapaths',{waitUntil:'networkidle0'});await page.waitForSelector('#path-demo-function');
  await page.click('#path-demo-function');await page.waitForSelector('#path-list button[data-index]');
  let result=await page.evaluate(()=>state.pathResult);assert.equal(result.path_count,1);assert.equal(result.paths[0].carrier_status,'supported_in_catalog');assert.equal(result.paths[0].nodes.length,4);
  assert.match(await page.$eval('#path-detail',el=>el.innerText),/Permutation Z/);assert.match(await page.$eval('#path-detail',el=>el.innerText),/Same-taxon supporting witness/);
  assert(await page.$('#path-canvas canvas'));assert(result.kg_snapshot_id.startsWith('functional-'));assert(result.source_hashes['module_functions.tsv']);checks.push('combined path, interactive graph, Z and witness');
  await page.click('#path-collapse');assert.equal(await page.evaluate(()=>state.kgCy.nodes().length),3);assert.equal(await page.evaluate(()=>state.pathResult.path_count),1);checks.push('compact view preserves evidence counts');await page.click('#path-collapse');
  await page.screenshot({path:output+'/combined-path.png',fullPage:true});
  await page.$eval('#path-source',el=>el.value='taxon:S__3300000322_5');await page.click('#path-run');
  await page.waitForFunction(()=>state.pathResult.source==='taxon:S__3300000322_5');result=await page.evaluate(()=>state.pathResult);
  assert.equal(result.path_count,1);assert.equal(result.paths[0].carrier_status,'no_complete_support_recorded');assert.equal(result.paths[0].witnesses.length,0);
  checks.push('member-only path does not inherit carrier support');
  await page.select('#path-carriers','true');await page.click('#path-run');await page.waitForFunction(()=>state.pathResult.carriers_only===true);
  assert.equal(await page.evaluate(()=>state.pathResult.path_count),0);checks.push('carrier-only filter');
  await page.select('#path-pattern','function_module_taxon');await page.$eval('#path-source',el=>el.value='kegg.module:M00091');await page.$eval('#path-target',el=>el.value='');await page.select('#path-carriers','false');await page.click('#path-run');
  await page.waitForFunction(()=>state.pathResult.metapath==='function_module_taxon');assert.equal(await page.evaluate(()=>state.pathResult.path_count),206);checks.push('canonical function ID and reverse search');
  await page.$eval('#path-snapshot',el=>el.value='another_snapshot');await page.click('#path-run');await page.waitForFunction(()=>state.pathResult.status==='missing' || state.pathResult.path_count===0);checks.push('snapshot isolation');
  await page.screenshot({path:output+'/scope.png',fullPage:true});
  await page.goto(base+'/query',{waitUntil:'networkidle0'});await page.click('#query-clear');await page.type('#query-input','Which functions are associated with S__3300000322_5 and M00091?');await page.click('#query-submit');
  await page.waitForSelector('#query-evidence .evidence-card');assert.match(await page.$eval('#conversation',el=>el.innerText),/no_complete_support_recorded/);assert.match(await page.$eval('#query-evidence',el=>el.innerText),/proof:functional/);
  assert.match(await page.$eval('#conversation',el=>el.innerText),/not measured activity/);checks.push('KG-backed Query with conservative proof citations');await page.screenshot({path:output+'/query.png',fullPage:true});
  await Promise.all([page.waitForNavigation({waitUntil:'networkidle0'}),page.click('#query-evidence a[href*="view=metapaths"]')]);await page.waitForFunction(()=>state.pathResult?.source==='taxon:S__3300000322_5');
  assert.equal(await page.$eval('#path-snapshot',el=>el.value),'catalog_unweighted_20261008');checks.push('Query proof deep link preserves scope');
  await page.goto(base+'/modules?view=functions',{waitUntil:'networkidle0'});await page.waitForSelector('#functional-results button[data-function-index]');await page.click('#functional-results button[data-function-index="0"]');
  await page.waitForSelector('#functional-detail a[href*="view=browser"]');checks.push('function-result association deep link');
  await Promise.all([page.waitForNavigation({waitUntil:'networkidle0'}),page.click('#functional-detail a[href*="view=metapaths"]')]);await page.waitForFunction(()=>state.pathResult?.metapath==='module_function');
  assert.equal(await page.$eval('#path-kind',el=>el.value),'vgae');assert.equal(await page.$eval('#path-snapshot',el=>el.value),'catalog_unweighted_20261008');checks.push('functional result opens scoped module path');
  const feature=await page.evaluate(()=>state.pathResult.paths[0].nodes.at(-1));
  await page.goto(base+'/knowledge-graph?view=browser&id='+encodeURIComponent(feature),{waitUntil:'networkidle0'});await page.waitForFunction(()=>document.getElementById('kg-node-badge').textContent==='FunctionalFeature');
  await Promise.all([page.waitForNavigation({waitUntil:'networkidle0'}),page.click('#kg-to-path')]);await page.waitForFunction(()=>state.pathResult?.metapath==='function_module_taxon');checks.push('function graph selection starts reverse metapath');
  assert.deepEqual(errors,[]);const report={status:'passed',checks,errors,base};fs.writeFileSync(output+'/functional_paths_browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
