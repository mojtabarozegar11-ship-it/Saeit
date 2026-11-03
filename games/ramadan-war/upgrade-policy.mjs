// Earned, non-purchasable campaign upgrades. This is not the MOJ1 payment ledger.
// Keep maxHp <= 200: the save validator must accept every legitimate upgrade.
const finite = value => typeof value === 'number' && Number.isFinite(value);
const whole = value => Number.isSafeInteger(value) && value >= 0;
export const UPGRADE_LIMITS = Object.freeze({power:12, armor:5, maxHp:200, rockets:24, drones:7});
export function canApplyEarnedUpgrade(state, kind) {
  if (!state || !Number.isInteger(kind) || kind < 0 || kind > 3) return {ok:false, reason:'invalid'};
  if (!whole(state.points) || state.points < 1) return {ok:false, reason:'points'};
  if (![state.power,state.armor,state.rockets,state.drones].every(whole) ||
      !finite(state.maxHp) || !finite(state.hp) || state.maxHp <= 0 ||
      state.maxHp > UPGRADE_LIMITS.maxHp || state.hp < 0 || state.hp > state.maxHp) {
    return {ok:false, reason:'invalid'};
  }
  if (kind === 0 && state.power >= UPGRADE_LIMITS.power) return {ok:false, reason:'cap'};
  if (kind === 1 && (state.armor >= UPGRADE_LIMITS.armor || state.maxHp >= UPGRADE_LIMITS.maxHp)) return {ok:false, reason:'cap'};
  if (kind === 2 && state.rockets >= UPGRADE_LIMITS.rockets) return {ok:false, reason:'cap'};
  if (kind === 3 && state.drones >= UPGRADE_LIMITS.drones) return {ok:false, reason:'cap'};
  return {ok:true, reason:null};
}
export function applyEarnedUpgrade(state, kind) {
  const gate=canApplyEarnedUpgrade(state,kind);
  if (!gate.ok) return gate;
  // No balance is consumed unless an actual gameplay improvement can be granted.
  if (kind===0) state.power+=1;
  else if (kind===1) {
    state.armor+=1;
    state.maxHp=Math.min(UPGRADE_LIMITS.maxHp,state.maxHp+20);
    state.hp=Math.min(state.maxHp,state.hp+30);
  } else if (kind===2) state.rockets=Math.min(UPGRADE_LIMITS.rockets,state.rockets+6);
  else state.drones=Math.min(UPGRADE_LIMITS.drones,state.drones+2);
  state.points-=1;
  return {ok:true, reason:null};
}
