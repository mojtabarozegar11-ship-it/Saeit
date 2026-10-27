// Enemy lifecycle policy: a defeated enemy must never attack or move again
// while waiting for the combat tick's reward/cleanup pass.
export function canEnemyAct(enemy) {
  return enemy !== null && typeof enemy === 'object' &&
    Number.isFinite(enemy.hp) && enemy.hp > 0 &&
    Number.isFinite(enemy.life) && enemy.life >= -4;
}

// Legacy saves may omit transient runtime fields. Restore safe finite defaults
// without changing earned kills, rewards, HP or objective progress.
export function restoreEnemyRuntime(enemy, index) {
  if (!Number.isFinite(enemy.life)) enemy.life = 1.5;
  if (!Number.isFinite(enemy.max) || enemy.max <= 0) enemy.max = Math.max(1, enemy.hp);
  if (enemy.strafe !== -1 && enemy.strafe !== 1) enemy.strafe = index % 2 ? 1 : -1;
  if (!Number.isFinite(enemy.pathTimer) || enemy.pathTimer < 0) enemy.pathTimer = 0;
  return enemy;
}


// Advance hostile bullets only while alive. Sweep the full frame segment in
// bounded increments, checking cover before contact at each point. Endpoint-only
// collision allowed tampered/fast restored projectiles to cross solid tiles or
// skip the player. Invalid physics and impossible jumps fail closed.
export function advanceHostileProjectile(bullet, dt, player, isWall) {
  if (!bullet || !Number.isFinite(bullet.life) || bullet.life <= 0 ||
      !Number.isFinite(dt) || dt < 0 ||
      !Number.isFinite(bullet.x) || !Number.isFinite(bullet.y) ||
      !Number.isFinite(bullet.vx) || !Number.isFinite(bullet.vy) ||
      !Number.isFinite(player?.x) || !Number.isFinite(player?.y) ||
      typeof isWall !== 'function') {
    if (bullet) bullet.life = -1;
    return false;
  }
  // A projectile expiring during this tick cannot damage the player.
  if (bullet.life <= dt) {
    bullet.life = -1;
    return false;
  }
  const dx = bullet.vx * dt;
  const dy = bullet.vy * dt;
  const distance = Math.hypot(dx, dy);
  // Arena is 16x16; traversing more than its entire width in one tick is
  // corrupt physics. The bound also guarantees finite collision work.
  if (!Number.isFinite(distance) || distance > 16) {
    bullet.life = -1;
    return false;
  }
  const steps = Math.max(1, Math.ceil(distance / 0.15));
  for (let i = 0; i <= steps; i++) {
    const x = bullet.x + dx * i / steps;
    const y = bullet.y + dy * i / steps;
    if (isWall(Math.floor(x), Math.floor(y))) {
      bullet.life = -1;
      return false;
    }
    if (Math.hypot(x - player.x, y - player.y) < 0.31) {
      bullet.x = x;
      bullet.y = y;
      bullet.life = -1;
      return true;
    }
  }
  bullet.x += dx;
  bullet.y += dy;
  bullet.life -= dt;
  return false;
}
