'use strict';
const assert = require('node:assert/strict');
const core = require('./nexus-core.js');

let physicalBlockLevels = 0;
let sourceLevels = 0;
for (let level = 1; level <= 240; level++) {
  const puzzle = core.generate(level);
  if (level < 35 || level % 20 === 0) assert.deepEqual(core.generate(level), puzzle);
  assert.equal(puzzle.signature, 'NEXUS3D-WORM-1');
  const occupied = new Set();
  for (const piece of puzzle.pieces) {
    const key = [piece.face, piece.u, piece.v].join(':');
    assert.ok(!occupied.has(key), 'duplicate head '+level);
    occupied.add(key);
    assert.ok(piece.path.length >= 7, 'worm too short '+level);
    assert.deepEqual(piece.path[piece.path.length - 1], [piece.u, piece.v]);
    assert.ok(piece.path.every(([u,v]) => Math.max(Math.abs(u),Math.abs(v))<=1.44),
      'body outside face '+level);
    const turns = piece.path.slice(2).reduce((total, point, index) => {
      const a = piece.path[index], b = piece.path[index+1];
      return total + (Math.abs((b[0]-a[0])*(point[1]-b[1]) -
        (b[1]-a[1])*(point[0]-b[0])) > .01 ? 1 : 0);
    }, 0);
    assert.ok(turns >= 2, 'worm does not bend '+level);
  }
  const start = core.initialState(puzzle);
  const blocked = puzzle.pieces.filter(piece => core.blockers(piece, start).length);
  if (blocked.length >= 2) physicalBlockLevels++;
  assert.ok(blocked.length >= 2, 'not a real untangling puzzle '+level);
  if (level < 9) assert.ok(puzzle.pieces.every(p=>p.gate===null));
  if (level >= 9) {
    sourceLevels++;
    assert.equal(puzzle.pieces[1].gate,'link');
    assert.equal(core.canExit(1,start),false);
  }
  if (level >= 12) {
    assert.equal(puzzle.pieces[2].gate,'phase');
    assert.ok(puzzle.solution.some(move=>move.type==='twist'));
  }
  if (level >= 20) assert.equal(puzzle.pieces[3].gate,'relay');
  if (level >= 24) assert.equal(puzzle.pieces[4].gate,'charge');
  let state=start;
  for (const move of puzzle.solution) {
    state=core.transition(state,move);
    assert.ok(state,'invalid solver move '+level);
  }
  assert.equal(state.removed.length,puzzle.pieces.length,'unsolved '+level);
  assert.deepEqual(core.solve(puzzle,state),[]);
}
// Exit checks look at the OTHER ARROW'S BODY, not just its head.
const escaping={id:0,face:'front',u:0,v:0,dir:0,path:[[0,-1],[0,0]]};
const cross={id:1,face:'front',u:1,v:1,dir:1,path:[[1,-.6],[1,.6],[1,1]]};
assert.equal(core.wormBlocks(escaping,cross),true);
const clear={...cross,path:[[1,1],[1.2,1.2]]};
assert.equal(core.wormBlocks(escaping,clear),false);
let turned={id:4,face:'front',u:0,v:0,dir:1,path:[[-.4,0],[-.2,0],[0,0]]};
const copy=JSON.parse(JSON.stringify(turned));
for(let i=0;i<4;i++) turned=core.twistPiece(turned,0,1);
assert.deepEqual(turned,copy);
assert.equal(core.generate(Infinity).level,1,'nonfinite Nexus level must be rejected');
assert.equal(core.generate(NaN).level,1,'NaN Nexus level must be rejected');
assert.equal(core.generate(-5).level,1,'negative Nexus level must normalize');
assert.equal(core.generate(1e30).level,100000,'extreme Nexus level must be bounded');
console.log('NEXUS_WORM_CORE_QA=PASS',{levels:240,physicalBlockLevels,sourceLevels});
