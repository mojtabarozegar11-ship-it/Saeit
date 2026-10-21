#!/usr/bin/env node
/* Runtime interaction probe: does F14 allow a keyboard-only player to plant? */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const [, ,enginePath,controllerPath]=process.argv;
assert(enginePath&&controllerPath,'Pinned engine and controller paths are required');
const actualEngine=require(path.resolve(enginePath));
const actualController=fs.readFileSync(path.resolve(controllerPath),'utf8');
function runController(controllerSource){
  let attempts=0,successes=0;
  const listeners={},elements=new Map();
  function el(id){
    if(elements.has(id))return elements.get(id);
    const handlers={};
    const element={
      id,width:900,height:540,hidden:false,disabled:false,textContent:'',firstChild:{textContent:''},
      dataset:{},classList:{toggle(){}},
      addEventListener(event,fn){handlers[event]=fn;},
      dispatch(event,params){if(handlers[event])handlers[event](params||{});},
      setAttribute(){},getBoundingClientRect(){return {left:0,top:0,width:900,height:540};},
      getContext(){return {};}
    };
    elements.set(id,element);return element;
  }
  const engine=Object.assign({},actualEngine,{
    plant(...args){
      attempts++;
      const r=actualEngine.plant(...args);
      if(r.ok)successes++;
      return r;
    }
  });
  const document={
    getElementById:el,querySelectorAll(){return [];},
    addEventListener(event,fn){listeners[event]=fn;}
  };
  const sandbox={
    window:{RootlineEngine:engine},document,
    localStorage:{getItem(){return null;},setItem(){}},
    performance:{now(){return 0;}},requestAnimationFrame(){},console
  };
  vm.runInNewContext(controllerSource,sandbox,{filename:'game.js',timeout:1000});
  el('launch').dispatch('click');
  const key=keyName=>{assert(listeners.keydown,'Keyboard listener missing');
    listeners.keydown({key:keyName,repeat:false,preventDefault(){}});
  };
  for(const c of ['1','ArrowRight','ArrowDown','Enter',' '])key(c);
  const plantedByKeyboard=successes;
  el('field').dispatch('pointerdown',{
    clientX:110,clientY:109,pointerType:'mouse',preventDefault(){}
  });
  return {keyboard_plants:plantedByKeyboard,pointer_plants:successes-plantedByKeyboard,
          attempts};
}
const baseline=runController(actualController);
const anchor="if(e.key.toLowerCase()==='p'";
assert(actualController.includes(anchor),'Controller keyboard branch changed: review probe');
const syntheticFix=actualController.replace(anchor,
    "if(e.key==='Enter'){E.plant(g,0,0);hud();} "+anchor);
const control=runController(syntheticFix);
assert(baseline.pointer_plants>0,'Unable to prove controller handles planting at all');
assert(control.keyboard_plants>baseline.keyboard_plants,'Probe cannot recognize keyboard planting in positive control');
const result={
  check:'keyboard_place_unit_from_keyboard_only',
  tested_via:'real Node.js VM execution of actual controller and actual game engine',
  keyboard_planting_supported:baseline.keyboard_plants>0,
  observed_successful_keyboard_placements:baseline.keyboard_plants,
  observed_successful_pointer_placements:baseline.pointer_plants,
  detection_positive_control:'PASS',
  verdict:baseline.keyboard_plants>0?'KEYBOARD_PLANTING_OBSERVED':'BLOCKED_NO_KEYBOARD_PLANTING'
};
process.stdout.write(JSON.stringify(result)+'\n');
