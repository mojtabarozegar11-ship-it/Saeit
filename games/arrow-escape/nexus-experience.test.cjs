'use strict';
const assert = require('node:assert/strict');
const experience = require('./nexus-experience.js');
const empty = experience.metrics([]);
assert.deepEqual(empty, { score: 0, chain: 0, maxChain: 0, removed: 0, twists: 0, energy: 0 });
const actions = [
  { type: 'remove', id: 0 }, { type: 'remove', id: 1 }, { type: 'remove', id: 2 },
  { type: 'twist', step: 1 }, { type: 'remove', id: 3 }
];
const stats = experience.metrics(actions);
assert.deepEqual(stats, { score: 505, chain: 1, maxChain: 3, removed: 4, twists: 1, energy: 20 });
assert.equal(experience.metrics(actions.slice(0, 3)).energy, 60);
assert.equal(experience.rating(7, 7), 3);
assert.equal(experience.rating(9, 7), 2);
assert.equal(experience.rating(12, 7), 1);
assert.equal(experience.worldFor(1).id, 'abyss');
assert.equal(experience.worldFor(5).id, 'abyss');
assert.equal(experience.worldFor(6).id, 'ember');
assert.equal(experience.worldFor(11).id, 'cosmos');
assert.equal(experience.worldFor(16).id, 'aurora');
assert.equal(experience.worldFor(21).id, 'abyss');
console.log('NEXUS_EXPERIENCE_QA=PASS', { combo: stats.maxChain, points: stats.score, chapters: 4 });
