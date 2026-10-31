// G-01 R57: fail-closed graphics recovery decisions, no browser dependency.
export function canEnterGameplay(graphicsUnavailable, documentHidden) {
  return graphicsUnavailable !== true && documentHidden !== true;
}
export function canReloadGraphics(graphicsUnavailable, saveStatus) {
  return graphicsUnavailable === true && saveStatus === 'saved';
}
