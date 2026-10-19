/* Functional RAG acceptance against an existing preview or production service. */
const puppeteer=require(process.env.NG_PUPPETEER_PATH||'puppeteer-core');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.NG_BROWSER_URL||'http://127.0.0.1:10292',out=process.argv[2]||'/tmp/ngraph-functional-rag';fs.mkdirSync(out,{recursive:true});
(async()=>{
 const b=await puppeteer.launch({executablePath:process.env.NG_CHROMIUM_PATH,headless:true,timeout:120000,args:['--no-sandbox','--disable-gpu']});
 const p=await b.newPage();await p.setViewport({width:1600,height:1100});p.setDefaultTimeout(60000);const errors=[],checks=[];p.on('pageerror',e=>errors.push(e.message));p.on('response',r=>{if(r.status()>=400) errors.push(r.status()+' '+r.url());});
 async function query(q){await p.$eval('#query-input',(e,q)=>e.value=q,q);await p.click('#query-submit');await p.waitForFunction(q=>readConversation().at(-1)?.question===q,{},q);return p.evaluate(()=>readConversation().at(-1));}
 try{
  await p.goto(base+'/query',{waitUntil:'networkidle0'});await p.click('#query-clear');
  let r=await query('Which modules support phosphatidylcholine biosynthesis?');assert.deepEqual(r.context.entities.functions,['M00091']);assert.match(r.answer,/q=/);assert(await p.$('#query-evidence a[href*="view=browser"]'));checks.push('recorded name, statistics and cited association link');
  r=await query('Which taxa support that?');assert.equal(r.graph.path_count,110);assert.equal(r.context.intent,'carriers');checks.push('function-to-carriers follow-up');
  r=await query('Show that along depth in ST8');assert.equal(r.table.total_count,115);assert.equal(r.table.profile_scope,'sample_wide_function');assert(await p.$('#query-evidence a[href*="/api/data/file"]'));checks.push('profile follow-up with bounded source evidence');await p.screenshot({path:out+'/profile-query.png',fullPage:true});
  await Promise.all([p.waitForNavigation({waitUntil:'networkidle0'}),p.click('#query-evidence a[href*="/modules?"]')]);await p.waitForFunction(()=>document.getElementById('profile-function')?.value==='M00091'&&document.querySelector('.profile-grid svg'));
  assert.equal(await p.$eval('#profile-core',e=>e.value),'ST8');assert.equal(await p.$eval('#functional-module',e=>e.value),'');checks.push('profile citation opens matching function and core plot');await p.screenshot({path:out+'/profile-plot.png',fullPage:true});
  await p.goto(base+'/query',{waitUntil:'networkidle0'});await p.click('#query-clear');r=await query('Which functions are associated with module M3?');assert.deepEqual(r.context.entities.functions,[]);assert.match(r.answer,/M00091/);checks.push('community label does not resolve a KEGG core M3 definition');
  r=await query('Compare enrichment in M3 and M4');assert.match(r.answer,/M00121/);assert.match(r.answer,/M00091/);checks.push('module comparison');
  r=await query('Which central taxa support M00091 in ST8?');assert.equal(r.table.total_count,29);assert.match(r.answer,/does not establish causal/);checks.push('centrality restricted to qualified supporting carriers');await p.screenshot({path:out+'/centrality-query.png',fullPage:true});
  await p.evaluate(()=>{const turns=readConversation();turns.at(-1).context.scope.kg_snapshot_id='other';saveConversation(turns);});r=await query('Which taxa support that?');assert.equal(r.status,'context_reset');checks.push('stale snapshot context reset');
  await p.evaluate(()=>window.scrollTo(0,0));await p.waitForNetworkIdle();await p.click('#query-clear');await p.waitForFunction(()=>readConversation().length===0);checks.push('clear resets execution context');
  const separate=await b.newPage();await separate.goto(base+'/query',{waitUntil:'networkidle0'});assert.equal(await separate.evaluate(()=>readConversation().length),0);await separate.close();checks.push('separate tab isolation');
  assert.deepEqual(errors,[]);const report={status:'passed',base,checks,errors};fs.writeFileSync(out+'/functional_rag_browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await b.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
