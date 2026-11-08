import test from 'node:test';
import assert from 'node:assert/strict';
import { evaluateSceneSnapshot, compareEditionSnapshots } from '../scripts/living_cities_canvas_gate.mjs';

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
    'no_playable_accessible_world_fallback',
  ]);
});

test('original world remains playable on a WebGL-unsupported device using 81 keyboard-friendly tiles', () => {
  assert.deepEqual(evaluateSceneSnapshot({ ...healthy, display: 'none', width: 0, height: 0,
    webgl2ApiPresent: false, hasAccessibleFallback: true, fallbackTileCount: 81 }), []);
});

test('an incomplete or decorative fallback cannot conceal a missing original world', () => {
  const snapshot = { ...healthy, display: 'none', width: 0, height: 0,
    webgl2ApiPresent: false, hasAccessibleFallback: true, fallbackTileCount: 3 };
  assert.deepEqual(evaluateSceneSnapshot(snapshot), [
    'world_canvas_hidden', 'world_canvas_zero_or_too_small', 'no_playable_accessible_world_fallback',
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

test('two matching world editions have no feature drift', () => {
  const edition = { languageOptions: 20, hasWorldTour: true, hasJourney: false, hasQuests: true };
  assert.deepEqual(compareEditionSnapshots(edition, { ...edition }), []);
});

test('actual reported differences between the two original editions are visible', () => {
  const z = { languageOptions: 0, hasWorldTour: false, hasJourney: true, hasQuests: false };
  const m = { languageOptions: 20, hasWorldTour: true, hasJourney: false, hasQuests: true };
  assert.deepEqual(compareEditionSnapshots(z, m).map((item) => item.field),
    ['languageOptions', 'hasWorldTour', 'hasJourney', 'hasQuests']);
});

test('localized branding differences alone are not declared a defect', () => {
  const core = { languageOptions: 20, hasWorldTour: true, hasJourney: false, hasQuests: true };
  assert.deepEqual(compareEditionSnapshots({ ...core, documentTitle: 'Worlds' },
    { ...core, documentTitle: 'Moj Coin' }), []);
});
