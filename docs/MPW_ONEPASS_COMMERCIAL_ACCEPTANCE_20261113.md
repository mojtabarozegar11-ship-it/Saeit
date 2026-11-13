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

## Independently observed public-blocker evidence — GitHub Actions 43429609528

- Source: [GitHub-hosted, public GET-only execution](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43429609528). Sanitized immutable evidence copy: `runtime/mpw_public_live_get_evidence_20261113.json`.
- **10/10 GET responses were categorized** without network failure: all three individual product pages exposed the expected product-specific checkout CTA; the central `/store/` remained the owned **static fallback** rather than dynamic catalog.
- All **six** canonical/alias checkout pages for product IDs 72, 225, 879 **still rendered email-requesting forms**, contrary to the expected email-free guest checkout policy.
- All six failed the strict `script-src 'none'` CSP check (category `checkout_csp_scripts_unverified`). This is a **security-header release blocker**, not a proof that the payment processor is inoperable. No raw header values, customer information or tokens were logged.
- The preliminary run [43429288934](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43429288934) already identified the fallback and header failures; the refined observer separated header and form evidence.
- **Never** label the three good GET product pages as completed sales or 10/10 commercially ready. The present public storefront fails the acceptance gate.

### Exact next release preconditions, in order

1. **Source equivalence**: establish a fresh, pinned read-only snapshot of the actual cPanel Passenger/Django app, database schema and static fallback state through the preexisting factory VPS runner; GitHub main/PR code alone is insufficient.
2. **Guest transaction policy**: integrate and run server-side invoice POST without email with a valid anonymous signed ownership claim and original session access; reconcile historical email recovery separately with owner-approved alternative recovery. Never expose receipts by public tx hash alone.
3. **CSP**: enforce the exact narrow script policy and no-store on both canonical and alias checkout responses; verify presence on live server, avoiding changes to the design of any site or subsite.
4. **Dynamic catalog**: remove only the exact owned static fallback after preflight, backups, rights-hash inventory, rollback and independently verified three-SKU checkout; never overwrite unrelated templates.
5. **Financial acceptance**: independently confirm one owner-approved TRX mainnet settlement for a nontrial SKU, match DB ledgers and private entitlement, verify a genuine authorized download, then measure net revenue only from independently proven sales. No transfer initiated by this audit.

Current release verdict: **BLOCKED / NOT DEPLOYED / REVENUE UNKNOWN**. The public GET probe independently verifies the blockers, not their remediation.

## Consolidation update — reviewed email-free guest candidate in this PR

PR #2263 **now contains executable source changes**, not solely an auditor.
The exact reviewed source snapshots below were brought from Draft #1890
without launching a production process:

- \`services/mpw_trx_guest_commerce.py\` — immutable signed browser owner,
  private non-deliverable \`@guest.mojplaywin.invalid\` internal invoice
  identifier, never collects a buyer mailbox, fail-closed privileged owner
  checks, exact unambiguous commercial route binding and correct
  post-commit analytics classification.
- \`scripts/mpw_guest_no_email_release.py\` — manually invoked, owner-gated,
  reversible, hash-pinned replacement of precisely the known email field
  and stale recovery copy in the **effective private cPanel checkout
  template**, not a blanket replacement of site templates.
- \`scripts/test_mpw_guest_route_patching.py\`,
  \`scripts/test_mpw_guest_first_order_identity.py\`, and
  \`tests/test_mpw_guest_no_email_release.py\` — isolated no-network
  regression tests for route preservation, guest concurrency, staff and
  legacy-email rejection, template integrity and release plan rollback.

The reviewed no-email patch is not a successful production checkout merely
because source-level tests pass. The **effective**
\`mpw_commerce/templates/mpw_commerce/product_checkout.html\` template is
not present in main GitHub and must be audited and surgically changed
only after its actual cPanel owner, content hash, and complete route
dependencies are confirmed. No fake checkout template may be shipped.

### Source integration of guarded cutover candidate #2213

The same Draft PR #2263 now includes the guarded dynamic-store cutover
script and its 45 isolated tests. Its invoked staging preflight checks
the **email-free** guest source and associated invoice dependencies;
unused definitions inherited from the earlier email-ownership proposal
are not part of the invoked preflight path.

Source integration does not activate /store/, change cPanel, or establish
a completed payment. The public static fallback must remain until the
effective cPanel template, permissions, guest invoice/entitlement flow,
CSP, and rollback are independently verified. Do not execute a legacy
email-recovery cutover by itself.

Latest reviewed source commit 72ac96edf0620747527d0e985768e5f02ba26219:
224/224 isolated unit tests passed; CI and Django CI passed. The public
GET-only release gate continues to identify the static storefront,
six email-collecting forms and strict CSP mismatch.

**This entire PR remains Draft / not merged / not deployed.** Commercial
sales, finality and authenticated download remain unverified. No
positive revenue figure or production readiness percentage is inferred
from the passing offline suite.

## Cycle 6 — actionable cPanel source reconciliation, without production changes

A new command-line probe, `scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py`,
can classify the installed guest adapter, locally present private checkout
template, Passenger staging source marker and owned static-store fallback.
It does NOT import Django, query MariaDB, access customer data, make HTTP
requests or change files. It must be executed **only through the already
authorized fingerprint-pinned read-only cPanel route** on the actual
`zomorod2` account. Do not interpret its GitHub-hosted synthetic tests as
an actual cPanel inspection.

The report deliberately sets
`effective_django_template_origin_verified=false`: file presence alone
does not prove which template Django selects. It also sets commercial
settlement, download and revenue to unverified or unknown. The source probe
must be followed by separate authorized effective-template and financial
proof before any production release.

An independent public observer now also records
`checkout_script_policy_categories`: bounded categories such as
`script_self_only`, `script_nonce_or_hash`, `script_unsafe_inline_or_eval`,
`script_none`, `script_src_missing` and `csp_missing`.
No raw CSP value, nonce, customer value or secret is recorded. A category
different from the target `script_none` is a **target-policy mismatch**;
it must not automatically be described as exploitable security weakness
or as a failed TRX processor.

Source validation: [GitHub Actions 43450196370](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43450196370)
passed **243/243 isolated unit tests** (66 public observer, 9
paid provenance, 104 email-free release, 3 telemetry, 45 dynamic cutover,
16 cPanel provenance). Independent guest-route and identity scripts passed.
These tests involve synthetic cPanel fixtures and no real cPanel login.

**Go/no-go remains NO-GO** until actual cPanel source equivalence,
dynamic storefront, six email-free buyer forms and authorized independent
settlement and delivery are proven. The changes remain a draft PR.
