// Offline, keyless and fail-closed. No chain transaction or deployment entrypoint.
// This report cannot authorize Mainnet, an independent audit, or a public sale.
import {readFileSync} from 'node:fs';
const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
const policy = read('../tokenomics.json');
const shasta = read('../shasta-deployment.json');
const blockers = [];
for (const name of [
  'releaseScheduleApproved', 'beneficiariesApproved', 'multisigApproved', 'mainnetReleaseApproved'
]) {
  if (policy.ownerApproval?.[name] !== true) blockers.push('OWNER_APPROVAL_MISSING_'+name);
}
blockers.push('INDEPENDENT_SECURITY_AUDIT_NOT_VERIFIED');
blockers.push('REWARD_ENTITLEMENT_POLICY_NOT_APPROVED');
blockers.push('REAL_IDENTITY_AND_ANTI_SYBIL_NOT_VERIFIED');
blockers.push('REWARD_ROOT_HUMAN_REVIEW_AND_ONCHAIN_FUNDING_NOT_VERIFIED');
blockers.push('SHASTA_REWARD_ESCROW_ADDRESS_AND_CLAIM_RECEIPTS_MISSING');
blockers.push('LEGAL_MARKET_REVIEW_NOT_VERIFIED');
blockers.push('MAINNET_KEY_CUSTODY_NOT_VERIFIED');
blockers.push('V1_GENESIS_VAULT_IMPERSONATION_F08');
blockers.push('V2_FACTORY_TVM_AND_SHASTA_ENERGY_AUDIT_PENDING');
if (shasta.network !== 'Shasta' || shasta.chain_scope !== 'TESTNET_ONLY' ||
    shasta.mainnet_deployed !== false || shasta.public_sale_enabled !== false ||
    shasta.real_payment_enabled !== false || shasta.allocation_distributed !== false) {
  throw new Error('PILOT_MANIFEST_NOT_FAIL_CLOSED');
}
const output = {
  project:'MOJ1',mode:'OFFLINE_READINESS_REPORT_ONLY',status:'BLOCKED',
  network:'SHASTA_ONLY',blocksMainnet:true,blockers,privateKeyAccessed:false,
  transactionBroadcast:false
};
console.log(JSON.stringify(output,null,2));
if (!process.argv.includes('--assert-blocked')) {
  console.error('MAINNET_RELEASE_DENIED: external review and separately approved release workflow required');
  process.exitCode = 2;
}
