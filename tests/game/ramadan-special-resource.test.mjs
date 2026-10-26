import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
function functionLine(name) {
  const line = game.split('\n').find(row => row.startsWith('function '+name+'('));
  assert.ok(line, name+' must remain an executable game function');
  return line;
}
const actions = functionLine('droneStrike')+'\n'+functionLine('special');

function harness({hero=5, drones=2, target={x:7,y:8}, skillTimer=0, droneTimer=0}={}) {
  const world = {hero,drones,skillTimer,droneTimer,missionPassed:false,x:2,y:3,hp:40,maxHp:100,shield:0};
  const saves=[], messages=[];
  const sandbox = {world,screen:'game',targetAim:()=>target,nearest:()=>target,
    toast:message=>messages.push(message),sync:()=>{},save:()=>saves.push({...world})};
  vm.runInNewContext(actions,sandbox);
  return {world,saves,messages,sandbox};
}

test('support skill does not spend its cooldown or a drone when inventory is empty', () => {
  const h=harness({drones:0});
  h.sandbox.special();
  assert.equal(h.world.skillTimer,0);
  assert.equal(h.world.drones,0);
  assert.equal(h.saves.length,0);
  assert.ok(h.messages.length>0);
});

test('support skill with no target does not consume resources or save a phantom strike', () => {
  const h=harness({target:null});
  h.sandbox.special();
  assert.equal(h.world.skillTimer,0);
  assert.equal(h.world.drones,2);
  assert.equal(h.saves.length,0);
});

test('successful support skill consumes exactly one drone and persists the cooldown', () => {
  const h=harness({hero:5});
  h.sandbox.special();
  assert.equal(h.world.drones,1);
  assert.equal(h.world.droneTimer,7);
  assert.equal(h.world.strikeX,7);
  assert.equal(h.world.strikeY,8);
  assert.equal(h.world.skillTimer,13.5);
  assert.equal(h.saves.length,1,'support action must persist only the final atomic state');
  assert.equal(h.saves.at(-1).skillTimer,13.5);
  assert.equal(h.saves.at(-1).drones,1);
  assert.equal(h.world.skillFired,true);
});

test('ordinary shield skill remains available without drone inventory and is saved', () => {
  const h=harness({hero:0,drones:0});
  h.sandbox.special();
  assert.equal(h.world.shield,12);
  assert.equal(h.world.skillTimer,13);
  assert.equal(h.saves.at(-1).shield,12);
});

test('cooldown blocks a repeated support activation without spending another drone', () => {
  const h=harness({skillTimer:3});
  h.sandbox.special();
  assert.equal(h.world.drones,2);
  assert.equal(h.world.skillTimer,3);
  assert.equal(h.saves.length,0);
});

test('ordinary drone action saves once and remains independent of the special skill cooldown', () => {
  const h=harness({hero:5});
  const success=h.sandbox.droneStrike();
  assert.equal(success,true);
  assert.equal(h.world.drones,1);
  assert.equal(h.world.skillTimer,0);
  assert.equal(h.saves.length,1);
  assert.equal(h.saves[0].drones,1);
});

test('failed ordinary drone action does not write an invalid save', () => {
  const h=harness({target:null});
  assert.equal(h.sandbox.droneStrike(),false);
  assert.equal(h.world.drones,2);
  assert.equal(h.saves.length,0);
});
