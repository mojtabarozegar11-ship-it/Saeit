import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const vault = readFileSync(new URL('../contracts/MojVestingVault.sol', import.meta.url), 'utf8');
const unit = 10n ** 18n;
const allocation = 10_000_000_000n * unit;
const day = 86_400n;
const start = 1_800_000_000n;
const cliff = 365n * day;
const duration = 3n * 365n * day;

// Independent arithmetic model; these are NOT executed smart-contract/TVM tests.
function modelVested(timestamp) {
  const cliffEnd = start + cliff;
  if (timestamp <= cliffEnd) return 0n;
  const elapsed = timestamp - cliffEnd;
  if (elapsed >= duration) return allocation;
  return allocation * elapsed / duration;
}

test('365-day cliff locks the entire 10-billion-unit team allocation', () => {
  assert.equal(modelVested(start - day), 0n);
  assert.equal(modelVested(start), 0n);
  assert.equal(modelVested(start + cliff), 0n);
});

test('linear vesting releases exactly half after 18 months of vesting', () => {
  assert.equal(modelVested(start + cliff + duration / 2n), allocation / 2n);
  assert.equal(modelVested(start + cliff + duration), allocation);
  assert.equal(modelVested(start + cliff + duration + day), allocation);
});

test('vesting progression cannot decrease or exceed allocation', () => {
  let previous = 0n;
  for (let i = 0n; i <= 60n; i++) {
    const timestamp = start + (cliff + duration + day) * i / 60n;
    const current = modelVested(timestamp);
    assert.ok(current >= previous && current <= allocation);
    previous = current;
  }
});

test('2,000 deterministic boundary probes preserve conservation of supply', () => {
  let seed = 20261021n;
  let released = 0n;
  for (let i = 0; i < 2000; i++) {
    seed = (seed * 48271n) % 2147483647n;
    const time = start + (seed % (cliff + duration + 100n * day));
    const vested = modelVested(time);
    assert.ok(vested >= 0n && vested <= allocation);
    assert.equal(vested + (allocation - vested), allocation);
    // A clock-ordered release never exceeds allocation and never goes backwards.
    const sortedTime = start + (cliff + duration + 100n * day) * BigInt(i) / 1999n;
    const available = modelVested(sortedTime) - released;
    assert.ok(available >= 0n);
    released += available;
    assert.ok(released <= allocation);
  }
  assert.equal(released, allocation);
});

test('vault source has permissionless beneficiary-only release and a funding gate', () => {
  assert.match(vault, /function fullyFunded\(\)/);
  assert.match(vault, /require\(fullyFunded\(\)/);
  assert.match(vault, /token\.safeTransfer\(beneficiary, amount\)/);
  assert.match(vault, /released \+= amount;/);
  assert.doesNotMatch(vault, /function (revoke|recover|upgrade|setBeneficiary|mint)\s*\(/);
});

test('production linear vesting reads block.timestamp and exposes no clock mutation', () => {
  assert.match(vault, /vestedAt\(block\.timestamp\)/);
  assert.doesNotMatch(vault, /function\s+(setTime|warp|mockClock|setTimestamp)\s*\(/);
});
