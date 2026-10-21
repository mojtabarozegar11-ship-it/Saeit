// Read-only Shasta recovery. No signing key and no transaction broadcast.
import {TronWeb} from 'tronweb';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {isAbsolute} from 'node:path';
import {openDeploymentJournal} from './deployment-journal.mjs';
import {reconcileDeployment} from './deployment-reconciler.mjs';

const path = process.env.MOJ1_DEPLOY_JOURNAL_PATH;
if (!path || !isAbsolute(path)) {
  throw new Error('MOJ1_DEPLOY_JOURNAL_PATH must be an absolute persistent path');
}
const recorded = JSON.parse(await readFile(path, 'utf8'));
if (recorded.version !== 1 || recorded.network !== 'Shasta') {
  throw new Error('Recovery supports the existing Shasta-only journal identity');
}
const hashes = {};
for (const name of ['MojCoin', 'MojAssets']) {
  const artifact = JSON.parse(await readFile(
    new URL(`../build/contracts/${name}.json`, import.meta.url), 'utf8'));
  if (artifact.contractName !== name || !artifact.abi || !artifact.bytecode) {
    throw new Error('Missing verified compiled artifact: ' + name);
  }
  hashes[name] = createHash('sha256')
    .update(JSON.stringify({abi: artifact.abi, bytecode: artifact.bytecode})).digest('hex');
}
const journal = await openDeploymentJournal(path, {
  network: 'Shasta', governance: recorded.governance, artifacts: hashes
});
const tronWeb = new TronWeb({fullHost: 'https://api.shasta.trongrid.io'});
try {
  const result = [];
  for (const name of ['MojCoin', 'MojAssets']) {
    if (journal.pending(name)) {
      result.push({name, ...await reconcileDeployment(journal, name, tronWeb)});
    } else {
      result.push({name, status: journal.verifiedAddress(name) ? 'ALREADY_VERIFIED' : 'NOT_STARTED'});
    }
  }
  console.log(JSON.stringify({
    mode: 'READ_ONLY_SHASTA_RECONCILIATION',
    noPrivateKey: true, noBroadcast: true, result
  }, null, 2));
} finally {
  await journal.close();
}
