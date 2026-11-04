// Ramadan War R58 low-graphics: offline functional regression suite (no browser, server or network).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('./low-graphics.html', import.meta.url), 'utf8');
const game = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(game, 'standalone game script missing');
const KEY = 'ramadan-war-r58-lowgraphics-save-v1';
const prior = (changes = {}) => ({
  format: 'RW-R58-LOWGRAPHICS', version: 1,
  stage: 5, lives: 9, hp: 65, score: 10000, kills: 18,
  rockets: 1, shield: 2, player: { x: 480, y: 440 }, ...changes
});

function boot(saved = null) {
  const els = Object.create(null);
  for (const match of html.matchAll(/id="([^"]+)"/g)) {
    const tag = html.slice(html.lastIndexOf('<', match.index), html.indexOf('>', match.index) + 1);
    els[match[1]] = {
      textContent: '', hidden: /\shidden(?:\s|>|=)/.test(tag), style: {},
      addEventListener() {}, setPointerCapture() {}, click() { this.onclick?.(); },
      getBoundingClientRect() { return { left: 0, top: 0, width: 960, height: 540 }; },
      files: [], value: '', scrollTop: 0
    };
  }
  const noOp = () => {};
  const context = new Proxy({}, { get: () => noOp });
  els.battle.getContext = kind => { assert.equal(kind, '2d'); return context; };
  const doc = {
    getElementById: id => { assert.ok(els[id], 'missing element ' + id); return els[id]; },
    querySelectorAll: () => [],
    addEventListener: noOp,
    createElement: () => ({ click: noOp })
  };
  const win = { addEventListener: noOp };
  const stored = new Map(saved ? [[KEY, JSON.stringify(saved)]] : []);
  const storage = {
    getItem: k => stored.get(k) ?? null,
    setItem: (k, v) => stored.set(k, v),
    removeItem: k => stored.delete(k)
  };
  const frames = [];
  new Function('document', 'window', 'localStorage', 'performance',
    'requestAnimationFrame', 'URL', 'Blob', 'setTimeout', game)(
      doc, win, storage, { now: () => 1000 },
      fn => frames.push(fn), { createObjectURL: () => 'blob:qa', revokeObjectURL: noOp },
      class FakeBlob {}, noOp);
  return { els, stored, frames };
}

test('completed campaign can be reopened without soft-lock and retained until deliberate restart', () => {
  const app = boot(prior({ completed: true }));
  assert.equal(app.els.continue.hidden, false);
  app.els.continue.onclick();
  assert.equal(app.els.heading.textContent, 'پیروزی کارزار');
  assert.equal(app.els.overlay.hidden, false);
  assert.equal(app.frames.length, 0, 'must not enter unwinnable live battle');
  assert.equal(JSON.parse(app.stored.get(KEY)).completed, true);
  app.els.start.onclick();
  const restarted = JSON.parse(app.stored.get(KEY));
  assert.equal(restarted.completed, false);
  assert.equal(restarted.stage, 0);
  assert.equal(restarted.lives, 100);
});

test('older save without completion marker still recognizes finished mission six', () => {
  const app = boot(prior());
  app.els.continue.onclick();
  assert.equal(app.els.heading.textContent, 'پیروزی کارزار');
  assert.equal(app.frames.length, 0);
});

test('regular progression resumes at the saved mission and does not overwrite score', () => {
  const app = boot(prior({ stage: 2, kills: 4, completed: false }));
  app.els.continue.onclick();
  assert.equal(app.els.stage.textContent, '3/۶');
  const saved = JSON.parse(app.stored.get(KEY));
  assert.equal(saved.stage, 2);
  assert.equal(saved.kills, 4);
  assert.equal(saved.score, 10000);
  assert.equal(saved.completed, false);
  assert.equal(app.frames.length, 1);
});

test('corrupt completed marker is rejected without starting a mission', () => {
  const app = boot(prior({ completed: true, stage: 2, kills: 4 }));
  assert.equal(app.els.continue.hidden, true);
  assert.equal(app.frames.length, 0);
});

test('legacy completed JSON import preserves the victory screen', async () => {
  const app = boot();
  const text = JSON.stringify(prior());
  app.els.file.files = [{ size: text.length, text: async () => text }];
  await app.els.file.onchange({ target: app.els.file });
  assert.equal(app.els.heading.textContent, 'پیروزی کارزار');
  assert.equal(JSON.parse(app.stored.get(KEY)).completed, true);
  assert.equal(app.frames.length, 0);
});
