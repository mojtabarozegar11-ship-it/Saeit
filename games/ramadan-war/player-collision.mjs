// Deterministic player movement with swept, radius-aware wall collision.
// Works for both keyboard and touch movement; no browser APIs or server writes.
export const PLAYER_RADIUS = 0.21;
const MAX_SUBSTEP = 0.16;

export function playerSpaceClear(x, y, wall, radius = PLAYER_RADIUS) {
  if (!Number.isFinite(x) || !Number.isFinite(y) ||
      !Number.isFinite(radius) || radius <= 0 || typeof wall !== 'function') return false;
  // Four footprint corners prevent diagonal clipping through blocked tiles.
  return !wall(Math.floor(x-radius), Math.floor(y-radius)) &&
         !wall(Math.floor(x-radius), Math.floor(y+radius)) &&
         !wall(Math.floor(x+radius), Math.floor(y-radius)) &&
         !wall(Math.floor(x+radius), Math.floor(y+radius));
}

export function movePlayerWithCollision(player, dx, dy, wall) {
  if (!player || !Number.isFinite(dx) || !Number.isFinite(dy) ||
      !Number.isFinite(player.x) || !Number.isFinite(player.y)) return false;
  if (dx === 0 && dy === 0) return false;
  // Swept substeps prevent crossing thin walls during frame-rate spikes.
  // The live game already clamps dt; this additional cap fails closed for callers.
  if (Math.abs(dx) > 10 || Math.abs(dy) > 10) return false;
  const steps = Math.max(1, Math.ceil(Math.max(Math.abs(dx), Math.abs(dy)) / MAX_SUBSTEP));
  const sx = dx / steps, sy = dy / steps;
  let moved = false;
  for (let i = 0; i < steps; i++) {
    if (sx && playerSpaceClear(player.x + sx, player.y, wall)) {
      player.x += sx; moved = true;
    }
    if (sy && playerSpaceClear(player.x, player.y + sy, wall)) {
      player.y += sy; moved = true;
    }
  }
  return moved;
}
