/* CPU-friendly CSS3D presentation. Uses exactly the same solver and saved moves. */
export function start(Core) {
  const $ = id => document.getElementById(id);
  const fmt = n => new Intl.NumberFormat('fa-IR').format(n);
  const storeKey = 'zm-arrow-nexus-v1';
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
    try { localStorage.setItem(storeKey, JSON.stringify({ version: 1, level, best, moves: history })); }
    catch (_) { /* Storage can be disabled. */ }
  }
  function fromStored() {
    try {
      const raw = JSON.parse(localStorage.getItem(storeKey) || 'null');
      if (!raw || raw.version !== 1 || !Number.isSafeInteger(raw.level) || raw.level < 1 || raw.level > 100000) return;
      level = raw.level;
      best = Number.isSafeInteger(raw.best) ? Math.max(1, Math.min(100000, raw.best)) : 1;
      puzzle = Core.generate(level);
      state = Core.initialState(puzzle);
      if (!Array.isArray(raw.moves)) return;
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
      for (const piece of state.pieces) {
        if (piece.face !== name || state.removed.includes(piece.id)) continue;
        const active = Core.canExit(piece, state);
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `nexus-css3d-arrow ${active ? 'ready' : piece.gate === 'phase' ? 'phase' : piece.gate === 'link' ? 'link' : 'blocked'}`;
        button.style.left = `${(piece.u + 1.5) / 3 * 100}%`;
        button.style.top = `${(1.5 - piece.v) / 3 * 100}%`;
        button.style.setProperty('--direction', `${-90 * piece.dir}deg`);
        button.dataset.pieceId = String(piece.id);
        const glyph = document.createElement('span');
        glyph.className = 'arrow-icon';
        glyph.textContent = '➜';
        button.append(glyph);
        button.setAttribute('aria-label', `پیکان ${fmt(piece.id + 1)} در وجه ${name}؛ ${active ? 'آماده خروج' : 'فعلاً قفل'}`);
        side.append(button);
      }
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
    message('همه پیکان‌ها آزاد شدند!');
  }
  function preview(id) {
    const piece = state.pieces.find(p => p.id === id);
    if (!piece) return;
    const active = Core.canExit(id, state);
    message(active ? 'این پیکان آزاد است؛ یک بار لمسش کن.' :
      piece.gate === 'link' && !state.removed.includes(piece.source) ? 'ابتدا پیکان پیوندی آبی را آزاد کن.' :
      piece.gate === 'phase' && state.phase !== piece.targetPhase ? 'برای دروازه طلایی، حلقه میانی را بچرخان.' :
      'مسیر این پیکان مسدود است؛ پیکان جلویی را اول آزاد کن.');
  }
  function remove(id) {
    if (!Core.canExit(id, state)) { preview(id); return; }
    const next = Core.transition(state, { type: 'remove', id });
    if (!next) return;
    state = next;
    history.push({ type: 'remove', id });
    persist();
    render();
    if (state.removed.length === puzzle.pieces.length) won();
    else message('پیکان آزاد شد؛ مکعب را بچرخان و مسیر بعدی را پیدا کن.');
  }
  function twist(step) {
    const next = Core.transition(state, { type: 'twist', step });
    if (!next) return;
    state = next;
    history.push({ type: 'twist', step });
    persist();
    render();
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
  else message('حالت سازگار سه‌بعدی فعال است. مکعب را بکش تا بچرخد و پیکان‌های روشن را لمس کن.');
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
