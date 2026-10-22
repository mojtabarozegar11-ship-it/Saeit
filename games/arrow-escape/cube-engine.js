/* Six-sided deterministic Arrow Escape cube. Each face has an independently
 * solvable arrow ordering; removing arrows never creates a new obstruction.
 * Geometry and artwork are original to Zomorod Melal. */
(function (root, factory) {
  const api = factory(typeof module === 'object' && module.exports
    ? require('./engine.js') : root.ArrowMazeCore);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ArrowCubeCore = api;
})(typeof window !== 'undefined' ? window : undefined, function (Core) {
  'use strict';
  const FACE_NAMES = Object.freeze(['front', 'right', 'back', 'left', 'top', 'bottom']);
  function generate(level) {
    const n = Math.max(1, Math.min(1000000, Math.floor(Number(level) || 1)));
    const perFace = Math.min(18, 8 + Math.floor((n - 1) / 4));
    const faces = FACE_NAMES.map((name, faceIndex) => {
      const original = Core.generate(140 + n * 7 + faceIndex * 11);
      const pieces = original.pieces.slice(0, perFace).map(p => ({
        id: name + '-' + p.id, face: faceIndex,
        dir: p.dir, path: p.path.map(cell => ({ x: cell.x, y: cell.y }))
      }));
      return { name, size: original.size, pieces };
    });
    return { level: n, faces, total: faces.reduce((sum, f) => sum + f.pieces.length, 0) };
  }
  function remainingFace(puzzle, faceIndex, removed) {
    return puzzle.faces[faceIndex].pieces.filter(p => !removed.has(p.id));
  }
  function canExit(puzzle, piece, removed) {
    return Core.canExit(piece, remainingFace(puzzle, piece.face, removed),
      puzzle.faces[piece.face].size);
  }
  function solution(puzzle, removed = new Set()) {
    const order = [];
    for (const face of puzzle.faces) {
      const remaining = face.pieces.filter(piece => !removed.has(piece.id));
      const ids = Core.solve(remaining, face.size);
      if (!ids) return null;
      order.push(...ids);
    }
    return order;
  }
  return Object.freeze({ FACE_NAMES, generate, remainingFace, canExit, solution });
});
