import test from 'node:test';
import assert from 'node:assert/strict';
import { selectRenderQuality } from './render-quality.mjs';

test('phone limits rendering work and disables shadow maps', () => {
  const q = selectRenderQuality(390, 844, 3, true, false);
  assert.equal(q.pixelRatio, 1.1);
  assert.equal(q.shadows, false);
});

test('large mobile viewport stays within its pixel budget', () => {
  const width = 1600, height = 1200;
  const q = selectRenderQuality(width, height, 3, true, false);
  assert.ok(width * height * q.pixelRatio ** 2 <= 900000 + 0.001);
  assert.equal(q.shadows, false);
});

test('desktop retains higher quality within budget', () => {
  const q = selectRenderQuality(1440, 900, 1.25, false, false);
  assert.equal(q.pixelRatio, 1.25);
  assert.equal(q.shadows, true);
});

test('software rendering is conservative even on desktop', () => {
  const q = selectRenderQuality(1024, 768, 2, false, true);
  assert.ok(q.pixelRatio <= 0.78);
  assert.equal(q.shadows, false);
});

test('invalid dimensions and dpr are handled safely', () => {
  const q = selectRenderQuality(NaN, -1, Infinity, true, false);
  assert.ok(Number.isFinite(q.pixelRatio));
  assert.ok(q.pixelRatio > 0);
  assert.equal(q.shadows, false);
});
