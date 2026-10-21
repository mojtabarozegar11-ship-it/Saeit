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
  if (!context || context.network !== 'Shasta' ||
      !context.governance || !context.artifacts?.MojCoin || !context.artifacts?.MojAssets) {
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
    if (Object.values(state.steps).some(step => step?.status === 'BROADCAST_UNCERTAIN')) {
      throw new Error('Unresolved Shasta broadcast in journal: DO NOT REDEPLOY; reconcile transaction externally');
    }

    return {
      snapshot: () => structuredClone(state),
      verifiedAddress(name) {
        const record = state.steps[name];
        if (record?.status === 'VERIFIED' && typeof record.address === 'string') return record.address;
        if (record) throw new Error('Unexpected deployment journal state for ' + name);
        return null;
      },
      async markBroadcastUncertain(name) {
        if (!['MojCoin', 'MojAssets'].includes(name) || state.steps[name]) {
          throw new Error('Cannot repeat or overwrite a journaled deployment: ' + name);
        }
        state.steps[name] = {status: 'BROADCAST_UNCERTAIN', startedAt: new Date().toISOString()};
        await save(); // Must finish durably BEFORE calling contract().new
      },
      async markVerified(name, address) {
        if (state.steps[name]?.status !== 'BROADCAST_UNCERTAIN' ||
            typeof address !== 'string' || !address) {
          throw new Error('Cannot confirm a step without recorded broadcast intent: ' + name);
        }
        state.steps[name] = {...state.steps[name], status: 'VERIFIED',
          address, verifiedAt: new Date().toISOString()};
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
