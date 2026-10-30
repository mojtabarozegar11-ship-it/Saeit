import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const js=readFileSync(new URL('../game.js',import.meta.url),'utf8');
test('manual private backup is redacted on blur',()=>{
 assert.match(js,/addEventListener\('blur',redactBackupCodeOnInactivity\)/);
 assert.match(js,/function redactBackupCodeOnInactivity\(\)\{/);
 assert.match(js,/if\(screen!=='backupCodePanel'\)return/);
 assert.match(js,/clearBackupCode\(\)/);
});
test('private backup is redacted when page is hidden',()=>{
 assert.match(js,/document.addEventListener\('visibilitychange',\(\)=>\{if\(document.hidden\)redactBackupCodeOnInactivity\(\)\}\)/);
});
test('bfcache return never presents an empty code as a valid backup',()=>{
 assert.match(js,/addEventListener\('pageshow',e=>\{if\(e.persisted\)redactBackupCodeOnInactivity\(\)\}\)/);
 assert.match(js,/backupCodeHint'\)\.textContent='کد خصوصی پس از خروج از صفحه پاک شد/);
});
