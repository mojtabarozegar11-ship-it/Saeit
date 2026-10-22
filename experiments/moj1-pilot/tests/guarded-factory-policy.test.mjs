import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source = readFileSync(new URL('../contracts/MojGenesisFactoryGuarded.sol', import.meta.url), 'utf8');
const coin = readFileSync(new URL('../contracts/MojCoinGuarded.sol', import.meta.url), 'utf8');

test('candidate V2 creates both genuine vault classes, not arbitrary destination contracts', () => {
  assert.match(source, /new MojVestingVault\s*\(/);
  assert.match(source, /new MojApprovalReserve\s*\(/);
  assert.doesNotMatch(source, /MojVestingVault\(beneficiaries\[i\]\)/);
  assert.doesNotMatch(source, /MojApprovalReserve\(beneficiaries\[i\]\)/);
  assert.match(source, /require\(msg\.sender == governance/);
  assert.match(source, /require\(!distributed/);
  assert.match(source, /require\(beneficiaries\[i\] != address\(0\)/);
  assert.match(source, /require\(beneficiaries\[i\] != beneficiaries\[j\]/);
  assert.match(source, /token\.safeTransfer\(vault, amount\)/);
  assert.doesNotMatch(source, /setTime|test\/MojApprovalReserveClockHarness/);
  assert.match(coin, /_mint\(address\(distributor\), MAX_SUPPLY\)/);
});

test('deployed Shasta V1 stays untouched and V2 remains local-only with no mainnet deployer', () => {
  const v1 = readFileSync(new URL('../contracts/MojGenesisDistributor.sol', import.meta.url), 'utf8');
  assert.match(v1, /MojVestingVault\(destinations\[i\]\)/);
  assert.match(source, /NOT DEPLOYED, NOT INDEPENDENTLY AUDITED/);
});
