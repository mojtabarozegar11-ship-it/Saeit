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
    return { ...piece, face, u, v, dir };
  }
  function initialState(levelData) {
    return {
      pieces: levelData.pieces.map(p => ({ ...p })),
      removed: [], phase: 0, twistsLeft: levelData.maxTwists
    };
  }
  function isUnlocked(piece, state) {
    if (piece.gate === 'link' && !state.removed.includes(piece.source)) return false;
    if (piece.gate === 'phase' && state.phase !== piece.targetPhase) return false;
    return true;
  }
  function blockers(piece, state) {
    const [dx, dy] = DIRS[piece.dir];
    return state.pieces.filter(other => other.id !== piece.id &&
      !state.removed.includes(other.id) && other.face === piece.face &&
      Array.from({ length: 2 }, (_, i) => i + 1).some(distance =>
        other.u === piece.u + dx * distance && other.v === piece.v + dy * distance));
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
  function generate(level) {
    const number = Math.max(1, Math.min(100000, Math.floor(Number(level) || 1)));
    const random = rngFor((Math.imul(number, 2654435761) ^ 0x9e3779b9) >>> 0);
    const advanced = number >= 4;
    const count = Math.min(10, 5 + Math.floor(number / 3));
    const maxTwists = advanced ? 2 : 0;
    let fallback;
    for (let attempt = 0; attempt < 30; attempt++) {
      const places = [];
      for (const face of FACE_NAMES) for (let u = -1; u <= 1; u++)
        for (let v = -1; v <= 1; v++) places.push({ face, u, v });
      for (let i = places.length - 1; i > 0; i--) {
        const j = Math.floor(random() * (i + 1));
        [places[i], places[j]] = [places[j], places[i]];
      }
      const pieces = places.slice(0, count).map((p, id) => ({
        ...p, id, dir: Math.floor(random() * 4),
        gate: null, source: null, targetPhase: 0
      }));
      // First relationship: arrow 0 releases arrow 1's circuit latch.
      if (number >= 2) { pieces[1].gate = 'link'; pieces[1].source = 0; }
      // Second relationship: a gold arrow needs the physical middle ring aligned.
      if (advanced) { pieces[2].gate = 'phase'; pieces[2].targetPhase = 1; }
      const candidate = { level: number, pieces, maxTwists, signature: 'NEXUS3D-1' };
      const solution = solve(candidate);
      if (!solution) continue;
      if (!fallback) fallback = { ...candidate, solution };
      const blockersPresent = pieces.filter(p => blockers(p, initialState(candidate)).length > 0).length;
      if (blockersPresent >= Math.min(2, count - 2)) return { ...candidate, solution };
    }
    if (fallback) return fallback;
    throw new Error('Could not generate a solvable level: ' + number);
  }
  return { FACES, FACE_NAMES, DIRS, position, tangent, twistPiece,
    initialState, blockers, canExit, actions, transition, solve, generate };
});
