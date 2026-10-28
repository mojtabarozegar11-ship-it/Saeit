// Fail-closed integrity guard for locally stored Ramadan War campaign state.
// Invalid saves are rejected without altering the original browser storage entry.
export function validateCampaignSave(s) {
  const finite = (n, min, max) => typeof n === 'number' && Number.isFinite(n) && n >= min && n <= max;
  const integer = (n, min, max) => Number.isInteger(n) && finite(n, min, max);
  const point = (o, min = -50, max = 50) => o && typeof o === 'object' && !Array.isArray(o) && finite(o.x, min, max) && finite(o.y, min, max);
  const group = (a, limit, predicate) => a === undefined || (Array.isArray(a) && a.length <= limit && a.every(predicate));
  if (!s || typeof s !== 'object' || Array.isArray(s)) return false;
  // A string/object "true" is truthy to the engine but previously bypassed
  // strict-true rejection, allowing a campaign save to enter endless/victory mode.
  // Missing legacy flags and explicit false remain compatible.
  for (const field of ['endless', 'victory', 'gameOver']) {
    if (s[field] !== undefined && s[field] !== false) return false;
  }
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
  // Untrusted runtime effects/counters are consumed by tick() and the WebGL renderer.
  // A malformed impacts object crashes Array.filter(), and NaN combo/shot counts
  // poison score or HUD state. Preserve legacy saves with absent optional fields.
  for (const [field, max] of [['shots', 1e9], ['combo', 1e7], ['best', 1e7], ['rocketHits', 1e7]]) {
    if (s[field] !== undefined && !integer(s[field], 0, max)) return false;
  }
  if (s.recoil !== undefined && !finite(s.recoil, 0, 10)) return false;
  for (const field of ['reloading', 'hit', 'skillFired']) {
    if (s[field] !== undefined && typeof s[field] !== 'boolean') return false;
  }
  if (!group(s.impacts, 128, e => point(e) &&
      finite(e.height, -10, 20) && finite(e.life, -1, 10) &&
      typeof e.type === 'string' && e.type.length > 0 && e.type.length <= 32)) return false;
  if (s.marker != null && (!point(s.marker, 0, 16) ||
      typeof s.marker.kind !== 'string' || s.marker.kind.length > 32)) return false;
  if (s.bossSpawned !== undefined && typeof s.bossSpawned !== 'boolean') return false;
  if (s.missionPassed !== undefined && typeof s.missionPassed !== 'boolean') return false;
  if (s.missionPassed === true) {
    // A cleared stage is an earned transition, not merely an empty arena.
    // Verify the same kill quotas and stage-specific objectives as game.js.
    // Never trust a locally edited missionPassed flag to unlock the next stage.
    const quotas = [4, 5, 5, 6, 7, 8];
    const requiredDone = [2, 1, 3, 2, 1, 0];
    if (s.enemies.length !== 0 || s.missionKills < quotas[s.mission] ||
        !s.objective) return false;
    if (s.mission === 1) {
      if (s.objective.done !== 1 || s.objective.hold < 22) return false;
    } else if (s.mission === 5) {
      if (s.objective.bossDefeated !== true) return false;
    } else if (s.objective.done !== requiredDone[s.mission]) return false;
  }
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
    'explosionTimer', 'muzzle']) {
    if (s[field] !== undefined && !finite(s[field], -1e8, 1e8)) return false;
  }
  // Time stop is a bounded five-second ability, not a user-editable permanent freeze.
  if (s.freeze !== undefined && !finite(s.freeze, 0, 5)) return false;
  if (s.strikeX !== undefined && !finite(s.strikeX, -50, 50)) return false;
  if (s.strikeY !== undefined && !finite(s.strikeY, -50, 50)) return false;
  if (s.objective != null && (typeof s.objective !== 'object' || Array.isArray(s.objective) ||
      !integer(s.objective.done, 0, 3) || !finite(s.objective.hold, 0, 100) ||
      typeof s.objective.bossDefeated !== 'boolean')) return false;
  if (s.objective != null) {
    // Prevent a locally edited in-progress save from exceeding the current
    // operation's actual site count or marking timed defence complete early.
    const maxDone = [2, 1, 3, 2, 1, 0];
    if (s.objective.done > maxDone[s.mission]) return false;
    if (s.mission === 1 && s.objective.done === 1 && s.objective.hold < 22) return false;
    if (s.mission !== 5 && s.objective.bossDefeated) return false;
  }
  return true;
}

// Keep live pickups untouched while bounding the persisted snapshot. Transient
// drops can accumulate during dense fights; an oversized save is rejected on
// next launch. Preserve all stage-recovery intel before retaining recent drops.
export function boundedCampaignPickups(pickups) {
  if (!Array.isArray(pickups)) return [];
  const intel = pickups.filter(p => p?.type === 'mission-intel');
  const transient = pickups.filter(p => p?.type !== 'mission-intel');
  const slots = Math.max(0, 60 - intel.length);
  return [...(slots ? transient.slice(-slots) : []), ...intel].slice(-60);
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
  // A defeated boss still in the entity list must be processed by the next tick;
  // do not spawn a duplicate before kill cleanup marks the objective complete.
  const trackedBoss = state.enemies.some(e => e?.boss === true);
  const corrected = state.bossSpawned !== trackedBoss;
  state.bossSpawned = trackedBoss;
  return corrected;
}

// A legacy or manipulated save may pass numeric position validation while
// placing the hero inside a solid wall. Recover to the known passable spawn
// without touching score, objectives, inventory or earned campaign progress.
export function restorePlayerPosition(state, isBlocked) {
  if (!state || typeof isBlocked !== 'function') return false;
  if (Number.isFinite(state.x) && Number.isFinite(state.y) &&
      !isBlocked(state.x | 0, state.y | 0)) return false;
  if (isBlocked(2, 7)) return false;
  state.x = 2.5;
  state.y = 7.5;
  return true;
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
