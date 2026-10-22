import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';

test('release attempt remains blocked; CI attests the blocked state', () => {
  const cmd = new URL('../scripts/release-readiness-offline.mjs', import.meta.url);
  const blocked = spawnSync(process.execPath, [cmd.pathname], {encoding:'utf8',timeout:10000});
  assert.equal(blocked.status, 2, blocked.stderr);
  assert.match(blocked.stderr, /MAINNET_RELEASE_DENIED/);
  const result = JSON.parse(blocked.stdout);
  assert.equal(result.status,'BLOCKED');
  assert.equal(result.blocksMainnet,true);
  assert.ok(result.blockers.includes('V1_GENESIS_VAULT_IMPERSONATION_F08'));
  assert.ok(result.blockers.includes('INDEPENDENT_SECURITY_AUDIT_NOT_VERIFIED'));
  assert.equal(result.transactionBroadcast,false);
  const ci = spawnSync(process.execPath, [cmd.pathname, '--assert-blocked'],
    {encoding:'utf8',timeout:10000});
  assert.equal(ci.status,0,ci.stderr);
  assert.equal(JSON.parse(ci.stdout).status,'BLOCKED');
});

test('readiness script is offline, has no signing or mutable blockchain API', () => {
  const src=readFileSync(new URL('../scripts/release-readiness-offline.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(src,/TronWeb|TRON_PRIVATE_KEY|signTransaction|sendRawTransaction|fetch\s*\(|https?:\/\//i);
});
