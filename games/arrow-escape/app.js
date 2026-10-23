/* Arrow Cube: real six-face interactive CSS-3D puzzle with spatial rotation.
 * The original game is independently designed; no third-party art or engine. */
(() => {
  'use strict';
  const Core = window.ArrowMazeCore;
  const Cube = window.ArrowCubeCore;
  if (!Core || !Cube) return;
  const $ = id => document.getElementById(id);
  const FA = n => new Intl.NumberFormat('fa-IR').format(n);
  const KEY = 'zm-arrow-cube-v2';
  const FACES = Cube.FACE_NAMES;
  const MAX_LIVES = 10;
  const initial = { x: -27, y: -34 };
  const stage = $('cubeStage');
  const box = $('puzzleCube');
  const rotator = $('cubeRotator');
  let puzzle = Cube.generate(1);
  let level = 1;
  let removed = new Set();
  let failed = new Set();
  let hearts = MAX_LIVES;
  let score = 0;
  let baseScore = 0;
  let best = 1;
  let combo = 0;
  let soundOn = true;
  let won = false;
  let animating = false;
  let animationVersion = 0;
  let audioContext;
  let hintId = '';
  let xAngle = initial.x, yAngle = initial.y, zoom = 1;
  const touches = new Map();
  let gesture = null;
  let pinchLength = 0;
  let pinchZoom = 1;
  let missedTaps = 0;

  const clamp = (v, low, high) => Math.min(high, Math.max(low, v));
  const finite = (v, fallback) => Number.isFinite(Number(v)) ? Number(v) : fallback;
  function readSave() {
    try { return JSON.parse(localStorage.getItem(KEY) || 'null'); }
    catch (_) { return null; }
  }
  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify({
        version: 2, level, removed: [...removed], failed: [...failed],
        hearts, score, baseScore, best, soundOn, won
      }));
    } catch (_) {}
  }
  function hydrate() {
    const s = readSave();
    if (!s || s.version !== 2 || !Number.isSafeInteger(s.level) ||
        s.level < 1 || s.level > 1000000) return;
    level = s.level;
    puzzle = Cube.generate(level);
    const ids = new Set(puzzle.faces.flatMap(face => face.pieces.map(p => p.id)));
    removed = new Set((Array.isArray(s.removed) ? s.removed : []).filter(id => ids.has(id)));
    failed = new Set((Array.isArray(s.failed) ? s.failed : []).filter(id => ids.has(id)));
    hearts = clamp(Math.floor(finite(s.hearts, MAX_LIVES)), 0, MAX_LIVES);
    score = clamp(Math.floor(finite(s.score, 0)), 0, 1e9);
    baseScore = clamp(Math.floor(finite(s.baseScore, 0)), 0, score);
    best = Math.max(level, Math.min(1e6, Math.floor(finite(s.best, level))));
    soundOn = s.soundOn !== false;
    won = Boolean(s.won) && removed.size === puzzle.total;
  }
  function updateUI() {
    $('level').textContent = FA(level);
    $('bestLevel').textContent = FA(best);
    $('score').textContent = FA(score);
    $('heartCount').textContent = '♥ × ' + FA(hearts);
    $('heartCount').setAttribute('aria-label', FA(hearts) + ' جان باقی مانده');
    $('progressText').textContent = FA(removed.size) + ' / ' + FA(puzzle.total);
    $('progressFill').style.width = (100 * removed.size / Math.max(1, puzzle.total)) + '%';
    $('soundButton').textContent = soundOn ? '♫' : '♪̸';
    $('soundButton').setAttribute('aria-label', soundOn ? 'قطع صدا' : 'وصل صدا');
    $('soundButton').setAttribute('aria-pressed', String(soundOn));
  }
  function status(message, kind = '') {
    $('statusText').textContent = message;
    $('statusText').className = 'status-text' + (kind ? ' ' + kind : '');
  }
  function paintAngle() {
    box.style.transform = 'rotateX(' + xAngle.toFixed(2) + 'deg) rotateY(' +
      yAngle.toFixed(2) + 'deg)';
    rotator.style.transform = 'scale(' + zoom.toFixed(3) + ')';
  }
  function point(p) { return (p.x + .5) + ' ' + (p.y + .5); }
  function arrowGraphic(piece, size) {
    const d = Core.DIRECTIONS[piece.dir];
    const path = piece.path;
    const end = path[path.length - 1];
    const tx = end.x + .5 + d[0] * .25, ty = end.y + .5 + d[1] * .25;
    const baseX = tx - d[0] * .34, baseY = ty - d[1] * .34;
    const wing = .17;
    const shape = 'M ' + path.map(point).join(' L ') + ' L ' + tx + ' ' + ty;
    const tip = [
      [tx + d[0] * .11, ty + d[1] * .11],
      [baseX - d[1] * wing, baseY + d[0] * wing],
      [baseX + d[1] * wing, baseY - d[0] * wing]
    ].map(p => p.join(',')).join(' ');
    const hint = piece.id === hintId ? ' hinted' : '';
    // The narrow visible stroke alone is almost impossible to hit on a phone.
    // Puzzle paths never occupy the same grid cell, so cell-sized invisible
    // targets make every arrow accessible without covering its neighbours.
    const hitPoints = path.map(p => '<circle class="arrow-hit-point" cx="' +
      (p.x + .5) + '" cy="' + (p.y + .5) + '" r=".47"/>').join('');
    return '<g class="cube-arrow' + hint + '" data-arrow-id="' + piece.id +
      '" role="button" aria-label="پیکان ' + piece.id +
      '" tabindex="-1"><path class="arrow-touch" d="' + shape +
      '"/><path class="arrow-stroke" d="' + shape +
      '"/><polygon class="arrow-head" points="' + tip + '"/>' + hitPoints + '</g>';
  }
  function renderFaces() {
    const html = puzzle.faces.map((face, faceIndex) => {
      const items = face.pieces.filter(piece => !removed.has(piece.id));
      return '<div class="cube-face face-' + face.name + '" data-face="' +
        face.name + '" aria-label="وجه ' + (faceIndex + 1) + ' از مکعب"><div class="surface-grain"></div>' +
        '<svg xmlns="http://www.w3.org/2000/svg" class="face-arrows" viewBox="0 0 ' +
        face.size + ' ' + face.size + '" aria-label="پیکان‌های وجه ' + (faceIndex + 1) + '">' +
        items.map(p => arrowGraphic(p, face.size)).join('') +
        '</svg><div class="face-corner" aria-hidden="true"></div></div>';
    }).join('');
    box.innerHTML = html;
    $('hintMoveButton').hidden = !hintId;
    paintAngle();
  }
  function beep(good) {
    if (!soundOn) return;
    try {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) return;
      if (!audioContext) audioContext = new Audio();
      if (audioContext.state === 'suspended') audioContext.resume();
      const now = audioContext.currentTime;
      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(good ? 520 : 205, now);
      oscillator.frequency.exponentialRampToValueAtTime(good ? 960 : 135, now + .16);
      gain.gain.setValueAtTime(.001, now);
      gain.gain.exponentialRampToValueAtTime(.055, now + .022);
      gain.gain.exponentialRampToValueAtTime(.001, now + .22);
      oscillator.connect(gain).connect(audioContext.destination);
      oscillator.start(now);
      oscillator.stop(now + .23);
    } catch (_) {}
  }
  function overlay(title, message, icon, buttonText, action) {
    $('overlayTitle').textContent = title;
    $('overlayMessage').textContent = message;
    $('overlayIcon').textContent = icon;
    $('overlayAction').textContent = buttonText + ' ←';
    $('overlayAction').onclick = action;
    $('gameOverlay').classList.remove('hidden');
    $('overlayAction').focus({ preventScroll: true });
  }
  function closeOverlay() { $('gameOverlay').classList.add('hidden'); }
  function win() {
    won = true;
    score += 140 + 8 * level + 13 * hearts;
    best = Math.max(best, level + 1);
    updateUI(); save();
    status('هر شش وجه آزاد شدند! مرحلهٔ بعد منتظر توست.', 'success');
    overlay('مکعب پاک شد! ✨', 'مرحلهٔ ' + FA(level) +
      ' با موفقیت تمام شد. یک مکعب تازه در راه است.', '◆', 'مرحلهٔ بعد', nextLevel);
  }
  function lose() {
    combo = 0;
    status('جان‌ها تمام شد؛ همین مکعب را دوباره امتحان کن.', 'error');
    overlay('هنوز راه هست!', 'با یک تلاش تازه و بدون از دست دادن امتیاز مرحله‌های قبلی برگرد.',
      '↻', 'تلاش دوباره', restart);
  }
  function findPiece(id) {
    for (const face of puzzle.faces) {
      const p = face.pieces.find(p => p.id === id);
      if (p) return p;
    }
    return null;
  }
  function pickArrow(id) {
    if (!id || won || !hearts || animating || !$('gameOverlay').classList.contains('hidden')) return;
    const piece = findPiece(id);
    if (!piece || removed.has(id)) return;
    const element = [...box.querySelectorAll('.cube-arrow')].find(el => el.dataset.arrowId === id);
    if (Core && Cube.canExit(puzzle, piece, removed)) {
      animating = true; combo++;
      beep(true);
      if (element) {
        element.classList.add('flying');
        const dir = Core.DIRECTIONS[piece.dir];
        element.animate([
          { opacity: 1, transform: 'translate(0,0) scale(1)' },
          { opacity: 0, transform: 'translate(' + (dir[0] * 170) + 'px,' +
            (dir[1] * 170) + 'px) scale(1.12)' }
        ], { duration: 350, easing: 'cubic-bezier(.15,.8,.2,1)', fill: 'forwards' });
      }
      const version = ++animationVersion;
      window.setTimeout(() => {
        if (version !== animationVersion) return;
        removed.add(id);
        score += 10 + Math.min(40, combo * 3);
        hintId = '';
        animating = false;
        missedTaps = 0;
        renderFaces();
        if (removed.size === puzzle.total) win();
        else {
          status('آفرین! ' + FA(puzzle.total - removed.size) + ' پیکان دیگر باقی مانده.', 'success');
          updateUI(); save();
        }
      }, 365);
    } else {
      combo = 0; beep(false);
      if (!failed.has(id)) { failed.add(id); hearts--; }
      if (element) {
        element.classList.add('blocked');
        window.setTimeout(() => element.classList.remove('blocked'), 360);
      }
      status('این پیکان مسدود است؛ وجه دیگری را بررسی کن.', 'error');
      updateUI(); save();
      if (!hearts) lose();
    }
  }
  function restart() {
    animationVersion++;
    removed.clear(); failed.clear(); combo = 0;
    hearts = MAX_LIVES; score = baseScore; won = false;
    hintId = ''; animating = false;
    missedTaps = 0;
    closeOverlay(); renderFaces(); updateUI(); save();
    status('مکعب تازه شد؛ آن را بچرخان و مسیر باز پیدا کن.');
  }
  function nextLevel() {
    animationVersion++;
    level = Math.min(1000000, level + 1);
    puzzle = Cube.generate(level);
    removed.clear(); failed.clear(); combo = 0;
    hearts = MAX_LIVES; baseScore = score; won = false;
    hintId = ''; animating = false;
    missedTaps = 0;
    xAngle = initial.x; yAngle = initial.y; zoom = 1;
    closeOverlay(); renderFaces(); updateUI(); save();
    status('مرحلهٔ ' + FA(level) + ' آماده است. شش وجه را بررسی کن.');
  }
  function focusFace(face) {
    const pose = [[0, 0], [0, -90], [0, 180], [0, 90], [-90, 0], [90, 0]][face];
    xAngle = pose[0]; yAngle = pose[1];
    box.classList.add('turning');
    paintAngle();
    window.setTimeout(() => box.classList.remove('turning'), 650);
  }
  function hint() {
    if (won || !hearts || animating) return;
    const candidate = puzzle.faces.flatMap(f => f.pieces).find(p =>
      !removed.has(p.id) && Cube.canExit(puzzle, p, removed));
    if (!candidate) { status('مکعب بررسی شد؛ برای تلاش مجدد بازنشانی کن.', 'error'); return; }
    hintId = candidate.id;
    renderFaces(); focusFace(candidate.face);
    // Keep the hint visible until acted on; don't expire it while scrolling.
    status('پیکان طلایی آزاد است؛ آن را لمس کن یا دکمهٔ «برداشتن پیکان طلایی» را بزن.', 'success');
    // An animated page scroll can move the target away during the next tap.
    stage.scrollIntoView({ behavior: 'instant', block: 'center' });
  }
  function arrowAt(x, y) {
    // A small tolerance around each tap helps with perspective, scrolling and
    // the natural inaccuracy of fingers on smaller Android screens.
    const offsets = [[0, 0], [0, -10], [-10, 0], [10, 0], [0, 10],
      [-8, -8], [8, -8], [-8, 8], [8, 8]];
    for (const [dx, dy] of offsets) {
      const target = document.elementFromPoint(x + dx, y + dy);
      const arrow = target && target.closest('[data-arrow-id]');
      if (arrow && stage.contains(arrow)) return arrow.dataset.arrowId;
    }
    return null;
  }
  function pointerDown(event) {
    if (event.button !== undefined && event.button !== 0) return;
    const target = event.target.closest?.('[data-arrow-id]');
    touches.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (touches.size === 1) {
      gesture = { x: event.clientX, y: event.clientY, moved: false,
        pointerType: event.pointerType,
        arrow: target?.dataset.arrowId || arrowAt(event.clientX, event.clientY) };
    } else if (touches.size === 2) {
      gesture = null;
      const points = [...touches.values()];
      pinchLength = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
      pinchZoom = zoom;
    }
    try { stage.setPointerCapture(event.pointerId); } catch (_) {}
  }
  function pointerMove(event) {
    if (!touches.has(event.pointerId)) return;
    const before = touches.get(event.pointerId);
    touches.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (touches.size >= 2) {
      const points = [...touches.values()];
      const length = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
      if (pinchLength > 5) zoom = clamp(pinchZoom * length / pinchLength, .64, 1.42);
      paintAngle();
    } else if (gesture) {
      const distance = Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y);
      if (distance > (gesture.pointerType === 'touch' ? 15 : 9)) gesture.moved = true;
      if (gesture.moved) {
        yAngle += (event.clientX - before.x) * .5;
        xAngle -= (event.clientY - before.y) * .5;
        box.classList.remove('turning');
        paintAngle();
        $('dragTip').classList.add('muted');
      }
    }
  }
  function pointerUp(event) {
    if (!touches.has(event.pointerId)) return;
    const old = gesture;
    const wasSingle = touches.size === 1;
    touches.delete(event.pointerId);
    if (wasSingle && old && !old.moved) {
      const id = old.arrow || arrowAt(event.clientX, event.clientY);
      if (id) { missedTaps = 0; pickArrow(id); }
      else if (++missedTaps >= 2) {
        status('پیکان را پیدا نکردی؟ «راهنمایی» را بزن و با دکمهٔ طلایی حرکت کن.');
      }
    }
    gesture = null;
    if (touches.size) {
      const p = [...touches.values()][0];
      gesture = { x: p.x, y: p.y, moved: true, arrow: null };
    }
  }
  function bindInput() {
    stage.addEventListener('pointerdown', pointerDown);
    stage.addEventListener('pointermove', pointerMove);
    stage.addEventListener('pointerup', pointerUp);
    stage.addEventListener('pointercancel', e => { touches.delete(e.pointerId); gesture = null; });
    stage.addEventListener('lostpointercapture', e => { touches.delete(e.pointerId); gesture = null; });
    stage.addEventListener('wheel', e => {
      e.preventDefault(); zoom = clamp(zoom - Math.sign(e.deltaY) * .07, .64, 1.42);
      paintAngle();
    }, { passive: false });
    stage.addEventListener('keydown', e => {
      const delta = 18;
      if (e.key === 'ArrowLeft') yAngle -= delta;
      else if (e.key === 'ArrowRight') yAngle += delta;
      else if (e.key === 'ArrowUp') xAngle += delta;
      else if (e.key === 'ArrowDown') xAngle -= delta;
      else return;
      e.preventDefault(); paintAngle();
    });
    $('zoomIn').addEventListener('click', () => { zoom = clamp(zoom + .13, .64, 1.42); paintAngle(); });
    $('zoomOut').addEventListener('click', () => { zoom = clamp(zoom - .13, .64, 1.42); paintAngle(); });
    $('resetView').addEventListener('click', () => {
      xAngle = initial.x; yAngle = initial.y; zoom = 1;
      box.classList.add('turning'); paintAngle();
      setTimeout(() => box.classList.remove('turning'), 650);
    });
    $('hintButton').addEventListener('click', hint);
    $('hintMoveButton').addEventListener('click', () => {
      if (hintId) pickArrow(hintId);
    });
    $('restartButton').addEventListener('click', restart);
    $('soundButton').addEventListener('click', () => {
      soundOn = !soundOn; updateUI(); save();
    });
  }
  hydrate(); renderFaces(); bindInput(); updateUI();
  if (won) overlay('مرحله تمام شده!', 'برای چالش بعدی آماده‌ای؟', '◆', 'مرحلهٔ بعد', nextLevel);
  else if (!hearts) lose();
  window.ArrowMazeDebug = Object.freeze({
    getState: () => ({
      mode: '3D', level, score, hearts, total: puzzle.total,
      remaining: puzzle.total - removed.size, faces: 6,
      solved: Boolean(Cube.solution(puzzle, removed)), xAngle, yAngle, zoom
    }),
    getPuzzle: () => puzzle,
    tap: id => pickArrow(id),
    face: focusFace
  });
})();
