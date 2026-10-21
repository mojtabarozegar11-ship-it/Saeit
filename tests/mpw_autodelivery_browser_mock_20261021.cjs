"use strict";
/* Exercise the exact Django checkout inline JS in an isolated Node VM:
 * no browser network, no real funds or SQL writes.
 * Usage: node tests/mpw_autodelivery_browser_mock_20261021.cjs /path/to/extracted.js
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const code = fs.readFileSync(process.argv[2], "utf8");
assert(code.includes("MPW_CRYPTO_AUTODELIVERY_POLL_V1"));
assert(!code.includes("{{"));
new vm.Script(code, {filename:"mpw-live-rendered-checkout.js"});

function tick() { return new Promise(resolve => setImmediate(resolve)); }
async function scenario(kind) {
  class Node {
    constructor(id) {this.id=id;this.textContent="";this.value="";this.hidden=true;
      this.disabled=false;this.children=[];this.listeners={};}
    addEventListener(name,fn) {this.listeners[name]=fn;}
    append(node) {this.children.push(node);}
    replaceChildren() {this.children=[];}
  }
  const names=["start","check","status","invoice","downloads","links","price","asset",
               "network","amount","receiver","expiry"];
  const elements=Object.fromEntries(names.map(name=>[name,new Node(name)]));
  elements.price.textContent="7.50";
  elements.asset.value="TRX";
  const timers=[];
  let nextId=1, checks=0, postCount=0;
  const requests=[];
  const docListeners={};
  const document={
    hidden:false,
    querySelector:()=>({value:"mock-csrf-token"}),
    getElementById:(id)=>{assert(elements[id],"missing DOM "+id);return elements[id];},
    createElement:id=>new Node(id),
    addEventListener:(event,handler)=>{docListeners[event]=handler;},
  };
  const window={
    tronWeb:{
      defaultAddress:{base58:"T"+"K".repeat(33)},
      trx:{signMessageV2:async()=>"test-signed-message"},
    },
    setTimeout:(fn,delay)=>{assert(delay>0);const id=nextId++;timers.push({id,fn,delay});return id;},
    clearTimeout:id=>{const at=timers.findIndex(v=>v.id===id);if(at>=0)timers.splice(at,1);},
  };
  const responses={
    "/commerce/checkout/order/":{order_id:37},
    "/commerce/checkout/challenge/":{challenge_id:"mock-challenge",message:"sign in simulation"},
    "/commerce/checkout/verify/":{verified:true},
    "/commerce/checkout/invoice/":{
      asset:"TRX",order_id:37,usd_total:"7.50",network:"tron-mainnet",
      amount_native:"26.25",receiver:"T"+"A".repeat(33),
      expires_at:"2026-10-21T06:44:00Z"
    },
  };
  const fetch=async(path,opts)=>{
    requests.push({path,method:opts.method,credentials:opts.credentials});
    assert.equal(opts.credentials,"same-origin");
    if(path.includes("/status/")) {
      assert.equal(opts.method,"GET");
      checks++;
      if (kind==="pending" || checks===1)
        return {ok:true,json:async()=>({can_access_purchased_items:false,download_paths:[]})};
      if (kind==="invalidLink")
        return {ok:true,json:async()=>({can_access_purchased_items:true,download_paths:["https://evil.example/file"]})};
      return {ok:true,json:async()=>({can_access_purchased_items:true,download_paths:["/commerce/download/109/"]})};
    }
    assert.equal(opts.method,"POST");
    postCount++;
    assert(responses[path],"unexpected payment endpoint "+path);
    return {ok:true,json:async()=>responses[path]};
  };
  const context={
    document,window,fetch,
    crypto:{randomUUID:()=>"00000000-0000-4000-8000-000000000001"},
    Date,Promise,console
  };
  vm.runInNewContext(code,context);
  assert(elements.start.listeners.click);
  assert(elements.check.listeners.click);
  await elements.start.listeners.click();
  assert.equal(postCount,4);
  assert.equal(elements.invoice.hidden,false);
  assert.equal(elements.downloads.hidden,true);
  assert(timers.length>0,"Expected automatically scheduled status check");
  let loop=0;
  while(timers.length && loop++<4){
    const next=timers.shift();
    next.fn();
    for(let i=0;i<8;i++)await tick();
    if(kind==="paid" && checks>=2)break;
    if(kind==="invalidLink" && checks>=2)break;
    if(kind==="pending" && checks>=2)break;
  }
  assert(checks>=2,"Automatic check must call read-only status twice");
  if(kind==="paid"){
    assert.equal(elements.downloads.hidden,false,"Paid entitlement must reveal download");
    assert.equal(elements.invoice.hidden,true);
    assert.equal(elements.links.children.length,1);
    assert.equal(elements.links.children[0].href,"/commerce/download/109/");
    assert.equal(timers.length,0,"Polling must stop after paid receipt");
  }else{
    assert.equal(elements.downloads.hidden,true,"Never release without backend-authorized link");
    assert.equal(elements.links.children.length,0);
    assert.equal(elements.invoice.hidden,false,"Unverified buyer must still see invoice");
    assert(timers.length>=1,"Pending payment needs a future check");
  }
  assert(!requests.some(x=>x.path.includes("download") && x.method==="POST"));
  console.log("MPW_AUTODELIVERY_JS_BROWSER_SIM="+JSON.stringify({
    scenario:kind,status_get_checks:checks,post_after_start:postCount,
    download_visible:!elements.downloads.hidden,
    backend_verified_download_links:elements.links.children.length,
    real_chain_transfer:false,production_order_written:false
  }));
}
(async()=>{for(const kind of ["paid","pending","invalidLink"])await scenario(kind);})()
  .catch(e=>{console.error(e);process.exitCode=1;});
