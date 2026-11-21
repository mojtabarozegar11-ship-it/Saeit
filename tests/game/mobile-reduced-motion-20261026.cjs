'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');

const checks = [
  ['games/ramadan-war/game.css', 'Accessible gameplay:', [
    '#game.firing #weaponArt', '#objectiveArrow', 'button:focus-visible',
    '@media (pointer: coarse)', '#interact, #special'
  ]],
  ['games/arrow-escape/style.css', 'Accessible feedback:', [
    '.cube-arrow.blocked', '.cube-arrow.hinted .arrow-stroke',
    '.cube-rotator, .cube-stage, .face-pip'
  ]],
  ['games/arrow-escape/nexus.css', 'Reduced-motion mode also covers', [
    '.nexus-worm-body.ready', '.nexus-burst-note',
    '.viewport.nexus-impact', '.nexus-css3d-cube'
  ]]
];
for (const [path, marker, required] of checks) {
  const css = fs.readFileSync(path, 'utf8');
  const start = css.lastIndexOf('/* ' + marker);
  assert.ok(start >= 0, path + ': accessibility fix missing');
  const section = css.slice(start);
  assert.match(section, /@media\s*\(prefers-reduced-motion:\s*reduce\)/, path + ': no reduced-motion rule');
  for (const selector of required) {
    assert.ok(section.includes(selector), path + ': missing ' + selector);
  }
  assert.match(section, /animation:\s*none\s*!important/, path + ': animation not suppressed');
  console.log('REDUCED_MOTION_STATIC_PASS ' + path);
}
