import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const reserve = readFileSync(new URL('../contracts/MojApprovalReserve.sol', import.meta.url), 'utf8');
const escrow = readFileSync(new URL('../contracts/MojGenesisDistributor.sol', import.meta.url), 'utf8');
const spec = JSON.parse(readFileSync(new URL('../tokenomics.json', import.meta.url), 'utf8'));

test('reserve hard caps match owner-approved bucket sizes without changing percentages', () => {
  assert.deepEqual(spec.allocation.map(x => x.percent), [35, 20, 15, 10, 15, 5]);
  assert.match(reserve, /LIQUIDITY_ALLOCATION\s*=\s*15_000_000_000\s*\*\s*10\s*\*\*\s*18/);
  assert.match(reserve, /CONTINGENCY_ALLOCATION\s*=\s*5_000_000_000\s*\*\s*10\s*\*\*\s*18/);
  assert.match(reserve, /LIQUIDITY_TRANCHE_CAP\s*=\s*1_000_000_000\s*\*\s*10\s*\*\*\s*18/);
  assert.match(reserve, /CONTINGENCY_TRANCHE_CAP\s*=\s*250_000_000\s*\*\s*10\s*\*\*\s*18/);
  assert.match(escrow, /reserve\.trancheCap\(\) == cap/);
});

test('no whole-reserve payout, separate delay and cooldown', () => {
  assert.match(reserve, /RELEASE_DELAY\s*=\s*30 days/);
  assert.match(reserve, /RELEASE_INTERVAL\s*=\s*90 days/);
  assert.match(reserve, /amount <= trancheCap/);
  assert.match(reserve, /executableAt < nextReleaseAt/);
  assert.match(reserve, /nextReleaseAt = _clock\(\) \+ RELEASE_INTERVAL/);
  assert.match(reserve, /token\.safeTransfer\(beneficiary, amount\)/);
  assert.doesNotMatch(reserve, /token\.safeTransfer\(beneficiary, allocation\)/);
});

test('unapproved policy cannot silently become an approved production release', () => {
  assert.equal(spec.ownerApproval.releaseScheduleApproved, false);
  assert.equal(spec.ownerApproval.beneficiariesApproved, false);
  assert.equal(spec.ownerApproval.mainnetReleaseApproved, false);
  assert.match(reserve, /msg\.sender == releaseController/);
  assert.match(reserve, /releaseScheduledAt = 0;/);
});
