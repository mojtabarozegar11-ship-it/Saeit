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
  // Legacy high-but-finite earned upgrades are normalized on restore; corrupt values fail closed.
  if (s.power !== undefined && !integer(s.power, 0, 100)) return false;
  if (s.armor !== undefined && !integer(s.armor, 0, 100)) return false;
  for (const [name, max] of [['score', 1e10], ['points', 1e7], ['kills', 1e7], ['missionKills', 1e6]]) {
    if (!integer(s[name], 0, max)) return false;
  }
  if (!Array.isArray(s.enemies) || s.enemies.length > 30 || !s.enemies.every(e =>
    point(e, 0, 16) && integer(e.type, 0, 3) && finite(e.hp, -10000, 10000) &&
    (e.boss === undefined || typeof e.boss === 'boolean') &&
    (e.route == null || (Array.isArray(e.route) && e.route.length === 2 && e.route.every(n => finite(n, 0, 16))))
  )) return false;
  if (s.bossSpawned !== undefined && typeof s.bossSpawned !== 'boolean') return false;
  if (s.missionPassed !== undefined && typeof s.missionPassed !== 'boolean') return false;
  if (s.missionPassed === true && s.enemies.length !== 0) return false;
  // Projectiles are integrated each frame; missing velocities poison the world with NaN.
  if (!group(s.hostile, 150, e => point(e) && finite(e.life, -10, 100) &&
      finite(e.vx, -50, 50) && finite(e.vy, -50, 50) && finite(e.hp, 0, 500))) return false;
  if (!group(s.missiles, 80, e => point(e) && finite(e.life, -10, 100) &&
      finite(e.vx, -50, 50) && finite(e.vy, -50, 50) &&
      (e.targetId === undefined || integer(e.targetId, -1, 29)))) return false;
  if (!group(s.pickups, 60, e => point(e, 0, 16) && finite(e.life, -10, 4000) &&
    ['ammo', 'health', 'intel', 'mission-intel'].includes(e.type))) return false;
  // Recovery pickups must be unique, stage-local and bounded by unfinished objectives.
  // Without this, a modified save can duplicate mission rewards or corrupt stage progress.
  if (Array.isArray(s.pickups)) {
    const intel=s.pickups.filter(p=>p.type==='mission-intel');
    const done=s.objective?.done ?? 0;
    if (intel.length && (s.mission!==2 || !integer(done,0,3) ||
        intel.some(p=>!integer(p.spotIndex,0,2)) ||
        new Set(intel.map(p=>p.spotIndex)).size!==intel.length ||
        intel.length>3-done)) return false;
  }
  // Preserve old saves without optional timers; fail closed on nonfinite saved clocks.
  for (const field of ['time', 'enemyTimer', 'shotTimer', 'reloadTimer', 'comboTimer',
    'rocketTimer', 'droneTimer', 'skillTimer', 'shield', 'strikeTimer', 'hitFlash',
    'explosionTimer', 'muzzle', 'freeze']) {
    if (s[field] !== undefined && !finite(s[field], -1e8, 1e8)) return false;
  }
  if (s.strikeX !== undefined && !finite(s.strikeX, -50, 50)) return false;
  if (s.strikeY !== undefined && !finite(s.strikeY, -50, 50)) return false;
  if (s.objective != null && (typeof s.objective !== 'object' || Array.isArray(s.objective) ||
      !integer(s.objective.done, 0, 3) || !finite(s.objective.hold, 0, 100) ||
      typeof s.objective.bossDefeated !== 'boolean')) return false;
  return true;
}

// Reconstruct missing objective items in legacy saves where a long pause expired
// the collectibles. Never reset already earned progress or grant a reward here.
export function restoreRecoveryPickups(state, sites) {
  if (!state || state.mission!==2 || !state.objective ||
      !Number.isInteger(state.objective.done) || state.objective.done<0 ||
      state.objective.done>3 || !Array.isArray(state.pickups) ||
      !Array.isArray(sites) || sites.length!==3) return 0;
  const existing=state.pickups.filter(p=>p?.type==='mission-intel');
  const remaining=3-state.objective.done;
  let needed=Math.max(0,remaining-existing.length);
  if (!needed) return 0;
  const occupied=new Set(existing.map(p=>p.spotIndex));
  let restored=0;
  for (let i=0;i<sites.length && needed>0;i++) {
    if (occupied.has(i)) continue;
    const site=sites[i];
    if (!Array.isArray(site) || site.length!==2 ||
        !site.every(n=>typeof n==='number' && Number.isFinite(n) && n>=0 && n<=16)) continue;
    state.pickups.push({x:site[0],y:site[1],type:'mission-intel',spotIndex:i,life:3600});
    needed--;restored++;
  }
  return restored;
}

// A saved final-stage encounter can lose its boss between spawn and persistence.
// Reconcile the spawn flag with the actual living boss, preserving earned kills and
// completed objectives. Never create a paid entitlement or change campaign rewards.
export function reconcileBossEncounter(state) {
  if (!state || state.mission !== 5 || state.endless === true ||
      state.missionPassed === true || !state.objective ||
      state.objective.bossDefeated === true || !Array.isArray(state.enemies)) return false;
  const liveBoss = state.enemies.some(e => e?.boss === true && e.hp > 0);
  const corrected = state.bossSpawned !== liveBoss;
  state.bossSpawned = liveBoss;
  return corrected;
}

// A cleared mission must resume at its results panel, not in a non-interactive arena.
export function resumeCampaignScreen(save) {
  return save?.missionPassed === true ? 'success' : 'game';
}

// Saved hero selection is untrusted browser storage; never use NaN or out-of-range array keys.
export function readHeroChoice(value) {
  if (typeof value !== 'string' && typeof value !== 'number') return 0;
  const raw = String(value).trim();
  if (!/^(?:0|[1-9][0-9]{0,1})$/.test(raw)) return 0;
  const hero = Number(raw);
  return hero <= 29 ? hero : 0;
}

// Browsers may block Web Storage entirely (privacy modes, sandboxed frames, policy).
// Never let storage access stop the playable, unsaved campaign.
export function storageRead(key) {
  try { return globalThis.localStorage?.getItem(key) ?? null; }
  catch { return null; }
}
export function storageWrite(key, value) {
  try {
    if (!globalThis.localStorage) return false;
    globalThis.localStorage.setItem(key, String(value));
    return true;
  } catch { return false; }
}
export function storageRemove(key) {
  try {
    if (!globalThis.localStorage) return false;
    globalThis.localStorage.removeItem(key);
    return true;
  } catch { return false; }
}
