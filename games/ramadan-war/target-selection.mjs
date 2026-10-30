// Pure, deterministic target selection; no browser or storage access.
export function chooseNearestTarget(enemies, x, y, range = Infinity, requireLineOfSight = false, isBlocked = () => false) {
 if (!Array.isArray(enemies) || ![x,y,range].every(v => typeof v === 'number' && !Number.isNaN(v)) || range < 0) return null;
 if (typeof isBlocked !== 'function') return null;
 let best = null, distance = range;
 for (const e of enemies) {
  if (!e || !(e.hp > 0) || !Number.isFinite(e.x) || !Number.isFinite(e.y)) continue;
  const d = Math.hypot(e.x - x, e.y - y);
  if (d < distance && (!requireLineOfSight || !isBlocked(x,y,e.x,e.y))) {best=e;distance=d;}
 }
 return best;
}
