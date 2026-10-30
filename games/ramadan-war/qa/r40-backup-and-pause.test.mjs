import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {copyCampaignBackupToClipboard} from '../backup-clipboard.mjs';
const js=readFileSync(new URL('../game.js',import.meta.url),'utf8');
const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
test('explicit home/pause copy actions never auto-copy or send a campaign',()=>{
  assert.match(html,/id="copySave"/);assert.match(html,/id="copyPauseSave"/);
  assert.match(js,/\$\('#copySave'\)\.onclick=copyCampaignBackup/);
  assert.match(js,/\$\('#copyPauseSave'\)\.onclick=copyCampaignBackup/);
  assert.match(js,/copyCampaignBackupToClipboard\(backup,navigator,document\)/);
});
test('clipboard success and failure are independently observable',async()=>{
  let text='';const doc={body:{}};
  assert.equal(await copyCampaignBackupToClipboard('save', {clipboard:{writeText:async s=>{text=s}}},doc),true);
  assert.equal(text,'save');
  assert.equal(await copyCampaignBackupToClipboard('',{},doc),false);
  assert.equal(await copyCampaignBackupToClipboard('save',{},doc),false);
});
test('clipboard permission failure falls back and cleans up textarea',async()=>{
  let removed=false,selected=false,created;
  const doc={body:{appendChild(a){created=a}},createElement:()=>({style:{},setAttribute(){},focus(){},select(){selected=true},remove(){removed=true}}),execCommand:x=>x==='copy'};
  const nav={clipboard:{writeText:async()=>{throw Error('blocked')}}};
  assert.equal(await copyCampaignBackupToClipboard('recovery',nav,doc),true);
  assert.equal(created.value,'recovery');assert.equal(selected,true);assert.equal(removed,true);
});
test('Escape resumes pause without stealing modified keys or file picker',()=>{
  assert.match(js,/screen==='pausePanel'&&e\.code==='Escape'&&!e\.repeat&&!isModifiedOrComposingKey\(e\)/);
  assert.match(js,/e\.target\?\.type!=='file'/);
  assert.match(js,/e\.preventDefault\(\);\$\('#resume'\)\.click\(\);return/);
});
