import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/index.mjs';

const base = 'https://moj-test.workers.dev';
const secret = 'A'.repeat(64);
const environment = { BRIDGE_SHARED_TOKEN: secret };

test('health is safe and does not reveal credentials', async () => {
  const response = await worker.fetch(new Request(base + '/health'), environment);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.ready, true);
  assert.equal(JSON.stringify(body).includes(secret), false);
});

test('arbitrary URLs are never proxied', async () => {
  const response = await worker.fetch(new Request(base + '/https://evil.example/'), environment);
  assert.equal(response.status, 404);
});

test('missing or incorrect secret is rejected before WebSocket setup', async () => {
  const none = await worker.fetch(new Request(base + '/ws/chat'), environment);
  assert.equal(none.status, 401);
  const wrong = await worker.fetch(
    new Request(base + '/ws/chat', { headers: { 'X-Moj-Bridge-Token': 'wrong' } }),
    environment
  );
  assert.equal(wrong.status, 401);
});

test('private path bearer works but still requires WebSocket upgrade', async () => {
  const good = await worker.fetch(new Request(base + '/bridge/' + secret + '/ws/chat'), environment);
  assert.equal(good.status, 426);
  const bad = await worker.fetch(new Request(base + '/bridge/' + 'B'.repeat(64) + '/ws/chat'), environment);
  assert.equal(bad.status, 401);
});

test('secret must never be blank or short', async () => {
  const response = await worker.fetch(
    new Request(base + '/ws/chat', { headers: { 'X-Moj-Bridge-Token': 'abc' } }),
    { BRIDGE_SHARED_TOKEN: 'abc' }
  );
  assert.equal(response.status, 401);
});
