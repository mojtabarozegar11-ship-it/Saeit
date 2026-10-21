// Only the public Shasta TESTNET is allowed. No CI auto-deployment, no mainnet code.
// Requires a dedicated funded Shasta wallet, three distinct TEST-only owner addresses,
// and a private persistent journal. NEVER use these prototype owners for real funds.
import {TronWeb} from 'tronweb';
import {readFile} from 'node:fs/promises';
import {isAbsolute} from 'node:path';
import {createHash} from 'node:crypto';
import {openDeploymentJournal} from './deployment-journal.mjs';
import {fingerprintRawTransaction, normalizedTronAddress, reconcileDeployment} from './deployment-reconciler.mjs';

if (process.env.MOJ1_GOV_DEPLOY_CONFIRM !== 'SHASTA_ONLY_TEST_GOVERNANCE') {
  throw new Error('Set MOJ1_GOV_DEPLOY_CONFIRM=SHASTA_ONLY_TEST_GOVERNANCE');
}
const key = process.env.TRON_PRIVATE_KEY;
if (!/^[0-9a-f]{64}$/i.test(key ?? '')) {
  throw new Error('Dedicated Shasta-only deployer private key required (never commit it)');
}
const journalPath = process.env.MOJ1_GOV_DEPLOY_JOURNAL_PATH;
if (!journalPath || !isAbsolute(journalPath)) {
  throw new Error('MOJ1_GOV_DEPLOY_JOURNAL_PATH must be an absolute private persistent path');
}
const tronWeb = new TronWeb({fullHost: 'https://api.shasta.trongrid.io', privateKey: key});
const input = (process.env.MOJ1_SHASTA_GOV_OWNERS ?? '').split(',').map(x => x.trim());
if (input.length !== 3 || input.some(x => !tronWeb.isAddress(x))) {
  throw new Error('MOJ1_SHASTA_GOV_OWNERS requires three valid Shasta-only signer addresses');
}
const owners = input.map(address => tronWeb.address.fromHex(tronWeb.address.toHex(address)));
const normalizedOwners = owners.map(address => normalizedTronAddress(address, tronWeb));
if (new Set(normalizedOwners).size !== 3) throw new Error('Three distinct signer keys required');

const name = 'MojPilotGovernance';
const artifact = JSON.parse(await readFile(new URL('../build/contracts/MojPilotGovernance.json', import.meta.url), 'utf8'));
if (artifact.contractName !== name ||
    artifact.abi?.find(x => x.type === 'constructor')?.inputs?.[0]?.type !== 'address[3]' ||
    !/^(?:0x)?(?:[0-9a-f]{2})+$/i.test(artifact.bytecode ?? '')) {
  throw new Error('Incorrect compiled Shasta pilot governance artifact');
}
const artifactHash = createHash('sha256').update(JSON.stringify({
  abi: artifact.abi, bytecode: artifact.bytecode
})).digest('hex');
const ownerFingerprint = createHash('sha256').update(normalizedOwners.join(':')).digest('hex');
const journal = await openDeploymentJournal(journalPath, {
  network: 'Shasta', governance: ownerFingerprint, artifacts: {[name]: artifactHash}
});

async function verifyGovernance(address) {
  const receipt = await tronWeb.trx.getContract(address);
  if (!receipt?.bytecode || !receipt?.contract_address ||
      normalizedTronAddress(receipt.contract_address, tronWeb) !== normalizedTronAddress(address, tronWeb)) {
    throw new Error('Shasta governance has no verified on-chain contract code');
  }
  const contract = await tronWeb.contract().at(address);
  const registeredOwners = [];
  for (let i = 0; i < 3; ++i) {
    const value = await contract.owners(i).call();
    registeredOwners.push(normalizedTronAddress(String(value), tronWeb));
  }
  if (registeredOwners.some((x,i) => x !== normalizedOwners[i]) ||
      String(await contract.nonce().call()) !== '0') {
    throw new Error('Shasta governance does not match three approved test owners and fresh nonce');
  }
  return normalizedTronAddress(address, tronWeb);
}

try {
  const pending = journal.pending(name);
  // Read-only recovery MUST run before verifiedAddress(), which intentionally throws
  // for an unresolved step. Never create a second transaction from a pending state.
  let verifiedAddress;
  if (pending) {
    const recovery = await reconcileDeployment(journal, name, tronWeb);
    if (recovery.status !== 'VERIFIED') {
      throw new Error('Shasta governance broadcast is uncertain: DO NOT REDEPLOY');
    }
    verifiedAddress = await verifyGovernance(tronWeb.address.fromHex(recovery.address));
  } else {
    const prior = journal.verifiedAddress(name);
    if (prior) {
      verifiedAddress = await verifyGovernance(tronWeb.address.fromHex(prior));
    } else {
      const balance = await tronWeb.trx.getBalance(tronWeb.defaultAddress.base58);
      if (BigInt(balance) <= 0n) {
        throw new Error('SHASTA_TEST_TRX_REQUIRED: wallet unfunded; no transaction created or broadcast');
      }
      const constructorABI = artifact.abi.find(x => x.type === 'constructor');
      const unsigned = await tronWeb.transactionBuilder.createSmartContract({
        abi: artifact.abi, bytecode: artifact.bytecode.replace(/^0x/, ''),
        name, feeLimit: 1_000_000_000, callValue: 0,
        userFeePercentage: 100, originEnergyLimit: 10_000_000,
        funcABIV2: constructorABI, parametersV2: [owners]
      }, tronWeb.defaultAddress.base58);
      const signed = await tronWeb.trx.sign(unsigned);
      if (!signed?.signature?.length || !/^[0-9a-f]{64}$/i.test(signed.txID ?? '') ||
          unsigned.txID !== signed.txID || !unsigned.contract_address ||
          signed.raw_data_hex !== unsigned.raw_data_hex ||
          typeof signed.raw_data?.expiration !== 'number' ||
          signed.raw_data.expiration <= Date.now()) {
        throw new Error('Governance deployment signing/expiry preflight failed');
      }
      await journal.markBroadcastUncertain(name, {
        txID: signed.txID, expectedAddress: normalizedTronAddress(unsigned.contract_address, tronWeb),
        rawDataSha256: fingerprintRawTransaction(signed.raw_data_hex)
      });
      // Exactly ONE transmission. Any timeout/ambiguous response must remain journal-blocked.
      let response;
      try {
        response = await tronWeb.trx.sendRawTransaction(signed);
      } catch (error) {
        throw new Error('Governance broadcast uncertain for txID ' + signed.txID +
          ': DO NOT REDEPLOY (' + error.message + ')');
      }
      if (!response?.result && response?.code !== 'DUP_TRANSACTION_ERROR') {
        throw new Error('Governance broadcast not confirmed: DO NOT REDEPLOY');
      }
      for (let i = 0; i < 20; ++i) {
        try {
          const reconciled = await reconcileDeployment(journal, name, tronWeb);
          if (reconciled.status === 'VERIFIED') {
            verifiedAddress = await verifyGovernance(tronWeb.address.fromHex(reconciled.address));
            break;
          }
        } catch (error) {
          if (/CHAIN_ATTESTATION_MISMATCH|CHAIN_EXECUTION_FAILED|CHAIN_CODE_NOT_VERIFIED/.test(error.message)) throw error;
        }
        await new Promise(resolve => setTimeout(resolve, 3000));
      }
      if (!verifiedAddress) throw new Error('Governance Shasta tx still uncertain: reconcile read-only; DO NOT REDEPLOY');
    }
  }
  console.log(JSON.stringify({
    mode: 'SHASTA_TEST_ONLY', name,
    governanceAddress: tronWeb.address.fromHex(verifiedAddress),
    ownerAddresses: owners, ownerFingerprint,
    artifactSha256: artifactHash, journal: journalPath,
    mainnet: false, realTokens: false,
    status: 'TEST_GOVERNANCE_ONCHAIN_VERIFIED'
  }, null, 2));
} finally {
  await journal.close();
}
