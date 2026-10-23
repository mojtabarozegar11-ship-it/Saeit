/* ARROW NEXUS: shared progression, audio, and cinematic effects for both renderers. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.NexusExperience = api;
})(typeof window !== 'undefined' ? window : undefined, function () {
  'use strict';
  const PROFILE = 'zm-arrow-nexus-v2-profile';
  const AUDIO = 'zm-arrow-nexus-v2-sound';
  const WORLDS = [
    { id: 'abyss', title: 'ژرفای اقیانوسی', label: 'ABYSS CIRCUIT' },
    { id: 'ember', title: 'دژِ آتش', label: 'EMBER FORGE' },
    { id: 'cosmos', title: 'مدار کیهانی', label: 'COSMIC ARRAY' },
    { id: 'aurora', title: 'قلمرو شفق', label: 'AURORA VAULT' }
  ];
  let booted = false;
  let muted = false;
  let audioContext = null;
  let profile = { records: {} };
  let lastContext = null;
  const $ = id => typeof document === 'undefined' ? null : document.getElementById(id);
  const fa = n => new Intl.NumberFormat('fa-IR').format(n);
  const worldFor = level => WORLDS[Math.floor((Math.max(1, level) - 1) / 5) % WORLDS.length];
  function metrics(actions) {
    let score = 0, chain = 0, maxChain = 0, removed = 0, twists = 0;
    for (const action of actions || []) {
      if (action.type === 'remove') {
        chain++;
        removed++;
        maxChain = Math.max(maxChain, chain);
        score += 100 + Math.min(chain - 1, 7) * 35;
      } else if (action.type === 'twist') {
        chain = 0;
        twists++;
      }
    }
    return { score, chain, maxChain, removed, twists, energy: Math.min(100, chain * 20) };
  }
  function rating(actual, reference) {
    if (!Number.isFinite(actual) || !Number.isFinite(reference) || reference < 1) return 1;
    return actual <= reference ? 3 : actual <= reference + 3 ? 2 : 1;
  }
  function readProfile() {
    try {
      const raw = JSON.parse(localStorage.getItem(PROFILE) || 'null');
      if (raw && typeof raw.records === 'object' && raw.records !== null && !Array.isArray(raw.records))
        profile = { records: raw.records };
    } catch (_) { /* Storage is optional. */ }
    try { muted = localStorage.getItem(AUDIO) === 'off'; } catch (_) { /* Optional. */ }
  }
  function writeProfile() {
    try { localStorage.setItem(PROFILE, JSON.stringify(profile)); } catch (_) { /* Optional. */ }
  }
  function sound(kind) {
    if (muted || typeof window === 'undefined') return;
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return;
    try {
      audioContext ||= new Audio();
      if (audioContext.state === 'suspended') audioContext.resume().catch(() => {});
      const notes = {
        release: [[440, 660], .16, 'sine'],
        twist: [[180, 320], .28, 'triangle'],
        locked: [[140, 115], .1, 'sawtooth'],
        win: [[523, 784], .49, 'sine'],
        pulse: [[330, 990], .3, 'sine']
      };
      const [freq, duration, waveform] = notes[kind] || notes.release;
      const osc = audioContext.createOscillator();
      const gain = audioContext.createGain();
      const now = audioContext.currentTime;
      osc.type = waveform;
      osc.frequency.setValueAtTime(freq[0], now);
      osc.frequency.exponentialRampToValueAtTime(freq[1], now + duration);
      gain.gain.setValueAtTime(.0001, now);
      gain.gain.exponentialRampToValueAtTime(.045, now + .015);
      gain.gain.exponentialRampToValueAtTime(.0001, now + duration);
      osc.connect(gain);
      gain.connect(audioContext.destination);
      osc.start(now);
      osc.stop(now + duration + .02);
    } catch (_) { /* Audio must never block input. */ }
  }
  function primeAudio() {
    if (muted || typeof window === 'undefined') return;
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return;
    try {
      audioContext ||= new Audio();
      if (audioContext.state === 'suspended') audioContext.resume().catch(() => {});
    } catch (_) { /* Audio is optional. */ }
  }
  function soundButton() {
    const button = $('soundToggle');
    if (!button) return;
    button.textContent = muted ? '◌ صدا خاموش' : '♫ صدا روشن';
    button.setAttribute('aria-pressed', String(!muted));
  }
  function burst(kind = 'release', point = null) {
    if (typeof document === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const layer = $('nexusFx');
    const view = $('viewport');
    if (!layer || !view) return;
    const rect = view.getBoundingClientRect();
    const x = point?.x == null ? rect.width / 2 : point.x - rect.left;
    const y = point?.y == null ? rect.height / 2 : point.y - rect.top;
    const count = kind === 'win' ? 46 : kind === 'pulse' ? 25 : kind === 'twist' ? 18 : 14;
    for (let i = 0; i < count; i++) {
      const particle = document.createElement('span');
      particle.className = 'nexus-particle ' + kind;
      const angle = (i / count) * Math.PI * 2 + (i % 3) * .17;
      const distance = kind === 'win' ? 110 + (i % 7) * 23 : 42 + (i % 5) * 21;
      particle.style.left = x + 'px';
      particle.style.top = y + 'px';
      particle.style.setProperty('--dx', Math.cos(angle) * distance + 'px');
      particle.style.setProperty('--dy', Math.sin(angle) * distance + 'px');
      particle.style.setProperty('--spin', (i % 2 ? 270 : -270) + 'deg');
      layer.append(particle);
      particle.addEventListener('animationend', () => particle.remove(), { once: true });
      setTimeout(() => particle.remove(), 1400);
    }
    if (kind === 'win' || kind === 'pulse') {
      view.classList.remove('nexus-impact');
      void view.offsetWidth;
      view.classList.add('nexus-impact');
      setTimeout(() => view.classList.remove('nexus-impact'), 520);
    }
  }
  function boot() {
    if (booted || typeof document === 'undefined') return;
    readProfile();
    booted = true;
    const toggle = $('soundToggle');
    if (toggle) toggle.addEventListener('click', () => {
      muted = !muted;
      try { localStorage.setItem(AUDIO, muted ? 'off' : 'on'); } catch (_) { /* Optional. */ }
      soundButton();
      if (!muted) sound('release');
    });
    soundButton();
  }
  function update(level, puzzle, actions) {
    boot();
    const experience = metrics(actions);
    lastContext = { level, puzzle, actions };
    const world = worldFor(level);
    if (typeof document !== 'undefined') {
      document.body.dataset.world = world.id;
      if ($('score')) $('score').textContent = fa(experience.score);
      if ($('combo')) $('combo').textContent = '×' + fa(Math.max(1, experience.chain));
      if ($('charge')) $('charge').style.width = experience.energy + '%';
      if ($('chargeLabel')) $('chargeLabel').textContent = experience.chain >= 3
        ? 'رزونانس فعال · آزادسازی زنجیره‌ای!' : 'رزونانس · ' + fa(experience.energy) + '٪';
      if ($('chapter')) $('chapter').textContent = world.title + ' · ' + world.label;
      if ($('par')) $('par').textContent = fa(puzzle.solution?.length || 0);
      const record = profile.records[level];
      if ($('medal')) $('medal').textContent = record ? '★'.repeat(record.stars) + '☆'.repeat(3 - record.stars) : '☆☆☆';
      if ($('record')) $('record').textContent = fa(record?.points || 0);
    }
    return experience;
  }
  function action(kind, level, puzzle, actions, point = null) {
    const data = update(level, puzzle, actions);
    if (kind === 'remove') {
      const amplified = data.chain >= 3;
      burst(amplified ? 'pulse' : 'release', point);
      sound(amplified ? 'pulse' : 'release');
    } else if (kind === 'twist') {
      burst('twist', point);
      sound('twist');
    } else if (kind === 'locked') sound('locked');
    return data;
  }
  function complete(level, puzzle, actions) {
    const stats = update(level, puzzle, actions);
    const stars = rating(actions.length, puzzle.solution?.length || actions.length);
    const previous = profile.records[level];
    if (!previous || stars > previous.stars || (stars === previous.stars && stats.score > previous.points)) {
      profile.records[level] = { stars, points: stats.score, actions: actions.length };
      writeProfile();
    }
    burst('win');
    sound('win');
    update(level, puzzle, actions);
    return { stars, score: stats.score, reference: puzzle.solution?.length || 0 };
  }
  return { boot, primeAudio, update, action, complete, metrics, rating, worldFor,
    getRecords: () => JSON.parse(JSON.stringify(profile.records)) };
});
