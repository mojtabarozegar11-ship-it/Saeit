const assert = require('node:assert/strict');
const Cube = require('./cube-engine.js');

for (let level = 1; level <= 250; level++) {
  const puzzle = Cube.generate(level);
  assert.deepEqual(Cube.generate(level), puzzle, `non-deterministic cube at level ${level}`);
  assert.equal(puzzle.faces.length, 6);
  assert.equal(new Set(puzzle.faces.map(f => f.name)).size, 6);
  assert.ok(puzzle.total >= 48 && puzzle.total <= 108);
  assert.equal(puzzle.faces.reduce((n, f) => n + f.pieces.length, 0), puzzle.total);
  const pieces = puzzle.faces.flatMap(face => face.pieces);
  assert.equal(new Set(pieces.map(p => p.id)).size, puzzle.total);
  const order = Cube.solution(puzzle);
  assert.ok(order && order.length === puzzle.total, `unsolvable level ${level}`);
  const removed = new Set();
  for (const id of order) {
    const piece = pieces.find(p => p.id === id);
    assert.ok(Cube.canExit(puzzle, piece, removed), `blocked arrow ${id} at level ${level}`);
    removed.add(id);
  }
  assert.deepEqual(Cube.solution(puzzle, removed), []);
}
console.log('ARROW_CUBE_3D_250_LEVELS_AND_ALL_EXIT_MOVES=PASS');
