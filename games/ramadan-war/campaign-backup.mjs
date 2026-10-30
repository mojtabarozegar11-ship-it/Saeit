// Offline-only, explicit user-controlled campaign backup. No network calls.
import {parseCampaignSave,validateCampaignSave} from './save-validation.mjs';

export const CAMPAIGN_BACKUP_FORMAT = 'ramadan-war-campaign-v1';
export const MAX_CAMPAIGN_BACKUP_BYTES = 512 * 1024;

function validCampaign(raw) {
  const campaign = parseCampaignSave(raw);
  return validateCampaignSave(campaign) ? campaign : null;
}

export function makeCampaignBackup(raw) {
  const campaign = validCampaign(raw);
  if (!campaign) return null;
  const result = JSON.stringify({format: CAMPAIGN_BACKUP_FORMAT, version: 1, campaign});
  return new TextEncoder().encode(result).byteLength <= MAX_CAMPAIGN_BACKUP_BYTES ? result : null;
}

export function readCampaignBackup(raw) {
  if (typeof raw !== 'string' || !raw.length ||
      new TextEncoder().encode(raw).byteLength > MAX_CAMPAIGN_BACKUP_BYTES) return null;
  try {
    // Accept an optional leading UTF-8 BOM from text editors after strict byte cap.
    const backup = JSON.parse(raw.charCodeAt(0) === 0xFEFF ? raw.slice(1) : raw);
    if (!backup || Array.isArray(backup) || backup.format !== CAMPAIGN_BACKUP_FORMAT ||
        backup.version !== 1 || !validateCampaignSave(backup.campaign)) return null;
    return JSON.stringify(backup.campaign);
  } catch { return null; }
}
