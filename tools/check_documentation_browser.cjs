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
  let previewReady=false;
  for (let attempt=0; attempt<2400; attempt++) {
    const state=await (await fetch('http://127.0.0.1:8080/__preview/status')).json();
    if (!state.building) { assert.equal(state.error,''); previewReady=true; break; }
    await wait(250);
  }
  assert(previewReady,'Local preview did not finish its build');
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
      const destination=new URL(url);
      const sameDocument=await evaluate('location.origin+location.pathname+location.search')===destination.origin+destination.pathname+destination.search;
      await evaluate(sameDocument?'delete window.__navigationPending;void 0;':'window.__navigationPending=true;void 0;');
      await command('Page.navigate',{url});
      const standalone=destination.pathname.includes('/diagrams/');
      await until(`!window.__navigationPending && location.pathname === ${JSON.stringify(destination.pathname)} && document.readyState === 'complete' && ${standalone?'!!window.Archify':"!!document.querySelector('.site-header')"}`);
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
    fs.mkdirSync(path.join(evidence,'exports'),{recursive:true});
    await command('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:path.join(evidence,'exports')});
    const bases=['http://127.0.0.1:8080/',`http://127.0.0.1:${server.address().port}${prefix}`];
    for(const base of bases){
      await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
      for(const route of ['', 'compiler/', 'tutorials/', 'reference/', 'reference/architecture/', 'reference/decisions/', 'contributors/', 'ontology/index-de.html', 'ontologies/']){
        await navigate(base+route);
        assert.equal(await evaluate("document.querySelectorAll('.site-navigation a').length"),6);
        assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow: '+route);
      }
      for(const [reference,dataset] of [['ontology/','contract'],['ontology/sql/','sql'],['ontology/decision-protocol/','decision-protocol'],['ontology/compiler/','compiler'],['ontology/decision/','decision'],['ontology/funding/','funding'],['ontology/cloud/','cloud'],['examples/sql-api/','sql-api']]){
        for(const language of ['de','en']){
          await navigate(base+reference+'index-'+language+'.html');
          assert.equal(await evaluate('document.documentElement.lang'),language);
          assert.equal(await evaluate('document.querySelectorAll("#content").length'),1);
          assert(await evaluate('!!document.querySelector(".rdf-term")'));
          assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
          for(const link of await evaluate('Array.from(document.querySelectorAll(".reference-downloads a"),a=>a.href)')) assert.equal((await fetch(link)).status,200,link);
        }
        await command('Page.navigate',{url:base+reference+'webvowl/?context=1#keep'});
        const graphRoute=dataset==='sql-api'?'/tutorials/sql-api/graph/':'/ontologies/';
        await until(`location.pathname.endsWith(${JSON.stringify(graphRoute)}) && new URLSearchParams(location.search).get('ontology')===${JSON.stringify(dataset)} && location.hash==='#keep'`);
      }
      await navigate(base+'ontology/index-de.html');
      await evaluate('window.scrollTo({top:0,behavior:"instant"});void 0;');
      await screenshot(base.includes(prefix)?'reference-overview-prefix':'reference-overview-root');
      await navigate(base+'ontology/index-de.html#GetEndpoint');
      assert(await evaluate('!!document.getElementById("GetEndpoint")'));
      await until('document.getElementById("GetEndpoint").getBoundingClientRect().top < innerHeight*.7');
      await screenshot(base.includes(prefix)?'reference-prefix':'reference-root');
      await evaluate("document.querySelector('[data-theme-toggle]').click();void 0;");
      await screenshot(base.includes(prefix)?'reference-theme-prefix':'reference-theme-root');
      await navigate(base+'ontologies/');
      await until("!!document.getElementById('graph')?._cyreg?.cy");
      assert.deepEqual(await evaluate("Array.from(document.querySelector('#ontology-select').options,o=>o.value)"),['dependencies','contract','sql','decision-protocol','compiler','decision','funding','cloud']);
      assert.equal(await evaluate("document.getElementById('ontology-select').value"),'dependencies');
      assert(await evaluate("document.getElementById('external-toggle-label').hidden"));
      assert(!await evaluate("!!document.getElementById('property-catalog')"));
      const migratedTerm='https://arturmiller.github.io/spec-compiler/ontology/#TransformationContract';
      assert(!await evaluate(`JSON.parse(document.getElementById('ontology-data').textContent).find(d=>d.key==='contract').nodes.some(n=>n.id===${JSON.stringify(migratedTerm)})`));
      for(const dataset of ['contract','sql','decision-protocol','compiler','decision','funding','cloud']){
        await evaluate(`document.getElementById('ontology-select').value=${JSON.stringify(dataset)};document.getElementById('ontology-select').dispatchEvent(new Event('change'));void 0;`);
        const links=await evaluate("['reference-de','reference-en','source-link'].map(id=>document.getElementById(id).href)");
        for(const link of links) assert.equal((await fetch(link)).status,200,link);
        assert.equal(await evaluate("document.getElementById('graph')._cyreg.cy.nodes().filter(n=>n.connectedEdges().length===0).length"),0,'Isolated term in '+dataset);
        const graphData=await evaluate(`JSON.parse(document.getElementById('ontology-data').textContent).find(d=>d.key===${JSON.stringify(dataset)})`);
        assert(graphData.nodes.some(n=>n.external),'Missing direct vocabulary context in '+dataset);
        assert(await evaluate("document.getElementById('show-external').checked && !document.getElementById('external-toggle-label').hidden"));
        await evaluate("window.scopeCy=document.getElementById('graph')._cyreg.cy;scopeCy.zoom(scopeCy.zoom()*.9);scopeCy.pan({x:scopeCy.pan().x+9,y:scopeCy.pan().y-7});scopeCy.nodes('[external=\"1\"]')[0].emit('tap');void 0;");
        const scopeViewport=await evaluate("({zoom:scopeCy.zoom(),pan:scopeCy.pan(),positions:scopeCy.nodes().map(n=>n.position())})");
        await evaluate("document.getElementById('show-external').click();void 0;");
        assert.equal(await evaluate("scopeCy.nodes('[external=\"1\"]:visible').length"),0);
        const localCount=graphData.nodes.filter(n=>!n.external).length;
        assert.equal(await evaluate("scopeCy.nodes(':visible').length"),localCount);
        assert.equal(await evaluate("scopeCy.edges(':visible').filter(e=>e.source().data('external')==='1'||e.target().data('external')==='1').length"),0);
        assert.equal(await evaluate("scopeCy.nodes(':selected')[0].data('external')"),'0');
        assert(!await evaluate("document.querySelector('#graph-side .eyebrow').textContent.includes('Externer Begriff')"));
        assert(await evaluate("Array.from(document.querySelectorAll('#graph-side [data-select]')).every(b=>scopeCy.getElementById(b.dataset.select).data('external')==='0')"));
        assert.equal(await evaluate("new URLSearchParams(location.search).get('external')"),'0');
        assert((await evaluate("document.getElementById('counts').textContent")).startsWith(localCount+'/'+graphData.nodes.length+' Knoten'));
        assertViewport(await evaluate("({zoom:scopeCy.zoom(),pan:scopeCy.pan(),positions:scopeCy.nodes().map(n=>n.position())})"),scopeViewport);
        await evaluate("document.querySelector('[data-edge-kind=\"type\"]').click();document.getElementById('search').value='test';document.getElementById('search').dispatchEvent(new Event('input'));void 0;");
        assert.equal(await evaluate("scopeCy.nodes('[external=\"1\"]:visible').length"),0);
        assertViewport(await evaluate("({zoom:scopeCy.zoom(),pan:scopeCy.pan(),positions:scopeCy.nodes().map(n=>n.position())})"),scopeViewport);
        await evaluate("document.querySelector('[data-edge-kind=\"all\"]').click();document.getElementById('search').value='';document.getElementById('search').dispatchEvent(new Event('input'));void 0;");
        if(dataset==='funding')await screenshot(base.includes(prefix)?'funding-local-only-prefix':'funding-local-only-root');
        await evaluate("document.getElementById('show-external').click();void 0;");
        assert.equal(await evaluate("scopeCy.nodes(':visible').length"),graphData.nodes.length);
        assert.equal(await evaluate("new URLSearchParams(location.search).get('external')"),null);
        assertViewport(await evaluate("({zoom:scopeCy.zoom(),pan:scopeCy.pan(),positions:scopeCy.nodes().map(n=>n.position())})"),scopeViewport);
        for(const term of graphData.nodes.filter(n=>n.external&&n.referenceHref?.startsWith('../ontology/'))){
          const target=new URL(term.referenceHref,base+'ontologies/');
          const response=await fetch(target);assert.equal(response.status,200);
          assert((await response.text()).includes('id="'+decodeURIComponent(target.hash.slice(1))+'"'),'Missing external reference anchor '+target);
        }
        if(dataset==='sql'){
          assert.equal(await evaluate("document.getElementById('graph')._cyreg.cy.getElementById('https://arturmiller.github.io/spec-compiler/ontology/sql/#SQLite').style('shape')"),'hexagon');
          await screenshot(base.includes(prefix)?'sql-context-prefix':'sql-context-root');
        }
        if(dataset==='funding'||dataset==='cloud'){
          await evaluate("window.contextCy=document.getElementById('graph')._cyreg.cy;contextCy.nodes('[external=\"1\"]')[0].emit('tap');void 0;");
          assert(await evaluate("document.getElementById('graph-side').textContent.includes('Externer Begriff')"));
          assert.equal(await evaluate("contextCy.nodes('[external=\"1\"]')[0].style('border-style')"),'dashed');
          await screenshot((dataset==='funding'?'funding-context':'cloud-context')+(base.includes(prefix)?'-prefix':'-root'));
        }
      }
      await evaluate("document.getElementById('show-external').click();document.getElementById('ontology-select').value='funding';document.getElementById('ontology-select').dispatchEvent(new Event('change'));void 0;");
      assert(!await evaluate("document.getElementById('show-external').checked"));
      assert.equal(await evaluate("document.getElementById('graph')._cyreg.cy.nodes('[external=\"1\"]:visible').length"),0);
      await navigate(base+'ontologies/?ontology=funding&external=0&term='+encodeURIComponent('https://arturmiller.github.io/spec-compiler/ontology/decision/#Case'));
      await until("!!document.getElementById('graph')?._cyreg?.cy");
      assert(!await evaluate("document.getElementById('show-external').checked"));
      assert.equal(await evaluate("document.getElementById('graph')._cyreg.cy.nodes('[external=\"1\"]:visible').length"),0);
      assert(!(await evaluate("new URLSearchParams(location.search).get('term')")).includes('/decision/'));
      await evaluate("document.getElementById('show-external').click();document.getElementById('ontology-select').value='cloud';document.getElementById('ontology-select').dispatchEvent(new Event('change'));void 0;");
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
      await navigate(base+'ontologies/?ontology=decision&term='+encodeURIComponent('https://arturmiller.github.io/spec-compiler/ontology/decision/#DecisionResult'));
      await until("!!document.getElementById('graph')?._cyreg?.cy");
      await evaluate("window.resultCy=document.getElementById('graph')._cyreg.cy;void 0;");
      assert.equal(await evaluate('resultCy.nodes().filter(n=>n.connectedEdges().length===0).length'),0);
      assert(await evaluate("document.getElementById('graph-side').textContent.includes('enthält Bedingungsauswertung')"));
      const resultViewport=await evaluate("({zoom:resultCy.zoom(),pan:resultCy.pan(),positions:resultCy.nodes().map(n=>n.position())})");
      await screenshot(base.includes(prefix)?'decision-result-prefix':'decision-result-root');
      for(const term of ['ConditionEvaluation','FactGap','ObligationEvaluation','RuleSet','Source']){
        await evaluate(`void resultCy.getElementById('https://arturmiller.github.io/spec-compiler/ontology/decision/#'+${JSON.stringify(term)}).emit('tap');`);
        assertViewport(await evaluate("({zoom:resultCy.zoom(),pan:resultCy.pan(),positions:resultCy.nodes().map(n=>n.position())})"),resultViewport);
        if(['RuleSet','Source'].includes(term)) assert(await evaluate("document.getElementById('graph-side').textContent.includes('Lokale Zieltyp-Beschränkung')"));
      }
      await evaluate("document.querySelector('[data-edge-kind=\"type\"]').click();void 0;");
      assert.equal(await evaluate("resultCy.edges(':visible').filter(e=>e.data('kind')!=='type').length"),0);
      assertViewport(await evaluate("({zoom:resultCy.zoom(),pan:resultCy.pan(),positions:resultCy.nodes().map(n=>n.position())})"),resultViewport);
      await navigate(base+'ontologies/?ontology=compiler&term='+encodeURIComponent('https://arturmiller.github.io/spec-compiler/ontology/compiler/#generatesArtifact'));
      await until("!!document.getElementById('graph')?._cyreg?.cy");
      assert(await evaluate("document.getElementById('graph-side').textContent.includes('Veraltet') && document.getElementById('graph-side').textContent.includes('expectsArtifact')"));
      await navigate(base+'ontologies/?ontology=contract&term='+encodeURIComponent(migratedTerm)+'&context=1');
      await until("new URLSearchParams(location.search).get('ontology')==='compiler' && !!document.getElementById('graph')?._cyreg?.cy");
      assert.equal(await evaluate("new URLSearchParams(location.search).get('term')"),'https://arturmiller.github.io/spec-compiler/ontology/compiler/#TransformationContract');
      assert.equal(await evaluate("document.getElementById('ontology-select').value"),'compiler');
      await screenshot(base.includes(prefix)?'compiler-graph-prefix':'compiler-graph-root');
      for(const anchor of ['TransformationContract',migratedTerm]){
        await command('Page.navigate',{url:base+'ontology/index-de.html?legacy=1#'+encodeURIComponent(anchor)});
        await until("location.pathname.endsWith('/ontology/compiler/index-de.html') && location.hash==='#TransformationContract' && location.search.includes('legacy=1')");
        assert(await evaluate("!!document.getElementById('TransformationContract')"));
      }
      for(const [term,dataset] of [['SqlTable','sql'],['DecisionProtocolV1','decision-protocol'],['inputJsonPointer','decision-protocol']]){
        const old='https://arturmiller.github.io/spec-compiler/ontology/#'+term;
        const current='https://arturmiller.github.io/spec-compiler/ontology/'+dataset+'/#'+term;
        await command('Page.navigate',{url:base+'ontologies/?ontology=contract&term='+encodeURIComponent(old)});
        await until(`new URLSearchParams(location.search).get('ontology')===${JSON.stringify(dataset)} && new URLSearchParams(location.search).get('term')===${JSON.stringify(current)} && !!document.getElementById('graph')?._cyreg?.cy`);
        await command('Page.navigate',{url:base+'ontology/index-de.html#'+term});
        await until(`location.pathname.endsWith(${JSON.stringify('/ontology/'+dataset+'/index-de.html')}) && location.hash===${JSON.stringify('#'+term)} && !!document.getElementById(${JSON.stringify(term)})`);
      }
      await command('Page.navigate',{url:base+'ontologies/overview.html'});
      await until("location.pathname.endsWith('/ontologies/') && !!document.getElementById('graph')?._cyreg?.cy");
      await evaluate("window.moduleCy=document.getElementById('graph')._cyreg.cy;void 0;");
      fs.writeFileSync(path.join(evidence,base.includes(prefix)?'module-routing-prefix.json':'module-routing-root.json'),JSON.stringify(await evaluate("moduleCy.edges().map(e=>({source:e.source().id(),target:e.target().id(),turn:e.data('turn'),style:e.style('taxi-turn'),points:e.segmentPoints?.()}))"),null,2));
      assert.equal(await evaluate("moduleCy.nodes(':visible').length"),7);
      const moduleViewport=await evaluate("({zoom:moduleCy.zoom(),pan:moduleCy.pan(),positions:moduleCy.nodes().map(n=>n.position())})");
      await screenshot(base.includes(prefix)?'dependencies-prefix':'dependencies-root');
      await evaluate("document.getElementById('show-products').click();void 0;");
      assert.equal(await evaluate("moduleCy.nodes(':visible').length"),11);
      assert.equal(await evaluate("moduleCy.nodes('[role=\"product\"]:visible').length"),4);
      assert.equal(await evaluate("moduleCy.edges().filter(e=>e.target().data('role')==='product').length"),0);
      assertViewport(await evaluate("({zoom:moduleCy.zoom(),pan:moduleCy.pan(),positions:moduleCy.nodes().map(n=>n.position())})"),moduleViewport);
      await screenshot(base.includes(prefix)?'product-specifications-prefix':'product-specifications-root');
      await evaluate("void moduleCy.nodes('[role=\"product\"]')[0].emit('tap');");
      assert(await evaluate("document.getElementById('graph-side').textContent.includes('Abschließende Produktspezifikation')"));
      assertViewport(await evaluate("({zoom:moduleCy.zoom(),pan:moduleCy.pan(),positions:moduleCy.nodes().map(n=>n.position())})"),moduleViewport);
      await evaluate("document.getElementById('show-products').click();void 0;");
      assert.equal(await evaluate("moduleCy.nodes(':visible').length"),7);
      assertViewport(await evaluate("({zoom:moduleCy.zoom(),pan:moduleCy.pan(),positions:moduleCy.nodes().map(n=>n.position())})"),moduleViewport);
      const dependencyData=await (await fetch(base+'ontologies/dependencies.json')).json();
      assert.equal(dependencyData.direction,'dependent-to-required');
      assert.deepEqual(dependencyData.dependencies.filter(e=>!e.from.startsWith('product-')).map(e=>[e.from,e.to]),[['cloud','decision'],['decision-protocol','decision'],['funding','decision']]);
      assert(!dependencyData.dependencies.some(e=>e.to.startsWith('product-')));
      await navigate(base+'tutorials/sql-api/graph/?ontology=sql-api');
      await until("!!document.getElementById('graph')?._cyreg?.cy");
      assert.deepEqual(await evaluate("Array.from(document.querySelector('#ontology-select').options,o=>o.value)"),['sql-api']);
      for(const link of await evaluate("['reference-de','reference-en','source-link'].map(id=>document.getElementById(id).href)")) assert.equal((await fetch(link)).status,200,link);
      await command('Page.navigate',{url:base+'graph/?ontology=funding&context=1#keep'});
      await until("location.pathname.endsWith('/ontologies/') && location.search.includes('ontology=funding') && location.hash==='#keep'");
      await command('Page.navigate',{url:base+'?ontology=cloud#keep'});
      await until("location.pathname.endsWith('/ontologies/') && location.search.includes('ontology=cloud') && location.hash==='#keep'");
      await navigate(base);
      await evaluate("document.querySelector('[data-search-open]').click();const input=document.getElementById('site-search-input');input.value='Rule Set';input.dispatchEvent(new Event('input'));void 0;");
      await until("document.querySelectorAll('#site-search-results a').length>0");
      assert(await evaluate("document.querySelector('#site-search').open"));
      await screenshot(base.includes(prefix)?'search-prefix':'search-root');
      assert(await evaluate("Array.from(document.querySelectorAll('#site-search-results a')).some(a=>a.href.includes('reference/glossary.html#rule-set'))"));
      await navigate(base+'reference/architecture/?diagram=system-context&node=compiler#diagram-system-context');
      await until("Array.from(document.querySelectorAll('.diagram-frame')).some(f=>f.src.includes('system-context.html#focus=compiler') && f.contentDocument?.querySelector('svg'))");
      await until("Array.from(document.querySelectorAll('.diagram-frame')).some(f=>f.src.includes('system-context.html') && f.contentWindow.Archify?.focus?.active?.()==='compiler')");
      assert(await evaluate("Array.from(document.querySelectorAll('.diagram-frame')).filter(f=>f.src.includes('system-context.html'))[0].contentDocument.documentElement.dataset.theme===document.documentElement.dataset.theme"));
      await navigate(base+'diagrams/compiler-components.html#focus=coordinator');
      await until("window.Archify?.focus?.active?.()==='coordinator'");
      const nodeDescription=JSON.parse(fs.readFileSync(path.join(root,'diagrams/compiler-components.json'),'utf8')).components.find(n=>n.id==='coordinator').description;
      assert.equal(await evaluate("document.querySelector('.semantic-passport-detail').textContent"),nodeDescription);
      assert(await evaluate("document.querySelector('text[data-node-summary] tspan')!==null"));
      assert(await evaluate("document.querySelector('#focus-authored-links a').href.includes('reference/glossary.html#spec-compiler')"));
      await screenshot(base.includes(prefix)?'node-details-prefix':'node-details-root');
      await evaluate("document.querySelector('button[data-format=\"svg\"]').click();void 0;");
      await until("document.documentElement.dataset.lastExportFormat==='svg'");
      assert.equal(await evaluate('document.documentElement.dataset.lastExportCanonical'),'true');
      assert(await evaluate("Number(document.documentElement.dataset.lastExportBytes)>0"));
      // Export controls are outside the passport and may clear node focus.
      await navigate(base+'diagrams/compiler-components.html#focus=coordinator');
      await until("window.Archify?.focus?.active?.()==='coordinator'");
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
      await until("!window.Archify.focus.active()");
      await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
      await navigate(base+'diagrams/compiler-components.html#focus=coordinator');
      await until("window.Archify?.focus?.active?.()==='coordinator'");
      await evaluate("document.querySelector('#focus-authored-links a').click();void 0;");
      await until("location.pathname.endsWith('/reference/glossary.html') && location.hash==='#spec-compiler'");
      assert.equal(await evaluate('location.origin'),new URL(base).origin);
      await command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
      await navigate(base+'diagrams/compiler-components.html#focus=coordinator');
      await until("window.Archify?.focus?.active?.()==='coordinator'");
      assert.equal(await evaluate("document.querySelector('.semantic-passport-detail').textContent"),nodeDescription);
      assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
      await screenshot(base.includes(prefix)?'node-details-mobile-prefix':'node-details-mobile-root');
      for(const route of ['', 'compiler/', 'reference/architecture/', 'tutorials/sql-api/', 'ontologies/', 'contributors/', 'ontology/index-de.html', 'ontology/compiler/index-de.html', 'ontology/sql/index-de.html', 'ontology/decision-protocol/index-de.html', 'examples/sql-api/index-en.html']){
        await navigate(base+route);
        assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile horizontal overflow: '+route);
      }
      await screenshot(base.includes(prefix)?'mobile-prefix':'mobile-root');
    }
    assert.deepEqual(errors,[],'Browser JavaScript exceptions');
    console.log('Browser checks passed: root/prefix, eight bilingual RDF references, seven reusable ontology graphs and SQL tutorial, explicit import overview, terminal product-specification toggle, namespace redirects, stable viewport and positions, zoom, theme, search, focus/Escape, SVG export, mobile.');
    fs.writeFileSync(path.join(evidence,'result.json'),JSON.stringify({ok:true,checks:['navigation','rdf-references','rdf-downloads','legacy-redirects','namespace-migration','ontology-dependencies','dependency-directions','terminal-product-toggle','reference-anchors','datasets','viewport','zoom','theme','search','glossary-search','redirects','diagram-focus','long-node-details','glossary-link-navigation','escape','canonical-svg-export','mobile-node-details','mobile'],screenshots:path.relative(root,evidence)},null,2));
    await command('Browser.close');
  } finally {
    socket?.close();browser.kill();server.close();
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;server.close();});
