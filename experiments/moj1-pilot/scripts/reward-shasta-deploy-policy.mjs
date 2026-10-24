// Keyless Shasta reward pilot plan: validation is NOT authorization to broadcast.
// Only a disposable, unmistakably non-MOJ1 test token may be used at this stage.
import {TronWeb} from 'tronweb';

export const SHASTA_REWARD_CONFIRMATION = 'SHASTA_DISPOSABLE_REWARD_ONLY';
export const REWARD_TEST_TOKEN_NAME = 'Disposable reward test';
export const REWARD_TEST_TOKEN_SYMBOL = 'TTEST';
export const REWARD_DEPLOYMENT_ARTIFACTS = Object.freeze(['MojRewardTestToken','MojRewardClaimsPilot']);
const MAX_FEE_SUN = 1_000_000_000n; // At most 1000 free Shasta TRX per deployment.
const MIN_FEE_SUN = 10_000_000n;

export function validateShastaRewardPlan(manifest, plan) {
  if (!manifest || manifest.project !== 'MOJ1' ||
      manifest.version !== 'V2_GUARDED_CANDIDATE' ||
      manifest.network !== 'Shasta' || manifest.chain_scope !== 'TESTNET_ONLY' ||
      manifest.mainnet_deployed !== false || manifest.distribution_enabled !== false ||
      manifest.public_sale_enabled !== false || manifest.real_payment_enabled !== false ||
      manifest.independent_security_audit !== 'PENDING') {
    throw new Error('GUARDED_V2_SHASTA_LOCK_REQUIRED');
  }
  for (const key of ['candidate_token_contract','candidate_genesis_factory','pilot_governance_contract']) {
    if (!TronWeb.isAddress(manifest[key] ?? '')) throw new Error('MISSING_GUARDED_V2_ADDRESS_'+key);
  }
  if (!plan || plan.confirmation !== SHASTA_REWARD_CONFIRMATION ||
      plan.network !== 'Shasta' || plan.mode !== 'DISPOSABLE_TEST_ONLY') {
    throw new Error('SHASTA_DISPOSABLE_CONFIRMATION_REQUIRED');
  }
  if (!TronWeb.isAddress(plan.operatorAddress ?? '') ||
      !TronWeb.isAddress(plan.governanceAddress ?? '')) {
    throw new Error('INVALID_TEST_OPERATOR_OR_GOVERNOR');
  }
  if (TronWeb.address.toHex(plan.governanceAddress).toLowerCase() !==
      TronWeb.address.toHex(manifest.pilot_governance_contract).toLowerCase()) {
    throw new Error('GOVERNANCE_MUST_MATCH_GUARDED_V2_MANIFEST');
  }
  const distinct = [
    plan.operatorAddress,manifest.candidate_token_contract,
    manifest.candidate_genesis_factory,manifest.pilot_governance_contract
  ].map(address => TronWeb.address.toHex(address).toLowerCase());
  if (new Set(distinct).size !== distinct.length) {
    throw new Error('TEST_OPERATOR_MUST_NOT_BE_CONTRACT_ADDRESS');
  }
  if (plan.tokenName !== REWARD_TEST_TOKEN_NAME ||
      plan.tokenSymbol !== REWARD_TEST_TOKEN_SYMBOL ||
      plan.tokenContractAddress !== undefined ||
      plan.rewardEscrowAddress !== undefined) {
    throw new Error('DISPOSABLE_TOKEN_ONLY_NO_MOJ1_FUNDING');
  }
  const allowedKeys = new Set(['confirmation','network','mode','operatorAddress',
    'governanceAddress','tokenName','tokenSymbol','feeLimitSun']);
  if (Object.keys(plan).some(key => !allowedKeys.has(key))) {
    throw new Error('UNSUPPORTED_OR_REAL_WORLD_DEPLOYMENT_FIELD');
  }
  if (typeof plan.feeLimitSun !== 'string' || !/^[1-9][0-9]*$/.test(plan.feeLimitSun)) {
    throw new Error('INVALID_EXPLICIT_TESTNET_FEE_LIMIT');
  }
  const fee = BigInt(plan.feeLimitSun);
  if (fee < MIN_FEE_SUN || fee > MAX_FEE_SUN) {
    throw new Error('TESTNET_FEE_LIMIT_OUT_OF_BOUNDS');
  }
  return Object.freeze({
    network: 'Shasta', tokenKind: 'DISPOSABLE_NON_MOJ1_TEST_TOKEN',
    tokenName: REWARD_TEST_TOKEN_NAME, tokenSymbol: REWARD_TEST_TOKEN_SYMBOL,
    governanceAddress: plan.governanceAddress, operatorAddress: plan.operatorAddress,
    feeLimitSun: fee.toString(), maxDeployments: 2,
    rewardEscrowDeployed: false, fundingAuthorized: false, rewardClaimAuthorized: false,
    mainnetAuthorized: false, preflightOnly: true
  });
}
