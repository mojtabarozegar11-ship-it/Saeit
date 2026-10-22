// Only CI workspace files: no web hosting, cloud deployment or live site writes.
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {renderMoj1StagingPage} from './render-preview.mjs';

const manifest = JSON.parse(await readFile(new URL('../../shasta-deployment.json', import.meta.url), 'utf8'));
const receipt = JSON.parse(await readFile(new URL('../../staging-evidence.json', import.meta.url), 'utf8'));
const html = renderMoj1StagingPage({manifest, receipt});
const dir = new URL('../../staging-preview/', import.meta.url);
await mkdir(dir, {recursive:true});
const report = {
  project: 'MOJ1', network: 'Shasta', environment: 'ISOLATED_GITHUB_ACTIONS_PREVIEW',
  readOnlyProof: true, syntheticOrderOnly: true, staticPageGenerated: true,
  productionCheckoutConnected: false, independentSecurityAuditApproved: false,
  legalReleaseApproved: false, mainnetCustodyApproved: false,
  publicSaleApproved: false, realPaymentEnabled: false,
  readyForMainnet: false
};
const files = [
  ['index.html', html],
  ['synthetic-receipt.json', JSON.stringify(receipt, null, 2) + '\n'],
  ['release-gates.json', JSON.stringify(report, null, 2) + '\n']
];
for (const [name, value] of files) {
  await writeFile(new URL(name, dir), value, {flag:'wx', mode:0o600});
}
const hashes = files.map(([name, value]) =>
  createHash('sha256').update(value).digest('hex') + '  ' + name).join('\n') + '\n';
await writeFile(new URL('SHA256SUMS', dir), hashes, {flag:'wx', mode:0o600});
console.log('MOJ1_ISOLATED_STATIC_PREVIEW=PASS');
console.log('MOJ1_REAL_CHECKOUT=UNMODIFIED');
console.log('MOJ1_MAINNET_RELEASE_GATE=CLOSED');
