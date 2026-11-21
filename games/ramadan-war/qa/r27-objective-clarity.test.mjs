import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {objectiveWaypoint} from '../objective-navigation.mjs';
const game=readFileSync(new URL('../game.js',import.meta.url),'utf8');
test('detour route count is grid path length, not misleading Euclidean meters',()=>{
  const open=(x,y)=>x>=1&&x<=5&&y>=1&&y<=5&&!(x===2&&y===1);
  const result=objectiveWaypoint(1.5,1.5,4.5,1.5,open,7);
  assert.equal(result.steps,5);
  assert.equal(Math.hypot(4.5-1.5,1.5-1.5),3);
  assert.match(game,/fa\(waypoint\.steps\)\+' خانه مسیر'/);
});
test('unreachable objective does not display a false direction arrow',()=>{
  assert.match(game,/arrow\.style\.visibility=waypoint\?'visible':'hidden'/);
  assert.match(game,/arrow\.setAttribute\('aria-hidden',String\(!waypoint\)\)/);
  assert.match(game,/:'مسیر بسته است'/);
});
test('completed objective clears stale arrow and uses accessible hidden state',()=>{
  assert.match(game,/\$\('#objectiveArrow'\)\.style\.visibility='hidden'/);
  assert.match(game,/\$\('#objectiveArrow'\)\.setAttribute\('aria-hidden','true'\)/);
});
