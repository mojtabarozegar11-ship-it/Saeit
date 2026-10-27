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


// Advance hostile bullets only while alive. Resolve solid walls before player
// contact so an expired shot or a shot striking cover cannot hurt the player.
// Returns true only for a new, valid player hit; caller applies armor/shield.
export function advanceHostileProjectile(bullet, dt, player, isWall) {
  if (!bullet || !Number.isFinite(bullet.life) || bullet.life <= 0 ||
      !Number.isFinite(dt) || dt < 0 ||
      !Number.isFinite(bullet.x) || !Number.isFinite(bullet.y) ||
      !Number.isFinite(bullet.vx) || !Number.isFinite(bullet.vy)) {
    if (bullet) bullet.life = -1;
    return false;
  }
  const x = bullet.x + bullet.vx * dt;
  const y = bullet.y + bullet.vy * dt;
  bullet.life -= dt;
  if (bullet.life <= 0 || !Number.isFinite(x) || !Number.isFinite(y) ||
      isWall(x | 0, y | 0)) {
    bullet.life = -1;
    return false;
  }
  bullet.x = x;
  bullet.y = y;
  if (Math.hypot(x - player.x, y - player.y) < .31) {
    bullet.life = -1;
    return true;
  }
  return false;
}
