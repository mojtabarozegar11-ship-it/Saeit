// Crash-safe, fail-closed local journal for experimental Shasta deployments.
// No signing keys are ever stored; keep the journal on persistent operator-controlled storage.
import {open, readFile, rename, mkdir, unlink} from 'node:fs/promises';
import {dirname, isAbsolute} from 'node:path';
import {randomUUID} from 'node:crypto';

async function atomicSave(path, value) {
  const temporary = path + '.' + randomUUID() + '.tmp';
  const descriptor = await open(temporary, 'wx', 0o600);
  try {
    await descriptor.writeFile(JSON.stringify(value, null, 2) + '\n', 'utf8');
    await descriptor.sync();
  } finally {
    await descriptor.close();
  }
  await rename(temporary, path);
  // The directory sync makes the rename durable on ordinary POSIX filesystems.
  const directory = await open(dirname(path), 'r');
  try {
    await directory.sync();
  } finally {
    await directory.close();
  }
}

export async function openDeploymentJournal(path, context) {
  if (typeof path !== 'string' || !isAbsolute(path)) {
    throw new Error('MOJ1_DEPLOY_JOURNAL_PATH must be an absolute persistent filesystem path');
  }
  // Only explicitly enumerated Shasta-only deployment manifests are supported.
  // A governance bootstrap uses a separate journal, so a token deployment cannot
  // overwrite or disguise a previously uncertain governance transaction.
  const manifest = context?.artifacts;
  const keys = manifest && Object.keys(manifest).sort().join(',');
  const validManifest = keys === 'MojAssets,MojCoin' || keys === 'MojPilotGovernance' ||
    keys === 'MojCoinGuarded' || keys === 'MojRewardClaimsPilot,MojRewardTestToken';
  if (!context || context.network !== 'Shasta' ||
      !context.governance || !validManifest) {
    throw new Error('Invalid Shasta deployment journal identity');
  }
  await mkdir(dirname(path), {recursive: true, mode: 0o700});
  let lock;
  try {
    lock = await open(path + '.lock', 'wx', 0o600);
  } catch (error) {
    if (error?.code === 'EEXIST') {
      throw new Error('Shasta journal lock exists: active or interrupted deployment; manual reconciliation required');
    }
    throw error;
  }

  let state;
  let closed = false;
  const save = async () => atomicSave(path, state);
  try {
    try {
      state = JSON.parse(await readFile(path, 'utf8'));
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
      state = {version: 1, ...context, steps: {}, createdAt: new Date().toISOString()};
      await save();
    }
    if (state.version !== 1 || state.network !== context.network ||
        state.governance !== context.governance ||
        JSON.stringify(state.artifacts) !== JSON.stringify(context.artifacts) ||
        !state.steps || typeof state.steps !== 'object') {
      throw new Error('Journal identity mismatch: refusing to use another governance or compiled artifact');
    }
    // Allow a read-only reconciler to inspect uncertain entries. This does NOT
    // authorize any new broadcast: markBroadcastUncertain rejects all pending steps.

    return {
      snapshot: () => structuredClone(state),
      pending(name) {
        const record = state.steps[name];
        if (record?.status === 'BROADCAST_UNCERTAIN') return structuredClone(record);
        return null;
      },
      verifiedAddress(name) {
        const record = state.steps[name];
        if (record?.status === 'VERIFIED' && typeof record.address === 'string') return record.address;
        if (record) throw new Error('Unresolved deployment journal state for ' + name + ': DO NOT REDEPLOY');
        return null;
      },
      async markBroadcastUncertain(name, details) {
        const othersPending = Object.values(state.steps).some(
          step => step?.status === 'BROADCAST_UNCERTAIN');
        if (!Object.prototype.hasOwnProperty.call(context.artifacts, name) || state.steps[name] || othersPending) {
          throw new Error('Cannot repeat or overwrite a journaled deployment: ' + name);
        }
        if (!/^[a-f0-9]{64}$/i.test(details?.txID ?? '') ||
            !/^[a-f0-9]{64}$/i.test(details?.rawDataSha256 ?? '') ||
            !/^41[a-f0-9]{40}$/i.test(details?.expectedAddress ?? '')) {
          throw new Error('Refusing to journal a broadcast without a complete signed txID and chain attestation');
        }
        state.steps[name] = {
          status: 'BROADCAST_UNCERTAIN',
          txID: details.txID.toLowerCase(),
          rawDataSha256: details.rawDataSha256.toLowerCase(),
          expectedAddress: details.expectedAddress.toLowerCase(),
          startedAt: new Date().toISOString()
        };
        await save(); // Durable BEFORE the only permitted sendRawTransaction.
      },
      async markVerified(name, address, txID) {
        const record = state.steps[name];
        if (record?.status !== 'BROADCAST_UNCERTAIN' ||
            !record.txID || record.txID !== txID?.toLowerCase() ||
            record.expectedAddress !== address?.toLowerCase()) {
          throw new Error('Cannot confirm without a matching journaled transaction receipt: ' + name);
        }
        state.steps[name] = {...record, status: 'VERIFIED',
          address: address.toLowerCase(), verifiedAt: new Date().toISOString()};
        await save();
      },
      async close() {
        if (closed) return;
        closed = true;
        await lock.close();
        await unlink(path + '.lock');
      }
    };
  } catch (error) {
    await lock.close();
    await unlink(path + '.lock');
    throw error;
  }
}
