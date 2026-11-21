// MOJ1 is the planned TRON-network purchase asset, not an active payment rail.
// Production checkout requires independently verified contract, decimals, ownership,
// jurisdictional compliance, server-side order/receipt validation, and owner approval.
// This browser module NEVER creates a payment intent or grants paid inventory.
export const MOJ1_COMMERCE = Object.freeze({
  asset:'MOJ1', network:'TRON', contractAddress:null, decimals:null,
  ownerApproved:false, checkoutEnabled:false, verifiedBackend:false
});
export const MOJ1_CATALOG = Object.freeze([
  Object.freeze({sku:'ramadan-reticle-theme', category:'cosmetic', priceAtomic:null, enabled:false}),
  Object.freeze({sku:'ramadan-armor-paint', category:'cosmetic', priceAtomic:null, enabled:false})
]);
export function checkMoj1Purchase({platform='web', sku}={}) {
  if (!['web','android','ios'].includes(platform)) return {allowed:false, code:'UNSUPPORTED_PLATFORM'};
  if (!MOJ1_CATALOG.some(item=>item.sku===sku)) return {allowed:false, code:'UNKNOWN_SKU'};
  // Mobile store billing rules cannot be bypassed by linking to an external wallet.
  if (platform!=='web') return {allowed:false, code:'PLATFORM_BILLING_NOT_APPROVED'};
  return {allowed:false, code:'OWNER_AND_CONTRACT_VERIFICATION_PENDING'};
}
