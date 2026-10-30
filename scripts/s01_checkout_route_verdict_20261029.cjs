'use strict';
// Pure classification of anonymous GET navigation; never a buyer-flow proof.
function classifyNavigation(path, http, finalPath, error, finalSearch = '') {
  const authGated = /\/checkout\/$/.test(path) || path.includes('/purchases/');
  const authRequired = authGated && finalPath === '/accounts/login/';
  // A login response with a mismatched next target can strand a buyer on
  // another product or an external site. Never count it as a healthy checkout.
  let safeLoginReturn = false;
  if (authRequired && typeof finalSearch === 'string' && finalSearch.startsWith('?')) {
    try {
      const params = new URLSearchParams(finalSearch);
      const nextValues = params.getAll('next');
      // A login redirect without the exact original return path strands the
      // buyer; extra/duplicate query keys make the navigation ambiguous.
      safeLoginReturn = [...params.keys()].every(key => key === 'next') &&
        nextValues.length === 1 && nextValues[0] === path;
    } catch (_) { safeLoginReturn = false; }
  }
  // No query is expected on a directly requested canonical checkout route.
  const expectedDestination = (finalPath === path && !finalSearch) ||
    (authRequired && safeLoginReturn);
  const unexpectedRedirect = !expectedDestination;
  // Redirect-only, malformed or missing responses are not successful page observations.
  // page.goto normally returns the final response, but classify defensively.
  const observedSafe = Number.isInteger(http) && http >= 200 && http < 300 && !error && expectedDestination;
  return {authRequired, unexpectedRedirect, observedSafe};
}
// Separate an observable anonymous page contract from paid-buyer delivery.
// Return specific, non-sensitive reasons; a single bad SKU/viewport fails closed.
function assessAnonymousRouteRows(rows, expectedPaths, expectedDevices) {
  const failures = [];
  if (!Array.isArray(rows) || !Array.isArray(expectedPaths) ||
      !Array.isArray(expectedDevices) || !expectedPaths.length || !expectedDevices.length)
    return {complete:false, failures:['INVALID_OBSERVATION_MATRIX']};
  const expected = new Set();
  for (const device of expectedDevices)
    for (const path of expectedPaths) expected.add(device + ':' + path);
  const seen = new Set();
  for (const row of rows) {
    const key = String(row?.device) + ':' + String(row?.path);
    if (!expected.has(key)) {failures.push('UNEXPECTED_ROW:' + key); continue;}
    if (seen.has(key)) failures.push('DUPLICATE_ROW:' + key);
    seen.add(key);
    if (row.observedSafe !== true) failures.push('UNSAFE_NAVIGATION:' + key);
    if (!Array.isArray(row.jsErrors) || row.jsErrors.length)
      failures.push('JS_ERRORS:' + key);
    if (['/store/product/72/','/store/product/225/','/store/product/879/'].includes(row.path)) {
      if (!Number.isInteger(row.checkoutLinks) || row.checkoutLinks < 1)
        failures.push('NO_USABLE_SKU_CHECKOUT_CTA:' + key);
      if (row.mismatchedCheckoutLinks !== 0)
        failures.push('MISMATCHED_SKU_CHECKOUT_CTA:' + key);
    }
  }
  for (const key of expected) if (!seen.has(key)) failures.push('MISSING_ROW:' + key);
  return {complete:failures.length === 0, failures};
}
// Registration links may include ?next=/store/product/<sku>/checkout/.
// They are NOT direct checkout CTAs and must not be counted as cross-SKU links.
function isDirectCheckoutHref(href) {
  if (typeof href !== 'string' || href.includes('?') || href.includes('#')) return false;
  const parts = href.split('/');
  return parts.length === 6 && parts[0] === '' && parts[1] === 'store' &&
    parts[2] === 'product' && /^[0-9]+$/.test(parts[3]) &&
    parts[4] === 'checkout' && parts[5] === '';
}
// Public CI artifacts must not persist redirect tokens, signed query values,
// URL fragments or arbitrary external URLs observed in anonymous page controls.
// Call this only AFTER classifying the raw in-memory CTA for exact SKU matching.
function redactObservedHref(href) {
  if (href === null) return null;
  if (href === '[external]' || href === '[invalid]') return href;
  if (typeof href !== 'string' || !href.startsWith('/') || href.startsWith('//'))
    return '[invalid]';
  try {
    const url = new URL(href, 'https://mojplaywin.com');
    if (url.origin !== 'https://mojplaywin.com') return '[external]';
    // A redirect or control path can itself contain a bearer token. Persist
    // only known public checkout navigation shapes; redact unknown paths.
    const safePath = url.pathname;
    const known = safePath === '/store/' ||
      /^\\/store\\/product\\/(?:72|225|879)\\/(?:checkout\\/)?$/.test(safePath) ||
      /^\\/accounts\\/(?:login|register)\\/$/.test(safePath) ||
      safePath === '/commerce/trx-easy/purchases/';
    if (!known) return '[redacted-path]';
    return safePath + (url.search ? '?[redacted]' : '') +
      (url.hash ? '#[redacted]' : '');
  } catch (_) { return '[invalid]'; }
}
module.exports = {classifyNavigation, assessAnonymousRouteRows, isDirectCheckoutHref, redactObservedHref};
