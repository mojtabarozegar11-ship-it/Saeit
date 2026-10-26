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
