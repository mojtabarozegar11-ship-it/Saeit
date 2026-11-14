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

## Cycle 6 — existing cPanel read-only bridge is wired, NOT dispatched

The existing `deploy/cpanel_direct_command.sh` and
`.github/workflows/cpanel-direct-command-bridge.yml` now explicitly
allow one extra **manual, read-only** choice:
`mpw_source_provenance`. It runs
`scripts/mpw_onepass_cpanel_source_provenance_readonly_20261113.py`
over the existing fingerprint-pinned factory-VPS-to-cPanel SSH connection
with `python3 -B` (stdin, no remote installation, no site edits).

The operation is restricted to the main-branch, owner-controlled
`workflow_dispatch` and has not been invoked in this cycle.
The reporting script refuses a non-`zomorod2` account. Its output
contains only bounded classifications and a prefix of the source digest,
not any template body, private values or customer records.
A green local test does NOT prove SSH access or the effective Django template.

The bridge and report passed 22 synthetic safety tests (16 provenance and
6 operation-wiring tests). Together with previous tests, **249/249**
isolated unit tests passed in
[GitHub Actions 43450899114](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43450899114).
Two independent guest identity/route scripts also passed.

Latest GET-only public observation in the same run:
10/10 routes categorized, 3 product detail GETs actionable,
static `/store/` fallback still present, all six checkout forms
collect email and **lack explicit `script-src`**. Missing
`script-src` is a target-CSP mismatch; it does not, by itself,
demonstrate exploitability because another CSP directive may provide
a fallback. No independent TRON settlement, buyer delivery or
collected commercial revenue has been verified.

Next production action remains a separately authorized read-only
execution of `mpw_source_provenance` against the real cPanel account,
followed by actual effective Django template resolution and rights
proof. No merge or production deployment is authorized by this
document.

## Cycle 7 — cPanel source classification now covers the actual commerce modules

The cPanel-only read-only source report was extended to include both
`core/mojplaywin_views.py` (storefront view) and
`mpw_commerce/product_checkout_page.py` (checkout/CSP source). It returns
bounded file-presence flags, SHA-256 prefixes and literal source markers;
it deliberately **does not** claim that those Python modules were imported
by Passenger or that `script-src` was sent in the HTTP response.

The static fallback classification now requires the exact owned leading
rewrite block at the very start of `public/.htaccess`. A duplicate rule
or a rule following unrelated directives cannot be certified. Even the
positive category `owned_static_fallback_rule_on_disk` is **not evidence
of an effective Apache route**.

### Next source reconciliation sequence

1. Observe public anonymous GETs and classify checkout forms/CSP; this is
   already established in the GitHub-hosted read-only gate.
2. Execute the separately controlled `mpw_source_provenance` option in
   the **existing** pinned cPanel bridge, once the reviewed code is
   approved and available to that main-only workflow. Do not
   activate the old cutover or the payment/release workflow.
3. Compare bounded guest, storefront and checkout source digests against
   the reviewed exact versions; verify the **effective** Django
   template origin and Passenger module separately using only
   owner-approved read-only diagnostics.
4. After all six public checkout forms and CSP are correct, request
   an owner-approved exact-source backup/cutover with rollback.
   Full commercial readiness still needs an approved real purchase,
   independently finalized TRX and an authenticated download.

The bridge has **not** been dispatched, the source audit has **not**
inspected actual cPanel yet, and no file or configuration was deployed.
Passing isolated code tests is not a substitute for these observations.

[Latest isolated regression results](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43453342347):
**257/257 passing** across public observer, provenance, guest source,
telemetry, dynamic cutover, source-only cPanel and bridge safety. Two
additional independent identity/route scripts passed.

## Cycle 8 — verified transport diagnosis and safe host-name remediation

A real, owner-triggered **read-only** Passenger diagnosis was launched by
the exact known Issue #1600 command. [GitHub-hosted run 43454715777](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43454715777)
verified the *pinned host keys*, but 5 VPS-proxied SSH attempts failed at
banner exchange and a direct cPanel attempt to the hardcoded
`178.239.147.125:1396` timed out. **It did not execute the remote source
inspector or touch the site.** Do not interpret this transport failure as
a payment, Django or data corruption finding.

The existing, previously successful *self-hosted factory-VPS* cPanel
authentication job was safely re-run without any write operations:
[run 43157969516, rerun job 131988664973](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43157969516).
It returned `CPANEL_SSH_AUTH_OK=1`, reported the expected cPanel host name
`zohal.pws-dns.net` and a connection address of
`178.239.147.124:1396`. The prior hardcoded `178.239.147.125`
address was a **plausible cause of runner-dependent transport mismatch**,
but NOT proof that the fixed address is globally dead. A later
self-hosted Passenger UAPI rerun on 13 November succeeded from the
existing main workflow, so distinguish runner reachability from address validity. The host key fingerprint is
still independently pinned and is not disabled or replaced.

PR #2263 now updates the cPanel SSH bridge in
`deploy/cpanel_direct_command.sh` (both pinned hop configurations) and
the existing issue-comment Passenger read-only workflow to use the
**verified DNS hostname** instead of relying on the fixed IP, while retaining the same key fingerprint. The same
ED25519 fingerprint, batch mode, strict known-host verification, original
VPS identity and no-forward-agent configuration remain in place.
The changes are only in the Draft branch, **not on main or cPanel**.

A separate control of cPanel template source now parses **real HTML
form fields**, rather than matching the word `email` in CSS or comments.
It also counts forms safely and distinguishes unreadable templates and
orphaned old labels. Seven new tests cover this behavior. Three
additional transport tests verify the authenticated hostname and pinning
are preserved. Combined [PR run 43456056199](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43456056199)
confirmed **267/267 isolated tests pass** and both standalone guest
identity/route checks pass.

### Remaining release blockers

The **actual cPanel source hash and effective Django template were not
read** in this cycle. The new source-provenance bridge option still
requires reviewed owner-approved availability on main and a separate
explicit manual read-only invocation. The public checkout still
collects email, the fallback is static and the strict CSP release target
is unverified. Real TRX settlement, buyer entitlement, authenticated
download and collected revenue are **unknown**.

Release remains **NO-GO**. No live merge, cPanel deployment/restart,
customer invoice, payment, email or paid tool invocation occurred.

## Cycle 9 — first fresh real cPanel Passenger mapping, no production mutations

**High-value real server evidence:** The existing self-hosted factory-VPS
`passenger_inventory` read-only job was re-run with its current main
workflow, without any merge:
[run 43162619527, rerun job 131997282584](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43162619527).
The cPanel UAPI call succeeded and reported two registered application
records in total, including exactly **one** entry for `mojplaywin.com`.
That entry's sanitized app-root classification has
`references_shared_saeit_staging=false` and an opaque fingerprint.
This does **not** prove the effective Django app, public URL resolver or
which private HTML template served the six checkout routes; those require
separate source/template and active routing inspection. The UAPI auditor
itself reports `production_isolation_proven=false`,
`release_permitted=false`.

The separate [owner-commanded private relay run 43457001017](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43457001017)
**failed before any remote source read**: five GitHub-hosted VPS SSH
banner timeouts and a direct fallback timeout to the fixed target.
The successful **same-day self-hosted** cPanel Passenger UAPI read means
the fixed IP cannot be called categorically unavailable; the actual
blocker is cloud-runner-dependent transport and lack of authoritative
effective-root/template proof.

**Source-only correction in Draft PR #2263:** the existing owner-gated
`.github/workflows/zomorod-private-command-dispatch.yml` now uses
`zohal.pws-dns.net` for both cPanel SSH modes, with the *same*
fingerprint-pinned ED25519 key, strict host checking, no agent forwarding,
and existing owner/main gating. Associated regression assertions were
updated and a new test requires preservation of the exact gate.
The dedicated Authenticated cPanel chat relay contract passed in
[run 43457852465](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43457852465).
No workflows were changed on main, so this fix has **not been proven on the
live private command relay**.

**Production verdict remains NO-GO.** The static storefront, six
email-collecting checkout forms and script policy mismatch were
independently observed on public GET; sales, on-chain settlement and
authorized delivery are unverified. Further safe action: obtain
effective Passenger root, Django template origin and exact source
fingerprints via the already authorized self-hosted route before
considering separate deployment approval. No paid or mutating
operation occurred.

## Cycle 11 — Restore privacy-safe commercial evidence collection via proven factory runner

**Root cause confirmed:** Last scheduled [MojPlayWin visitor and support inbox read-only audit,
run 43477203438](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43477203438)
failed at its cloud GitHub runner SSH relay setup *before* any financial
or checkout evidence was collected. There is no defensible conclusion of
zero revenue, a completed payment or a working download from that run.
Separately, the existing self-hosted factory-to-cPanel SSH verification and
Passenger inventory succeeded in
[runs 43157969516](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43157969516)
and [43162619527](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43162619527).

**Existing workflow repaired in Draft PR #2263:**
`.github/workflows/mpw-sales-intake-readonly-20261024.yml` now runs
its pre-existing hourly sales audit on `[self-hosted, factory-vps]`
and SSHes directly to `zohal.pws-dns.net:1396` as `zomorod2`.
The previously approved ED25519 fingerprint, strict host verification,
noninteractive authentication, no agent forwarding, bounded SSH timeouts,
private temporary credentials and unconditional cleanup are all maintained.
The unnecessary cloud-to-VPS proxy and VPS SSH private key were removed
from this path. Seven remote Python invocations are now `-B` to suppress
bytecode-file side effects. Its live sales, paid-proof, heartbeat and
access diagnostics remain pre-existing read-only operations.

**Validation without PR merge:** PR #2263 currently reports
`mergeable_state=dirty`. GitHub does not reliably execute
`pull_request` workflows for a conflicted merge ref. Therefore the
existing `.github/workflows/mpw-onepass-public-audit-readonly-20261113.yml`
was given a strictly scoped **Draft-branch-only `push` trigger for its
isolated safety-contract job**. It does not run the public buyer journey
or access cPanel when triggered this way. In
[run 43479642220](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43479642220),
**284/284 isolated unit tests passed**, including nine new checks for
the self-hosted sales audit, and both standalone guest identity/route
checks passed. The branch's historic broad CI and Django CI succeeded
on the prior reviewed commit; they are **not** new broad CI results for
this Draft head.

**Merge conflict footprint identified, not silently resolved:**
GitHub reports the PR is 86+ commits ahead of its merge base and behind
one new main commit (Zomorod 10-card carousel). Exactly three PR-touched
paths overlap that new main commit:
`deploy/cpanel_direct_command.sh`,
`scripts/test_zomorod_onepass_20261113.py`, and
`scripts/test_zomorod_vision_ux_20261113.py`.
The main commit also includes new Zomorod assets and functions that must
not be overwritten. Resolve these conflicts while preserving both main
carousel code and the new MojPlayWin guarded audit, with separate
owner approval before any merge of the PR into main. No force-push or
merge was attempted.

**Commercial status remains NO-GO:** No actual production
cutover, payment POST, customer invoice, TRX settlement, entitled
download, email or fee occurred in this cycle. The public store
is still static, six checkout pages request email and their explicit
target `script-src` policy is not verified. Actual received sales
remain **UNKNOWN** until an authorized read-only production audit
successfully returns defensible independent payment and fulfillment
evidence. A green unit test is not commercial proof.
