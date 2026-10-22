// Keyless MOJ1 informational testnet adapter for MojPlayWin guest-checkout-shaped orders.
// Pure functions: no RPC, keys, wallet, database, HTTP, state change or payment handler.
const PINNED = Object.freeze({
  network: 'Shasta', chain_scope: 'TESTNET_ONLY',
  rpc: 'https://api.shasta.trongrid.io',
  token_contract: 'TKg1oVb91qHzeLC74djmeeAnMMmb9PYJ6F',
  nft_contract: 'TM1V6UqsfcpySZWKYze3i5PKPdk9Cxh4N8',
  governance_contract: 'TPvMW5cSHKfCuttghjWqmUEScH33vaA1Yy',
  genesis_escrow: 'TDYGu1oTf9bhAU3S6qMZE7BRC3HDZJ6QVP',
  symbol: 'MOJ1', name: 'Moj 1', decimals: 18,
  total_supply_whole: '100000000000',
  mojplaywin_integration_mode: 'READ_ONLY_STAGING',
  allocation_distributed: false, mainnet_deployed: false,
  public_sale_enabled: false, real_payment_enabled: false
});
const requireTrue = (condition, error) => {
  if (!condition) throw new Error('MOJ1_STAGING_' + error);
};
const FIELD_NAMES = [
  'amount_sun', 'claim_sha', 'expires_ms', 'id', 'issued_ms', 'product_id',
  'rate', 'receiver', 'sender', 'status', 'synthetic', 'txid', 'usd'
].sort().join('|');

export function validateStagingManifest(manifest) {
  requireTrue(manifest && typeof manifest === 'object' && !Array.isArray(manifest), 'MANIFEST_INVALID');
  for (const [key, value] of Object.entries(PINNED)) {
    requireTrue(manifest[key] === value, 'MANIFEST_' + key.toUpperCase() + '_BLOCKED');
  }
  requireTrue(Array.isArray(manifest.test_governance_owners) &&
    manifest.test_governance_owners.length === 3 &&
    new Set(manifest.test_governance_owners).size === 3, 'TEST_GOVERNANCE_OWNERS_INVALID');
  requireTrue(manifest.schema_version === 1 && manifest.project === 'MOJ1', 'SCHEMA_INVALID');
  return true;
}

// Negative ID, zero value and absent wallet fields cannot be a transferable
// mpw_guest_trx_20261020.guest_database invoice.
export function makeSyntheticGuestOrder() {
  return Object.freeze({
    id: -1, product_id: 0, usd: '0.00', rate: '0',
    amount_sun: 0, sender: null, receiver: null,
    issued_ms: 0, expires_ms: 0, claim_sha: null,
    txid: null, status: 'pending', synthetic: true
  });
}

export function previewSyntheticCheckout({manifest, chainProof, order}) {
  validateStagingManifest(manifest);
  requireTrue(order && typeof order === 'object' && !Array.isArray(order), 'ORDER_INVALID');
  requireTrue(Object.keys(order).sort().join('|') === FIELD_NAMES, 'ORDER_FIELDS_REJECTED');
  for (const [key, expected] of Object.entries(makeSyntheticGuestOrder())) {
    requireTrue(order[key] === expected, 'REAL_ORDER_OR_PAYMENT_REJECTED_' + key.toUpperCase());
  }
  requireTrue(chainProof && typeof chainProof === 'object', 'CHAIN_PROOF_REQUIRED');
  requireTrue(chainProof.mode === 'MOJ1_SHASTA_PUBLIC_READ_ONLY' &&
    chainProof.status === 'PASS' && chainProof.mainnet === false &&
    chainProof.privateKeyUsed === false && chainProof.paymentsModified === false &&
    chainProof.escrowFullyFunded === true && chainProof.distributed === false,
    'CHAIN_READONLY_ATTESTATION_FAILED');
  const match = {
    token: 'token_contract',
    escrow: 'genesis_escrow',
    governance: 'governance_contract',
    nft: 'nft_contract',
    totalWholeTokens: 'total_supply_whole'
  };
  for (const [proofKey, manifestKey] of Object.entries(match)) {
    requireTrue(chainProof[proofKey] === manifest[manifestKey],
      'CHAIN_IDENTITY_MISMATCH_' + proofKey.toUpperCase());
  }
  const expectedContracts = new Set([
    'MojPilotGovernance', 'MojCoin', 'MojGenesisDistributor', 'MojAssets'
  ]);
  requireTrue(Array.isArray(chainProof.bytecodeEvidence) &&
    chainProof.bytecodeEvidence.length === expectedContracts.size, 'BYTECODE_PROOF_INCOMPLETE');
  for (const proof of chainProof.bytecodeEvidence) {
    requireTrue(proof && expectedContracts.delete(proof.contract), 'BYTECODE_IDENTITY_REJECTED');
    requireTrue(typeof proof.method === 'string' &&
      /^(CREATION_AND_|ATTESTED_PARENT_PLUS_)(EXACT_RUNTIME_MATCH|RUNTIME_MATCH_WITH_(CHECKED_IMMUTABLES|VERIFIED_IMMUTABLE_ADDRESS_SLOTS))$/.test(proof.method),
      'BYTECODE_METHOD_REJECTED');
    requireTrue(/^[0-9a-f]{64}$/.test(proof.runtimeSha256), 'BYTECODE_HASH_INVALID');
    requireTrue(proof.contract === 'MojGenesisDistributor' ||
      /^[0-9a-f]{64}$/.test(proof.creationSha256), 'CREATION_HASH_INVALID');
  }
  requireTrue(expectedContracts.size === 0, 'BYTECODE_PROOF_INCOMPLETE');
  // No mutation, payment approval, settlement or delivery instruction is returned.
  return Object.freeze({
    schema: 'moj1_mpw_synthetic_readonly_v1',
    status: 'PASS', sourceCheckoutShape: 'mpw_guest_trx_20261020/guest_database.py',
    orderKind: 'SYNTHETIC_ONLY', orderId: 'MOJ1-READONLY-TEST-ONLY',
    orderState: 'NOT_A_REAL_ORDER',
    tokenSymbol: manifest.symbol, tokenNetwork: manifest.network,
    tokenContract: manifest.token_contract, tokenSupplyWhole: manifest.total_supply_whole,
    escrowFullyFunded: true, distributed: false,
    paymentMethod: 'UNAVAILABLE', paymentEnabled: false,
    deliveryEnabled: false, orderWriteEnabled: false,
    mainnetEnabled: false, keysUsed: false,
    sourceOfChainProof: 'SHASTA_PUBLIC_READ_ONLY',
    realMojPlayWinGatewayChanged: false
  });
}
