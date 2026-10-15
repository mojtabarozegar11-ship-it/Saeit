"use strict";
/* Independent runnable product self-test with Node built-in assertions. */
const assert=require("node:assert/strict");
const e=require("./engine.js");
assert.equal(e.SIZE,6);assert.equal(e.COUNT,36);
const seen=new Set();
let maxLength=0,minLength=Infinity;
for(let n=1;n<=36;n++){
  const level=e.generateLevel(n);
  const regenerated=e.generateLevel(n);
  assert.deepEqual(level,regenerated,"level must reproduce offline");
  assert.equal(level.beacons.length,3);
  assert.equal(new Set(level.beacons).size,3);
  assert.equal(new Set(level.walls).size,level.walls.length);
  for(const cell of [...level.walls,...level.beacons]){
    assert(Number.isInteger(cell)&&cell>=0&&cell<36);
    assert(cell!==level.start&&cell!==level.exit);
  }
  assert(level.beacons.every(c=>!level.walls.includes(c)));
  const pattern=JSON.stringify([level.walls,level.beacons]);
  assert(!seen.has(pattern),"every stage needs distinct topology");
  seen.add(pattern);
  const path=e.shortestRoute(level);
  assert(typeof path==="string"&&path.length>=10);
  assert.equal(path.length,level.optimalMoves);
  assert(level.energyBudget>level.optimalMoves);
  maxLength=Math.max(maxLength,path.length);
  minLength=Math.min(minLength,path.length);
  let game=e.fresh(n);
  assert.equal(game.status,"playing");
  const impossible=e.apply(game,"left");
  assert.strictEqual(impossible,game,"out of bounds moves cost no energy");
  let used=0;
  for(const char of path){
    const direction=e.decode(char);
    assert(direction);
    assert.equal(e.hint(game),direction);
    game=e.apply(game,direction);
    used++;
  }
  assert.equal(game.status,"won",n+" route should win");
  assert.equal(game.moves,path.length);
  assert.equal(game.mask,7);
  assert.equal(game.at,e.EXIT);
  assert.equal(e.award(game),3);
  assert.equal(e.apply(game,"up"),game,"won game immutable");
  const assisted={...game,assisted:true};
  assert.equal(e.award(assisted),1);
}
assert.equal(seen.size,36);
assert.equal(e.shortestRoute(e.generateLevel(1),e.EXIT,7),"");
assert.throws(()=>e.generateLevel(0),/stage/);
assert.throws(()=>e.generateLevel(37),/stage/);
assert.throws(()=>e.apply(e.fresh(1),"teleport"),/unknown direction/);
console.log("ASTRA_CIRCUIT_COURIER_36_VERIFIED_SOLVABLE=PASS");
console.log("ASTRA_CIRCUIT_COURIER_BFS_OPTIMAL_MOVES_MIN="+minLength);
console.log("ASTRA_CIRCUIT_COURIER_BFS_OPTIMAL_MOVES_MAX="+maxLength);
console.log("ASTRA_CIRCUIT_COURIER_NODE_TEST=PASS");
