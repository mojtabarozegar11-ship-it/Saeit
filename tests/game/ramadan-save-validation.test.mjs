import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {validateCampaignSave, boundedCampaignPickups, restoreRecoveryPickups, reconcileBossEncounter, restorePlayerPosition, resumeCampaignScreen, readHeroChoice, storageRead, storageWrite, storageRemove} from '../../games/ramadan-war/save-validation.mjs';

const fresh = () => ({
  hero: 0, mission: 0, lives: 100, x: 2.5, y: 7.5, angle: 0,
  hp: 100, maxHp: 100, ammo: 8, magazine: 8, rockets: 12, drones: 3,
  score: 0, points: 0, kills: 0, missionKills: 0, enemies: [],
  hostile: [], missiles: [], pickups: [],
  objective: {done: 0, hold: 0, bossDefeated: false}, endless: false
});

test('accepts an ordinary campaign save and a legacy save without optional arrays', () => {
  assert.equal(validateCampaignSave(fresh()), true);
  const legacy = fresh();
  delete legacy.pickups; delete legacy.hostile; delete legacy.missiles;
  assert.equal(validateCampaignSave(legacy), true);
});
test('truthy forged mode flags cannot bypass campaign restore boundaries', () => {
  const valid=fresh();
  assert.equal(validateCampaignSave(valid),true);
  assert.equal(validateCampaignSave({...valid,endless:false,victory:false,gameOver:false}),true);
  for(const flag of ['endless','victory','gameOver']){
    for(const value of [true,'true',1,[],{},null]){
      assert.equal(validateCampaignSave({...valid,[flag]:value}),false,
        flag+' must not become truthy or non-boolean after restore');
    }
  }
});

test('rejects broken player positions and numeric progress before engine initialization', () => {
  for (const patch of [
    {x: null}, {x: NaN}, {x: Infinity}, {y: -1}, {angle: '0'},
    {hero: 30}, {mission: 6}, {lives: 0}, {hp: -1},
    {maxHp: 0}, {ammo: 9}, {magazine: 0}, {rockets: -1},
    {drones: 100}, {score: -1}, {score: 1.2}, {points: Infinity}
  ]) assert.equal(validateCampaignSave({...fresh(), ...patch}), false, JSON.stringify(patch));
});
test('rejects invalid enemy routes and oversized or malformed entity arrays', () => {
  const enemy = {x: 8, y: 7, type: 1, hp: 30, route: [6.5, 7.5]};
  assert.equal(validateCampaignSave({...fresh(), enemies: [enemy]}), true);
  for (const enemies of [
    [null], [{...enemy, x: '8'}], [{...enemy, route: 'not-a-route'}],
    [{...enemy, route: [NaN, 3]}], Array(31).fill(enemy)
  ]) assert.equal(validateCampaignSave({...fresh(), enemies}), false);
  for (const patch of [
    {hostile: {}}, {missiles: [null]}, {pickups: [{x: 2, y: 3, life: 20, type: 'unknown'}]},
    {pickups: Array(61).fill({x: 2, y: 3, life: 20, type: 'ammo'})}
  ]) assert.equal(validateCampaignSave({...fresh(), ...patch}), false);
});
test('runtime counters, render effects and marker are validated before restoring a save', () => {
  const effect = {x: 8.5, y: 7.5, height: 1.08, life: .24, type: 'body'};
  const valid = {...fresh(), shots: 18, combo: 2, best: 1, rocketHits: 1,
    recoil: .16, reloading: false, hit: true, skillFired: false,
    impacts: [effect], marker: {x: 8.5, y: 3.5, kind: 'activate'}};
  assert.equal(validateCampaignSave(valid), true);
  assert.equal(validateCampaignSave({...fresh(), impacts: [], marker: null}), true);
  for (const patch of [
    {shots: 'NaN'}, {shots: Infinity}, {combo: NaN}, {combo: -1},
    {best: '1'}, {rocketHits: 1.5}, {recoil: NaN}, {recoil: -1},
    {reloading: 'false'}, {hit: []}, {skillFired: 1},
    {impacts: {}}, {impacts: [null]}, {impacts: [{...effect, x: '8.5'}]},
    {impacts: [{...effect, height: Infinity}]},
    {impacts: [{...effect, life: '0.2'}]},
    {impacts: Array(129).fill(effect)},
    {marker: {x: NaN, y: 3.5, kind: 'activate'}},
    {marker: {x: 8.5, y: 3.5, kind: {}}}
  ]) assert.equal(validateCampaignSave({...fresh(), ...patch}), false, JSON.stringify(patch));
  // Invalid data must be rejected, not silently repaired or granted as progress.
  assert.equal(valid.combo, 2);
  assert.equal(valid.impacts.length, 1);
});

test('preserves valid objective progress while refusing corrupted mission completion', () => {
  assert.equal(validateCampaignSave({...fresh(), objective: {done: 2, hold: 18.5, bossDefeated: false}}), true);
  for (const objective of [[], 'done', {done: 999, hold: 0, bossDefeated: false},
    {done: 1, hold: Infinity, bossDefeated: false},
    {done: 1, hold: 0, bossDefeated: 'yes'}])
    assert.equal(validateCampaignSave({...fresh(), objective}), false);
  assert.equal(validateCampaignSave({...fresh(), endless: true}), false);
  assert.equal(validateCampaignSave({...fresh(), gameOver: true}), false);
});

test('in-progress objective state cannot exceed stage-specific site and timer rules', () => {
  const maxDone=[2,1,3,2,1,0];
  for(let mission=0;mission<6;mission++){
    const objective={done:maxDone[mission],hold:mission===1?22:0,bossDefeated:false};
    const good={...fresh(),mission,objective};
    assert.equal(validateCampaignSave(good),true,'valid objective stage '+mission);
    assert.equal(validateCampaignSave({...good,objective:{...objective,done:maxDone[mission]+1}}),false,
      'out-of-stage objective progress '+mission);
    if(mission!==5)assert.equal(validateCampaignSave({...good,objective:{...objective,bossDefeated:true}}),false,
      'boss reward must remain final-stage only');
  }
  const premature={...fresh(),mission:1,objective:{done:1,hold:10,bossDefeated:false}};
  assert.equal(validateCampaignSave(premature),false,'defence cannot be marked complete before 22 seconds');
  assert.equal(validateCampaignSave({...premature,objective:{...premature.objective,done:0}}),true,
    'partially completed timed defence remains playable');
});

test('reversible release manifest ships and checks every new imported save module', () => {
  const deploy = readFileSync(new URL('../../games/ramadan-war/deploy.py', import.meta.url), 'utf8');
  const client = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.match(client, /import \{[^}]*\bcampaignSaveDisposition\b[^}]*\} from '\.\/save-validation\.mjs'/);
  assert.match(deploy, /ASSETS=\[[^\n]*'save-validation\.mjs'/);
  assert.match(deploy, /b'\.\/save-validation\.mjs' in new\['game\.js'\]/);
});

test('completed campaign stage resumes to its result panel; ongoing stage resumes to play', () => {
  const active = fresh();
  assert.equal(resumeCampaignScreen(active), 'game');
  assert.equal(resumeCampaignScreen({...active, missionPassed: false}), 'game');
  const cleared = {...active, missionPassed: true, missionKills: 4,
    objective: {done: 2, hold: 0, bossDefeated: false}};
  assert.equal(validateCampaignSave(cleared), true);
  assert.equal(resumeCampaignScreen(cleared), 'success');
});

test('rejects malformed completion flags and impossible cleared stage with living enemies', () => {
  for (const missionPassed of [null, 'true', 1, [], {}])
    assert.equal(validateCampaignSave({...fresh(), missionPassed}), false);
  const enemy = {x: 8, y: 7, type: 1, hp: 30};
  assert.equal(validateCampaignSave({...fresh(), missionPassed: true, enemies: [enemy]}), false);
});

test('completed stage flags cannot bypass actual stage objectives or kill quotas', () => {
  const goals = [
    {mission: 0, quota: 4, done: 2},
    {mission: 1, quota: 5, done: 1, hold: 22},
    {mission: 2, quota: 5, done: 3},
    {mission: 3, quota: 6, done: 2},
    {mission: 4, quota: 7, done: 1},
    {mission: 5, quota: 8, done: 0, bossDefeated: true}
  ];
  for (const {mission, quota, done, hold = 0, bossDefeated = false} of goals) {
    const state = {...fresh(), mission, missionKills: quota, missionPassed: true,
      objective: {done, hold, bossDefeated}};
    assert.equal(validateCampaignSave(state), true, 'valid completion stage ' + mission);
    assert.equal(validateCampaignSave({...state, missionKills: quota - 1}), false,
      'insufficient kills cannot clear stage ' + mission);
    assert.equal(validateCampaignSave({...state, objective: null}), false,
      'missing objectives cannot clear stage ' + mission);
    if (mission === 1) {
      assert.equal(validateCampaignSave({...state, objective: {...state.objective, hold: 21.99}}), false);
      assert.equal(validateCampaignSave({...state, objective: {...state.objective, done: 0}}), false);
    } else if (mission === 5) {
      assert.equal(validateCampaignSave({...state, objective: {...state.objective, bossDefeated: false}}), false);
    } else {
      assert.equal(validateCampaignSave({...state, objective: {...state.objective, done: done - 1}}), false);
    }
    assert.equal(validateCampaignSave({...state, missionPassed: false}), true,
      'ordinary in-progress saves remain compatible');
  }
});

test('restore branch presents completed stage results instead of trapping player in arena', () => {
  const client = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.match(client, /if\(resumeCampaignScreen\(world\)==='success'\)\{showResult\(/);
  assert.match(client, /showResult\('منطقه پاکسازی شد'/);
  assert.match(client, /showScreen\('game'\);last=performance\.now\(\);scheduleFrame\(\)/);
});


test('accepts live projectiles and rejects projectiles with invalid movement or damage', () => {
  const hostile = {x: 4, y: 6, life: 3, vx: 2, vy: -3, hp: 8};
  const missile = {x: 2.5, y: 7.5, life: 2, vx: 7.5, vy: 0, targetId: 0};
  assert.equal(validateCampaignSave({...fresh(), hostile: [hostile], missiles: [missile]}), true);
  for (const bad of [{...hostile, vx: undefined}, {...hostile, vy: Infinity},
    {...hostile, hp: '8'}, {...hostile, vx: 1000}]) {
    assert.equal(validateCampaignSave({...fresh(), hostile: [bad]}), false);
  }
  for (const bad of [{...missile, vx: undefined}, {...missile, vy: NaN},
    {...missile, targetId: 30}, {...missile, targetId: '0'}]) {
    assert.equal(validateCampaignSave({...fresh(), missiles: [bad]}), false);
  }
});

test('rejects corrupt saved clocks and drone impact coordinates without breaking legacy saves', () => {
  assert.equal(validateCampaignSave({...fresh(), time: 37.5, enemyTimer: -.5, strikeX: 8, strikeY: 7}), true);
  for (const field of ['time', 'enemyTimer', 'shotTimer', 'reloadTimer', 'comboTimer',
    'rocketTimer', 'droneTimer', 'skillTimer', 'shield', 'strikeTimer', 'hitFlash',
    'explosionTimer', 'muzzle', 'freeze']) {
    assert.equal(validateCampaignSave({...fresh(), [field]: Infinity}), false, field);
    assert.equal(validateCampaignSave({...fresh(), [field]: '0'}), false, field);
  }
  for (const patch of [{strikeX: NaN}, {strikeY: Infinity}, {strikeX: '5'}])
    assert.equal(validateCampaignSave({...fresh(), ...patch}), false);
});

test('corrupt or manipulated hero preference never breaks initial character rendering', () => {
  for (const [input,expected] of [['0',0],['5',5],['29',29],[8,8],[' 2 ',2]])
    assert.equal(readHeroChoice(input),expected,String(input));
  for (const input of [null,undefined,'','30','-1','NaN','Infinity','1e1','3.5',{},[],1/0])
    assert.equal(readHeroChoice(input),0,String(input));
  const game = readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  assert.match(game,/let hero=readHeroChoice\(storageRead\('rwHero'\)\),world=null/);
});

test('blocked or absent Web Storage cannot crash startup, pause, win or hero selection', () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  try {
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true, get() { throw new Error('SecurityError: storage denied'); }
    });
    assert.equal(storageRead('rwHero'), null);
    assert.equal(storageWrite('rwHero', 2), false);
    assert.equal(storageRemove('rwNativeCampaign'), false);
    Object.defineProperty(globalThis, 'localStorage', {configurable: true, value: undefined});
    assert.equal(storageRead('rwWin'), null);
    assert.equal(storageWrite('rwWin', '1'), false);
    assert.equal(storageRemove('rwWin'), false);
    const data = new Map();
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: {
        getItem: key => data.has(key) ? data.get(key) : null,
        setItem: (key, value) => data.set(key, value),
        removeItem: key => data.delete(key)
      }
    });
    assert.equal(storageWrite('rwHero', 7), true);
    assert.equal(storageRead('rwHero'), '7');
    assert.equal(storageRemove('rwHero'), true);
    assert.equal(storageRead('rwHero'), null);
  } finally {
    if (original) Object.defineProperty(globalThis, 'localStorage', original);
    else delete globalThis.localStorage;
  }
});

test('game contains no direct localStorage access outside guarded helpers', () => {
  const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.doesNotMatch(game, /localStorage/);
  assert.match(game, /storageRead\('rwWin'\)/);
  assert.match(game, /storageWrite\('rwHero',hero\)/);
  assert.match(game, /storageRemove\(saveKey\)/);
});

test('persisted pickup snapshots retain recovery objectives without mutating live drops', () => {
  const transient=Array.from({length:80},(_,i)=>({x:2.5,y:7.5,type:'ammo',life:20,serial:i}));
  const sites=[[4.5,2.5],[12.5,4.5],[8.5,12.5]];
  const intel=[0,1,2].map(spotIndex=>({x:sites[spotIndex][0],y:sites[spotIndex][1],type:'mission-intel',spotIndex,life:3600}));
  const live=[...intel,...transient];
  const snapshot=boundedCampaignPickups(live);
  assert.equal(live.length,83,'live gameplay pickups are never removed');
  assert.equal(snapshot.length,60);
  assert.deepEqual(snapshot.filter(p=>p.type==='mission-intel'),intel);
  assert.equal(snapshot.filter(p=>p.type==='ammo')[0].serial,23,'recent transient drops are retained');
  assert.equal(validateCampaignSave({...fresh(),mission:2,pickups:snapshot}),true);
  assert.deepEqual(boundedCampaignPickups([]),[]);
  assert.deepEqual(boundedCampaignPickups(null),[]);
});

test('runtime persists bounded pickup snapshots without truncating live mission rewards', () => {
  const game=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  assert.ok(game.includes('JSON.stringify({...world,pickups:boundedCampaignPickups(world.pickups)})'));
  assert.ok(game.includes('import {validateCampaignSave, boundedCampaignPickups, restoreRecoveryPickups'));
});

test('recovery intel remains stage-local, unique and cannot be duplicated in a save', () => {
  const sites=[[4.5,2.5],[12.5,4.5],[8.5,12.5]];
  const intel=(spotIndex)=>({x:sites[spotIndex]?.[0]??4.5,y:sites[spotIndex]?.[1]??2.5,type:'mission-intel',spotIndex,life:3600});
  const state={...fresh(),mission:2,pickups:[intel(0),intel(1)]};
  assert.equal(validateCampaignSave(state),true);
  for(const pickups of [[intel(0),intel(0)],[intel(3)],[{...intel(1),spotIndex:'1'}]]) {
    assert.equal(validateCampaignSave({...state,pickups}),false);
  }
  assert.equal(validateCampaignSave({...fresh(),pickups:[intel(0)]}),false);
  assert.equal(validateCampaignSave({...state,objective:{done:2,hold:0,bossDefeated:false}}),false);
});

test('legacy recovery save with expired intel can finish without losing collected progress', () => {
  const sites=[[4.5,2.5],[12.5,4.5],[8.5,12.5]];
  const state={...fresh(),mission:2,objective:{done:1,hold:0,bossDefeated:false},pickups:[]};
  assert.equal(validateCampaignSave(state),true);
  assert.equal(restoreRecoveryPickups(state,sites),2);
  assert.equal(state.objective.done,1,'repair must not award unearned completion');
  assert.equal(state.pickups.length,2);
  assert.equal(new Set(state.pickups.map(p=>p.spotIndex)).size,2);
  assert.equal(validateCampaignSave(state),true);
  assert.equal(restoreRecoveryPickups(state,sites),0,'repair must be idempotent');
  const cleared={...state,objective:{done:3,hold:0,bossDefeated:false},pickups:[]};
  assert.equal(restoreRecoveryPickups(cleared,sites),0);
  const elsewhere={...state,mission:1,pickups:[]};
  assert.equal(restoreRecoveryPickups(elsewhere,sites),0);
});

test('active recovery collectibles never time out and restored legacy items are wired to the client', () => {
  const game=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  assert.match(game,/restoreRecoveryPickups\(world,OPERATIONS\[2\]\.sites\)/);
  assert.match(game,/if\(p\.type!=='mission-intel'\)p\.life-=dt/);
  assert.match(game,/p\.type!=='mission-intel'&&p\.life<=0/);
});

test('final mission recovers a missing boss without erasing earned campaign progress', () => {
  const s={...fresh(),mission:5,missionKills:8,score:2400,points:6,bossSpawned:true,enemies:[]};
  assert.equal(validateCampaignSave(s),true);
  assert.equal(reconcileBossEncounter(s),true);
  assert.equal(s.bossSpawned,false);
  assert.equal(s.missionKills,8);
  assert.equal(s.score,2400);
  assert.equal(s.points,6);
  assert.equal(reconcileBossEncounter(s),false,'recovery is idempotent');
});
test('a living final boss cannot be duplicated by a corrupted spawn flag', () => {
  const s={...fresh(),mission:5,bossSpawned:false,enemies:[{x:8.5,y:7.5,type:3,hp:410,boss:true}]};
  assert.equal(validateCampaignSave(s),true);
  assert.equal(reconcileBossEncounter(s),true);
  assert.equal(s.bossSpawned,true);
  assert.equal(reconcileBossEncounter(s),false);
});
test('a defeated boss awaiting cleanup does not trigger a duplicate boss spawn', () => {
  const s={...fresh(),mission:5,bossSpawned:false,enemies:[{x:8.5,y:7.5,type:3,hp:-5,boss:true}]};
  assert.equal(validateCampaignSave(s),true);
  assert.equal(reconcileBossEncounter(s),true);
  assert.equal(s.bossSpawned,true,'next tick must process the existing boss death');
});
test('completed and unrelated encounters remain untouched, malformed boss flags fail validation', () => {
  for(const s of [
    {...fresh(),mission:5,bossSpawned:true,objective:{done:0,hold:0,bossDefeated:true}},
    {...fresh(),mission:2,bossSpawned:true},
    {...fresh(),mission:5,missionPassed:true,bossSpawned:true}
  ]) {const before=structuredClone(s);assert.equal(reconcileBossEncounter(s),false);assert.deepEqual(s,before);}
  for(const flag of ['true',1,{},null])assert.equal(validateCampaignSave({...fresh(),bossSpawned:flag}),false);
  assert.equal(validateCampaignSave({...fresh(),enemies:[{x:8,y:7,type:3,hp:40,boss:'yes'}]}),false);
});
test('runtime restores boss flags and spawns a missing boss even when kill quota was reached', () => {
  const client=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  assert.match(client,/reconcileBossEncounter\(world\)/);
  assert.match(client,/world\.mission===5&&!world\.endless&&!world\.bossSpawned&&!world\.objective\?\.bossDefeated/);
});


test('wall-embedded saved player is safely relocated without losing progress or rewards', () => {
  const s={...fresh(),mission:2,x:4.5,y:6.5,score:1250,points:8,missionKills:3,
    objective:{done:1,hold:0,bossDefeated:false}};
  assert.equal(validateCampaignSave(s),true,'numeric-only validation accepts old wall position');
  assert.equal(restorePlayerPosition(s,(x,y)=>x===4&&y===6),true);
  assert.equal(s.x,2.5);
  assert.equal(s.y,7.5);
  assert.equal(s.score,1250);
  assert.equal(s.points,8);
  assert.equal(s.missionKills,3);
  assert.equal(s.objective.done,1);
  assert.equal(restorePlayerPosition(s,(x,y)=>x===4&&y===6),false,'idempotent recovery');
});

test('valid player position is not moved and an unavailable fallback fails closed', () => {
  const valid={...fresh(),x:6.5,y:5.5};
  assert.equal(restorePlayerPosition(valid,(x,y)=>x===4&&y===6),false);
  assert.equal(valid.x,6.5);
  const blocked={...fresh(),x:4.5,y:6.5};
  assert.equal(restorePlayerPosition(blocked,(x,y)=>(x===4&&y===6)||(x===2&&y===7)),false);
  assert.equal(blocked.x,4.5,'do not move to an obstructed fallback');
});

test('campaign restore repairs obstructed player location before engine build', () => {
  const client=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  assert.match(client,/restorePlayerPosition\(world,\(x,y\)=>tile\(x,y\)!==0\);hero=world\.hero/);
});

test('restored time stop expires normally and forged permanent freezes fail closed', () => {
  for (const freeze of [0,.04,2.5,5])
    assert.equal(validateCampaignSave({...fresh(),freeze}),true);
  for (const freeze of [-1,5.01,1e8,Infinity,NaN,'5',null])
    assert.equal(validateCampaignSave({...fresh(),freeze}),false,String(freeze));
});


test('crowded recovery saves retain unique mission intel when the runtime restores 30 pickups', () => {
  const ammo = Array.from({length:57}, (_,i) => ({x:2,y:3,life:20,type:'ammo',serial:i}));
  const sites=[[4.5,2.5],[12.5,4.5],[8.5,12.5]];
  const intel = Array.from({length:3}, (_,i) => ({
    x:sites[i][0],y:sites[i][1],life:3600,type:'mission-intel',spotIndex:i
  }));
  const saved={...fresh(),mission:2,pickups:[...ammo,...intel]};
  assert.equal(validateCampaignSave(saved),true,'crowded saved recovery stage is valid');
  const restored=boundedCampaignPickups(saved.pickups).slice(-30);
  assert.equal(restored.length,30);
  assert.deepEqual(restored.filter(p=>p.type==='mission-intel').map(p=>p.spotIndex),[0,1,2],
    'all original recovery items must survive the runtime cap');
  assert.deepEqual(restored.filter(p=>p.type==='ammo').map(p=>p.serial),
    Array.from({length:27},(_,i)=>i+30),'keep the newest transient drops');
  const resumed={...saved,pickups:restored};
  assert.equal(validateCampaignSave(resumed),true);
  assert.equal(restoreRecoveryPickups(resumed,[[4,5],[5,6],[6,7]]),0,
    'recovery must not create replacement intel when original items were preserved');
  assert.equal(saved.pickups.length,60,'original persisted snapshot is not mutated');
  const client=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  assert.ok(client.includes('world.pickups=boundedCampaignPickups(world.pickups).slice(-30)'),
    'production restore must use the intel-preserving bounded selection');
  assert.ok(!client.includes('world.pickups=(world.pickups||[]).slice(0,30)'),
    'the old first-30 truncation would silently discard mission intel');
});


test('one animation frame owns gameplay after rapid pause/resume and repeated resume clicks', () => {
  const source=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  const start=source.indexOf('let frameQueued=false;');
  const end=source.indexOf('\nfunction playTone(',start);
  assert.ok(start>0&&end>start,'extract the actual production frame scheduler');
  const queued=[];let ticks=0,renders=0;
  const context={screen:'game',last:0,
    requestAnimationFrame:callback=>{queued.push(callback);return queued.length;},
    tick:()=>{ticks++;},render:()=>{renders++;}
  };
  runInNewContext(source.slice(start,end)+'\nglobalThis.schedule=scheduleFrame;',context);
  context.schedule();context.schedule();context.schedule();
  assert.equal(queued.length,1,'multiple resume requests share one pending RAF');
  queued.shift()(16);
  assert.equal(ticks,1);assert.equal(renders,1);
  assert.equal(queued.length,1,'one follow-up frame is queued');
  context.screen='pausePanel';
  queued.shift()(32);
  assert.equal(ticks,1,'paused frame must not advance the simulation');
  assert.equal(queued.length,0,'paused frame must not reschedule itself');
  context.screen='game';context.schedule();context.schedule();
  assert.equal(queued.length,1,'resume schedules exactly one new frame');
  context.screen='pausePanel';context.screen='game';context.schedule();
  assert.equal(queued.length,1,'rapid pause/resume reuses an already pending frame');
  queued.shift()(48);
  assert.equal(ticks,2,'rapid toggles must not double the simulation speed');
  assert.equal(renders,2);
  assert.equal(queued.length,1);
  const callSites=(source.match(/scheduleFrame\(\)/g)||[]).length;
  assert.ok(callSites>=7,'all gameplay resume paths must use the single-flight scheduler');
  assert.equal((source.match(/requestAnimationFrame\(frame\)/g)||[]).length,1,
    'only the scheduler itself may request an animation frame');
});


test('public Ramadan telemetry cannot mutate the campaign or invoke QA-only controls', () => {
  const source=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  const start=source.indexOf('const qaIsLocal=');
  const end=source.indexOf(';if(storageRead(saveKey))',start);
  assert.ok(start>0&&end>start,'extract the actual published debug API setup');
  const world={objective:{done:1,hold:0},enemies:[],mission:0,hero:0,endless:false};
  const makeContext=hostname=>({
    window:{},location:{hostname},NAMES:['Hero'],SKILLS:['Skill'],
    world,screen:'game',engine:{stats:()=>({renderer:'webgl-threejs'})},
    plan:()=>({kind:'activate'}),objectiveTarget:()=>2,
    fire:()=>{},launchRocket:()=>{},droneStrike:()=>{},tick:()=>{},interactObjective:()=>{}
  });
  const publicContext=makeContext('zomorodmelal.ir');
  runInNewContext(source.slice(start,end),publicContext);
  const publicApi=publicContext.window.RamadanWarDebug;
  assert.deepEqual(Object.keys(publicApi),['heroes','skills','getState']);
  assert.equal(Object.isFrozen(publicApi),true);
  assert.equal(publicApi.tick,undefined);
  assert.equal(publicApi.start,undefined);
  assert.equal(publicApi.spawnTestEnemy,undefined);
  assert.equal(publicApi.spawnTestPickup,undefined);
  const telemetry=publicApi.getState();
  telemetry.objective.done=999;
  assert.equal(world.objective.done,1,'public telemetry must not expose mutable campaign references');
  const localContext=makeContext('localhost');
  runInNewContext(source.slice(start,end),localContext);
  assert.equal(typeof localContext.window.RamadanWarDebug.tick,'function');
  assert.equal(typeof localContext.window.RamadanWarDebug.qaMission,'function');
});


test('new recovery saves restore only uncollected intel sites and remain idempotent', () => {
  const sites=[[4.5,2.5],[12.5,4.5],[8.5,12.5]];
  const intel=i=>({x:sites[i][0],y:sites[i][1],type:'mission-intel',spotIndex:i,life:3600});
  const state={...fresh(),mission:2,objective:{done:1,hold:0,bossDefeated:false,collectedSites:[0]},pickups:[intel(1)]};
  assert.equal(validateCampaignSave(state),true);
  assert.equal(restoreRecoveryPickups(state,sites),1);
  assert.deepEqual(state.pickups.filter(p=>p.type==='mission-intel').map(p=>p.spotIndex).sort(),[1,2]);
  assert.equal(restoreRecoveryPickups(state,sites),0);
  assert.deepEqual(state.objective.collectedSites,[0]);
  assert.equal(validateCampaignSave(state),true);
});

test('new recovery ledger rejects forged rewards, duplicate sites and pickup overlap', () => {
  const sites=[[4.5,2.5],[12.5,4.5],[8.5,12.5]];
  const intel=i=>({x:sites[i][0],y:sites[i][1],type:'mission-intel',spotIndex:i,life:3600});
  const state={...fresh(),mission:2,objective:{done:1,hold:0,bossDefeated:false,collectedSites:[0]},pickups:[intel(1),intel(2)]};
  assert.equal(validateCampaignSave(state),true);
  for(const collectedSites of [[0,0],[0,3],['0'],[0,1],[],null]) {
    assert.equal(validateCampaignSave({...state,objective:{...state.objective,collectedSites}}),false,String(collectedSites));
  }
  assert.equal(validateCampaignSave({...state,pickups:[intel(0),intel(1)]}),false,'collected site must never be re-awarded');
  assert.equal(validateCampaignSave({...fresh(),objective:{...fresh().objective,collectedSites:[]}}),false,'ledger belongs only to recovery stage');
});

test('legacy recovery with missing pickups remains playable but never invents provenance', () => {
  const sites=[[4.5,2.5],[12.5,4.5],[8.5,12.5]];
  const state={...fresh(),mission:2,objective:{done:1,hold:0,bossDefeated:false},pickups:[]};
  assert.equal(restoreRecoveryPickups(state,sites),2);
  assert.equal(state.objective.done,1);
  assert.equal(state.objective.collectedSites,undefined,'cannot assert which legacy site was collected');
  assert.equal(validateCampaignSave(state),true);
});

test('campaign interaction, timed defence and intel rewards save immediately', () => {
  const client=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  assert.match(client,/o\.done\+\+;world\.score\+=250;[^\n]*sync\(\);save\(\);return true;/);
  assert.match(client,/o\.done=1;toast\('دفاع موفق • موقعیت تثبیت شد'\);save\(\)/);
  assert.match(client,/o\.collectedSites\.push\(index\);/);
  assert.match(client,/toast\('اطلاعات حیاتی بازیابی شد'\);sync\(\);save\(\);continue/);
});
