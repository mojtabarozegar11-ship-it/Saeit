# MojPlayWin — One-pass commercial audit/release boundary (2026-11-13)

## Actual execution scope

This bundle is **read-only / source-only** until an authorized production
deployment is separately verified. It does not silently modify cPanel, VPS,
Passenger, MariaDB, cron, payments, mail, or customer purchase records.

- Public buyer-journey observer: \`scripts/mpw_onepass_public_sales_audit_20261113.py\`
  performs only ten bounded HTTPS GETs. It classifies the live storefront,
  canonical details, primary checkout and legacy checkout aliases for SKU
  72/225/879. It checks product-specific POST actions and CSRF but NEVER
  submits a form or makes an invoice. It highlights the mismatch between
  email-free guest checkout policy and legacy email fields.
- Payment provenance auditor: \`scripts/mpw_paid_provenance_readonly_20261105.py\`
  now separates historical trial 779, trial-mixed orders, configured
  nontrial products and out-of-allowlist cases. All counts explicitly apply
  to the first 100 examined paid intents. It does not infer commercial
  revenues from paid flags or ledger records.
- Isolated stdlib tests:
  \`tests/test_mpw_onepass_public_sales_audit_20261113.py\` and
  \`tests/test_mpw_paid_sku_scope_20261113.py\`.
- Existing hourly automation \`Automation_75923e04f34081918a223da21a8d53e4\`
  monitors external evidence. It cannot replace a privileged cPanel
  reconciliation or validate buyer downloads.

## Production acceptance: one accountable release, not scattered merges

1. Verify fixed SSH host fingerprints and use the **existing** factory VPS
   runner to read cPanel production source, without replacing keys or opening
   new ports. The GitHub-hosted runner path failed at host-key discovery in
   run 43413348378; a broken observer is **not** proof of broken checkout.
2. Perform exact source/hash comparison against
   \`/home/zomorod2/Saeit-staging\` and current public
   \`/store/\` fallback. Preserve all live templates and independent sites.
3. Reconcile changes across Drafts #1890 (email-free guest), #2205
   (host-local monitoring), #2204 (paid source scope), #2213
   (dynamic storefront), #2217 (three-SKU release gates) and
   #2207 (product detail/source rights) before any merge. Never merge
   these conflicting branches independently or treat their assertions as
   deployed.
4. Authenticate the **real** read-only production MariaDB account with
   least privilege; count intended public SKU paid flags separately from
   trial 779, confirm finality independently on TRON mainnet, prevent
   tx-hash reuse, link receipt/entitlement and observe an authenticated
   customer download with an owner-approved real purchase.
5. Check complete guest-no-email order creation including invoice server,
   signed private entitlement, anti-replay and cross-browser recovery.
   Neither public GET/HTTP 200 nor offline CI validates this.
6. Release only with owner-approved source-equivalent backup, immutable
   rollback, verified rights and no other site changes. No purchase,
   email send, deployment, migration, or billing without separate
   transaction-specific confirmation.

## Non-fabrication contract

\`confirmed_current_commercial_sales\`, revenue, verified download and
independent on-chain finality remain **unknown**, not zero, whenever their
corresponding proof is absent. Historical trial 779 is not revenue
from the three currently offered products. Expose only aggregate counts
and classifications, never buyer e-mail, PII or transaction hashes.

Source evidence: GitHub Actions run 43413348378 failed before cPanel
query execution; previous documented GET inspection showed static
fallback. These historical observations are not real-time site status.
