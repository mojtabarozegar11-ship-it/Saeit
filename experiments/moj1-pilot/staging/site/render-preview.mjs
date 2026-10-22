// An offline static review page. No script tags, forms, wallets, checkout,
// network requests, analytics, external assets or production configuration.
import {validateStagingManifest} from '../mojplaywin-readonly-bridge.mjs';

const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
})[char]);
const must = (ok, code) => { if (!ok) throw Error('MOJ1_PREVIEW_' + code); };

export function renderMoj1StagingPage({manifest, receipt}) {
  validateStagingManifest(manifest);
  must(receipt && typeof receipt === 'object' && !Array.isArray(receipt), 'RECEIPT_INVALID');
  must(receipt.schema === 'moj1_mpw_synthetic_readonly_v1' &&
    receipt.status === 'PASS' && receipt.orderKind === 'SYNTHETIC_ONLY' &&
    receipt.orderState === 'NOT_A_REAL_ORDER' &&
    receipt.orderId === 'MOJ1-READONLY-TEST-ONLY' &&
    receipt.tokenNetwork === 'Shasta' &&
    receipt.tokenContract === manifest.token_contract &&
    receipt.tokenSymbol === manifest.symbol &&
    receipt.tokenSupplyWhole === manifest.total_supply_whole &&
    receipt.escrowFullyFunded === true && receipt.distributed === false &&
    receipt.sourceOfChainProof === 'SHASTA_PUBLIC_READ_ONLY', 'RECEIPT_UNVERIFIED');
  for (const key of ['paymentEnabled', 'deliveryEnabled', 'orderWriteEnabled',
    'mainnetEnabled', 'keysUsed', 'realMojPlayWinGatewayChanged']) {
    must(receipt[key] === false, 'UNSAFE_FLAG_' + key.toUpperCase());
  }
  must(receipt.paymentMethod === 'UNAVAILABLE', 'PAYMENT_RAIL_UNSAFE');
  const html = [
    '<!doctype html>',
    '<html lang="en">',
    '<head>',
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<meta name="robots" content="noindex,nofollow,noarchive">',
    '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">',
    '<title>MOJ1 | Shasta Testnet Preview — MojPlayWin</title>',
    '<meta name="description" content="MOJ1 Shasta testnet informational preview. No sales or payments.">',
    '<style>',
    ':root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,sans-serif}',
    '*{box-sizing:border-box}body{margin:0;color:#eaf1ff;background:#091323;line-height:1.5}',
    '.shell{max-width:1100px;margin:auto;padding:24px}',
    '.top{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}',
    '.brand{font-size:1.05rem;font-weight:800;letter-spacing:.02em}.brand span{color:#5bd8cd}',
    '.pill{display:inline-block;padding:8px 12px;border-radius:99px;border:1px solid #42647b;color:#b3e9e5;background:#163047;font-size:.76rem;letter-spacing:.06em;font-weight:750}',
    '.hero{position:relative;overflow:hidden;border:1px solid #29455e;border-radius:26px;margin-top:25px;padding:clamp(24px,6vw,58px);background:radial-gradient(circle at 90% 10%,#194c64,#102338 48%,#0d1b31)}',
    '.eyebrow{font-size:.82rem;text-transform:uppercase;letter-spacing:.17em;color:#71ded1;font-weight:800}',
    'h1{font-size:clamp(2.7rem,7vw,5.8rem);margin:10px 0;letter-spacing:-.055em;line-height:1.05}',
    '.sub{max-width:650px;font-size:clamp(1rem,2.1vw,1.25rem);color:#b8c9d9;margin:0 0 24px}',
    '.tagline{display:inline-flex;gap:10px;align-items:center;color:#f9df92;background:#51442255;border:1px solid #8c7133;padding:12px 15px;border-radius:13px;font-weight:700}',
    '.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:20px 0}',
    '.card{background:#11223a;border:1px solid #27415b;border-radius:19px;padding:23px;min-width:0}',
    '.k{font-size:.78rem;color:#99b5cb;letter-spacing:.08em;text-transform:uppercase}',
    '.v{font-size:clamp(1.15rem,2.7vw,1.65rem);font-weight:800;margin-top:8px;overflow-wrap:anywhere}',
    '.v.green{color:#79e2bb}.v.amber{color:#f9df92}',
    '.panel{border:1px solid #315169;background:#122c3c;border-radius:19px;padding:22px;margin-top:20px}',
    '.panel h2{margin:0 0 10px;font-size:1.1rem}.panel p{color:#c0d3df;margin:8px 0}',
    'code{display:block;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere;background:#081725;padding:12px;border-radius:10px;color:#a9ecf1;font-size:.9rem}',
    '.notice{margin:20px 0 30px;padding:18px;border-left:4px solid #d4ae4f;background:#2c2a25;border-radius:8px;color:#f5e9c2}',
    '.footer{font-size:.85rem;color:#85a6bd;padding-bottom:22px}',
    '@media(max-width:720px){.grid{grid-template-columns:1fr}.shell{padding:16px}.hero{margin-top:15px}}',
    '</style>',
    '</head>',
    '<body data-testnet-only="true" data-synthetic-only="true">',
    '<main class="shell">',
    '<header class="top"><div class="brand">MOJ<span>PLAYWIN</span> / LAB</div><div class="pill">SHASTA TESTNET · VERIFIED READ-ONLY</div></header>',
    '<section class="hero" aria-labelledby="title">',
    '<div class="eyebrow">Digital asset · research preview</div>',
    '<h1 id="title">MOJ1</h1>',
    '<p class="sub">A testnet-only look at the Moj 1 token. Contract information is independently checked against public Shasta chain state. This is not a sale, investment offer, checkout or wallet connection.</p>',
    '<div class="tagline">◈ Demonstration only · No real value</div>',
    '</section>',
    '<section class="grid" aria-label="Testnet token facts">',
    '<article class="card"><div class="k">Network</div><div class="v green">SHASTA</div></article>',
    '<article class="card"><div class="k">Fixed supply</div><div class="v">100,000,000,000 MOJ1</div></article>',
    '<article class="card"><div class="k">Genesis allocation</div><div class="v green">100% in escrow</div></article>',
    '<article class="card"><div class="k">Token distribution</div><div class="v amber">Not started</div></article>',
    '<article class="card"><div class="k">Public sale</div><div class="v amber">Disabled</div></article>',
    '<article class="card"><div class="k">Real payments</div><div class="v amber">Disabled</div></article>',
    '</section>',
    '<section class="panel" aria-label="Contract identity">',
    '<h2>Verified Shasta token contract</h2>',
    '<p>Read-only identity; this is a testnet address and has no mainnet sale status.</p>',
    '<code>@@CONTRACT@@</code>',
    '</section>',
    '<section class="panel" aria-label="Checkout integration isolation">',
    '<h2>MojPlayWin integration test</h2>',
    '<p>Synthetic guest-order-shaped record: <strong>@@ORDER@@</strong></p>',
    '<p>No customer wallet, money transfer, production database write, payment confirmation, download entitlement or delivery is available.</p>',
    '</section>',
    '<aside class="notice"><strong>Notice:</strong> MOJ1 is undergoing technical testing. No buying, selling, transfer, or investment promises are available here. Production requires separate security, custody and legal reviews.</aside>',
    '<footer class="footer">MojPlayWin · MOJ1 isolated staging evidence · Not indexed · No wallet connection · No real payment</footer>',
    '</main></body></html>'
  ].join('\n');
  return html.replaceAll('@@CONTRACT@@', escapeHtml(receipt.tokenContract))
    .replaceAll('@@ORDER@@', escapeHtml(receipt.orderId));
}
