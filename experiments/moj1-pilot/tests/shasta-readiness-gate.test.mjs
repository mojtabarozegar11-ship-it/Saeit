// Fail-closed readiness tests: only local child processes with public dummy key.
// No transaction signing, network broadcast, RPC calls, or real wallet access.
import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const script = resolve(root, 'scripts/deploy-shasta.mjs');

function dryAttempt(overrides = {}) {
  return spawnSync(process.execPath, [script], {
    cwd: root, encoding: 'utf8', timeout: 10000,
    env: {
      ...process.env,
      TRON_PRIVATE_KEY: '1'.repeat(64), // published dummy key; never fund
      MOJ1_DEPLOY_CONFIRM: 'SHASTA_ONLY',
      MOJ1_DEPLOY_JOURNAL_PATH: '/tmp/moj1-dummy-journal-never-written.json',
      MOJ_SHASTA_GOVERNANCE: '',
      ...overrides
    }
  });
}

test('Shasta deployer refuses to proceed with no on-chain governance address', () => {
  const result = dryAttempt();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /approved Shasta multisig contract address/);
  assert.doesNotMatch(result.stdout, /tokenAddress|BOTH_CONTRACTS_VERIFIED/);
});

test('Shasta deployer refuses malformed governance before touching the chain', () => {
  const result = dryAttempt({MOJ_SHASTA_GOVERNANCE: 'not-a-tron-address'});
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /approved Shasta multisig contract address/);
});

test('Shasta deployment source has explicit governance contract-code and ambiguity gates', () => {
  const src = readFileSync(script, 'utf8');
  assert.match(src, /https:\/\/api\.shasta\.trongrid\.io/);
  assert.equal(src.includes('https://api.trongrid.io'), false);
  assert.match(src, /governanceContract\?\.bytecode/);
  assert.match(src, /journal\.markBroadcastUncertain/);
  assert.match(src, /reconcileDeployment/);
  assert.match(src, /DO NOT REDEPLOY/);
});
