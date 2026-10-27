"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const root = __dirname;
const file = name => fs.readFileSync(path.join(root,name),"utf8");
const pages = ["index.html","revenue/index.html","casino/index.html"];
const scripts = ["app.js","revenue/models.js","casino/casino.js"];
const reads = Object.fromEntries([...pages,...scripts,"README.md"].map(name=>[name,file(name)]));
function requireUniqueHtmlIds(name) {
  const source=reads[name];
  const ids=[...source.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]);
  assert.equal(new Set(ids).size,ids.length,name+": duplicate HTML ids");
  return ids;
}
const ids={
  "index.html":requireUniqueHtmlIds("index.html"),
  "revenue/index.html":requireUniqueHtmlIds("revenue/index.html"),
  "casino/index.html":requireUniqueHtmlIds("casino/index.html")
};
for(const name of scripts){new vm.Script(reads[name],{filename:name});}
function verifyDollarRefs(scriptName,htmlName){
  const referenced=[...reads[scriptName].matchAll(/\$\("([^"]+)"\)/g)].map(x=>x[1]);
  const missing=[...new Set(referenced.filter(id=>!ids[htmlName].includes(id)))];
  assert.deepEqual(missing,[],scriptName+": missing DOM element IDs");
}
verifyDollarRefs("app.js","index.html");
verifyDollarRefs("casino/casino.js","casino/index.html");
for(const htmlName of pages) {
  const source=reads[htmlName];
  for(const matched of source.matchAll(/<script\b[^>]*\bsrc="([^"]+)"[^>]*>/g)) {
    assert.ok(!/^https?:\/\//.test(matched[1]),htmlName+": unexpected external script");
    const linked=path.resolve(root,path.dirname(htmlName),matched[1]);
    assert.ok(linked.startsWith(root+path.sep) && fs.existsSync(linked),htmlName+": missing local JavaScript "+matched[1]);
  }
  for(const matched of source.matchAll(/<link\b[^>]*\bhref="([^"]+\.css)"[^>]*>/g)) {
    const linked=path.resolve(root,path.dirname(htmlName),matched[1]);
    assert.ok(linked.startsWith(root+path.sep) && fs.existsSync(linked),htmlName+": missing local CSS "+matched[1]);
  }
}
const modelSource=reads["revenue/models.js"];
const match=modelSource.match(/const models=(\[[\s\S]*?\]);\nconst grid=/);
assert.ok(match,"Revenue dataset literal not found");
const models=JSON.parse(match[1]);
assert.equal(models.length,50,"Must have exactly fifty non-casino revenue models");
assert.equal(new Set(models.map(m=>m.name)).size,50,"Revenue names must be unique");
const byCategory=new Map();
for(const m of models) {
  for(const field of ["category","name","description","gate"])assert.ok(typeof m[field]==="string" && m[field].length>=3,"Incomplete model: "+m.name);
  byCategory.set(m.category,(byCategory.get(m.category)||0)+1);
}
assert.equal(byCategory.size,10,"Expected ten categories");
for(const [name,count] of byCategory)assert.equal(count,5,name+": expected five models");
const casino=reads["casino/index.html"],casinoCode=reads["casino/casino.js"];
assert.match(casino,/REAL-MONEY GATE LOCKED/);
assert.match(casino,/NO MONEY STAKES/);
assert.match(casino,/id="age-overlay"/);
assert.match(casinoCode,/getRandomValues/);
assert.ok(!/\b(fetch|XMLHttpRequest|WebSocket)\s*\(/.test(casinoCode),"Casino module must have no network financial integration");
assert.ok(!/<form\b/i.test(casino),"No cashier or wager form is permitted");
assert.ok(reads["README.md"].includes("Fifty non-casino revenue channels"));
assert.ok(reads["index.html"].includes("./casino/") && reads["index.html"].includes("./revenue/"),"Home must link both portals");
process.stdout.write(JSON.stringify({result:"PASS",pages:pages.length,javascriptFiles:scripts.length,models:models.length,categories:byCategory.size,casinoRealMoney:"LOCKED"},null,2)+"\n");
