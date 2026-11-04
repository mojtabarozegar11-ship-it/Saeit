// Battle-scored points are a single-player gameplay resource, not a token,
// payment, or server-authoritative ledger. Keep awards atomic and compatible
// with the numeric limits already accepted by save-validation.mjs.
export const REWARD_LIMITS = Object.freeze({score: 10_000_000_000, points: 10_000_000});

export function grantBattleReward(state, scoreDelta = 0, pointsDelta = 0) {
  if (!state || typeof state !== 'object') return false;
  if (![state.score, state.points, scoreDelta, pointsDelta].every(Number.isSafeInteger)) return false;
  if (state.score < 0 || state.points < 0 || scoreDelta < 0 || pointsDelta < 0 ||
      (scoreDelta === 0 && pointsDelta === 0)) return false;
  // Reject the whole award before changing either field. A partially applied
  // award would create an inconsistent save if one counter hit its limit.
  if (state.score > REWARD_LIMITS.score - scoreDelta ||
      state.points > REWARD_LIMITS.points - pointsDelta) return false;
  state.score += scoreDelta;
  state.points += pointsDelta;
  return true;
}

// This marker is already part of R58 saves and is validated on restore.
// Recording completion before the next frame makes the award idempotent even
// when the completion callback is reached again. The caller must first verify
// its mission objectives and that no enemies remain.
export function completeMissionOnce(state) {
  if (!state || typeof state !== 'object' || state.endless === true ||
      state.victory === true || state.gameOver === true ||
      (state.missionPassed !== false && state.missionPassed !== undefined) ||
      !Number.isInteger(state.mission) || state.mission < 0 || state.mission > 5 ||
      !Number.isSafeInteger(state.score) || !Number.isSafeInteger(state.points) ||
      state.score < 0 || state.points < 0 ||
      state.score > REWARD_LIMITS.score || state.points > REWARD_LIMITS.points) {
    return {completed: false, rewardGranted: false};
  }
  // Reaching the points cap must not strand a successfully completed mission.
  const rewardGranted = grantBattleReward(state, 0, 1);
  state.missionPassed = true;
  return {completed: true, rewardGranted};
}
