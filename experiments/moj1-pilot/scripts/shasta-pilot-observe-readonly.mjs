// MOJ1 Shasta observation only. This module has no signer, key, builder or broadcast path.
// Live state is observed via public Shasta RPC, NOT proof of reward escrow deployment or audit.
import {TronWeb} from 'tronweb';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const SHASTA = 'https://api.shasta.trongrid.io';
const CONTRACT_FIELDS = ['candidate_token_contract', 'candidate_genesis_factory', 'pilot_governance_contract'];

export async function observeExistingShastaPilot(manifest, client) {
  if (!manifest || manifest.project !== 'MOJ1' || manifest.version !== 'V2_GUARDED_CANDIDATE' ||
      manifest.network !== 'Shasta' || manifest.chain_scope !== 'TESTNET_ONLY' ||
      manifest.mainnet_deployed !== false || manifest.public_sale_enabled !== false ||
      manifest.real_payment_enabled !== false || manifest.distribution_enabled !== false ||
      manifest.independent_security_audit !== 'PENDING') {
    throw new Error('Unsafe manifest: Shasta-only no-distribution invariants required');
  }
  if (!client?.trx || typeof client.trx.getCurrentBlock !== 'function' ||
      typeof client.trx.getContract !== 'function') throw new Error('Read-only RPC client required');
  for (const field of CONTRACT_FIELDS) {
    if (typeof manifest[field] !== 'string' || !TronWeb.isAddress(manifest[field])) {
      throw new Error('Missing or invalid ' + field);
    }
  }
  const addresses = CONTRACT_FIELDS.map(field => TronWeb.address.toHex(manifest[field]).toLowerCase());
  if (new Set(addresses).size !== addresses.length) throw new Error('Duplicate pilot contract address');
  const block = await client.trx.getCurrentBlock();
  const number = block?.block_header?.raw_data?.number;
  const blockID = block?.blockID;
  if (!Number.isSafeInteger(number) || number < 1 ||
      typeof blockID !== 'string' || !/^[0-9a-fA-F]{64}$/.test(blockID)) {
    throw new Error('Shasta block is missing or invalid');
  }
  const contracts = [];
  for (const field of CONTRACT_FIELDS) {
    const deployed = await client.trx.getContract(manifest[field]);
    const raw = typeof deployed?.bytecode === 'string' ? deployed.bytecode.replace(/^0x/, '') : '';
    if (!/^(?:[0-9a-fA-F]{2})+$/.test(raw) || raw.length < 4) {
      throw new Error(field + ': deployed bytecode unavailable on Shasta');
    }
    contracts.push({
      role: field, address: manifest[field],
      observedBytecodeSha256: createHash('sha256').update(Buffer.from(raw, 'hex')).digest('hex'),
      observedByteLength: raw.length / 2
    });
  }
  return {
    project: 'MOJ1', version: 'V2_GUARDED_CANDIDATE', network: 'Shasta', status: 'V2_CANDIDATE_CONTRACTS_OBSERVED_READ_ONLY',
    observedBlockNumber: number, observedBlockId: blockID, contracts,
    sourceBytecodeEquivalenceVerified: false, governanceSignersVerified: false,
    balanceAndLiabilitiesVerified: false,
    rewardClaimsEscrow: 'NO_VERIFIED_REWARD_ESCROW_ADDRESS_IN_MANIFEST',
    rewardClaimsIntegration: 'NOT_RUN', transactionBroadcast: false,
    privateKeyAccessed: false, testnetRewardPayoutAuthorized: false,
    mainnetAuthorized: false, publicDistributionAuthorized: false
  };
}

const invoked = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invoked) {
  if (process.argv.length !== 3 || process.argv[2] !== '--read-only') {
    console.error('Usage: node scripts/shasta-pilot-observe-readonly.mjs --read-only');
    process.exitCode = 2;
  } else {
    try {
      const manifest = JSON.parse(readFileSync(new URL('../shasta-v2-deployment.json', import.meta.url), 'utf8'));
      const client = new TronWeb({fullHost: SHASTA});
      const result = await observeExistingShastaPilot(manifest, client);
      process.stdout.write(JSON.stringify(result, null, 2) + '\n');
    } catch (error) {
      console.error('SHASTA_READ_ONLY_OBSERVATION_FAILED: ' + error.message);
      process.exitCode = 2;
    }
  }
}
