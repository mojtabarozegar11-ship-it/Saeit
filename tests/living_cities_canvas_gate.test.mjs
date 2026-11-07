import test from 'node:test';
import assert from 'node:assert/strict';
import { evaluateSceneSnapshot } from '../scripts/living_cities_canvas_gate.mjs';

const healthy = {
  hasOriginalGameTitle: true,
  hasBuildTab: true,
  hasWorldCanvas: true,
  display: 'block',
  visibility: 'visible',
  width: 900,
  height: 550,
};

test('visible original game scene passes', () => {
  assert.deepEqual(evaluateSceneSnapshot(healthy), []);
});

test('regression: hidden scene fails even when the build tab is visible', () => {
  assert.deepEqual(evaluateSceneSnapshot({ ...healthy, display: 'none', width: 0, height: 0 }), [
    'world_canvas_hidden',
    'world_canvas_zero_or_too_small',
  ]);
});

test('missing original scene cannot be replaced by an unrelated facade', () => {
  assert.deepEqual(evaluateSceneSnapshot({ ...healthy, hasOriginalGameTitle: false, hasWorldCanvas: false }), [
    'original_living_cities_missing',
    'world_canvas_missing',
  ]);
});

test('failure is explicit when the build section is missing', () => {
  assert.deepEqual(evaluateSceneSnapshot({ ...healthy, hasBuildTab: false }), ['build_tab_missing']);
});

test('empty observations fail closed', () => {
  assert.deepEqual(evaluateSceneSnapshot(null), ['missing_scene_snapshot']);
});
