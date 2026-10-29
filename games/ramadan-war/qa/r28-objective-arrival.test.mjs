import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {canInteractAt,objectiveWaypoint} from '../objective-navigation.mjs';
const game=readFileSync(new URL('../game.js',import.meta.url),'utf8');
test('interaction range guidance uses same predicate as actual interaction',()=>{
 assert.match(game,/const inInteractRange=\['activate','extract'\]\.includes\(p\.kind\)\&\&canInteractAt\(world\.x,world\.y,site\[0\],site\[1\]\)/);
 assert.match(game,/inInteractRange\?\(p\.kind==='extract'/);
 assert.match(game,/تعامل آماده است · دکمه تعامل را بزن/);
 assert.equal(canInteractAt(3.5,4.5,4.5,4.5),true);
});
test('extract arrival keeps kill quota visible rather than claiming readiness',()=>{
 assert.match(game,/p\.kind==='extract'\&\&world\.missionKills<p\.quota/);
 assert.match(game,/ابتدا دشمنان باقی‌مانده را پاکسازی کن/);
});
test('defense hold uses same radius as objective timer and suppresses misleading waypoint',()=>{
 assert.match(game,/const inDefenseZone=p\.kind==='defend'\&\&Math\.hypot\(world\.x-site\[0\],world\.y-site\[1\]\)<2\.5/);
 assert.match(game,/inDefenseZone\?'در منطقه دفاع · موقعیت را حفظ کن'/);
 assert.match(game,/const waypoint=\(inInteractRange\|\|inDefenseZone\)\?null:objectiveWaypoint/);
 assert.ok(objectiveWaypoint(8.5,7.5,8.5,7.5,()=>true,16));
});
test('guidance hides arrow and assistive direction when already at objective',()=>{
 assert.match(game,/arrow\.style\.visibility=waypoint\?'visible':'hidden'/);
 assert.match(game,/arrow\.setAttribute\('aria-hidden',String\(!waypoint\)\)/);
});
