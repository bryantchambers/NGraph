const puppeteer=require(process.env.NG_PUPPETEER_PATH||'puppeteer-core');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.NG_BROWSER_URL||'http://127.0.0.1:10291',out=process.argv[2];fs.mkdirSync(out,{recursive:true});
const question='If I was seeding a new environment similar to that found in core R1 at 150 kya, what are the top 100 taxa I would need?';
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.NG_CHROMIUM_PATH,headless:true,timeout:120000,args:['--no-sandbox','--disable-gpu']});
 try{
  const page=await browser.newPage();page.setDefaultTimeout(85000);await page.setViewport({width:1500,height:1100});const errors=[],checks=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto(base+'/query',{waitUntil:'networkidle0'});
  async function ask(q){await page.$eval('#query-input',(e,v)=>e.value=v,q);const pending=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/query'&&r.request().method()==='POST');await page.click('#query-submit');const data=await(await pending).json();await page.waitForFunction(()=>!document.getElementById('query-submit').disabled);return data;}
  const prior=await ask('Which functions are associated with module M3?');assert.equal(prior.llm_status,'validated');checks.push('actual Gemini module turn establishes conversation context');
  for(const mode of ['followup','fresh']){
   if(mode==='fresh')await page.click('#query-clear');
   const data=await ask(question);fs.writeFileSync(out+'/'+mode+'.json',JSON.stringify(data,null,2));
   assert.equal(data.query_type,'seeding');assert.equal(data.llm_status,'evidence_checked');assert.equal(data.llm_finish_reason,'STOP');assert.equal(data.core,'GeoB25202_R1');assert.equal(data.age_target,150);assert.equal(data.top_taxa.length,100);assert.equal(data.table_evidence.rows.length,100);assert(data.llm_evidence_ids.some(id=>id.startsWith('sample-ranking:')));assert.deepEqual(data.context.entities.modules,[]);
   const turn=await page.evaluate(()=>readConversation().at(-1));assert.equal(turn.answer,data.llm_answer);assert.match(turn.provider,/Gemini/);assert(!turn.answer.includes('Choose an unambiguous recorded entity'));
   assert.equal(await page.$$eval('#query-evidence table tbody tr',r=>r.length),100);await page.screenshot({path:out+'/'+mode+'.png',fullPage:true});checks.push(mode+' exact user question displays cited Gemini prose and 100 ranked evidence rows');
  }
  assert.deepEqual(errors,[]);const report={status:'passed',base,checks,errors};fs.writeFileSync(out+'/acceptance.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
