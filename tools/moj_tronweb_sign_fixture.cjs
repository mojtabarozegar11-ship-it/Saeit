// Isolated, network-free TronWeb 6.5.1 interoperability check.
// Test-only fixed key; NEVER use this key to receive money or copy to a site.
const { Trx } = require('tronweb');

async function run() {
  const privateKey = '0'.repeat(63) + '1'; // public test fixture ONLY
  const message = [
    'MOJ Commerce — verify receiving wallet ownership',
    'Domain: mojplaywin.com',
    'Network: tron-mainnet',
    'Merchant: 00000000000040008000000000000001',
    'Nonce: 0123456789abcdef'.repeat(3),
    'Expires-UTC: 2026-10-21T23:59:59+00:00',
    'No funds transfer or approval is requested.'
  ].join('\n');
  const signature = await Trx.signMessageV2(message, privateKey);
  const address = await Trx.verifyMessageV2(message, signature);
  if (typeof address !== 'string' || !address.startsWith('T')) {
    throw new Error('Official TronWeb returned no mainnet address');
  }
  process.stdout.write(JSON.stringify({message, signature, address}));
}
run().catch(err => { console.error('TRONWEB_INTEROP_FAILED', err.message); process.exit(1); });