// Read-only reconciliation of a journaled deployment. NEVER broadcasts or signs.
import {createHash} from 'node:crypto';

const HEX64 = /^[a-f0-9]{64}$/i;
const HEX40 = /^41[a-f0-9]{40}$/i;

export function fingerprintRawTransaction(rawHex) {
  if (typeof rawHex !== 'string' || !/^(?:[a-f0-9]{2})+$/i.test(rawHex)) {
    throw new Error('Missing canonical transaction raw_data_hex');
  }
  return createHash('sha256').update(Buffer.from(rawHex, 'hex')).digest('hex');
}

export function normalizedTronAddress(address, tronWeb) {
  if (typeof address !== 'string' || !address) throw new Error('Missing contract address');
  const hex = tronWeb.address.toHex(address);
  if (!HEX40.test(hex ?? '')) throw new Error('Invalid TRON address in chain receipt');
  return hex.toLowerCase();
}

export async function reconcileDeployment(journal, name, tronWeb) {
  const pending = journal.pending(name);
  if (!pending) return {status: 'NOT_PENDING'};
  // Old contract().new() deployments did not preserve a txID. They require external
  // investigation and owner approval; neither guessing nor resubmitting is safe.
  if (!HEX64.test(pending.txID ?? '') ||
      !HEX64.test(pending.rawDataSha256 ?? '') || !pending.expectedAddress) {
    throw new Error('LEGACY_UNRESOLVED: no pre-broadcast txID/attestation; DO NOT REDEPLOY');
  }

  // Both reads must refer to the SAME fully-confirmed transaction and the
  // exact raw bytes whose digest was journaled before the first broadcast.
  const tx = await tronWeb.trx.getTransaction(pending.txID);
  if (!tx?.txID) return {status: 'PENDING', txID: pending.txID};
  if (tx.txID.toLowerCase() !== pending.txID.toLowerCase() ||
      fingerprintRawTransaction(tx.raw_data_hex) !== pending.rawDataSha256 ||
      tx.raw_data?.contract?.length !== 1 ||
      tx.raw_data.contract[0]?.type !== 'CreateSmartContract') {
    throw new Error('CHAIN_ATTESTATION_MISMATCH: transaction is not the journaled creation');
  }

  const info = await tronWeb.trx.getTransactionInfo(pending.txID);
  if (!info?.id) return {status: 'PENDING', txID: pending.txID};
  if (info.id.toLowerCase() !== pending.txID.toLowerCase()) {
    throw new Error('CHAIN_ATTESTATION_MISMATCH: receipt ID differs');
  }
  if (info.receipt?.result !== 'SUCCESS' || info.result === 'FAILED') {
    throw new Error('CHAIN_EXECUTION_FAILED: never replace a finalized transaction automatically');
  }
  const address = normalizedTronAddress(info.contract_address, tronWeb);
  if (address !== normalizedTronAddress(pending.expectedAddress, tronWeb)) {
    throw new Error('CHAIN_ATTESTATION_MISMATCH: deployed address differs');
  }
  const contract = await tronWeb.trx.getContract(address);
  if (!contract?.bytecode || !contract?.contract_address ||
      normalizedTronAddress(contract.contract_address, tronWeb) !== address) {
    throw new Error('CHAIN_CODE_NOT_VERIFIED: keep journal blocked');
  }

  // Only a matching solidified on-chain receipt and non-empty contract code may
  // transition the local journal out of its fail-closed pending state.
  await journal.markVerified(name, address, pending.txID);
  return {status: 'VERIFIED', name, txID: pending.txID, address};
}
