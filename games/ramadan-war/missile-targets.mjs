// Preserve homing targets when dead enemies are removed from the dense enemy array.
// Missiles store indices in local saves, so update the indices in place for compatibility.
export function removeEnemyAndRetargetMissiles(enemies, missiles, removedIndex) {
  if (!Array.isArray(enemies) || !Array.isArray(missiles) ||
      !Number.isInteger(removedIndex) || removedIndex < 0 || removedIndex >= enemies.length) {
    return null;
  }
  const [removed] = enemies.splice(removedIndex, 1);
  for (const missile of missiles) {
    if (!missile || !Number.isInteger(missile.targetId)) continue;
    if (missile.targetId === removedIndex) missile.targetId = -1;
    else if (missile.targetId > removedIndex) missile.targetId -= 1;
  }
  return removed;
}

// Rockets must collide with solid cover even while homing on a live enemy.
// Check the entire movement segment, not just the endpoint: an untrusted
// restored velocity or a slow frame must not let a missile tunnel through walls.
// Fail closed on invalid state and cap the work to the 16x16 arena dimensions.
export function missileMotionValid(missile, dt) {
  return Boolean(missile) && Number.isFinite(dt) && dt >= 0 &&
    Number.isFinite(missile.life) && missile.life > 0 &&
    Number.isFinite(missile.x) && Number.isFinite(missile.y) &&
    Number.isFinite(missile.vx) && Number.isFinite(missile.vy) &&
    Math.hypot(missile.vx * dt, missile.vy * dt) <= 16;
}

export function missilePathBlocked(missile, dt, isWall) {
  if (!missileMotionValid(missile, dt) || typeof isWall !== 'function') return true;
  const dx = missile.vx * dt, dy = missile.vy * dt;
  const distance = Math.hypot(dx, dy);
  const steps = Math.max(1, Math.ceil(distance / 0.15));
  for (let i = 0; i <= steps; i++) {
    const x = missile.x + dx * i / steps;
    const y = missile.y + dy * i / steps;
    if (isWall(Math.floor(x), Math.floor(y))) return true;
  }
  return false;
}
