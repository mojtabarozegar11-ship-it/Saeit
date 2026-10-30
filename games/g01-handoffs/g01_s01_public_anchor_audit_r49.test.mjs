import test from 'node:test';
import assert from 'node:assert/strict';
import {auditPublicAnchorTargets} from './g01_s01_public_anchor_audit_r49.mjs';

function anchor({name='',left=0,visible=true}={}) {
  const self={
    innerText:name,textContent:name,
    getAttribute:k=>k==='aria-label'?name:null,
    getClientRects:()=>visible?[{}]:[],
    getBoundingClientRect:()=>({left,top:0,width:30,height:20}),
    querySelectorAll:()=>[],
    contains:other=>other===self
  };
  return self;
}
test('reports anonymous visible anchor without leaking URLs or text',()=>{
  const good=anchor({name:'Checkout',left:0});
  const bad=anchor({left:40});
  const hidden=anchor({name:'hidden',left:80,visible:false});
  const overlay={};
  const doc={
    querySelectorAll:()=>[good,bad,hidden],
    elementFromPoint:x=>x<40?good:overlay,
    defaultView:{getComputedStyle:()=>({display:'block',visibility:'visible'})}
  };
  const out=auditPublicAnchorTargets(doc);
  assert.deepEqual(out,{scanned:3,visible:2,unnamed:1,center_obstructed:1,
    issues:[{index:1,kind:'unnamed'},{index:1,kind:'center_obstructed'}]});
  assert.equal(JSON.stringify(out).includes('Checkout'),false);
  assert.equal(JSON.stringify(out).includes('http'),false);
});
test('fails closed without DOM hit testing',()=>{
  assert.throws(()=>auditPublicAnchorTargets({querySelectorAll:()=>[]}),TypeError);
});
