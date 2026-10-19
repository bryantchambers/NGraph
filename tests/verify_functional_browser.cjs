/* Exercise frozen enrichment, provenance, pagination and separate core profiles. */
const puppeteer=require(process.env.NG_PUPPETEER_PATH || 'puppeteer-core');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.NG_BROWSER_URL || 'http://127.0.0.1:10291';
const output=process.argv[2] || '/tmp/ngraph-functional-browser';
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.NG_CHROMIUM_PATH,headless:true,timeout:120000,args:['--no-sandbox','--disable-gpu']});
 const page=await browser.newPage();await page.setViewport({width:1600,height:1000});page.setDefaultTimeout(30000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try {
  await page.goto(base+'/modules?view=functions',{waitUntil:'networkidle0'});
  await page.waitForSelector('#functional-results button[data-function-index]');
  assert.match(await page.$eval('#functional-results',el=>el.innerText),/\bZ\b/);
  assert.match(await page.$eval('#functional-status',el=>el.innerText),/catalog_unweighted_20261008/);
  await page.click('#functional-next');await page.waitForNetworkIdle();
  assert.match(await page.$eval('#functional-page',el=>el.innerText),/41/);
  await page.select('#functional-qualified','true');await page.waitForNetworkIdle();
  assert.equal(await page.$$eval('#functional-results button[data-function-index]',els=>els.length),4);
  await page.click('#functional-results button[data-function-index="0"]');await page.waitForSelector('#functional-contributors button[data-carrier-index]');
  assert.match(await page.$eval('#functional-detail',el=>el.innerText),/Permutation Z/);
  await page.click('#functional-contributors button[data-carrier-index="0"]');await page.click('#inventory-open');await page.waitForSelector('#taxon-inventory table');
  assert.match(await page.$eval('#taxon-inventory',el=>el.innerText),/K\d{5}/);
  await page.screenshot({path:output+'/enrichment.png',fullPage:true});
  await page.goto(base+'/modules?view=profiles',{waitUntil:'networkidle0'});await page.waitForSelector('.profile-grid svg');
  assert.match(await page.$eval('#functional-content',el=>el.innerText),/not absolute abundance/);
  await page.select('#profile-axis','age');await page.waitForNetworkIdle();
  assert.match(await page.$eval('#functional-content',el=>el.innerText),/kyr BP/);
  await page.screenshot({path:output+'/profiles.png',fullPage:true});
  assert.deepEqual(errors,[]);
  const result={status:'passed',checks:['Z display','snapshot','pagination','four qualified results','carrier provenance','indexed KO inventory','separate depth/age profiles'],errors};
  fs.writeFileSync(output+'/functional_browser_result.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
