import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const deployScript = resolve(root, 'scripts/deploy-shasta.mjs');

function attempt(env) {
  return spawnSync(process.execPath, [deployScript], {
    cwd: root,
    encoding: 'utf8',
    timeout: 10000,
    env: {...process.env, TRON_PRIVATE_KEY: '', MOJ_SHASTA_TREASURY: '', MOJ1_DEPLOY_CONFIRM: '', ...env}
  });
}

test('deployment refuses to run without exact Shasta confirmation', () => {
  const result = attempt({MOJ1_DEPLOY_CONFIRM: 'MAINNET'});
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /SHASTA_ONLY/);
});

test('deployment refuses to run without a test-only signing key', () => {
  const result = attempt({MOJ1_DEPLOY_CONFIRM: 'SHASTA_ONLY'});
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /dedicated 64-hex-character Shasta-only test wallet key/);
});
