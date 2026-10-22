// Accept only a fresh Shasta read-only proof from the separate verifier.
// This process never deploys contracts or accesses a live checkout.
import {readFile} from 'node:fs/promises';
import {isAbsolute} from 'node:path';
import {makeSyntheticGuestOrder, previewSyntheticCheckout} from './mojplaywin-readonly-bridge.mjs';

if (process.argv.length !== 3 || !isAbsolute(process.argv[2])) {
  throw new Error('USAGE: node staging/run-mojplaywin-staging.mjs /absolute/path/to/fresh-shasta-proof.json');
}
const manifest = JSON.parse(await readFile(new URL('../shasta-deployment.json', import.meta.url), 'utf8'));
const chainProof = JSON.parse(await readFile(process.argv[2], 'utf8'));
console.log(JSON.stringify(previewSyntheticCheckout({
  manifest, chainProof, order: makeSyntheticGuestOrder()
}), null, 2));
