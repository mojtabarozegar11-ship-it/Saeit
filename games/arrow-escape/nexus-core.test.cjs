'use strict';
const assert = require('node:assert/strict');
const core = require('./nexus-core.js');

let twistStages = 0;
let causalStages = 0;
for (let level = 1; level <= 240; level++) {
  const puzzle = core.generate(level);
  assert.deepEqual(core.generate(level), puzzle, 'seed must be reproducible ' + level);
  const occupied = new Set();
  for (const piece of puzzle.pieces) {
    const coords = [piece.face, piece.u, piece.v].join(',');
    assert.ok(!occupied.has(coords), 'two arrows occupy same surface cell ' + level);
    occupied.add(coords);
  }
  if (level >= 2) {
    causalStages++;
    assert.equal(puzzle.pieces[1].gate, 'link');
    assert.equal(core.canExit(1, core.initialState(puzzle)), false);
  }
  if (level >= 8) {
    assert.equal(puzzle.pieces[3].gate, 'relay');
    assert.deepEqual(puzzle.pieces[3].sources, [0, 1]);
    assert.equal(core.canExit(3, core.initialState(puzzle)), false);
  }
  if (level >= 12) {
    assert.equal(puzzle.pieces[4].gate, 'charge');
    assert.equal(core.canExit(4, core.initialState(puzzle)), false);
    assert.ok(puzzle.pieces.length <= 12);
  }
  if (level >= 4) {
    twistStages++;
    assert.equal(puzzle.pieces[2].gate, 'phase');
    assert.equal(core.canExit(2, core.initialState(puzzle)), false);
    assert.ok(puzzle.solution.some(move => move.type === 'twist'), 'twist is required ' + level);
  }
  let state = core.initialState(puzzle);
  for (const move of puzzle.solution) {
    const next = core.transition(state, move);
    assert.ok(next, 'invalid move ' + level + ' ' + JSON.stringify(move));
    state = next;
  }
  assert.equal(state.removed.length, puzzle.pieces.length, 'incomplete solver result ' + level);
  assert.deepEqual(core.solve(puzzle, state), []);
}

for (const face of core.FACE_NAMES) for (let u = -1; u <= 1; u++)
  for (let v = -1; v <= 1; v++) for (let dir = 0; dir < 4; dir++) {
    const original = { id: 0, face, u, v, dir };
    let rotated = original;
    for (let turn = 0; turn < 4; turn++) rotated = core.twistPiece(rotated, 0, 1);
    assert.deepEqual(rotated, original, 'four turns must restore piece geometry');
    assert.deepEqual(core.twistPiece(core.twistPiece(original, 0, 1), 0, -1), original,
      'turn left must reverse turn right');
  }
const invalid = core.generate(4);
assert.equal(core.transition(core.initialState(invalid), { type: 'remove', id: 2 }), null);
assert.equal(core.transition(core.initialState(invalid), { type: 'twist', step: 0 }), null);
console.log('NEXUS_CORE_QA=PASS', { stages: 240, twistStages, causalStages, surfaces: 216 });
