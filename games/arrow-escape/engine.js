/* Arrow Escape: deterministic, dependency-free, solvable puzzle generation.
 * Each arrow is a self-avoiding grid path. It leaves the board by translating
 * its entire shape in the direction of its final segment. A collision anywhere
 * along that swept path blocks the move.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ArrowMazeCore = api;
})(typeof window !== 'undefined' ? window : undefined, function () {
  'use strict';
  const DIRECTIONS = [[1, 0], [0, 1], [-1, 0], [0, -1]];
  const key = (x, y) => x + ',' + y;
  function seededRandom(seed) {
    let state = (seed >>> 0) || 0x9e3779b9;
    return function () {
      state ^= state << 13;
      state ^= state >>> 17;
      state ^= state << 5;
      return (state >>> 0) / 4294967296;
    };
  }
  function canExit(piece, others, size) {
    if (!piece || !Number.isInteger(piece.dir) || piece.dir < 0 || piece.dir >= DIRECTIONS.length ||
        !Array.isArray(piece.path) || !piece.path.length || !Array.isArray(others) ||
        !Number.isInteger(size) || size < 1 || size > 100) return false;
    // Fail closed on damaged or imported puzzle data instead of allowing phantom exits.
    const validPoint = p => p && Number.isInteger(p.x) && Number.isInteger(p.y) &&
      p.x >= 0 && p.y >= 0 && p.x < size && p.y < size;
    if (!piece.path.every(validPoint)) return false;
    const occupied = new Set();
    for (const other of others) {
      if (!other || !Array.isArray(other.path) || !other.path.length ||
          !other.path.every(validPoint)) return false;
      if (other.id === piece.id) continue;
      for (const p of other.path) occupied.add(key(p.x, p.y));
    }
    const [dx, dy] = DIRECTIONS[piece.dir];
    for (let shift = 1; shift <= size * 2 + 3; shift++) {
      let visible = false;
      for (const p of piece.path) {
        const x = p.x + dx * shift;
        const y = p.y + dy * shift;
        if (x < 0 || y < 0 || x >= size || y >= size) continue;
        visible = true;
        if (occupied.has(key(x, y))) return false;
      }
      if (!visible) return true;
    }
    return false;
  }
  function solve(pieces, size) {
    if (!Array.isArray(pieces) || !Number.isInteger(size) || size < 1 || size > 100) return null;
    const remaining = pieces.slice();
    const order = [];
    while (remaining.length) {
      const index = remaining.findIndex(piece => canExit(piece, remaining, size));
      if (index < 0) return null;
      order.push(remaining[index].id);
      remaining.splice(index, 1);
    }
    return order;
  }
  function makeCandidate(rng, size, occupied, id, level) {
    const path = [];
    const used = new Set();
    const x = Math.floor(rng() * size);
    const y = Math.floor(rng() * size);
    if (occupied.has(key(x, y))) return null;
    path.push({ x, y });
    used.add(key(x, y));
    let dir = Math.floor(rng() * 4);
    const maxLength = Math.min(7, 3 + Math.floor(level / 16));
    const intended = 2 + Math.floor(rng() * (maxLength - 1));
    let turns = 0;
    for (let n = 1; n < intended; n++) {
      const options = [dir, dir, dir, (dir + 1) % 4, (dir + 3) % 4];
      const rotated = Math.floor(rng() * options.length);
      let chosen = -1;
      for (let i = 0; i < options.length; i++) {
        const trial = options[(rotated + i) % options.length];
        if (trial !== dir && turns >= 2) continue;
        const nx = path[path.length - 1].x + DIRECTIONS[trial][0];
        const ny = path[path.length - 1].y + DIRECTIONS[trial][1];
        if (nx < 0 || ny < 0 || nx >= size || ny >= size ||
            occupied.has(key(nx, ny)) || used.has(key(nx, ny))) continue;
        chosen = trial;
        break;
      }
      if (chosen < 0) break;
      if (chosen !== dir) turns++;
      dir = chosen;
      const p = path[path.length - 1];
      const next = { x: p.x + DIRECTIONS[dir][0], y: p.y + DIRECTIONS[dir][1] };
      path.push(next);
      used.add(key(next.x, next.y));
    }
    return path.length >= 2 ? { id, dir, path } : null;
  }
  function generate(level) {
    const requested = Number(level);
    const number = Number.isFinite(requested) ? Math.max(1, Math.min(1000000, Math.floor(requested))) : 1;
    const size = Math.min(11, 7 + Math.floor((number - 1) / 20));
    const target = Math.min(22, 6 + Math.floor((number - 1) * 0.62));
    const rng = seededRandom((Math.imul(number, 2654435761) ^ 0x6d2b79f5) >>> 0);
    let best = [];
    for (let pass = 0; pass < 3; pass++) {
      const pieces = [];
      const occupied = new Set();
      for (let attempts = 0; attempts < target * 170 && pieces.length < target; attempts++) {
        const piece = makeCandidate(rng, size, occupied, pieces.length, number);
        if (!piece) continue;
        const group = [...pieces, piece];
        if (!solve(group, size)) continue;
        pieces.push(piece);
        for (const p of piece.path) occupied.add(key(p.x, p.y));
      }
      if (pieces.length > best.length) best = pieces;
      if (best.length >= target) break;
    }
    return {
      level: number,
      size,
      pieces: best,
      solution: solve(best, size) || [],
      target
    };
  }
  return { DIRECTIONS, canExit, solve, generate };
});
