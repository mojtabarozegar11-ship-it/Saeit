// Keyboard commands are only gameplay inputs while the arena owns focus.
// Menu buttons must retain native Enter/Space behavior for keyboard and assistive users.
export function isInteractiveTarget(target) {
  return Boolean(target && typeof target.closest === 'function' &&
    target.closest('button, a, input, textarea, select, summary, [contenteditable], [role="button"], [role="textbox"]'));
}

const COMMANDS = Object.freeze({
  KeyQ: 'rocket',
  KeyE: 'drone',
  KeyF: 'special',
  KeyR: 'reload',
  KeyG: 'interact'
});

export function keyboardAction(code, screen, target, repeat = false) {
  if (screen !== 'game' || isInteractiveTarget(target)) return null;
  if (repeat && code !== 'Space') return null;
  if (code === 'Escape') return 'pause';
  if (code === 'Space') return 'fire';
  return Object.hasOwn(COMMANDS, code) ? COMMANDS[code] : null;
}
