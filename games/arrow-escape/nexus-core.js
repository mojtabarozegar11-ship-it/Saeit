/* ARROW NEXUS 3D — deterministic, solver-verified six-face puzzle engine.
 * All mechanics are independent of the renderer and do not require network access.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ArrowNexusCore = api;
})(typeof window !== 'undefined' ? window : undefined, function () {
  'use strict';

  const FACES = Object.freeze({
    front:  { n: [0, 0, 1],  u: [1, 0, 0],  v: [0, 1, 0] },
    right:  { n: [1, 0, 0],  u: [0, 0, -1], v: [0, 1, 0] },
    back:   { n: [0, 0, -1], u: [-1, 0, 0], v: [0, 1, 0] },
    left:   { n: [-1, 0, 0], u: [0, 0, 1],  v: [0, 1, 0] },
    top:    { n: [0, 1, 0],  u: [1, 0, 0],  v: [0, 0, -1] },
    bottom: { n: [0, -1, 0], u: [1, 0, 0],  v: [0, 0, 1] }
  });
  const FACE_NAMES = Object.keys(FACES);
  const DIRS = [[1, 0], [0, 1], [-1, 0], [0, -1]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const plus = (a, b) => a.map((x, i) => x + b[i]);
  const scale = (a, n) => a.map(x => x * n);
  const position = p => {
    const f = FACES[p.face];
    return plus(plus(f.n, scale(f.u, p.u)), scale(f.v, p.v));
  };
  const tangent = p => {
    const f = FACES[p.face];
    const d = DIRS[p.dir];
    return plus(scale(f.u, d[0]), scale(f.v, d[1]));
  };
  function rotateY(v, step) { return step === 1 ? [v[2], v[1], -v[0]] : [-v[2], v[1], v[0]]; }
  function twistPiece(piece, ring, step) {
    const p = position(piece);
    if (p[1] !== ring) return { ...piece };
    const normal = rotateY(FACES[piece.face].n, step);
    const face = FACE_NAMES.find(name => dot(FACES[name].n, normal) === 1);
    const rotatedPosition = rotateY(p, step);
    const rotatedTangent = rotateY(tangent(piece), step);
    const f = FACES[face];
    const u = dot(rotatedPosition, f.u);
    const v = dot(rotatedPosition, f.v);
    const dx = dot(rotatedTangent, f.u);
    const dy = dot(rotatedTangent, f.v);
    const dir = DIRS.findIndex(d => d[0] === dx && d[1] === dy);
    if (dir < 0) throw new Error('Invalid tangent after twist');
    const path = piece.path?.map(([pu, pv]) => {
      const point = plus(plus(FACES[piece.face].n, scale(FACES[piece.face].u, pu)), scale(FACES[piece.face].v, pv));
      const turned = rotateY(point, step);
      return [dot(turned, f.u), dot(turned, f.v)];
    });
    return { ...piece, face, u, v, dir, ...(path ? { path } : {}) };
  }
  function initialState(levelData) {
    return {
      pieces: levelData.pieces.map(p => ({ ...p, ...(p.path ? { path: p.path.map(v => v.slice()) } : {}) })),
      removed: [], phase: 0, twistsLeft: levelData.maxTwists
    };
  }
  function isUnlocked(piece, state) {
    if (piece.gate === 'link' && !state.removed.includes(piece.source)) return false;
    if (piece.gate === 'phase' && state.phase !== piece.targetPhase) return false;
    if (piece.gate === 'relay' && !piece.sources.every(id => state.removed.includes(id))) return false;
    if (piece.gate === 'charge' && state.removed.length < piece.required) return false;
    return true;
  }
  function pointSegmentDistanceSq(p, a, b) {
    const vx = b[0] - a[0], vy = b[1] - a[1];
    const denom = vx * vx + vy * vy;
    const t = denom ? Math.max(0, Math.min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / denom)) : 0;
    const x = a[0] + vx * t - p[0], y = a[1] + vy * t - p[1];
    return x * x + y * y;
  }
  function segmentsTouch(a, b, c, d, radius = .19) {
    const cross = (v, w) => v[0] * w[1] - v[1] * w[0];
    const r = [b[0] - a[0], b[1] - a[1]], s = [d[0] - c[0], d[1] - c[1]];
    const q = [c[0] - a[0], c[1] - a[1]], denom = cross(r, s);
    if (Math.abs(denom) > 1e-8) {
      const t = cross(q, s) / denom, u = cross(q, r) / denom;
      if (t >= 0 && t <= 1 && u >= 0 && u <= 1) return true;
    }
    const limit = radius * radius;
    return pointSegmentDistanceSq(a, c, d) < limit ||
      pointSegmentDistanceSq(b, c, d) < limit ||
      pointSegmentDistanceSq(c, a, b) < limit ||
      pointSegmentDistanceSq(d, a, b) < limit;
  }
  function wormBlocks(piece, other) {
    const [dx, dy] = DIRS[piece.dir];
    const start = [piece.u + dx * .13, piece.v + dy * .13];
    const end = [piece.u + dx * 2.6, piece.v + dy * 2.6];
    const nodes = other.path || [[other.u, other.v]];
    if (nodes.length === 1) return pointSegmentDistanceSq(nodes[0], start, end) < .19 ** 2;
    return nodes.slice(1).some((next, i) => segmentsTouch(start, end, nodes[i], next));
  }
  function blockers(piece, state) {
    return state.pieces.filter(other => other.id !== piece.id &&
      !state.removed.includes(other.id) && other.face === piece.face && wormBlocks(piece, other));
  }
  function canExit(pieceOrId, state) {
    const piece = typeof pieceOrId === 'object' ? pieceOrId : state.pieces.find(p => p.id === pieceOrId);
    return Boolean(piece) && !state.removed.includes(piece.id) &&
      isUnlocked(piece, state) && blockers(piece, state).length === 0;
  }
  function actions(state) {
    const choices = state.pieces.filter(p => canExit(p, state)).map(p => ({ type: 'remove', id: p.id }));
    if (state.twistsLeft > 0) {
      choices.push({ type: 'twist', step: 1 }, { type: 'twist', step: -1 });
    }
    return choices;
  }
  function transition(state, action) {
    if (action.type === 'remove') {
      if (!canExit(action.id, state)) return null;
      return { ...state, removed: [...state.removed, action.id] };
    }
    if (action.type === 'twist') {
      if (![-1, 1].includes(action.step) || state.twistsLeft <= 0) return null;
      return {
        ...state, pieces: state.pieces.map(p => twistPiece(p, 0, action.step)),
        twistsLeft: state.twistsLeft - 1,
        phase: (state.phase + action.step + 4) % 4
      };
    }
    return null;
  }
  function fingerprint(state) {
    return [state.removed.slice().sort((a, b) => a - b).join(','), state.phase,
      state.twistsLeft, state.pieces.map(p => [p.face, p.u, p.v, p.dir].join(':')).join('|')].join('~');
  }
  function solve(levelData, start, maxVisited = 50000) {
    const state = start || initialState(levelData);
    const visited = new Set();
    function visit(current, path) {
      if (current.removed.length === current.pieces.length) return path;
      if (visited.size >= maxVisited) return null;
      const key = fingerprint(current);
      if (visited.has(key)) return null;
      visited.add(key);
      for (const action of actions(current)) {
        const result = visit(transition(current, action), [...path, action]);
        if (result) return result;
      }
      return null;
    }
    return visit(state, []);
  }
  function rngFor(seed) {
    let state = (seed >>> 0) || 1;
    return () => {
      state ^= state << 13; state ^= state >>> 17; state ^= state << 5;
      return (state >>> 0) / 4294967296;
    };
  }
  // A worm is one continuous curved arrow, never a single square tile.
  // Every body point participates in physical exit-ray collision checks.
  function makeWormPath(piece, random) {
    const [dx, dy] = DIRS[piece.dir];
    const head = [piece.u, piece.v];
    let best = null;
    for (let attempt = 0; attempt < 16; attempt++) {
      const points = [head];
      let heading = [-dx, -dy], turns = 0;
      const steps = 8 + Math.floor(random() * 3);
      for (let i = 0; i < steps; i++) {
        const choices = i === 0 ? [heading] :
          [[-heading[1], heading[0]], [heading[1], -heading[0]], heading];
        const order = choices.map((dir, idx) => ({ dir, score: random() + (idx < 2 && i % 2 === 0 ? 1.0 : 0) }))
          .sort((x, y) => y.score - x.score);
        let selected = null;
        for (const { dir } of order) {
          const last = points[points.length - 1];
          const next = [Number((last[0] + dir[0] * .36).toFixed(3)),
            Number((last[1] + dir[1] * .36).toFixed(3))];
          if (Math.max(Math.abs(next[0]), Math.abs(next[1])) > 1.44) continue;
          if (points.slice(0, -2).some(p => Math.hypot(next[0] - p[0], next[1] - p[1]) < .28)) continue;
          selected = { dir, next };
          break;
        }
        if (!selected) break;
        if (selected.dir[0] !== heading[0] || selected.dir[1] !== heading[1]) turns++;
        heading = selected.dir;
        points.push(selected.next);
      }
      const result = points.reverse();
      if (!best || result.length > best.path.length || (result.length === best.path.length && turns > best.turns))
        best = { path: result, turns };
      if (result.length >= 8 && turns >= 3) return result;
    }
    return best.path;
  }
  function generate(level) {
    const requested = Number(level);
    const number = Number.isFinite(requested) ? Math.max(1, Math.min(100000, Math.floor(requested))) : 1;
    const random = rngFor((Math.imul(number, 2654435761) ^ 0x9e3779b9) >>> 0);
    const advanced = number >= 12;
    const count = Math.min(12, 5 + Math.floor(number / 3));
    const maxTwists = advanced ? 2 : 0;
    const layout = ['front', 'front', 'front', 'right', 'front', 'top',
      'front', 'right', 'front', 'top', 'right', 'front'];
    let fallback;
    for (let attempt = 0; attempt < 90; attempt++) {
      const available = {};
      for (const face of FACE_NAMES) {
        available[face] = [];
        for (let u = -1; u <= 1; u++) for (let v = -1; v <= 1; v++) {
          if (u !== 0 || v !== 0) available[face].push({ face, u, v });
        }
        for (let i = available[face].length - 1; i > 0; i--) {
          const j = Math.floor(random() * (i + 1));
          [available[face][i], available[face][j]] = [available[face][j], available[face][i]];
        }
      }
      const pieces = Array.from({ length: count }, (_, id) => {
        const place = available[layout[id]].pop();
        const piece = { ...place, id, dir: Math.floor(random() * 4),
          gate: null, source: null, targetPhase: 0, layer: id % 4 };
        piece.path = makeWormPath(piece, random);
        return piece;
      });
      // Untangling the arrows themselves is the complete opening gameplay.
      // Circuit/rotation modifiers begin only after the player learns the worm mechanic.
      if (number >= 9) { pieces[1].gate = 'link'; pieces[1].source = 0; }
      if (advanced) { pieces[2].gate = 'phase'; pieces[2].targetPhase = 1; }
      if (number >= 20) { pieces[3].gate = 'relay'; pieces[3].sources = [0, 1]; }
      if (number >= 24) { pieces[4].gate = 'charge'; pieces[4].required = 3; }
      const candidate = { level: number, pieces, maxTwists, signature: 'NEXUS3D-WORM-1' };
      const solution = solve(candidate);
      if (!solution) continue;
      const blocked = pieces.filter(p => blockers(p, initialState(candidate)).length > 0).length;
      const otherBodyBlock = pieces.some(p => {
        const [dx, dy] = DIRS[p.dir];
        return blockers(p, initialState(candidate)).some(other =>
          Math.abs(other.u - p.u) > .001 || Math.abs(other.v - p.v) > .001);
      });
      if (!fallback || blocked > fallback.blocked) fallback = { candidate, solution, blocked };
      if (blocked >= Math.min(2, count - 2) && otherBodyBlock) return { ...candidate, solution };
    }
    if (fallback) return { ...fallback.candidate, solution: fallback.solution };
    throw new Error('Could not generate a solvable worm level: ' + number);
  }

  return { FACES, FACE_NAMES, DIRS, position, tangent, twistPiece, makeWormPath, wormBlocks,
    initialState, blockers, canExit, actions, transition, solve, generate };
});
