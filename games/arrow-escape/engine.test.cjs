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
// Malformed saved/imported puzzle data must fail closed, not throw inside the UI.
const validPiece = {id: 1, dir: 0, path: [{x: 2, y: 2}, {x: 3, y: 2}]};
for (const invalid of [
  null,
  {...validPiece, dir: -1},
  {...validPiece, dir: 4},
  {...validPiece, dir: NaN},
  {...validPiece, path: []},
  {...validPiece, path: [{x: Infinity, y: 2}]},
  {...validPiece, path: [{x: 100, y: 2}]}
]) assert.equal(game.canExit(invalid, [validPiece], 7), false);
assert.equal(game.canExit(validPiece, [null], 7), false);
assert.equal(game.canExit(validPiece, [validPiece], NaN), false);
assert.equal(game.canExit(validPiece, null, 7), false);
assert.ok(withBlockers > 10, 'levels contain no challenging dependencies');
console.log('ARROW_SOLVABLE_LEVELS=PASS', { tested, withBlockers, min, max });
