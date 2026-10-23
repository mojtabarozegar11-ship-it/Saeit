/* CPU-friendly CSS3D presentation. Uses exactly the same solver and saved moves. */
export function start(Core) {
  const $ = id => document.getElementById(id);
  const Experience = window.NexusExperience;
  Experience.boot();
  const fmt = n => new Intl.NumberFormat('fa-IR').format(n);
  const storeKey = 'zm-arrow-nexus-worm-v3';
  const legacyKey = 'zm-arrow-nexus-v1';
  let level = 1;
  let best = 1;
  let puzzle;
  let state;
  let history = [];
  let yaw = 31;
  let pitch = -24;
  let pointer = null;
  let dragged = false;
  const view = $('viewport');
  const cube = document.createElement('div');
  const frame = document.createElement('div');
  const canvas = $('nexusCanvas');
  canvas.hidden = true;
  frame.className = 'nexus-css3d';
  frame.setAttribute('aria-label', 'نمایش سه‌بعدی جایگزین؛ برای چرخاندن مکعب بکشید و برای آزادسازی روی پیکان لمس کنید');
  cube.className = 'nexus-css3d-cube';
  frame.append(cube);
  view.append(frame);

  function message(value) { $('message').textContent = value; }
  function persist() {
    try { localStorage.setItem(storeKey, JSON.stringify({ version: 3, level, best, moves: history })); }
    catch (_) { /* Storage can be disabled. */ }
  }
  function fromStored() {
    try {
      const raw = JSON.parse(localStorage.getItem(storeKey) || localStorage.getItem(legacyKey) || 'null');
      if (!raw || ![1, 3].includes(raw.version) || !Number.isSafeInteger(raw.level) || raw.level < 1 || raw.level > 100000) return;
      level = raw.level;
      best = Number.isSafeInteger(raw.best) ? Math.max(1, Math.min(100000, raw.best)) : 1;
      puzzle = Core.generate(level);
      state = Core.initialState(puzzle);
      if (raw.version !== 3 || !Array.isArray(raw.moves)) return;
      for (const action of raw.moves.slice(0, 250)) {
        if (!action || !['twist', 'remove'].includes(action.type)) break;
        const next = Core.transition(state, action);
        if (!next) break;
        history.push(action);
        state = next;
      }
    } catch (_) { level = 1; best = 1; puzzle = null; history = []; }
  }
  fromStored();
  puzzle ||= Core.generate(level);
  state ||= Core.initialState(puzzle);

  function orbit() { cube.style.transform = `rotateX(${pitch}deg) rotateY(${yaw}deg)`; }
  function render() {
    $('stage').textContent = fmt(level);
    $('best').textContent = fmt(best);
    $('twists').textContent = fmt(state.twistsLeft);
    $('progress').textContent = `${fmt(state.removed.length)} / ${fmt(puzzle.pieces.length)}`;
    $('twistLeft').disabled = $('twistRight').disabled = state.twistsLeft === 0;
    $('undo').disabled = history.length === 0;
    $('hint').disabled = state.removed.length === puzzle.pieces.length;
    Experience.update(level, puzzle, history);
    const faces = Core.FACE_NAMES.map(name => {
      const side = document.createElement('div');
      side.className = `nexus-css3d-face face-${name}`;
      const grid = document.createElement('div');
      grid.className = 'nexus-css3d-grid';
      for (let i = 0; i < 9; i++) {
        const tile = document.createElement('span');
        tile.className = 'nexus-css3d-tile';
        grid.append(tile);
      }
      side.append(grid);
      // SVG polylines are true tangled arrows, not one square button per arrow.
      // Clicking the body or its head selects the same physical worm.
      const ns = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(ns, 'svg');
      svg.setAttribute('viewBox', '0 0 300 300');
      svg.setAttribute('class', 'nexus-css3d-worms');
      svg.setAttribute('aria-label', 'فلش‌های مارپیچی درهم‌تنیده');
      const pal = ['#5ce7cd', '#6fb4fd', '#f4b36b', '#d879ef', '#ff7d96',
        '#92e87f', '#f2d473', '#70bff9', '#c9a7ff', '#fc9c7e', '#9ee5d0', '#e5aaff'];
      const map = ([u, v]) => [150 + u * 100, 150 - v * 100];
      function wormLine(points) {
        const a = points.map(map);
        const parts = ['M', ...a[0]];
        for (let i = 0; i < a.length - 1; i++) {
          const p0 = a[Math.max(0, i - 1)], p1 = a[i];
          const p2 = a[i + 1], p3 = a[Math.min(a.length - 1, i + 2)];
          parts.push('C', p1[0] + (p2[0] - p0[0]) / 6,
            p1[1] + (p2[1] - p0[1]) / 6,
            p2[0] - (p3[0] - p1[0]) / 6,
            p2[1] - (p3[1] - p1[1]) / 6, ...p2);
        }
        return parts.join(' ');
      }
      for (const piece of state.pieces.filter(p => p.face === name &&
          !state.removed.includes(p.id)).sort((a, b) => a.layer - b.layer)) {
        const ready = Core.canExit(piece, state);
        const color = pal[piece.id % pal.length];
        const d = wormLine(piece.path);
        const glow = document.createElementNS(ns, 'path');
        glow.setAttribute('d', d);
        glow.setAttribute('class', 'nexus-worm-glow');
        glow.setAttribute('stroke', color);
        svg.append(glow);
        const body = document.createElementNS(ns, 'path');
        body.setAttribute('d', d);
        body.setAttribute('class', 'nexus-worm-body' + (ready ? ' ready' : ' blocked'));
        body.setAttribute('stroke', color);
        svg.append(body);
        const hit = document.createElementNS(ns, 'path');
        hit.setAttribute('d', d);
        hit.setAttribute('class', 'nexus-worm-hit');
        hit.dataset.pieceId = String(piece.id);
        hit.setAttribute('role', 'button');
        hit.setAttribute('tabindex', '0');
        hit.setAttribute('aria-label', 'کرم‌فلش شماره ' + fmt(piece.id + 1) +
          (ready ? ' آماده خروج' : ' مسدود'));
        svg.append(hit);
        const [dx, dy] = Core.DIRS[piece.dir];
        const end = [piece.u, piece.v], perp = [-dy, dx];
        const triangle = [[end[0] + dx * .24, end[1] + dy * .24],
          [end[0] - dx * .14 + perp[0] * .18, end[1] - dy * .14 + perp[1] * .18],
          [end[0] - dx * .14 - perp[0] * .18, end[1] - dy * .14 - perp[1] * .18]];
        const head = document.createElementNS(ns, 'polygon');
        head.setAttribute('points', triangle.map(v => map(v).join(',')).join(' '));
        head.setAttribute('class', 'nexus-worm-tip' + (ready ? ' ready' : ''));
        head.setAttribute('fill', ready ? '#f6fff7' : color);
        head.setAttribute('stroke', color);
        head.dataset.pieceId = String(piece.id);
        svg.append(head);
      }
      side.append(svg);
      return side;
    });
    cube.replaceChildren(...faces);
    orbit();
  }
  function won() {
    if (state.removed.length !== puzzle.pieces.length) return;
    best = Math.max(best, level + 1);
    persist();
    $('victory').classList.remove('hidden');
    const award = Experience.complete(level, puzzle, history);
    $('victoryDetail').textContent = 'امتیاز ' + fmt(award.score) + ' · ' +
      '★'.repeat(award.stars) + '☆'.repeat(3 - award.stars) + ' · مسیر مرجع ' + fmt(award.reference) + ' حرکت';
    message('همه پیکان‌ها آزاد شدند!');
  }
  function preview(id) {
    const piece = state.pieces.find(p => p.id === id);
    if (!piece) return;
    const active = Core.canExit(id, state);
    message(active ? 'این پیکان آزاد است؛ یک بار لمسش کن.' :
      piece.gate === 'link' && !state.removed.includes(piece.source) ? 'ابتدا پیکان پیوندی آبی را آزاد کن.' :
      piece.gate === 'phase' && state.phase !== piece.targetPhase ? 'برای دروازه طلایی، حلقه میانی را بچرخان.' :
      piece.gate === 'relay' ? 'مدار دوگانه: دو پیکان منبع باید آزاد شوند.' :
      piece.gate === 'charge' ? 'میدان رزونانس: حداقل سه پیکان را آزاد کن.' :
      'بدنهٔ یک فلش مارپیچی مسیر این فلش را بسته؛ گره را باز کن.');
  }
  function remove(id) {
    if (!Core.canExit(id, state)) { preview(id); Experience.action('locked', level, puzzle, history); return; }
    const next = Core.transition(state, { type: 'remove', id });
    if (!next) return;
    state = next;
    history.push({ type: 'remove', id });
    persist();
    render();
    const bonus = Experience.action('remove', level, puzzle, history);
    if (state.removed.length === puzzle.pieces.length) won();
    else message(bonus.chain >= 3 ? 'رزونانس فعال! زنجیره ' + fmt(bonus.chain) + ' حرکت پشت سر هم.'
      : 'پیکان آزاد شد؛ مکعب را بچرخان و مسیر بعدی را پیدا کن.');
  }
  function twist(step) {
    const next = Core.transition(state, { type: 'twist', step });
    if (!next) return;
    state = next;
    history.push({ type: 'twist', step });
    persist();
    yaw += step * 12;
    render();
    Experience.action('twist', level, puzzle, history);
    message(state.phase === 1 ? 'دروازه طلایی هم‌راستا شد!' : 'حلقه میانی چرخید؛ مسیرهای خروج عوض شدند.');
  }
  function reset(rewind = false) {
    if (rewind && !history.length) return;
    if (rewind) history.pop(); else history = [];
    state = Core.initialState(puzzle);
    for (const action of history) state = Core.transition(state, action);
    $('victory').classList.add('hidden');
    persist();
    render();
    message(rewind ? 'آخرین حرکت برگردانده شد.' : 'معما دوباره آغاز شد.');
  }
  function next() {
    level++;
    puzzle = Core.generate(level);
    state = Core.initialState(puzzle);
    history = [];
    $('victory').classList.add('hidden');
    persist();
    render();
    message('مرحله تازه آغاز شد؛ پیکان‌ها و قفل‌های جدید را کشف کن.');
  }
  function hint() {
    const steps = Core.solve(puzzle, state);
    if (!steps?.length) { message('مسیری پیدا نشد؛ دوباره شروع کن.'); return; }
    const first = steps[0];
    if (first.type === 'twist') message(first.step === -1 ? 'راهنما: حلقه را به چپ بچرخان.' : 'راهنما: حلقه را به راست بچرخان.');
    else preview(first.id);
  }
  frame.addEventListener('pointerdown', event => {
    Experience.primeAudio();
    pointer = { x: event.clientX, y: event.clientY };
    dragged = false;
  });
  frame.addEventListener('pointermove', event => {
    if (!pointer) return;
    const dx = event.clientX - pointer.x;
    const dy = event.clientY - pointer.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) dragged = true;
    if (dragged) {
      yaw += dx * .46;
      pitch = Math.max(-78, Math.min(78, pitch - dy * .45));
      orbit();
    }
    pointer = { x: event.clientX, y: event.clientY };
  });
  frame.addEventListener('pointerup', () => { pointer = null; });
  frame.addEventListener('pointercancel', () => { pointer = null; });
  frame.addEventListener('keydown', event => {
    if ((event.key === 'Enter' || event.key === ' ') && event.target.dataset.pieceId) {
      event.preventDefault();
      remove(Number(event.target.dataset.pieceId));
    }
  });
  frame.addEventListener('click', event => {
    const target = event.target.closest('[data-piece-id]');
    if (!target) return;
    if (dragged) { dragged = false; return; }
    remove(Number(target.dataset.pieceId));
  });
  $('twistLeft').addEventListener('click', () => twist(-1));
  $('twistRight').addEventListener('click', () => twist(1));
  $('hint').addEventListener('click', hint);
  $('undo').addEventListener('click', () => reset(true));
  $('restart').addEventListener('click', () => reset());
  $('next').addEventListener('click', next);
  render();
  if (state.removed.length === puzzle.pieces.length) won();
  else message('کرم‌فلش‌های درهم‌تنیده را لمس کن؛ اول مسیری را آزاد کن که بدنۀ فلش دیگری جلوی آن نیست.');
  window.ArrowNexusDebug = Object.freeze({
    getState: () => ({ level, best, remaining: state.pieces.length - state.removed.length,
      twistsLeft: state.twistsLeft, phase: state.phase, actions: history.slice(), solution: Core.solve(puzzle, state) }),
    getPuzzle: () => puzzle,
    requestRemove: id => remove(id),
    requestTwist: step => twist(step),
    getRenderer: () => false,
    mode: 'css3d'
  });
}
