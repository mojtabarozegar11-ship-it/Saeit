// Fail-closed integrity guard for locally stored Ramadan War campaign state.
// Invalid saves are rejected without altering the original browser storage entry.
export function validateCampaignSave(s) {
  const finite = (n, min, max) => typeof n === 'number' && Number.isFinite(n) && n >= min && n <= max;
  const integer = (n, min, max) => Number.isInteger(n) && finite(n, min, max);
  const point = (o, min = -50, max = 50) => o && typeof o === 'object' && !Array.isArray(o) && finite(o.x, min, max) && finite(o.y, min, max);
  const group = (a, limit, predicate) => a === undefined || (Array.isArray(a) && a.length <= limit && a.every(predicate));
  if (!s || typeof s !== 'object' || Array.isArray(s) || s.endless === true || s.victory === true || s.gameOver === true) return false;
  if (!integer(s.hero, 0, 29) || !integer(s.mission, 0, 5) || !integer(s.lives, 1, 100)) return false;
  if (!finite(s.x, 0.5, 15) || !finite(s.y, 0.5, 15) || !finite(s.angle, -1e8, 1e8)) return false;
  if (!finite(s.maxHp, 1, 200) || !finite(s.hp, 0.01, s.maxHp)) return false;
  if (!integer(s.ammo, 0, 40) || !integer(s.magazine, 1, 40) || s.ammo > s.magazine) return false;
  if (!integer(s.rockets, 0, 24) || !integer(s.drones, 0, 7)) return false;
  for (const [name, max] of [['score', 1e10], ['points', 1e7], ['kills', 1e7], ['missionKills', 1e6]]) {
    if (!integer(s[name], 0, max)) return false;
  }
  if (!Array.isArray(s.enemies) || s.enemies.length > 30 || !s.enemies.every(e =>
    point(e, 0, 16) && integer(e.type, 0, 3) && finite(e.hp, -10000, 10000) &&
    (e.route == null || (Array.isArray(e.route) && e.route.length === 2 && e.route.every(n => finite(n, 0, 16))))
  )) return false;
  if (s.missionPassed !== undefined && typeof s.missionPassed !== 'boolean') return false;
  if (s.missionPassed === true && s.enemies.length !== 0) return false;
  if (!group(s.hostile, 150, e => point(e) && finite(e.life, -10, 100))) return false;
  if (!group(s.missiles, 80, e => point(e) && finite(e.life, -10, 100))) return false;
  if (!group(s.pickups, 60, e => point(e, 0, 16) && finite(e.life, -10, 4000) &&
    ['ammo', 'health', 'intel', 'mission-intel'].includes(e.type))) return false;
  if (s.objective != null && (typeof s.objective !== 'object' || Array.isArray(s.objective) ||
      !integer(s.objective.done, 0, 3) || !finite(s.objective.hold, 0, 100) ||
      typeof s.objective.bossDefeated !== 'boolean')) return false;
  return true;
}

// A cleared mission must resume at its results panel, not in a non-interactive arena.
export function resumeCampaignScreen(save) {
  return save?.missionPassed === true ? 'success' : 'game';
}
