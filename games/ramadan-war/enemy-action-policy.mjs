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
