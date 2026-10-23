/* Arrow Cube — dense, deterministic winding tracks on all SIX real 3D faces.
 * Geometry, generator and artwork are original. Each band is partitioned into
 * non-overlapping Hamiltonian serpents. Their exit directions share one axis,
 * so every band has at least one legal move and every level is solvable.
 */
(function (root, factory) {
  const api = factory(typeof module === 'object' && module.exports
    ? require('./engine.js') : root.ArrowMazeCore);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.ArrowCubeCore = api;
})(typeof window !== 'undefined' ? window : undefined, function (Core) {
  'use strict';
  const FACE_NAMES = Object.freeze(['front', 'right', 'back', 'left', 'top', 'bottom']);
  function random(seed) {
    let x = seed >>> 0;
    return () => {
      x ^= x << 13; x ^= x >>> 17; x ^= x << 5;
      return (x >>> 0) / 4294967296;
    };
  }
  function rotateCell(u, v, size, quarterTurns) {
    if (quarterTurns === 1) return { x: size - v - 1, y: u };
    if (quarterTurns === 2) return { x: size - u - 1, y: size - v - 1 };
    if (quarterTurns === 3) return { x: v, y: size - u - 1 };
    return { x: u, y: v };
  }
  function localDir(a, b) {
    const dx = b.x - a.x, dy = b.y - a.y;
    return dx > 0 ? 0 : dy > 0 ? 1 : dx < 0 ? 2 : 3;
  }
  function mosaicPieces(name, faceIndex, size, rng) {
    const pieces = [];
    const tileSize = size / 3;
    for (let row = 0; row < 3; row++) {
      for (let col = 0; col < 3; col++) {
        const options = [];
        if (col === 0) options.push(2); // leave through the left cube edge
        if (col === 2) options.push(0);
        if (row === 0) options.push(3);
        if (row === 2) options.push(1);
        // Center tiles become available after their surrounding tiles depart.
        if (!options.length) options.push(0, 1, 2, 3);
        const direction = options[Math.floor(rng() * options.length)];
        // Each mini-maze has 2 or 3 parallel nested serpents; its neighbors
        // use different axis orientations, breaking the repetitive stripe look.
        const heights = tileSize === 5 ? [2, 3] :
          tileSize === 6 ? [2, 2, 2] : [2, 2, 3];
        let v0 = 0;
        for (const height of heights) {
          const path = [];
          for (let v = 0; v < height; v++) {
            // End every serpent heading to the right *before* rotation.
            const forward = (v % 2 === 0) === (height % 2 === 1);
            for (let u = 0; u < tileSize; u++) {
              const localU = forward ? u : tileSize - u - 1;
              const localV = v0 + v;
              const rotated = rotateCell(localU, localV, tileSize, direction);
              path.push({ x: col * tileSize + rotated.x,
                y: row * tileSize + rotated.y });
            }
          }
          const dir = localDir(path[path.length - 2], path[path.length - 1]);
          pieces.push({ id: name + '-' + pieces.length, face: faceIndex,
            dir, path, area: path.length });
          v0 += height;
        }
      }
    }
    return pieces;
  }
  function generate(level) {
    const n = Math.max(1, Math.min(1000000, Math.floor(Number(level) || 1)));
    const size = n < 8 ? 15 : n < 35 ? 18 : 21;
    const faces = FACE_NAMES.map((name, faceIndex) => {
      const rng = random((Math.imul(n, 0x9e3779b1) ^
        Math.imul(faceIndex + 1, 0x85ebca6b) ^ 0x3c6ef372) >>> 0);
      const pieces = [];
      const turn = (faceIndex + (n % 3 === 0 ? 1 : 0)) % 4;
      const targetBands = size / 3;
      for (let band = 0; band < targetBands; band++) {
        // Irregular widths make neighboring serpents form a labyrinth.
        const widths = [];
        let left = size;
        const targetSections = size === 15 ? 3 : size === 18 ? 4 : 5;
        for (let i = 0; i < targetSections; i++) {
          const later = targetSections - 1 - i;
          const min = Math.max(3, left - later * 7);
          const max = Math.min(7, left - later * 3);
          const w = i === targetSections - 1 ? left :
            Math.max(min, Math.min(max, min + Math.floor(rng() * (max - min + 1))));
          widths.push(w); left -= w;
        }
        let u0 = 0;
        // All pieces in one band travel toward the same perimeter edge;
        // there is always an available move, without cyclic dependencies.
        const travelRight = rng() > .5;
        for (let section = 0; section < widths.length; section++) {
          const width = widths[section];
          const path = [];
          for (let v = band * 3; v < band * 3 + 3; v++) {
            const forward = ((v - band * 3) % 2 === 0) === travelRight;
            for (let offset = 0; offset < width; offset++) {
              const u = u0 + (forward ? offset : width - offset - 1);
              path.push(rotateCell(u, v, size, turn));
            }
          }
          const dir = localDir(path[path.length - 2], path[path.length - 1]);
          pieces.push({ id: name + '-' + pieces.length, face: faceIndex,
            dir, path, area: path.length });
          u0 += width;
        }
      }
      // Four mosaic faces + two full-length winding band faces make the cube
      // visually coherent without six identical repeated grids.
      const finalPieces = (faceIndex % 3 === 2) ? pieces :
        mosaicPieces(name, faceIndex, size, rng);
      return { name, size, pieces: finalPieces };
    });
    return { level: n, faces, total: faces.reduce((sum, face) => sum + face.pieces.length, 0) };
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
