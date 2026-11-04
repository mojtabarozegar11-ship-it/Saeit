import test from 'node:test';
import assert from 'node:assert/strict';
import {confirmedImportedCampaignSnapshot} from './save-validation.mjs';

test('restored unchanged campaign uses verified imported snapshot', () => {
  const imported = '{"mission":2,"missionPassed":false}';
  assert.equal(confirmedImportedCampaignSnapshot(imported, imported, 'saved'), imported);
});

test('restored completed stage uses its newly normalized committed snapshot', () => {
  const imported = '{"mission":2,"missionPassed":true}';
  const normalized = '{"mission":2,"missionPassed":true,"pickups":[]}';
  assert.equal(confirmedImportedCampaignSnapshot(normalized, normalized, 'saved'), normalized);
  assert.equal(confirmedImportedCampaignSnapshot(imported, normalized, 'saved'), null);
});

test('a competing tab write is rejected instead of adopted', () => {
  const committed = '{"mission":2}';
  assert.equal(confirmedImportedCampaignSnapshot(committed, '{"mission":4}', 'saved'), null);
});

test('failed or blocked writes cannot be reported as verified imports', () => {
  const saved = '{"mission":2}';
  assert.equal(confirmedImportedCampaignSnapshot(saved, saved, 'failed'), null);
  assert.equal(confirmedImportedCampaignSnapshot(saved, null, 'saved'), null);
});

test('missing and empty committed snapshots are rejected', () => {
  assert.equal(confirmedImportedCampaignSnapshot(undefined, undefined, 'saved'), null);
  assert.equal(confirmedImportedCampaignSnapshot('', '', 'saved'), null);
});
