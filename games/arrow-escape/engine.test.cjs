'use strict';
const assert = require('node:assert/strict');
const game = require('./engine.js');
let tested = 0, withBlockers = 0, min = Infinity, max = 0;
for (const level of [...Array(200)].map((_, index) => index + 1).concat([500, 999, 10000, 50000])) {
  const board = game.generate(level);
  assert.equal(board.level, level);
  assert.ok(board.size >= 7 && board.size <= 11);
  assert.ok(board.pieces.length >= 4, 'too few pieces at level ' + level);
  assert.deepEqual(game.generate(level), board, 'non-deterministic board ' + level);
  min = Math.min(min, board.pieces.length);
  max = Math.max(max, board.pieces.length);
  const global = new Set();
  for (const piece of board.pieces) {
    assert.ok(piece.path.length >= 2);
    const perPiece = new Set();
    for (const point of piece.path) {
      assert.ok(point.x >= 0 && point.x < board.size && point.y >= 0 && point.y < board.size);
      const coordinate = point.x + ',' + point.y;
      assert.ok(!global.has(coordinate), 'overlap: ' + level);
      assert.ok(!perPiece.has(coordinate), 'self-intersection: ' + level);
      perPiece.add(coordinate);
      global.add(coordinate);
    }
    if (!game.canExit(piece, board.pieces, board.size)) withBlockers++;
  }
  const solution = game.solve(board.pieces, board.size);
  assert.ok(solution && solution.length === board.pieces.length, 'unsolvable: ' + level);
  const remaining = board.pieces.slice();
  for (const id of solution) {
    const index = remaining.findIndex(piece => piece.id === id);
    assert.ok(index >= 0);
    assert.equal(game.canExit(remaining[index], remaining, board.size), true);
    remaining.splice(index, 1);
  }
  assert.equal(remaining.length, 0);
  tested++;
}
assert.equal(game.generate(Infinity).level,1,'infinite level must be rejected safely');
assert.equal(game.generate(NaN).level,1,'NaN level must be rejected safely');
assert.equal(game.generate(-20).level,1,'negative level must normalize to first level');
assert.equal(game.generate(1e30).level,1000000,'extreme level must be bounded');
assert.ok(withBlockers > 10, 'levels contain no challenging dependencies');
console.log('ARROW_SOLVABLE_LEVELS=PASS', { tested, withBlockers, min, max });
