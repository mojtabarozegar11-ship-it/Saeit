import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const js=readFileSync(new URL('../game.js',import.meta.url),'utf8');
test('successful pasted-code import wipes hidden private textarea',()=>{
 assert.match(js,/else \{clearBackupCode\(\);backupCodeReturnFocus=null;\} \/\/ Never retain an imported private code/);
});
test('back-forward cache pagehide wipes private textarea',()=>{
 assert.match(js,/addEventListener\('pagehide',\(\)=>\{clearBackupCode\(\);save\(\)\}\)/);
});
test('keyboard focus trapped and Escape closes dialog without resuming gameplay',()=>{
 assert.match(js,/backupCodePanel'\)\.addEventListener\('keydown'/);
 assert.match(js,/e\.key==='Escape'/);
 assert.match(js,/e\.key!=='Tab'/);
 assert.match(js,/backupCodeReturnFocus\.focus\(\{preventScroll:true\}\)/);
});
