'use strict';
/* Executable DOM/Canvas interaction regressions; no network, payments or deployment. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function boot(slug, stored = {}) {
  const html = fs.readFileSync(path.join(__dirname, '../../site_releases/mojplaywin/games-20261021', slug, 'index.html'), 'utf8');
  const match = html.match(/<script>([\s\S]*?)<\/script>/);
  assert.ok(match, 'inline game script missing: ' + slug);
  const listeners = {};
  const elements = {};
  let raf;
  let ts = 0;
  const canvas2d = new Proxy({}, {
    get(target, key) {
      if (key in target) return target[key];
      if (key === 'createLinearGradient' || key === 'createRadialGradient') return () => ({addColorStop() {}});
      return () => {};
    },
    set(target, key, value) { target[key] = value; return true; }
  });
  let document;
  function makeElement(id, dataset = {}) {
    return {
      id, dataset, hidden: false, textContent: '', listeners: {},
      addEventListener(event, callback) { (this.listeners[event] ||= []).push(callback); },
      focus() { document.activeElement = this; },
      getBoundingClientRect() { return {left: 0, top: 0, width: 960, height: 600}; },
      getContext() { return canvas2d; }
    };
  }
  document = {
    body: {}, hidden: false, activeElement: null,
    getElementById(id) { return elements[id] ||= makeElement(id); },
    querySelectorAll(query) {
      if (query !== '[data-control]') return [];
      return ['pulse', 'beam', 'frost', 'petal1', 'petal2', 'petal3', 'petal4', 'petal5', 'petal6', 'replay', 'strike', 'focus']
        .map(name => makeElement('control-' + name, {control: name}));
    },
    addEventListener(name, cb) { (listeners[name] ||= []).push(cb); }
  };
  const window = {addEventListener() {}};
  const localStorage = {
    getItem(k) { return Object.hasOwn(stored, k) ? stored[k] : null; },
    setItem(k, v) { stored[k] = String(v); }
  };
  vm.runInNewContext(match[1], {
    document, window, localStorage, requestAnimationFrame(cb) { raf = cb; }, console, Math
  }, {timeout: 5000, filename: slug + '.js'});
  const el = id => document.getElementById(id);
  function click(id) {
    for (const callback of el(id).listeners.click || []) callback({target: el(id)});
  }
  function press(key, target = el('playfield')) {
    const event = {key, target, repeat: false, defaultPrevented: false, preventDefault() {this.defaultPrevented = true;}};
    for (const callback of listeners.keydown || []) callback(event);
    return event;
  }
  function frame() { ts += 45; assert.equal(typeof raf, 'function'); raf(ts); }
  function until(predicate, maxFrames = 160) {
    for (let i = 0; i < maxFrames; i++) { if (predicate()) return; frame(); }
    assert.fail('game state did not become reachable');
  }
  return {el, click, press, frame, until, document, stored};
}

function testPulse() {
  const g = boot('pulse-forge', {'mpw-beta-20261021-pulse-forge': 'Infinity'});
  assert.equal(g.el('best').textContent, '0', 'invalid saved best must not render Infinity');
  g.click('playButton');
  const initialNotice = g.el('flash').textContent;
  const buttonEvent = g.press(' ', g.el('soundButton'));
  assert.equal(buttonEvent.defaultPrevented, false, 'Space on a real button must remain native');
  assert.equal(g.el('flash').textContent, initialNotice, 'Space on toolbar must not strike the reactor');
  const arenaEvent = g.press(' ', g.el('playfield'));
  assert.equal(arenaEvent.defaultPrevented, true, 'Space in arena must not scroll page');
  assert.match(g.el('flash').textContent, /Signal missed|PERFECT SYNC/);
  console.log('PASS pulse-forge: native button keys, arena strike and corrupt-record validation');
}

function testCipher() {
  const g = boot('cipher-garden');
  g.click('playButton');
  g.until(() => g.el('state').textContent === 'YOUR TURN');
  g.press('r');
  assert.equal(g.el('state').textContent, 'WATCH');
  assert.match(g.el('flash').textContent, /1 assists left/);
  g.until(() => g.el('state').textContent === 'YOUR TURN');
  g.press('r');
  assert.match(g.el('flash').textContent, /0 assists left/);
  g.until(() => g.el('state').textContent === 'YOUR TURN');
  g.press('r');
  assert.equal(g.el('state').textContent, 'YOUR TURN', 'third replay must not reset pattern');
  assert.match(g.el('flash').textContent, /No replays remain/);
  console.log('PASS cipher-garden: replay is functional, bounded and not unlimited');
}

function testSkyline() {
  const g = boot('skyline-keeper');
  g.click('playButton');
  const onButton = g.press(' ', g.el('pauseButton'));
  assert.equal(onButton.defaultPrevented, false, 'toolbar button must keep native Space');
  assert.equal(g.el('flash').textContent.includes('deployed'), false);
  g.press('Enter');
  assert.match(g.el('flash').textContent, /deployed/);
  g.press('ArrowRight');
  assert.match(g.el('flash').textContent, /PLATFORM 2 \/ 1/);
  g.press('Enter');
  assert.match(g.el('flash').textContent, /deployed/);
  g.press('ArrowDown');
  assert.match(g.el('flash').textContent, /PLATFORM 2 \/ 2/);
  g.press('Enter');
  assert.match(g.el('flash').textContent, /deployed/);
  console.log('PASS skyline-keeper: three distinct keyboard tower deployments');
}

testPulse();
testCipher();
testSkyline();
console.log('MPW_FIVE_INTERACTION_REGRESSION_PASS');
