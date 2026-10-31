import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {readAimSensitivity,aimMultiplier,nextAimSensitivity,aimSensitivityLabel} from '../aim-sensitivity.mjs';
const js=readFileSync(new URL('../game.js',import.meta.url),'utf8');
const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
test('invalid stored aim sensitivity falls back safely',()=>{for(const v of [null,undefined,'NaN','fast','__proto__',{},'']){assert.equal(readAimSensitivity(v),'normal');assert.equal(aimMultiplier(v),1)}});
test('three bounded aim levels cycle and scale both axes',()=>{assert.equal(aimMultiplier('low'),.65);assert.equal(aimMultiplier('high'),1.4);assert.equal(nextAimSensitivity('low'),'normal');assert.equal(nextAimSensitivity('normal'),'high');assert.equal(nextAimSensitivity('high'),'low');assert.equal(aimSensitivityLabel('normal'),'معمولی');assert.match(js,/world\.angle-=dx\*\(W<700\?\.008:\.0045\)\*aimMultiplier\(aimSensitivity\)/);assert.match(js,/engine\.look\(0,dy\*aimMultiplier\(aimSensitivity\),W\)/)});
test('pause recovery uses existing validated import transaction',()=>{assert.match(html,/id="importPauseSave"/);assert.match(html,/id="aimSensitivity"/);assert.match(js,/\$\('#importPauseSave'\)\.onclick=\(\)=>\$\('#importSaveFile'\)\.click\(\)/);assert.match(js,/readCampaignBackup\(await file\.text\(\)\)/);assert.match(js,/if\(!restore\(\)\)/)});
