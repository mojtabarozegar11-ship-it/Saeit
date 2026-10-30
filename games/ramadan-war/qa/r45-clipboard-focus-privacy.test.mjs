import test from 'node:test';
import assert from 'node:assert/strict';
import {copyCampaignBackupToClipboard} from '../backup-clipboard.mjs';

test('legacy fallback restores keyboard focus and removes sensitive temporary field',async()=>{
 let copied='',removed=false,restored=0;
 const original={isConnected:true,focus:()=>restored++};
 const doc={hidden:false,activeElement:original,body:{appendChild(a){copied=a.value}},
   createElement:()=>({style:{},setAttribute(){},focus(){},select(){},remove(){removed=true}}),
   execCommand:cmd=>cmd==='copy'};
 const nav={clipboard:{writeText:async()=>{throw new Error('permission denied')}}};
 assert.equal(await copyCampaignBackupToClipboard('private',nav,doc),true);
 assert.equal(copied,'private');assert.equal(removed,true);assert.equal(restored,1);
});
test('hidden tab cannot start clipboard write',async()=>{
 let calls=0;
 const doc={hidden:true,body:{}};
 assert.equal(await copyCampaignBackupToClipboard('private',{clipboard:{writeText:async()=>calls++}},doc),false);
 assert.equal(calls,0);
});
test('denied async permission must not fall back to hidden-tab legacy copy',async()=>{
 let fallback=0;
 const doc={hidden:false,body:{},createElement:()=>{fallback++;throw Error('unexpected')},execCommand:()=>true};
 const nav={clipboard:{writeText:async()=>{doc.hidden=true;throw Error('permission denied')}}};
 assert.equal(await copyCampaignBackupToClipboard('private',nav,doc),false);
 assert.equal(fallback,0);
});
test('legacy copy failure cleans up and restores focus',async()=>{
 let removed=0,restored=0;
 const doc={hidden:false,body:{appendChild(){}},activeElement:{isConnected:true,focus(){restored++}},
 createElement:()=>({style:{},setAttribute(){},focus(){},select(){},remove(){removed++}}),execCommand:()=>false};
 assert.equal(await copyCampaignBackupToClipboard('private',{},doc),false);
 assert.equal(removed,1);assert.equal(restored,1);
});
