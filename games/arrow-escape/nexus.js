/* ARROW NEXUS 3D — Three.js renderer and touch-first puzzle client. */
import * as THREE from './three.module.js';

const Core = window.ArrowNexusCore;
const $ = id => document.getElementById(id);
const FA = n => new Intl.NumberFormat('fa-IR').format(n);
const SAVE_KEY = 'zm-arrow-nexus-v1';
const canvas = $('nexusCanvas');
const viewport = $('viewport');
const colors = { free: 0x5ce7cd, blocked: 0x8aa9b4, phase: 0xf5c87b, link: 0xd879ef, source: 0x6fb4fd };
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let level = 1;
let best = 1;
let puzzle = Core.generate(level);
let state = Core.initialState(puzzle);
let moveLog = [];
let busy = false;
let renderer;
let scene;
let camera;
let fixedGroup;
let ringGroup;
let arrowMeshes = [];
let arrowGroups = new Map();
let previewLine;
let azimuth = .62;
let elevation = .47;
let zoom = 8.6;
let initialPointer = null;
let longPressTimer;
let previewTimer;
let frameId;

function message(text) { $('message').textContent = text; }
function validateSavedLog(raw) {
  if (!raw || raw.version !== 1 || !Number.isSafeInteger(raw.level) || raw.level < 1 || raw.level > 100000) return;
  level = raw.level;
  best = Number.isSafeInteger(raw.best) ? Math.max(1, Math.min(100000, raw.best)) : 1;
  puzzle = Core.generate(level);
  state = Core.initialState(puzzle);
  moveLog = [];
  if (Array.isArray(raw.moves)) for (const move of raw.moves.slice(0, 250)) {
    if (!move || !['twist', 'remove'].includes(move.type)) break;
    const next = Core.transition(state, move);
    if (!next) break;
    state = next;
    moveLog.push(move);
  }
}
function load() {
  try { validateSavedLog(JSON.parse(localStorage.getItem(SAVE_KEY) || 'null')); }
  catch (_) { level = 1; puzzle = Core.generate(1); state = Core.initialState(puzzle); moveLog = []; }
}
function save() {
  try { localStorage.setItem(SAVE_KEY, JSON.stringify({ version: 1, level, best, moves: moveLog })); }
  catch (_) { /* Private browsing can prevent storage. */ }
}
function ui() {
  $('stage').textContent = FA(level);
  $('best').textContent = FA(best);
  $('twists').textContent = FA(state.twistsLeft);
  $('progress').textContent = FA(state.removed.length) + ' / ' + FA(puzzle.pieces.length);
  $('twistLeft').disabled = $('twistRight').disabled = busy || state.twistsLeft === 0;
  $('undo').disabled = busy || moveLog.length === 0;
  $('hint').disabled = busy || state.removed.length === puzzle.pieces.length;
}
function vector(values) { return new THREE.Vector3(...values); }
function surfacePoint(piece, offset = 1.62) {
  const f = Core.FACES[piece.face];
  return vector(f.n).multiplyScalar(offset)
    .add(vector(f.u).multiplyScalar(piece.u))
    .add(vector(f.v).multiplyScalar(piece.v));
}
function orientation(piece) {
  const f = Core.FACES[piece.face];
  return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(
    vector(f.u), vector(f.v), vector(f.n)
  ));
}
function makePieceShape() {
  const shape = new THREE.Shape();
  shape.moveTo(-.36, -.095);
  shape.lineTo(.055, -.095);
  shape.lineTo(.055, -.26);
  shape.lineTo(.4, 0);
  shape.lineTo(.055, .26);
  shape.lineTo(.055, .095);
  shape.lineTo(-.36, .095);
  shape.closePath();
  return shape;
}
const arrowGeometry = new THREE.ExtrudeGeometry(makePieceShape(), {
  depth: .045, steps: 1, bevelEnabled: true, bevelThickness: .02, bevelSize: .015, bevelSegments: 2
});
const glowGeometry = new THREE.ShapeGeometry(makePieceShape());
const cubeGeometry = new THREE.BoxGeometry(.976, .976, .976);
const borderGeometry = new THREE.EdgesGeometry(cubeGeometry);
const cubeMaterial = new THREE.MeshPhysicalMaterial({
  color: 0x143b49, metalness: .72, roughness: .31, clearcoat: .8, clearcoatRoughness: .22
});
const edgeMaterial = new THREE.LineBasicMaterial({ color: 0x3f8891, transparent: true, opacity: .35 });

function cubie(x, y, z) {
  const group = new THREE.Group();
  group.position.set(x, y, z);
  const cube = new THREE.Mesh(cubeGeometry, cubeMaterial);
  group.add(cube);
  const edges = new THREE.LineSegments(borderGeometry, edgeMaterial);
  group.add(edges);
  return group;
}
function makeArrow(piece) {
  const group = new THREE.Group();
  group.position.copy(surfacePoint(piece));
  group.quaternion.copy(orientation(piece));
  const active = Core.canExit(piece.id, state);
  const blocked = !active && Core.blockers(piece, state).length > 0;
  const name = active ? (piece.id === 0 && puzzle.level >= 2 ? 'source' : 'free') :
    blocked ? 'blocked' : piece.gate === 'phase' ? 'phase' : piece.gate === 'link' ? 'link' : 'blocked';
  const color = colors[name];
  const shape = new THREE.Mesh(arrowGeometry, new THREE.MeshPhysicalMaterial({
    color, emissive: color, emissiveIntensity: active ? .55 : .17,
    metalness: .33, roughness: .27, clearcoat: .93
  }));
  shape.rotation.z = piece.dir * Math.PI / 2;
  shape.userData.pieceId = piece.id;
  group.add(shape);
  arrowMeshes.push(shape);
  const aura = new THREE.Mesh(glowGeometry, new THREE.MeshBasicMaterial({
    color, transparent: true, opacity: active ? .21 : .09, depthWrite: false, side: THREE.DoubleSide
  }));
  aura.scale.set(1.22, 1.22, 1.22);
  aura.position.z = -.035;
  aura.rotation.z = piece.dir * Math.PI / 2;
  group.add(aura);
  arrowGroups.set(piece.id, group);
  const worldPos = Core.position(piece);
  (worldPos[1] === 0 ? ringGroup : fixedGroup).add(group);
}
function removeGroup(parent) {
  while (parent.children.length) {
    const child = parent.children[0];
    parent.remove(child);
    child.traverse(obj => {
      if (obj.material && ![cubeMaterial, edgeMaterial].includes(obj.material)) obj.material.dispose();
      if (obj.geometry && ![cubeGeometry, borderGeometry, arrowGeometry, glowGeometry].includes(obj.geometry)) obj.geometry.dispose();
    });
  }
}
function clearPreview() {
  clearTimeout(previewTimer);
  if (!previewLine) return;
  scene.remove(previewLine);
  previewLine.geometry.dispose();
  previewLine.material.dispose();
  previewLine = null;
}
function preview(pieceId, persistent = false) {
  clearPreview();
  const piece = state.pieces.find(p => p.id === pieceId);
  if (!piece || state.removed.includes(pieceId)) return;
  const result = Core.canExit(piece, state);
  const from = surfacePoint(piece, 1.72);
  const tangent = vector(Core.tangent(piece));
  const to = from.clone().addScaledVector(tangent, 2.8);
  const geometry = new THREE.BufferGeometry().setFromPoints([from, to]);
  previewLine = new THREE.Line(geometry, new THREE.LineDashedMaterial({
    color: result ? 0x5ce7cd : 0xff8494, dashSize: .15, gapSize: .1, transparent: true, opacity: .9
  }));
  previewLine.computeLineDistances();
  scene.add(previewLine);
  message(result ? 'پیش‌نمایش: این پیکان می‌تواند خارج شود.' :
    piece.gate === 'link' && !state.removed.includes(piece.source) ? 'ابتدا پیکان آبی پیوندی را آزاد کن.' :
    piece.gate === 'phase' && state.phase !== piece.targetPhase ? 'دروازه طلایی به پیچش حلقه میانی نیاز دارد.' :
    'یک پیکان در مسیر خروج قرار دارد.');
  if (!persistent) previewTimer = setTimeout(clearPreview, 2000);
}
function rebuild() {
  clearPreview();
  removeGroup(fixedGroup);
  removeGroup(ringGroup);
  ringGroup.rotation.y = 0;
  arrowMeshes = [];
  arrowGroups.clear();
  for (const y of [-1, 0, 1]) for (const x of [-1, 0, 1]) for (const z of [-1, 0, 1]) {
    (y === 0 ? ringGroup : fixedGroup).add(cubie(x, y, z));
  }
  for (const piece of state.pieces) if (!state.removed.includes(piece.id)) makeArrow(piece);
  ui();
}
function cameraPosition() {
  camera.position.set(zoom * Math.cos(elevation) * Math.sin(azimuth),
    zoom * Math.sin(elevation), zoom * Math.cos(elevation) * Math.cos(azimuth));
  camera.lookAt(0, 0, 0);
}
function resize() {
  const rect = viewport.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  camera.aspect = rect.width / rect.height;
  camera.updateProjectionMatrix();
  renderer.setSize(rect.width, rect.height, false);
}
function initialize() {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.4;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(37, 1, .1, 50);
  scene.add(new THREE.AmbientLight(0x9edbe2, 1.8));
  const key = new THREE.DirectionalLight(0xe4fff2, 3.2); key.position.set(5, 7, 6); scene.add(key);
  const rim = new THREE.DirectionalLight(0x40bde9, 2.1); rim.position.set(-4, -2, -6); scene.add(rim);
  const gold = new THREE.PointLight(0xffcb83, 7, 12); gold.position.set(3, 1.7, -1); scene.add(gold);
  fixedGroup = new THREE.Group();
  ringGroup = new THREE.Group();
  scene.add(fixedGroup, ringGroup);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(2.7, .018, 6, 150),
    new THREE.MeshBasicMaterial({ color: 0x4ac7c7, transparent: true, opacity: .13 }));
  ring.rotation.x = Math.PI / 2;
  scene.add(ring);
  cameraPosition();
  resize();
  rebuild();
  const animate = () => { frameId = requestAnimationFrame(animate); renderer.render(scene, camera); };
  animate();
}
function record(action, next) {
  state = next;
  moveLog.push(action);
  save();
}
function celebrateIfWon() {
  if (state.removed.length !== puzzle.pieces.length) return false;
  best = Math.max(best, level + 1);
  save();
  $('victory').classList.remove('hidden');
  $('next').focus({ preventScroll: true });
  message('تمام پیکان‌ها آزاد شدند؛ فوق‌العاده بود!');
  return true;
}
function playRemove(id) {
  if (busy || !Core.canExit(id, state)) {
    if (!busy) preview(id);
    return;
  }
  const next = Core.transition(state, { type: 'remove', id });
  const piece = state.pieces.find(p => p.id === id);
  const group = arrowGroups.get(id);
  const original = group.position.clone();
  const heading = vector(Core.tangent(piece));
  busy = true;
  ui();
  const duration = reducedMotion ? 0 : 280;
  const started = performance.now();
  function animate(now) {
    const t = duration ? Math.min(1, (now - started) / duration) : 1;
    const ease = 1 - (1 - t) ** 3;
    group.position.copy(original).addScaledVector(heading, ease * 3.4);
    group.scale.setScalar(1 - ease * .25);
    if (t < 1) { requestAnimationFrame(animate); return; }
    record({ type: 'remove', id }, next);
    busy = false;
    rebuild();
    if (!celebrateIfWon()) message('مسیر باز شد! حالا قفل‌ها و پیکان‌های دیگر را بررسی کن.');
  }
  requestAnimationFrame(animate);
}
function playTwist(step) {
  if (busy || state.twistsLeft <= 0) return;
  const next = Core.transition(state, { type: 'twist', step });
  if (!next) return;
  busy = true;
  ui();
  const duration = reducedMotion ? 0 : 480;
  const started = performance.now();
  function animate(now) {
    const t = duration ? Math.min(1, (now - started) / duration) : 1;
    const eased = t < .5 ? 4 * t ** 3 : 1 - ((-2 * t + 2) ** 3) / 2;
    ringGroup.rotation.y = step * Math.PI / 2 * eased;
    if (t < 1) { requestAnimationFrame(animate); return; }
    record({ type: 'twist', step }, next);
    busy = false;
    rebuild();
    message(state.phase === 1 ? 'حلقه هم‌راستا شد؛ دروازه طلایی را بررسی کن!' : 'چیدمان مکعب تغییر کرد. راه تازه را پیدا کن.');
  }
  requestAnimationFrame(animate);
}
function undo() {
  if (busy || !moveLog.length) return;
  moveLog.pop();
  state = Core.initialState(puzzle);
  for (const action of moveLog) state = Core.transition(state, action);
  $('victory').classList.add('hidden');
  rebuild();
  save();
  message('حرکت قبلی بازگردانده شد.');
}
function reset() {
  if (busy) return;
  moveLog = [];
  state = Core.initialState(puzzle);
  $('victory').classList.add('hidden');
  rebuild();
  save();
  message('همان معما از آغاز آماده است.');
}
function nextLevel() {
  level++;
  puzzle = Core.generate(level);
  state = Core.initialState(puzzle);
  moveLog = [];
  $('victory').classList.add('hidden');
  rebuild();
  save();
  message(level === 2 ? 'جدید: فلش آبی، قفل فلش بنفش را باز می‌کند.' :
    level === 4 ? 'جدید: حلقه میانی را بچرخان تا دروازه طلایی فعال شود.' : 'معمای تازه آغاز شد.');
}
function hint() {
  if (busy) return;
  const solution = Core.solve(puzzle, state);
  if (!solution || !solution.length) { message('حرکت معتبری پیدا نشد؛ مرحله را از نو شروع کن.'); return; }
  const first = solution[0];
  if (first.type === 'twist') {
    const control = first.step === -1 ? $('twistLeft') : $('twistRight');
    control.focus({ preventScroll: true });
    message('راهنمایی: برای ادامه، حلقه میانی را ' + (first.step === -1 ? 'به چپ' : 'به راست') + ' بچرخان.');
  } else preview(first.id);
}
function pick(event) {
  const box = canvas.getBoundingClientRect();
  const mouse = new THREE.Vector2(
    (event.clientX - box.left) / box.width * 2 - 1,
    -(event.clientY - box.top) / box.height * 2 + 1
  );
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(mouse, camera);
  const intersections = raycaster.intersectObjects(arrowMeshes, false);
  return intersections.length ? intersections[0].object.userData.pieceId : null;
}
function listen() {
  const clearHold = () => { clearTimeout(longPressTimer); longPressTimer = null; };
  canvas.addEventListener('pointerdown', event => {
    if (busy || !$('victory').classList.contains('hidden')) return;
    initialPointer = { id: event.pointerId, x: event.clientX, y: event.clientY,
      startX: event.clientX, startY: event.clientY, moved: false, long: false };
    canvas.setPointerCapture(event.pointerId);
    clearHold();
    longPressTimer = setTimeout(() => {
      if (!initialPointer || initialPointer.moved) return;
      const id = pick(event);
      if (id !== null) { preview(id, true); initialPointer.long = true; }
    }, 520);
  });
  canvas.addEventListener('pointermove', event => {
    if (!initialPointer || initialPointer.id !== event.pointerId) return;
    const dx = event.clientX - initialPointer.x;
    const dy = event.clientY - initialPointer.y;
    if (Math.hypot(event.clientX - initialPointer.startX, event.clientY - initialPointer.startY) > 8) {
      initialPointer.moved = true;
      clearHold();
    }
    if (initialPointer.moved) {
      azimuth += dx * .009;
      elevation = Math.max(-1.16, Math.min(1.16, elevation + dy * .008));
      cameraPosition();
    }
    initialPointer.x = event.clientX;
    initialPointer.y = event.clientY;
  });
  canvas.addEventListener('pointerup', event => {
    clearHold();
    if (!initialPointer || initialPointer.id !== event.pointerId) return;
    const previous = initialPointer;
    initialPointer = null;
    if (!previous.moved && !previous.long && !busy) {
      const id = pick(event);
      if (id !== null) playRemove(id);
    }
  });
  canvas.addEventListener('pointercancel', () => { initialPointer = null; clearHold(); });
  canvas.addEventListener('wheel', event => {
    event.preventDefault();
    zoom = Math.max(6, Math.min(12, zoom + Math.sign(event.deltaY) * .45));
    cameraPosition();
  }, { passive: false });
  canvas.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft') azimuth -= .12;
    if (event.key === 'ArrowRight') azimuth += .12;
    if (event.key === 'ArrowUp') elevation = Math.min(1.16, elevation + .1);
    if (event.key === 'ArrowDown') elevation = Math.max(-1.16, elevation - .1);
    cameraPosition();
  });
  $('twistLeft').addEventListener('click', () => playTwist(-1));
  $('twistRight').addEventListener('click', () => playTwist(1));
  $('hint').addEventListener('click', hint);
  $('undo').addEventListener('click', undo);
  $('restart').addEventListener('click', reset);
  $('next').addEventListener('click', nextLevel);
  window.addEventListener('resize', resize, { passive: true });
  new ResizeObserver(resize).observe(viewport);
}
load();
try {
  initialize();
  listen();
  if (state.removed.length === state.pieces.length) celebrateIfWon();
  else if (level >= 4 && !moveLog.length) message('چرخش واقعی حلقه فعال است؛ فلش طلایی به هم‌راستایی نیاز دارد.');
} catch (error) {
  console.warn('ARROW_NEXUS_WEBGL_UNAVAILABLE_USING_CSS3D', error);
  import('./nexus-fallback.js').then(module => module.start(Core)).catch(fallbackError => {
    message('اجرای بازی در این دستگاه ممکن نشد؛ لطفاً صفحه را دوباره بارگذاری کنید.');
    console.error('ARROW_NEXUS_ALL_RENDERERS_FAILED', fallbackError);
  });
}
window.ArrowNexusDebug = Object.freeze({
  getState: () => ({ level, best, remaining: state.pieces.length - state.removed.length,
    twistsLeft: state.twistsLeft, phase: state.phase, actions: moveLog.slice(),
    solution: Core.solve(puzzle, state) }),
  getPuzzle: () => puzzle,
  requestRemove: id => playRemove(id),
  requestTwist: step => playTwist(step),
  getRenderer: () => Boolean(renderer && frameId)
});
