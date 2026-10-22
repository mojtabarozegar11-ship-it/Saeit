/* Accessible, touch-first client for Arrow Escape. No network or accounts. */
(() => {
  'use strict';
  const Core = window.ArrowMazeCore;
  if (!Core) return;
  const $ = id => document.getElementById(id);
  const canvas = $('gameBoard');
  const ctx = canvas.getContext('2d');
  const STORAGE_KEY = 'zm-arrow-escape-v1';
  const FA = n => new Intl.NumberFormat('fa-IR').format(n);
  let audioContext;
  let level = 1;
  let puzzle = Core.generate(1);
  let removed = new Set();
  let hearts = 5;
  let score = 0;
  let baseScore = 0;
  let best = 1;
  let soundOn = true;
  let won = false;
  let animating = null;
  let hintId = -1;
  let hintExpires = 0;
  let boardWidth = 720;
  let animationFrame = 0;

  function safeRead() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); }
    catch (_) { return null; }
  }
  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        version: 1, level, removed: [...removed], hearts, score,
        baseScore, best, soundOn, won
      }));
    } catch (_) { /* Browsers can disable local storage. Game still works. */ }
  }
  function hydrate() {
    const data = safeRead();
    if (!data || data.version !== 1 || !Number.isSafeInteger(data.level) ||
        data.level < 1 || data.level > 1000000) return;
    level = data.level;
    puzzle = Core.generate(level);
    const legitimate = new Set(puzzle.pieces.map(p => p.id));
    removed = new Set((Array.isArray(data.removed) ? data.removed : []).filter(id => legitimate.has(id)));
    hearts = Math.max(0, Math.min(5, Number(data.hearts) || 0));
    score = Math.max(0, Math.min(1000000000, Number(data.score) || 0));
    baseScore = Math.max(0, Math.min(score, Number(data.baseScore) || 0));
    best = Math.max(level, Number(data.best) || level);
    soundOn = data.soundOn !== false;
    won = data.won === true && removed.size === puzzle.pieces.length;
  }
  function remaining() {
    return puzzle.pieces.filter(piece => !removed.has(piece.id));
  }
  function updateUI() {
    $('level').textContent = FA(level);
    $('bestLevel').textContent = FA(best);
    $('score').textContent = FA(score);
    $('heartCount').textContent = ('♥ '.repeat(hearts) + '♡ '.repeat(5 - hearts)).trim();
    $('heartCount').setAttribute('aria-label', FA(hearts) + ' جان باقی مانده');
    const count = puzzle.pieces.length;
    $('progressText').textContent = FA(removed.size) + ' / ' + FA(count);
    $('progressFill').style.width = (count ? 100 * removed.size / count : 100) + '%';
    $('soundButton').textContent = soundOn ? '♫' : '♪̸';
    $('soundButton').setAttribute('aria-label', soundOn ? 'قطع صدا' : 'وصل صدا');
    $('soundButton').setAttribute('aria-pressed', String(soundOn));
  }
  function status(message, type) {
    const element = $('statusText');
    element.textContent = message;
    element.className = 'status-text' + (type ? ' ' + type : '');
  }
  function resize() {
    const rect = canvas.getBoundingClientRect();
    const nextWidth = Math.max(100, Math.round(rect.width * Math.min(2, window.devicePixelRatio || 1)));
    if (canvas.width !== nextWidth) {
      canvas.width = nextWidth;
      canvas.height = nextWidth;
    }
    boardWidth = canvas.width;
    render();
  }
  function cellData() {
    const size = puzzle.size;
    const margin = boardWidth * .065;
    return { margin, cell: (boardWidth - margin * 2) / size, size };
  }
  function drawPiece(piece, offset, color, emphasize) {
    const { margin, cell } = cellData();
    const [dx, dy] = Core.DIRECTIONS[piece.dir];
    const px = p => margin + (p.x + .5 + dx * offset) * cell;
    const py = p => margin + (p.y + .5 + dy * offset) * cell;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.beginPath();
    const path = piece.path;
    ctx.moveTo(px(path[0]), py(path[0]));
    for (let i = 1; i < path.length; i++) ctx.lineTo(px(path[i]), py(path[i]));
    const end = path[path.length - 1];
    const tipX = px(end) + dx * cell * .28;
    const tipY = py(end) + dy * cell * .28;
    ctx.lineTo(tipX, tipY);
    ctx.strokeStyle = '#fffdf4';
    ctx.lineWidth = cell * (emphasize ? .4 : .35);
    ctx.stroke();
    ctx.strokeStyle = color;
    ctx.lineWidth = cell * (emphasize ? .27 : .24);
    ctx.stroke();
    ctx.beginPath();
    const halfWidth = cell * .21;
    const arrowLength = cell * .3;
    const tailX = tipX - dx * arrowLength;
    const tailY = tipY - dy * arrowLength;
    ctx.moveTo(tipX + dx * cell * .11, tipY + dy * cell * .11);
    ctx.lineTo(tailX - dy * halfWidth, tailY + dx * halfWidth);
    ctx.lineTo(tailX + dy * halfWidth, tailY - dx * halfWidth);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }
  function render() {
    if (!ctx) return;
    const { margin, cell, size } = cellData();
    ctx.clearRect(0, 0, boardWidth, boardWidth);
    const bg = ctx.createLinearGradient(0, 0, boardWidth, boardWidth);
    bg.addColorStop(0, '#fffefa');
    bg.addColorStop(1, '#f1f5ed');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, boardWidth, boardWidth);
    ctx.fillStyle = '#e0e8db';
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        ctx.beginPath();
        ctx.arc(margin + (x + .5) * cell, margin + (y + .5) * cell,
          Math.max(1.1, cell * .021), 0, Math.PI * 2);
        ctx.fill();
      }
    }
    const active = remaining();
    const showingHint = Date.now() < hintExpires;
    for (const piece of active) {
      if (animating && animating.id === piece.id) continue;
      const highlighted = showingHint && piece.id === hintId;
      drawPiece(piece, 0, highlighted ? '#19a577' : '#25312c', highlighted);
    }
    if (animating) {
      const ease = 1 - Math.pow(1 - Math.min(1, animating.progress), 3);
      drawPiece(animating.piece, ease * (size + 7), '#24a780', true);
    }
  }
  function distanceToSegment(x, y, a, b) {
    const vx = b.x - a.x, vy = b.y - a.y;
    const length = vx * vx + vy * vy;
    const t = length ? Math.max(0, Math.min(1, ((x - a.x) * vx + (y - a.y) * vy) / length)) : 0;
    return Math.hypot(x - a.x - t * vx, y - a.y - t * vy);
  }
  function pickPiece(event) {
    const rect = canvas.getBoundingClientRect();
    const { margin, cell } = cellData();
    const x = ((event.clientX - rect.left) * canvas.width / rect.width - margin) / cell - .5;
    const y = ((event.clientY - rect.top) * canvas.height / rect.height - margin) / cell - .5;
    let chosen = null;
    let closest = .43;
    for (const piece of remaining()) {
      const path = piece.path;
      for (let i = 1; i < path.length; i++) {
        const distance = distanceToSegment(x, y, path[i - 1], path[i]);
        if (distance < closest) {
          chosen = piece;
          closest = distance;
        }
      }
    }
    return chosen;
  }
  function beep(positive) {
    if (!soundOn) return;
    try {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) return;
      if (!audioContext) audioContext = new Audio();
      if (audioContext.state === 'suspended') audioContext.resume();
      const now = audioContext.currentTime;
      const tone = audioContext.createOscillator();
      const volume = audioContext.createGain();
      tone.type = 'sine';
      tone.frequency.setValueAtTime(positive ? 540 : 210, now);
      tone.frequency.exponentialRampToValueAtTime(positive ? 850 : 130, now + .12);
      volume.gain.setValueAtTime(.001, now);
      volume.gain.exponentialRampToValueAtTime(.07, now + .02);
      volume.gain.exponentialRampToValueAtTime(.001, now + .17);
      tone.connect(volume).connect(audioContext.destination);
      tone.start(now);
      tone.stop(now + .18);
    } catch (_) { /* Sound is optional. */ }
  }
  function showOverlay(title, message, icon, actionText, action) {
    $('overlayTitle').textContent = title;
    $('overlayMessage').textContent = message;
    $('overlayIcon').textContent = icon;
    $('overlayAction').innerHTML = '';
    $('overlayAction').textContent = actionText + ' ←';
    $('overlayAction').onclick = action;
    $('gameOverlay').classList.remove('hidden');
    $('overlayAction').focus({ preventScroll: true });
  }
  function closeOverlay() {
    $('gameOverlay').classList.add('hidden');
  }
  function win() {
    won = true;
    score += 100 + 10 * level + hearts * 15;
    best = Math.max(best, level + 1);
    save();
    updateUI();
    status('تبریک! همهٔ مسیرها آزاد شدند.', 'success');
    showOverlay('درخشان بود! ✨', 'مرحلهٔ ' + FA(level) + ' را تمام کردی. آمادهٔ چالش بعدی هستی؟',
      '✦', 'مرحلهٔ بعد', nextLevel);
  }
  function failure() {
    status('جان‌ها تمام شد؛ دوباره تلاش کن.', 'error');
    showOverlay('این بار نشد!', 'نگران نباش؛ همان معما منتظر توست. دوباره امتحان کن.',
      '↻', 'تلاش دوباره', restart);
  }
  function removeAnimated(piece) {
    const started = performance.now();
    animating = { id: piece.id, piece, progress: 0 };
    function frame(now) {
      if (!animating) return;
      animating.progress = Math.min(1, (now - started) / 365);
      render();
      if (animating.progress < 1) {
        animationFrame = requestAnimationFrame(frame);
        return;
      }
      animating = null;
      removed.add(piece.id);
      score += 10 + Math.min(level, 100);
      hintExpires = 0;
      render();
      if (removed.size === puzzle.pieces.length) {
        win();
      } else {
        status('آفرین! مسیر آزاد شد. بعدی را پیدا کن.', 'success');
        save();
        updateUI();
      }
    }
    animationFrame = requestAnimationFrame(frame);
  }
  function clickBoard(event) {
    if (won || hearts === 0 || animating || !$('gameOverlay').classList.contains('hidden')) return;
    const piece = pickPiece(event);
    if (!piece) return;
    if (Core.canExit(piece, remaining(), puzzle.size)) {
      beep(true);
      removeAnimated(piece);
    } else {
      hearts--;
      beep(false);
      status(hearts ? 'این مسیر بسته است! اول پیکان‌های جلوی آن را آزاد کن.' : 'جان‌ها تمام شد.', 'error');
      updateUI();
      save();
      if (!hearts) failure();
    }
  }
  function restart() {
    cancelAnimationFrame(animationFrame);
    animating = null;
    removed.clear();
    hearts = 5;
    score = baseScore;
    won = false;
    hintExpires = 0;
    closeOverlay();
    updateUI();
    render();
    save();
    status('مرحله از نو شروع شد. اول مسیرهای باز را پیدا کن.');
  }
  function nextLevel() {
    cancelAnimationFrame(animationFrame);
    animating = null;
    level++;
    puzzle = Core.generate(level);
    baseScore = score;
    removed.clear();
    hearts = 5;
    won = false;
    hintExpires = 0;
    closeOverlay();
    updateUI();
    render();
    save();
    status('مرحلهٔ تازه آماده است! پیکان‌ها را آزاد کن.');
  }
  function hint() {
    if (won || !hearts || animating) return;
    const choices = remaining().filter(p => Core.canExit(p, remaining(), puzzle.size));
    if (!choices.length) return;
    hintId = choices[0].id;
    hintExpires = Date.now() + 1900;
    render();
    status('پیکان سبز می‌تواند همین الان خارج شود.', 'success');
    setTimeout(() => { if (Date.now() >= hintExpires) render(); }, 2000);
  }
  hydrate();
  canvas.addEventListener('pointerup', clickBoard);
  $('hintButton').addEventListener('click', hint);
  $('restartButton').addEventListener('click', restart);
  $('soundButton').addEventListener('click', () => { soundOn = !soundOn; updateUI(); save(); });
  window.addEventListener('resize', resize, { passive: true });
  updateUI();
  resize();
  if (won) winRestored();
  else if (!hearts) failure();
  function winRestored() {
    status('مرحله کامل شده است؛ به مرحلهٔ بعد برو.', 'success');
    showOverlay('مرحله تمام شد!', 'برای ادامه آماده‌ای؟', '✦', 'مرحلهٔ بعد', nextLevel);
  }
  window.ArrowMazeDebug = Object.freeze({
    getState: () => ({ level, score, hearts, size: puzzle.size, total: puzzle.pieces.length,
      remaining: remaining().length, solved: Boolean(Core.solve(remaining(), puzzle.size)) }),
    getPuzzle: () => puzzle
  });
})();
