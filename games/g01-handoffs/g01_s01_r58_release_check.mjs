// G→S-01: independent read-only UI release check. No server/network writes.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve,dirname} from 'node:path';
const base=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const game=readFileSync(resolve(base,'ramadan-war/game.js'),'utf8');
const policy=readFileSync(resolve(base,'ramadan-war/moj1-commerce-policy.mjs'),'utf8');
const echo=readFileSync(resolve(base,'echoform/signal-lattice-r43.html'),'utf8');
const roham=readFileSync(resolve(base,'../templates/studio_raha/index.html'),'utf8');
assert.match(game,/function nextMission\(\)\{if\(!world\|\|!canEnterGameplay\(graphicsUnavailable,document\.hidden\)\)return/);
assert.match(game,/function resumeInMemoryCampaign\(\)\{if\(!hasResumableCampaignInMemory\(\)\|\|!canEnterGameplay/);
assert.match(echo,/document\.addEventListener\('freeze',/);
assert.match(roham,/document\.addEventListener\('freeze',backgroundPause\)/);
for(const key of ['ownerApproved','checkoutEnabled','verifiedBackend'])assert.match(policy,new RegExp(key+'\\s*:\\s*false'));
console.log('G01 S01 R58 source-only preflight: 5 checks PASS; NO deployment/backup/rollback acceptance implied');
