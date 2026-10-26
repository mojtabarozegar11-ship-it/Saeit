// Offline hypothetical AMM V2 sell-side calculator for MOJ1 feasibility.
// This is not a price oracle, live DEX quote, token mint, trade, or investment advice.
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const SCALE = 10n ** 18n;
const BPS = 10000n;

export function parseUnits(value) {
  if (typeof value !== 'string' || !/^\d+(?:\.\d{1,18})?$/.test(value.trim())) {
    throw new Error('AMOUNT_MUST_BE_NONNEGATIVE_DECIMAL_WITH_AT_MOST_18_PLACES');
  }
  const [whole, fractional = ''] = value.trim().split('.');
  return BigInt(whole) * SCALE + BigInt(fractional.padEnd(18, '0'));
}

export function formatUnits(value) {
  const negative = value < 0n;
  const absolute = negative ? -value : value;
  const whole = absolute / SCALE;
  const fraction = (absolute % SCALE).toString().padStart(18, '0').replace(/0+$/, '');
  return (negative ? '-' : '') + whole.toString() + (fraction ? '.' + fraction : '');
}

function ratio(numerator, denominator) {
  if (denominator === 0n) throw new Error('ZERO_DENOMINATOR');
  return formatUnits(numerator * SCALE / denominator);
}

export function simulateSell({ tokenReserve, quoteReserve, tokensSold, feeBps = 30 }) {
  if (!Number.isInteger(feeBps) || feeBps < 0 || feeBps >= 10000) {
    throw new Error('INVALID_FEE_BPS');
  }
  const t = parseUnits(tokenReserve);
  const q = parseUnits(quoteReserve);
  const x = parseUnits(tokensSold);
  if (t === 0n || q === 0n || x === 0n) throw new Error('ZERO_RESERVE_OR_TRADE');
  const effective = x * (BPS - BigInt(feeBps)) / BPS;
  if (effective === 0n) throw new Error('TRADE_TOO_SMALL_AT_18_DECIMAL_PRECISION');

  // Constant-product model. Fee remains in the token-side pool balance.
  const out = q * effective / (t + effective);
  if (out === 0n) throw new Error('ZERO_QUOTE_OUTPUT_AT_18_DECIMAL_PRECISION');
  const tAfter = t + x;
  const qAfter = q - out;
  const discountBps = BPS - (out * t * BPS / (x * q));

  return {
    model: 'HYPOTHETICAL_CONSTANT_PRODUCT_V2',
    quoteAsset: 'USDT_ASSUMED_FOR_SCENARIO_ONLY',
    noOnchainExecution: true,
    liveMarketVerified: false,
    liquidityProvided: false,
    tokenReserveBefore: formatUnits(t),
    quoteReserveBefore: formatUnits(q),
    tokensSold: formatUnits(x),
    feeBps,
    quoteReceived: formatUnits(out),
    spotQuotePerTokenBefore: ratio(q, t),
    executionQuotePerToken: ratio(out, x),
    spotQuotePerTokenAfter: ratio(qAfter, tAfter),
    tokenReserveAfter: formatUnits(tAfter),
    quoteReserveAfter: formatUnits(qAfter),
    executionDiscountBps: discountBps.toString(),
  };
}

function runCli() {
  const args = process.argv.slice(2);
  if (args.length % 2 !== 0) throw new Error('EXPECTED_FLAG_VALUE_PAIRS');
  const allowed = new Set(['--token-reserve', '--quote-reserve', '--sell-tokens', '--fee-bps']);
  const flags = new Map();
  for (let i = 0; i < args.length; i += 2) {
    if (!allowed.has(args[i]) || flags.has(args[i])) throw new Error('UNKNOWN_OR_DUPLICATE_FLAG');
    flags.set(args[i], args[i + 1]);
  }
  for (const required of ['--token-reserve', '--quote-reserve', '--sell-tokens']) {
    if (!flags.has(required)) throw new Error('MISSING_' + required.slice(2).toUpperCase());
  }
  const feeText = flags.get('--fee-bps') ?? '30';
  if (!/^\d+$/.test(feeText)) throw new Error('FEE_BPS_MUST_BE_INTEGER');
  const result = simulateSell({
    tokenReserve: flags.get('--token-reserve'),
    quoteReserve: flags.get('--quote-reserve'),
    tokensSold: flags.get('--sell-tokens'),
    feeBps: Number(feeText),
  });
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { runCli(); } catch (error) {
    process.stderr.write(String(error?.message ?? error) + '\n');
    process.exitCode = 1;
  }
}
