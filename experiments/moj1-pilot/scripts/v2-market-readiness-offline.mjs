// Offline MOJ1 V2 evidence-consistency inspection only; NEVER authorizes a release.
// No private keys, wallet, RPC, network fetch, deployment, pricing, or transactions.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const ANCHOR = '4411b28325be44c54d7917b4c67786348521b6a9';
const ALLOCATION = Object.freeze({
  player_rewards_and_ecosystem:35,
  product_and_security_development:20,
  future_liquidity_reserve:15,
  team_and_contributors:10,
  partners_and_creators:15,
  contingency_and_audit_reserve:5,
});

function safeUint(value) {
  if (typeof value !== 'string' || !/^(?:0|[1-9]\d*)$/.test(value)) return null;
  return BigInt(value);
}

export function assessV2MarketGate(tokenomics, v1, v2) {
  const inconsistencies = [];
  const fail = (code, condition) => { if (!condition) inconsistencies.push(code); };
  if (!tokenomics || !v1 || !v2 || typeof tokenomics !== 'object' ||
      typeof v1 !== 'object' || typeof v2 !== 'object') {
    return {
      project:'MOJ1', status:'NO_GO', marketOrMainnetAuthorized:false,
      offline:true, transactionBroadcast:false,
      inconsistencies:['MISSING_OR_INVALID_INPUT_MANIFEST'],
      blockers:['INDEPENDENT_AUDIT_NOT_ATTESTED','LEGAL_REVIEW_NOT_ATTESTED',
        'TREASURY_AND_LIQUIDITY_NOT_FUNDED_OR_ATTESTED','OWNER_MAINNET_APPROVAL_REQUIRED'],
    };
  }

  fail('WRONG_V2_IDENTITY', v2.project === 'MOJ1' && v2.version === 'V2_GUARDED_CANDIDATE' &&
    v2.contractStandard === 'TRC-20');
  fail('V2_NOT_TESTNET_ONLY', v2.network === 'Shasta' && v2.chain_scope === 'TESTNET_ONLY');
  fail('V1_NOT_TESTNET_ONLY', v1.network === 'Shasta' && v1.chain_scope === 'TESTNET_ONLY');
  fail('V2_TRANSACTION_FLAGS_NOT_CLOSED', v2.distribution_enabled === false &&
    v2.public_sale_enabled === false && v2.real_payment_enabled === false &&
    v2.mainnet_deployed === false);
  fail('V1_TRANSACTION_FLAGS_NOT_CLOSED', v1.allocation_distributed === false &&
    v1.public_sale_enabled === false && v1.real_payment_enabled === false &&
    v1.mainnet_deployed === false);
  fail('V2_V1_IDENTITY_COLLISION', typeof v2.candidate_token_contract === 'string' &&
    typeof v1.token_contract === 'string' &&
    v2.candidate_token_contract !== v1.token_contract &&
    v2.previous_V1_token_testnet === v1.token_contract);
  fail('V2_FACTORY_MISSING', typeof v2.candidate_genesis_factory === 'string' &&
    v2.candidate_genesis_factory.length > 20 &&
    v2.candidate_genesis_factory !== v2.candidate_token_contract);
  fail('FROZEN_AUDIT_ANCHOR_MISMATCH', v2.source_audit_anchor_commit === ANCHOR);

  const v2Supply = safeUint(v2.total_supply_whole);
  const escrow = safeUint(v2.escrow_balance_whole);
  const policySupply = typeof tokenomics.totalWholeTokens === 'number' &&
    Number.isSafeInteger(tokenomics.totalWholeTokens) &&
    tokenomics.totalWholeTokens >= 0 ? BigInt(tokenomics.totalWholeTokens) : null;
  fail('SUPPLY_OR_ESCROW_MISMATCH',
    v2Supply === 100000000000n && escrow === v2Supply && policySupply === v2Supply &&
    tokenomics.fixedSupply === true && tokenomics.decimals === 18);

  const buckets = tokenomics.allocation;
  if (!Array.isArray(buckets) || buckets.length !== 6) {
    inconsistencies.push('ALLOCATION_SIX_BUCKETS_REQUIRED');
  } else {
    let percentages = 0, tokens = 0n;
    const seen = new Set();
    let allocationValid = true;
    for (const item of buckets) {
      if (!item || typeof item.bucket !== 'string' || seen.has(item.bucket) ||
          !(item.bucket in ALLOCATION) || !Number.isSafeInteger(item.percent) ||
          item.percent !== ALLOCATION[item.bucket] ||
          !Number.isSafeInteger(item.tokens) || item.tokens < 0 ||
          BigInt(item.tokens) !== 100000000000n * BigInt(item.percent) / 100n) {
        allocationValid = false;
      } else {
        percentages += item.percent;
        tokens += BigInt(item.tokens);
      }
      if (item?.bucket) seen.add(item.bucket);
    }
    fail('ALLOCATION_POLICY_MISMATCH',
      allocationValid && seen.size === 6 && percentages === 100 && tokens === v2Supply);
  }

  const approvals = tokenomics.ownerApproval;
  fail('UNVERIFIED_OWNER_RELEASE_STATE', approvals &&
    approvals.releaseScheduleApproved === false &&
    approvals.beneficiariesApproved === false &&
    approvals.multisigApproved === false &&
    approvals.mainnetReleaseApproved === false);
  fail('EXTERNAL_REVIEW_STATUS_NOT_PENDING',
    v2.independent_security_audit === 'PENDING' &&
    v2.production_custody === 'PENDING' && v2.legal_market_review === 'PENDING');

  return {
    project:'MOJ1', version:'V2_GUARDED_CANDIDATE',
    status:'NO_GO', marketOrMainnetAuthorized:false,
    offline:true, transactionBroadcast:false, testnetEvidenceOnly:true,
    auditAnchor:ANCHOR, inconsistencies,
    blockers:[
      'INDEPENDENT_AUDIT_NOT_ATTESTED',
      'FULL_DEPENDENCY_AND_F08_REMEDIATION_REVIEW_REQUIRED',
      'LEGAL_AND_TARGET_MARKET_REVIEW_NOT_ATTESTED',
      'BENEFICIARIES_RELEASE_SCHEDULE_AND_MULTISIG_NOT_APPROVED',
      'NO_VERIFIED_REAL_USDT_TRX_LIQUIDITY_OR_BUYERS',
      'OWNER_MAINNET_AND_FINANCIAL_APPROVAL_REQUIRED',
    ],
  };
}

function runCli() {
  const read = relative => JSON.parse(readFileSync(new URL(relative, import.meta.url), 'utf8'));
  const result = assessV2MarketGate(
    read('../tokenomics.json'), read('../shasta-deployment.json'), read('../shasta-v2-deployment.json'));
  process.stdout.write(JSON.stringify(result,null,2) + '\n');
  if (!process.argv.includes('--assert-blocked') || result.inconsistencies.length) {
    process.exitCode = 2;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { runCli(); }
  catch (error) { process.stderr.write('MARKET_GATE_UNAVAILABLE: '+String(error.message)+'\n'); process.exitCode = 2; }
}
