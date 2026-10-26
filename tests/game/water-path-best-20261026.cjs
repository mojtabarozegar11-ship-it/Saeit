'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('content/zomorod-hourly-20261023/water-path-game/index.html','utf8');
const script=html.split('<script>')[1]?.split('</script>')[0];
assert.ok(script,'Water Path playable script must exist');
new vm.Script(script,'water-path.js');
const start=script.indexOf('function bestForStage(');
const end=script.indexOf('function rnd(',start);
assert.ok(start>=0&&end>start,'validated per-stage record helper must exist');
const fn=script.slice(start,end);
const records=vm.runInNewContext(
 'const bests={0:12,1:1,2:100001,3:"5",4:Infinity,5:-4,6:0,7:100000};'+fn+
 '[0,1,2,3,4,5,6,7,8].map(bestForStage)',
 {Number}
);
assert.deepEqual(Array.from(records),[12,1,null,null,null,null,null,100000,null],
 'valid records survive; strings, forged extremes and nonfinite values are rejected');
assert.ok(html.includes('id="best"'),'players must see their per-stage best record');
assert.ok(script.includes('bestDisplay.textContent="بهترین حرکت: "+(bestForStage(stage)??"—")'),
 'rendered HUD must update the best record after each move and victory');
assert.ok(script.includes('if(best===null||turns<best)bests[stage]=turns'),
 'victory must only replace a record with a genuinely better move count');
console.log('WATER_PATH_PERSONAL_BEST=PASS: visible, bounded, per-stage records');
