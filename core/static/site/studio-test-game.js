/* Zomorod Melal Studio - experimental game lives controller */
(() => {
  'use strict';
  const MAX_LIVES = 5;
  let lives = MAX_LIVES;

  function render() {
    const el = document.querySelector('[data-studio-lives]');
    if (!el) return;
    el.textContent = '❤️'.repeat(lives) + '🖤'.repeat(MAX_LIVES - lives);
    el.setAttribute('aria-label', `تعداد جان: ${lives} از ${MAX_LIVES}`);
  }

  window.ZomorodStudioGame = {
    maxLives: MAX_LIVES,
    getLives: () => lives,
    reset: () => { lives = MAX_LIVES; render(); return lives; },
    loseLife: () => { lives = Math.max(0, lives - 1); render(); return lives; },
    gainLife: () => { lives = Math.min(MAX_LIVES, lives + 1); render(); return lives; }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', render);
  else render();
})();
