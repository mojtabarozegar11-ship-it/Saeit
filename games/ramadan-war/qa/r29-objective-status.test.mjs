import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {canInteractAt} from '../objective-navigation.mjs';
const game=readFileSync(new URL('../game.js',import.meta.url),'utf8');
test('recovery pickup proximity suppresses arrow and reports automatic collection',()=>{
 assert.ok(game.includes("const nearIntel=p.kind==='recover'&&Math.hypot(world.x-site[0],world.y-site[1])<.78"));
 assert.ok(game.includes("const waypoint=(inInteractRange||inDefenseZone||nearIntel)?null:objectiveWaypoint"));
 assert.ok(game.includes("nearIntel?'بستهٔ اطلاعاتی در حال جمع‌آوری است'"));
});
test('boss is not called complete before spawning',()=>{assert.ok(game.includes("p.kind==='boss'&&!o.bossDefeated?'فرمانده هنوز ظاهر نشده است'"))});
test('missing recovery pickup is not falsely called complete',()=>{assert.ok(game.includes("p.kind==='recover'&&o.done<p.sites.length?"));
 assert.ok(game.includes('بستهٔ اطلاعاتی پیدا نشد؛ مرحله را دوباره بررسی کن'))});
test('remaining quota remains visible after local objective is done',()=>{assert.ok(game.includes("world.missionKills<p.quota?'هدف موضعی انجام شد · پاکسازی دشمنان باقی مانده'"))});
test('R28 interaction boundary remains unchanged',()=>{assert.equal(canInteractAt(0,0,1.35,0),true);assert.equal(canInteractAt(0,0,1.36,0),false)});
