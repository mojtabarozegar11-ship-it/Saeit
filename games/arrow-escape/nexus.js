/* ARROW NEXUS 3D — Three.js renderer and touch-first puzzle client. */
import * as THREE from './three.module.js';

const Core = window.ArrowNexusCore;
const Experience = window.NexusExperience;
const $ = id => document.getElementById(id);
const FA = n => new Intl.NumberFormat('fa-IR').format(n);
const SAVE_KEY = 'zm-arrow-nexus-worm-v3';
const LEGACY_KEY = 'zm-arrow-nexus-v1';
const canvas = $('nexusCanvas');
const viewport = $('viewport');
const colors = { free: 0x5ce7cd, blocked: 0x8aa9b4, phase: 0xf5c87b, link: 0xd879ef, source: 0x6fb4fd, relay: 0x619ef5, charge: 0xffa06e };
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
let orbitVelocityX = 0;
let orbitVelocityY = 0;
let atmosphere;
let accentLight;

function message(text) { $('message').textContent = text; }
function validateSavedLog(raw) {
  if (!raw || ![1, 3].includes(raw.version) || !Number.isSafeInteger(raw.level) || raw.level < 1 || raw.level > 100000) return;
  level = raw.level;
  best = Number.isSafeInteger(raw.best) ? Math.max(1, Math.min(100000, raw.best)) : 1;
  puzzle = Core.generate(level);
  state = Core.initialState(puzzle);
  moveLog = [];
  if (raw.version === 3 && Array.isArray(raw.moves)) for (const move of raw.moves.slice(0, 250)) {
    if (!move || !['twist', 'remove'].includes(move.type)) break;
    const next = Core.transition(state, move);
    if (!next) break;
    state = next;
    moveLog.push(move);
  }
}
function load() {
  try { validateSavedLog(JSON.parse(localStorage.getItem(SAVE_KEY) || localStorage.getItem(LEGACY_KEY) || 'null')); }
  catch (_) { level = 1; puzzle = Core.generate(1); state = Core.initialState(puzzle); moveLog = []; }
}
function save() {
  try { localStorage.setItem(SAVE_KEY, JSON.stringify({ version: 3, level, best, moves: moveLog })); }
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
  Experience.update(level, puzzle, moveLog);
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
// A worm consists of a long winding body and a physical three-dimensional
// arrowhead. The same body coordinates are used by the collision engine.
const cubeGeometry = new THREE.BoxGeometry(.976, .976, .976);
const borderGeometry = new THREE.EdgesGeometry(cubeGeometry);
const cubeMaterial = new THREE.MeshPhysicalMaterial({
  color: 0x143b49, metalness: .72, roughness: .31, clearcoat: .8, clearcoatRoughness: .22
});
const edgeMaterial = new THREE.LineBasicMaterial({ color: 0x3f8891, transparent: true, opacity: .35 });
function cubie(x, y, z) {
  const group = new THREE.Group();
  group.position.set(x, y, z);
  group.add(new THREE.Mesh(cubeGeometry, cubeMaterial));
  group.add(new THREE.LineSegments(borderGeometry, edgeMaterial));
  return group;
}
function makeArrow(piece) {
  const group = new THREE.Group();
  group.position.copy(surfacePoint(piece));
  group.quaternion.copy(orientation(piece));
  const active = Core.canExit(piece.id, state);
  const palette = [0x5ce7cd, 0x6fb4fd, 0xf4b36b, 0xd879ef, 0xff7d96,
    0x92e87f, 0xf2d473, 0x70bff9, 0xc9a7ff, 0xfc9c7e, 0x9ee5d0, 0xe5aaff];
  const tone = palette[piece.id % palette.length];
  const mat = new THREE.MeshPhysicalMaterial({
    color: tone, emissive: tone, emissiveIntensity: active ? .43 : .14,
    metalness: .46, roughness: .24, clearcoat: 1, clearcoatRoughness: .18
  });
  const nodes = piece.path.map(([u, v], i) =>
    new THREE.Vector3(u - piece.u, v - piece.v, .12 + piece.layer * .075 +
      .028 * Math.sin(i * 1.95 + piece.id)));
  const curve = new THREE.CatmullRomCurve3(nodes, false, 'centripetal', .35);
  const tubeLength = Math.max(38, nodes.length * 9);
  const body = new THREE.Mesh(new THREE.TubeGeometry(curve, tubeLength, .073, 8, false), mat);
  body.userData.pieceId = piece.id;
  group.add(body);
  arrowMeshes.push(body);
  const halo = new THREE.Mesh(new THREE.TubeGeometry(curve, tubeLength, .11, 6, false),
    new THREE.MeshBasicMaterial({ color: tone, transparent: true,
      opacity: active ? .12 : .045, depthWrite: false }));
  group.add(halo);
  const [dx, dy] = Core.DIRS[piece.dir];
  const arrow = new THREE.Mesh(new THREE.ConeGeometry(.17, .36, 8),
    new THREE.MeshPhysicalMaterial({ color: active ? 0xf5fffc : tone,
      emissive: tone, emissiveIntensity: active ? .8 : .35,
      metalness: .38, roughness: .23, clearcoat: 1 }));
  arrow.position.set(dx * .15, dy * .15, nodes[nodes.length - 1].z);
  arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(dx, dy, 0));
  arrow.userData.pieceId = piece.id;
  group.add(arrow);
  arrowMeshes.push(arrow);
  const cap = new THREE.Mesh(new THREE.SphereGeometry(.08, 9, 7), mat);
  cap.position.copy(nodes[0]);
  cap.userData.pieceId = piece.id;
  group.add(cap);
  arrowMeshes.push(cap);
  const beadGeo = new THREE.SphereGeometry(.085, 7, 6);
  for (let i = 1, count = Math.min(12, nodes.length * 2); i < count; i++) {
    const bead = new THREE.Mesh(beadGeo, mat);
    bead.position.copy(curve.getPoint(i / count));
    bead.scale.set(.72, .72, .56);
    bead.userData.pieceId = piece.id;
    group.add(bead);
    arrowMeshes.push(bead);
  }
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
      if (obj.geometry && ![cubeGeometry, borderGeometry].includes(obj.geometry)) obj.geometry.dispose();
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
    piece.gate === 'relay' ? 'مدار دوگانه را فعال کن: ابتدا هر دو پیکان منبع را خارج کن.' :
    piece.gate === 'charge' ? 'میدان رزونانس: دست‌کم سه پیکان دیگر را آزاد کن.' :
    'بدنهٔ یک فلش مارپیچی جلوی سر این فلش را گرفته؛ گره را از بیرون باز کن.');
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
  const world = Experience.worldFor(level).id;
  const palettes = { abyss: [0x143b49, 0x3f8891, 0x40bde9],
    ember: [0x59362f, 0xa77855, 0xff935a], cosmos: [0x302f62, 0x8d79d6, 0x9876ff],
    aurora: [0x144945, 0x57bca9, 0x6bffce] };
  const palette = palettes[world];
  cubeMaterial.color.setHex(palette[0]);
  edgeMaterial.color.setHex(palette[1]);
  if (accentLight) accentLight.color.setHex(palette[2]);
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
  accentLight = new THREE.PointLight(0x4ff8e6, 10, 15);
  accentLight.position.set(-3, 3, 4);
  scene.add(accentLight);
  atmosphere = new THREE.Group();
  const orbits = [
    [3.12, 0x6ffbe2, .24, Math.PI / 2],
    [3.36, 0xf4c57c, .14, Math.PI / 3],
    [3.68, 0x8b9cf5, .13, -.43]
  ];
  for (const [radius, tone, opacity, tilt] of orbits) {
    const circle = new THREE.Mesh(new THREE.TorusGeometry(radius, .012, 6, 128),
      new THREE.MeshBasicMaterial({ color: tone, transparent: true, opacity, depthWrite: false }));
    circle.rotation.x = tilt;
    atmosphere.add(circle);
  }
  const stars = [];
  let seed = 0x9e3779b9;
  const random = () => { seed ^= seed << 13; seed ^= seed >>> 17; seed ^= seed << 5; return (seed >>> 0) / 4294967296; };
  for (let i = 0; i < 175; i++) {
    const radius = 4.3 + random() * 4.2, theta = random() * Math.PI * 2, phi = Math.acos(random() * 2 - 1);
    stars.push(radius * Math.sin(phi) * Math.cos(theta), radius * Math.cos(phi), radius * Math.sin(phi) * Math.sin(theta));
  }
  const starGeometry = new THREE.BufferGeometry();
  starGeometry.setAttribute('position', new THREE.Float32BufferAttribute(stars, 3));
  atmosphere.add(new THREE.Points(starGeometry, new THREE.PointsMaterial({
    color: 0xa4fff3, size: .055, transparent: true, opacity: .6, sizeAttenuation: true
  })));
  scene.add(atmosphere);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(2.7, .018, 6, 150),
    new THREE.MeshBasicMaterial({ color: 0x4ac7c7, transparent: true, opacity: .13 }));
  ring.rotation.x = Math.PI / 2;
  scene.add(ring);
  cameraPosition();
  resize();
  rebuild();
  const animate = () => {
    frameId = requestAnimationFrame(animate);
    if (atmosphere && !reducedMotion) atmosphere.rotation.y += .0012;
    if (!initialPointer && (Math.abs(orbitVelocityX) + Math.abs(orbitVelocityY)) > .0001) {
      azimuth += orbitVelocityX;
      elevation = Math.max(-1.16, Math.min(1.16, elevation + orbitVelocityY));
      orbitVelocityX *= .91;
      orbitVelocityY *= .91;
      cameraPosition();
    }
    renderer.render(scene, camera);
  };
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
  const badge = Experience.complete(level, puzzle, moveLog);
  $('victoryDetail').textContent = 'امتیاز ' + FA(badge.score) + ' · ' + '★'.repeat(badge.stars) +
    '☆'.repeat(3 - badge.stars) + ' · مسیر مرجع ' + FA(badge.reference) + ' حرکت';
  message('تمام پیکان‌ها آزاد شدند؛ فوق‌العاده بود!');
  return true;
}
function playRemove(id) {
  if (busy || !Core.canExit(id, state)) {
    if (!busy) { preview(id); Experience.action('locked', level, puzzle, moveLog); }
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
    group.rotation.z = Math.sin(ease * Math.PI * 2.5) * (1 - ease) * .065;
    group.scale.setScalar(1 - ease * .16);
    if (t < 1) { requestAnimationFrame(animate); return; }
    record({ type: 'remove', id }, next);
    busy = false;
    rebuild();
    const bonus = Experience.action('remove', level, puzzle, moveLog);
    if (!celebrateIfWon()) message(bonus.chain >= 3
      ? 'رزونانس ' + FA(bonus.chain) + ' برابری! پیکان‌های بعدی امتیاز بیشتری دارند.'
      : 'مسیر باز شد! حالا قفل‌ها و پیکان‌های دیگر را بررسی کن.');
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
    Experience.action('twist', level, puzzle, moveLog);
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
    level === 12 ? 'جدید: حلقه میانی را بچرخان تا دروازه طلایی فعال شود.' : 'معمای تازه آغاز شد.');
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
    Experience.primeAudio();
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
      orbitVelocityX = dx * .0024;
      orbitVelocityY = dy * .002;
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
Experience.boot();
try {
  initialize();
  listen();
  if (state.removed.length === state.pieces.length) celebrateIfWon();
  else if (!moveLog.length) message('بدنه‌های مارپیچی روی هم افتاده‌اند؛ فلشی را لمس کن که مسیر سرش آزاد است.');
} catch (error) {
  console.warn('ARROW_NEXUS_WEBGL_UNAVAILABLE_USING_CSS3D', error);
  import('./nexus-fallback.js?v=worm-1-20261023').then(module => module.start(Core)).catch(fallbackError => {
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
