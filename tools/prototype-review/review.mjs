/** Optional, offline browser evidence for static prototype files.
 * No provider keys, project environment, hosting credentials or remote API.
 * PASS means these checks passed, not that a product is accepted or beautiful.
 */
import {createServer} from 'node:http';
import {readFile, realpath, mkdir, writeFile} from 'node:fs/promises';
import {resolve, relative, extname, sep, join, isAbsolute} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';

const TYPES={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'application/javascript; charset=utf-8'};
export function inside(root, path) { const part=relative(root,path); return part!=='' && part!=='..' && !part.startsWith(`..${sep}`) && !isAbsolute(part); }
export function readField(object, path) {return path.split('.').reduce((value,key)=>value?.[key],object);}

function locator(page,step) {
  if(step.role) return page.getByRole(step.role,{name:step.name,exact:step.exact??false});
  if(step.label) return page.getByLabel(step.label,{exact:step.exact??false});
  throw new Error('Each action requires a role/name or label; arbitrary scripts are not supported.');
}
export async function perform(page,steps) {
  for(const step of steps) {
    if(step.action==='reload') {await page.reload({waitUntil:'networkidle'});continue;}
    if(step.action==='downloadJson') {
      const pending=page.waitForEvent('download'); await locator(page,step).click();
      const download=await pending; const path=await download.path();
      const object=JSON.parse(await readFile(path,'utf8'));
      for(const [field,expected] of Object.entries(step.expected||{})) assert.deepEqual(readField(object,field),expected,`download ${field}`);
      continue;
    }
    const target=locator(page,step);
    switch(step.action) {
      case 'click': await target.click();break;
      case 'fill': await target.fill(step.value);break;
      case 'check': await target.check();break;
      case 'press': await target.press(step.key);break;
      case 'expectText': assert.ok((await target.innerText()).includes(step.text),step.text);break;
      case 'expectVisible': await target.waitFor({state:'visible'});break;
      case 'expectHidden': await target.waitFor({state:'hidden'});break;
      case 'expectCount': assert.equal(await target.count(),step.count);break;
      default: throw new Error(`Unsupported action ${step.action}`);
    }
  }
}

export async function review(directory, output, scenarios=[]) {
  const root=await realpath(directory); await mkdir(output,{recursive:true});
  const report={status:'FAIL',scope:'Browser baseline and supplied scenarios only; manual visual and acceptance review required.',viewports:[],scenarios:[],errors:[],blockedRequests:[],files:{}};
  const snapshots=new Map();
  for(const name of ['index.html','styles.css','app.js']) {
    const canonical=await realpath(join(root,name));assert.ok(inside(root,canonical),'artifact symlink escapes directory');
    const bytes=await readFile(canonical);assert.ok(bytes.length<=2_000_000,'artifact file exceeds review limit');
    snapshots.set(`/${name}`,bytes);
    report.files[name]=createHash('sha256').update(bytes).digest('hex');
  }
  const server=createServer(async(req,res)=>{
    try {
      const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
      if(pathname==='/favicon.ico') {res.writeHead(204);res.end();return;}
      const path=pathname==='/'?'/index.html':pathname;
      const bytes=snapshots.get(path);assert.ok(bytes);
      // Serve only immutable captured browser files, never a dossier, report,
      // local secret or a file edited while this review is running.
      res.writeHead(200,{'content-type':TYPES[extname(path)],'cache-control':'no-store','x-content-type-options':'nosniff'});res.end(bytes);
    } catch {res.writeHead(404);res.end('Not found');}
  });
  await new Promise(done=>server.listen(0,'127.0.0.1',done));
  const origin=`http://127.0.0.1:${server.address().port}`;
  let browser;
  try {
    browser=await chromium.launch({headless:true,...(process.env.BROWSER_CHANNEL?{channel:process.env.BROWSER_CHANNEL}:{})});
    async function contextFor(width) {
      const context=await browser.newContext({viewport:{width,height:1000},reducedMotion:'reduce',serviceWorkers:'block',acceptDownloads:true});
      await context.route('**/*',async route=>{
        const url=new URL(route.request().url());
        if(url.origin===origin) await route.continue();
        else {report.blockedRequests.push(url.origin);await route.abort('blockedbyclient');}
      });
      context.on('page',page=>{page.on('pageerror',error=>report.errors.push(error.message));page.on('console',message=>{if(message.type()==='error')report.errors.push(message.text());});});
      return context;
    }
    for(const width of [1440,768,390]) {
      const context=await contextFor(width); const page=await context.newPage();
      const response=await page.goto(origin,{waitUntil:'networkidle'});assert.equal(response.status(),200);
      assert.equal(await page.getByRole('heading',{level:1}).count(),1,'one h1');
      assert.equal(await page.getByRole('main').count(),1,'one main');
      const layout=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
      assert.ok(layout.scrollWidth<=width+1,`Horizontal overflow at ${width}px`);
      await page.screenshot({path:join(output,`viewport-${width}.png`)});
      await page.screenshot({path:join(output,`prototype-${width}.png`),fullPage:true});
      await page.keyboard.press('Tab');
      const focus=await page.evaluate(()=>({tag:document.activeElement?.tagName,outline:getComputedStyle(document.activeElement).outlineStyle}));
      assert.notEqual(focus.tag,'BODY','keyboard can reach a control');
      await page.screenshot({path:join(output,`focus-${width}.png`)});
      report.viewports.push({width,layout,firstFocus:focus});await context.close();
    }
    for(const scenario of scenarios) {
      const context=await contextFor(scenario.width||390);const page=await context.newPage();
      await page.goto(origin,{waitUntil:'networkidle'});
      await perform(page,scenario.steps);
      await page.screenshot({path:join(output,`scenario-${report.scenarios.length+1}.png`),fullPage:true});
      report.scenarios.push({name:scenario.name,status:'PASS',steps:scenario.steps.length});await context.close();
    }
    assert.deepEqual(report.errors,[],'browser errors');assert.deepEqual(report.blockedRequests,[],'prototype must not depend on external services');
    report.status='PASS';
  } catch(error) {report.failure=String(error);}
  finally {if(browser)await browser.close();await new Promise(done=>server.close(done));await writeFile(join(output,'browser-review.json'),JSON.stringify(report,null,2));}
  return report;
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===resolve(process.argv[1])) {
  const [, , directory, output, scenarioFile]=process.argv;
  if(!directory||!output) throw new Error('Usage: node review.mjs ARTIFACT_DIRECTORY OUTPUT_DIRECTORY [SCENARIOS_JSON]');
  const scenarios=scenarioFile?JSON.parse(await readFile(scenarioFile,'utf8')):[];
  const result=await review(resolve(directory),resolve(output),scenarios);console.log(JSON.stringify(result,null,2));if(result.status!=='PASS')process.exitCode=1;
}
