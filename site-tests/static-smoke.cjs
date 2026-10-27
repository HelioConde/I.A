/**
 * Luna Pages dependency-free QA gate.
 * Run from repository root: node site-tests/static-smoke.cjs
 */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const root=path.resolve(__dirname,"../site");
const read=(name)=>fs.readFileSync(path.join(root,name),"utf8");
const html=read("index.html"),css=read("styles.css"),js=read("app.js");
const worker=read("service-worker.js"),manifest=JSON.parse(read("manifest.webmanifest"));
const assets=["index.html","styles.css","app.js","favicon.svg","manifest.webmanifest","service-worker.js"];
for(const file of assets)assert.ok(fs.statSync(path.join(root,file)).isFile(),file+" missing");
assert.equal(new Set(assets).size,assets.length);
new vm.Script(js,{filename:"site/app.js"});
new vm.Script(worker,{filename:"site/service-worker.js"});
assert.match(html,/lang="pt-BR"/);
assert.match(html,/name="viewport"/);
assert.match(html,/id="network-notice"[^>]*hidden/);
assert.match(css,/\[hidden\]\s*\{display:none!important\}/);
assert.match(css,/prefers-reduced-motion:reduce/);
assert.match(js,/textContent/);
assert.doesNotMatch(js,/fetch\(/);
assert.doesNotMatch(js,/(^|[^.\w])eval\(/);
assert.doesNotMatch(html,/\son[a-z]+\s*=/i);
assert.doesNotMatch(html,/<script[^>]+src=["']https?:/i);
assert.equal(manifest.start_url,"./");
assert.equal(manifest.scope,"./");
assert.ok(worker.includes('const CACHE_NAME'));
for(const file of ["./index.html","./styles.css","./app.js","./favicon.svg","./manifest.webmanifest"]) {
  assert.ok(worker.includes(JSON.stringify(file)),"missing offline asset "+file);
}
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]);
assert.equal(ids.length,new Set(ids).size,"duplicate DOM IDs");
const idSet=new Set(ids);
for(const match of js.matchAll(/\$\("([^"]+)"\)/g)) {
  assert.ok(idSet.has(match[1]),"missing JS DOM target "+match[1]);
}
for(const match of html.matchAll(/\baria-controls="([^"]+)"/g)){
  assert.ok(idSet.has(match[1]),"invalid aria-controls "+match[1]);
}
for(const match of html.matchAll(/\bfor="([^"]+)"/g)){
  assert.ok(idSet.has(match[1]),"invalid label association "+match[1]);
}
console.log("PASS: six static assets, script syntax, subpath URLs, hidden elements, CSP readiness, accessibility IDs and offline shell.");
