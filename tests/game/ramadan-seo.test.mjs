import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const html = readFileSync(new URL('../../games/ramadan-war/index.html', import.meta.url), 'utf8');
const head = html.split('</head>')[0];

test('Ramadan War has one production canonical URL and Persian document language', () => {
  assert.match(html, /<html lang="fa" dir="rtl">/);
  assert.equal((head.match(/rel="canonical"/g) || []).length, 1);
  assert.match(head, /rel="canonical" href="https:\/\/zomorodmelal\.ir\/ramadan-war\/"/);
});

test('Ramadan War sharing metadata points to the real game without invented images', () => {
  assert.match(head, /property="og:type" content="website"/);
  assert.match(head, /property="og:locale" content="fa_IR"/);
  assert.match(head, /property="og:url" content="https:\/\/zomorodmelal\.ir\/ramadan-war\/"/);
  assert.match(head, /property="og:title" content="[^"]+"/);
  assert.match(head, /property="og:description" content="[^"]+"/);
  assert.match(head, /name="twitter:card" content="summary"/);
  assert.doesNotMatch(head, /property="og:image"/);
});

test('mobile viewport permits user zoom instead of locking page magnification', () => {
  const viewport = head.match(/<meta name="viewport" content="([^"]+)"/)?.[1];
  assert.ok(viewport, 'viewport metadata must exist');
  assert.match(viewport, /width=device-width/);
  assert.doesNotMatch(viewport, /user-scalable\s*=\s*(?:no|0)|maximum-scale\s*=\s*1/i);
});
