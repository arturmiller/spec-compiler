/* Optional end-to-end browser check; Node 24 and a Chromium-family browser. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const {spawn} = require('node:child_process');

const root = path.resolve(__dirname, '../build/ontology-site');
const evidence = path.resolve(__dirname, '../.cache/documentation-browser');
fs.mkdirSync(evidence, {recursive: true});
const browserPath = process.env.DOCUMENTATION_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
if (!fs.existsSync(browserPath)) throw new Error('Set DOCUMENTATION_BROWSER to a Chromium-family browser executable.');
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const prefix = '/spec-compiler/';
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (!url.pathname.startsWith(prefix)) return response.writeHead(404).end();
  let file = path.resolve(root, decodeURIComponent(url.pathname.slice(prefix.length)) || 'index.html');
  if (!file.startsWith(root + path.sep)) return response.writeHead(403).end();
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
  if (!fs.existsSync(file)) return response.writeHead(404).end();
  const types = {'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.json':'application/json','.ttl':'text/turtle'};
  response.writeHead(200, {'Content-Type':types[path.extname(file)] || 'application/octet-stream'});
  fs.createReadStream(file).pipe(response);
});

async function main() {
  for (let attempt=0; attempt<100; attempt++) {
    const state=await (await fetch('http://127.0.0.1:8080/__preview/status')).json();
    if (!state.building) { assert.equal(state.error,''); break; }
    await wait(250);
  }
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'spec-documentation-browser-'));
  const browser = spawn(browserPath, ['--headless=new', '--disable-gpu', '--no-first-run', '--remote-debugging-port=0', '--user-data-dir='+profile, 'about:blank'], {stdio:'ignore', windowsHide:true});
  let socket;
  try {
    const portFile = path.join(profile, 'DevToolsActivePort');
    for (let i=0; i<100 && !fs.existsSync(portFile); i++) await wait(100);
    const port = fs.readFileSync(portFile, 'utf8').split('\n')[0];
    const tab = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, {method:'PUT'})).json();
    socket = new WebSocket(tab.webSocketDebuggerUrl);
    await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
    let nextId=0;
    const pending=new Map(), errors=[];
    socket.onmessage=event=>{
      const message=JSON.parse(String(event.data));
      if(message.method==='Runtime.exceptionThrown') errors.push(message.params.exceptionDetails);
      if(message.id && pending.has(message.id)){
        const {resolve,reject}=pending.get(message.id);pending.delete(message.id);
        message.error ? reject(message.error) : resolve(message.result);
      }
    };
    const command=(method,params={})=>new Promise((resolve,reject)=>{
      const id=++nextId;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));
    });
    const evaluate=async expression=>{
      const result=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
      if(result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
      return result.result.value;
    };
    const until=async expression=>{
      for(let i=0;i<100;i++){if(await evaluate(expression))return;await wait(100);}
      throw new Error('Browser condition did not become true: '+expression);
    };
    const navigate=async url=>{
      await evaluate('window.__navigationPending=true;void 0;');
      await command('Page.navigate',{url});
      await until(`!window.__navigationPending && location.pathname === ${JSON.stringify(new URL(url).pathname)} && document.readyState === 'complete' && !!document.querySelector('.site-header')`);
    };
    const screenshot=async name=>{
      const shot=await command('Page.captureScreenshot',{format:'png'});
      fs.writeFileSync(path.join(evidence,name+'.png'),Buffer.from(shot.data,'base64'));
    };
    const assertViewport = (actual, expected) => {
      assert(Math.abs(actual.zoom-expected.zoom)<1e-8);
      assert(Math.abs(actual.pan.x-expected.pan.x)<1e-8);
      assert(Math.abs(actual.pan.y-expected.pan.y)<1e-8);
      assert.deepEqual(actual.positions,expected.positions);
    };
    await command('Runtime.enable');await command('Page.enable');
    const bases=['http://127.0.0.1:8080/',`http://127.0.0.1:${server.address().port}${prefix}`];
    for(const base of bases){
      await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
      for(const route of ['', 'architecture/', 'workflows/', 'decisions/', 'development/', 'ontology/index-de.html']){
        await navigate(base+route);
        assert.equal(await evaluate("document.querySelectorAll('.site-navigation a').length"),6);
        assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow: '+route);
      }
      await navigate(base+'ontologies/');
      await until("!!document.getElementById('graph')._cyreg?.cy");
      assert.deepEqual(await evaluate("Array.from(document.querySelector('#ontology-select').options,o=>o.value)"),['contract','decision','funding','cloud','sql-api']);
      for(const dataset of ['contract','decision','funding','cloud','sql-api']){
        await evaluate(`document.getElementById('ontology-select').value=${JSON.stringify(dataset)};document.getElementById('ontology-select').dispatchEvent(new Event('change'));void 0;`);
        const links=await evaluate("['reference-de','reference-en','source-link'].map(id=>document.getElementById(id).href)");
        for(const link of links) assert.equal((await fetch(link)).status,200,link);
      }
      await evaluate("window.testCy=document.getElementById('graph')._cyreg.cy;testCy.zoom(testCy.zoom()*.9);testCy.pan({x:testCy.pan().x+13,y:testCy.pan().y-11});void 0;");
      const viewport=await evaluate("({zoom:testCy.zoom(),pan:testCy.pan(),positions:testCy.nodes().map(n=>n.position())})");
      await evaluate("void testCy.nodes()[1].emit('tap');");
      assertViewport(await evaluate("({zoom:testCy.zoom(),pan:testCy.pan(),positions:testCy.nodes().map(n=>n.position())})"),viewport);
      await evaluate("document.getElementById('zoom-in').click();void 0;");
      assert(Math.abs(await evaluate('testCy.zoom()') - viewport.zoom*1.25)<1e-8);
      await evaluate("document.getElementById('zoom-out').click();void 0;");
      assert(Math.abs(await evaluate('testCy.zoom()') - viewport.zoom)<1e-8);
      const beforeTheme=await evaluate("document.documentElement.dataset.theme");
      await evaluate("document.querySelector('[data-theme-toggle]').click();void 0;");
      assert.notEqual(await evaluate("document.documentElement.dataset.theme"),beforeTheme);
      assertViewport(await evaluate("({zoom:testCy.zoom(),pan:testCy.pan(),positions:testCy.nodes().map(n=>n.position())})"),viewport);
      const wheelPosition=await evaluate("(() => {const r=document.getElementById('graph').getBoundingClientRect();return {x:r.left+r.width/2,y:Math.min(innerHeight-10,r.top+r.height/2)};})()");
      const beforeWheel=await evaluate('testCy.zoom()');
      await command('Input.dispatchMouseEvent',{type:'mouseWheel',...wheelPosition,deltaX:0,deltaY:-120});
      await until(`Math.abs(testCy.zoom()-${beforeWheel})>1e-6`);
      await screenshot(base.includes(prefix)?'graph-prefix':'graph-root');
      await command('Page.navigate',{url:base+'graph/?ontology=funding&context=1#keep'});
      await until("location.pathname.endsWith('/ontologies/') && location.search.includes('ontology=funding') && location.hash==='#keep'");
      await command('Page.navigate',{url:base+'?ontology=cloud#keep'});
      await until("location.pathname.endsWith('/ontologies/') && location.search.includes('ontology=cloud') && location.hash==='#keep'");
      await navigate(base);
      await evaluate("document.querySelector('[data-search-open]').click();const input=document.getElementById('site-search-input');input.value='Rule Set';input.dispatchEvent(new Event('input'));void 0;");
      await until("document.querySelectorAll('#site-search-results a').length>0");
      assert(await evaluate("document.querySelector('#site-search').open"));
      await screenshot(base.includes(prefix)?'search-prefix':'search-root');
      await navigate(base+'architecture/?diagram=system-context&node=compiler#diagram-system-context');
      await until("Array.from(document.querySelectorAll('.diagram-frame')).some(f=>f.src.includes('system-context.html#focus=compiler') && f.contentDocument?.querySelector('svg'))");
      await until("Array.from(document.querySelectorAll('.diagram-frame')).some(f=>f.src.includes('system-context.html') && f.contentWindow.Archify?.focus?.active?.()==='compiler')");
      assert(await evaluate("Array.from(document.querySelectorAll('.diagram-frame')).filter(f=>f.src.includes('system-context.html'))[0].contentDocument.documentElement.dataset.theme===document.documentElement.dataset.theme"));
      await command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
      for(const route of ['', 'architecture/', 'ontologies/', 'development/']){
        await navigate(base+route);
        assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile horizontal overflow: '+route);
      }
      await screenshot(base.includes(prefix)?'mobile-prefix':'mobile-root');
    }
    assert.deepEqual(errors,[],'Browser JavaScript exceptions');
    console.log('Browser checks passed: root/prefix navigation, five graphs, stable viewport, zoom controls, theme, search, redirects, diagram focus, mobile.');
    fs.writeFileSync(path.join(evidence,'result.json'),JSON.stringify({ok:true,checks:['navigation','datasets','viewport','zoom','theme','search','redirects','diagram-focus','mobile'],screenshots:path.relative(root,evidence)},null,2));
    await command('Browser.close');
  } finally {
    socket?.close();browser.kill();server.close();
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;server.close();});
