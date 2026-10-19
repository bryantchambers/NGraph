/* Real provider checks plus deterministic browser fallback regressions. */
const puppeteer=require(process.env.NG_PUPPETEER_PATH||'puppeteer-core');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.NG_BROWSER_URL||'http://127.0.0.1:10293';
const out=process.argv[2]||'/tmp/ngraph-gemini-console';fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.NG_CHROMIUM_PATH,headless:true,timeout:120000,args:['--no-sandbox','--disable-gpu']});
 try{
  const page=await browser.newPage();page.setDefaultTimeout(85000);await page.setViewport({width:1500,height:1100});const errors=[],checks=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto(base+'/query',{waitUntil:'networkidle0'});
  async function ask(question){
   await page.evaluate(()=>{saveConversation([]);showConversation();});await page.select('#query-provider','gemini');await page.$eval('#query-input',(e,q)=>e.value=q,question);
   const pending=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/query'&&r.request().method()==='POST');await page.click('#query-submit');
   const data=await(await pending).json();await page.waitForFunction(()=>!document.getElementById('query-submit').disabled);
   const turn=await page.evaluate(()=>readConversation().at(-1));assert(turn,'Answer must be visible');assert(turn.answer.trim());return {data,turn};
  }
  let r=await ask('What evidence types were retrieved? Describe their provenance and limitations without biological interpretation.');assert.equal(r.data.llm_status,'evidence_checked');assert.equal(r.data.llm_finish_reason,'STOP');assert(!r.turn.answer.trim().startsWith('{'));assert(r.data.llm_evidence_ids.length);checks.push('general Gemini question renders complete prose, not truncated JSON');
  fs.writeFileSync(out+'/general.json',JSON.stringify(r.data,null,2));await page.screenshot({path:out+'/general.png',fullPage:true});
  r=await ask('Which functions are associated with module M3?');assert.equal(r.data.llm_status,'validated');assert.match(r.turn.answer,/M00091/);checks.push('functional Gemini question renders validated answer');
  fs.writeFileSync(out+'/functional.json',JSON.stringify(r.data,null,2));await page.screenshot({path:out+'/functional.png',fullPage:true});
  await page.setRequestInterception(true);
  const handler=req=>{if(new URL(req.url()).pathname==='/api/query')req.respond({status:200,contentType:'application/json',body:JSON.stringify({llm_status:'output_truncated',llm_answer:'',answer_lines:['Recorded local evidence'],retrieved_cards:[]})});else req.continue();};
  page.on('request',handler);
  r=await ask('Controlled truncation regression');assert.match(r.turn.answer,/Gemini reached its response limit/);assert.match(r.turn.answer,/Recorded local evidence/);checks.push('truncation displays explicit local fallback');
  await page.evaluate(()=>{Storage.prototype.setItem=function(){throw new DOMException('Storage quota exceeded','QuotaExceededError');};});
  r=await ask('Controlled storage regression');assert.match(r.turn.answer,/Recorded local evidence/);assert(await page.$('#conversation button[data-turn]'));checks.push('storage failure still renders answer in memory');
  assert.deepEqual(errors,[]);const report={status:'passed',base,checks,errors};fs.writeFileSync(out+'/console_acceptance.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
