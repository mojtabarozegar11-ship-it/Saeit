# MojPlayWin — cPanel-local commerce observability (C28–C33)

## Why

The scheduled read-only GitHub Action stopped **before any live payment query**.
The first failure in run `42512241401` was the VPS SSH host-key scan:
`MPW_AUDIT_VPS_RELAY=unreachable_after_4_attempts`. Four successive Action
runs (#91–#94) failed; the last observed successful live read was #90.
Do not infer that the payment reconciler itself stopped: the SSH relay failed.

## Delivery candidate (not installed)

`mpw_host_local_sales_health_20261109.py` runs **on the same cPanel host** as
the established Python/Django runtime. It uses no VPS, SSH, GitHub Actions,
mail sender, or crypto network. It invokes three revision-pinned read-only
probe sources, keeps only approved aggregate fields, and atomically writes
one private `0600` JSON snapshot:

`/home/zomorod2/.private_mojplaywin_main_agents/mpw_readonly_health_latest.json`

It reports `operational_evidence_fresh=true` only if all three probes complete
with valid typed aggregate markers, and the payment-reconciliation cron log
shows a recent successful run plus repeated scheduled-run indications.
Repeated log entries are a *heuristic*, not independent proof that no manual
invocation occurred. It **always** records
`commercial_sale_or_customer_delivery_inferred=false`: the latest monitoring
snapshot is not an independent buyer-download or blockchain audit.

### C29 source-integrity hardening

Each source is verified against the exact audited Git blob revision before
execution, and its verified bytes are passed over Python standard input. A
changed, missing, symlinked, or oversized source fails closed. The approved
Git blob identities are pinned in `PINNED_SOURCE_BLOBS` in the runner.
Copying a different source version, including the newer Draft PR #2204 paid
scope classifier, requires review, updating its pin, and rerunning checks.
The pins are version-integrity controls, not proof of site health.

### C31 privacy and fail-closed hardening

- The original `mpw_sales_intake_readonly_20261024.py` probe is **not run**:
  it inspects support-mail headers and raw visitor logs that are unnecessary
  for payment monitoring.
- The dedicated `mpw_paid_aggregate_readonly_c31.py` source emits only
  bounded numeric counts and fixed boolean markers. It does not serialize
  per-order rows, buyer/order IDs, emails, or payment hashes.
- The runner rejects non-integer counts, negative values, nested or free-form
  whitelisted values, incomplete markers, unexpected write claims, and
  contradictory totals. A `0600` snapshot also requires an owner-only `0700`
  parent directory.
- Freshness requires the cron source to indicate a recent **successful**
  reconcile and at least two recent successes spaced plausibly for a
  once-per-minute schedule. An unverified scheduler remains a release caveat.
- No database permission isolation is provided by the Python source itself.
  Prior to any deployment, the actual runtime must be proven to use a
  SELECT-only database role with no DML, DDL, mail, or payment permissions.

### C32 view-side-effect reduction

- `mpw_runtime_flags_aggregate_readonly_c32.py` replaces the old payment
  baseline probe for this collector. It uses Django URL resolution and reads
  boolean feature flags but never creates a `django.test.Client`, performs a
  GET request, or invokes a checkout/login view.
- The runner requires all six known routes to resolve and zero HTTP view
  invocations. This is configuration-only evidence, not a real user journey.
- The aggregate paid probe inspects `SHOW GRANTS FOR CURRENT_USER` before its
  first paid-state query, rejecting privileged, role-based, or global SELECT
  grants and SELECT grants outside the configured database. It then sets
  `SET SESSION TRANSACTION READ ONLY` and verifies MariaDB
  11.x `@@session.transaction_read_only`. Neither step changes sales records.
- The 28 targeted offline tests cover the C31 privacy/fail-closed cases, C32
  view-free route resolution, and SELECT-only grant/session guards. They do
  not validate the real cPanel account or eliminate the need for an independent
  least-privilege review.

### C33 pre-Django credential isolation

- The paid probe **cannot** start Django with the storefront's default
  `DATABASE_URL`. Before importing Django, it requires a distinct, protected
  credential file at the fixed path
  `/home/zomorod2/.private_mojplaywin_main_agents/mpw_readonly_db_url.secret`.
  Its parent must be owner-only `0700`, and the regular credential file must
  be owner-only `0600` with no symlinks. Missing or unsafe credentials abort
  without falling back to the production application database account.
- The file must contain precisely a local `mysql://` URI for a separately
  provisioned **SELECT-only** cPanel MariaDB user. The URI is never printed or
  committed. After Django initializes, the probe checks its actual database
  name and verifies the actual MariaDB grants and session read-only mode
  before paid-state queries. Account creation/permissions are not automated.
- The flags/route probe forces an ephemeral in-memory SQLite database *before*
  `django.setup()`. Configuration/route inspection therefore cannot silently
  inherit the storefront's real MariaDB credentials. This remains route
  configuration evidence only.
- A second privacy pass removed all per-intent ORM iteration and joins to
  Order records. The only commerce query is an aggregate `COUNT` of paid
  payment-intent states. No row-level buyer, order, blockchain receipt, or
  provider-reference data are materialized by the observer.
  `walletless_persisted_credit_verified=0` now means **not checked**;
  both `walletless_credit_verification_performed` and
  `payment_intent_detail_read_performed` are explicitly `false`. Do not
  interpret these zeros as evidence of no credited sales.
- Do **not** put database passwords in crontab arguments, GitHub secrets,
  source code, reports, or web-accessible directories. The protected local
  credential file is a **future installation prerequisite**, not a file that
  this PR has created on the host.

## Proposed one-time installation after explicit deployment approval

1. Confirm the active cPanel account `zomorod2`, Python interpreter
   `/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python`, private directory,
   and an independently verified SELECT-only database role. Provision the
   separate owner-only `0600` `mpw_readonly_db_url.secret` file outside the
   web root **only after separate authorization**, using no live storefront
   database credentials. Do not modify the
   public site or production order tables; reject deployment if it would run
   with unrestricted Django DB credentials.
2. Review and copy this runner plus these **exact revision-pinned** read-only sources into a
   non-public directory named `mpw_readonly_sources` under the private root:
   - `scripts/mpw_payment_cron_heartbeat_readonly.py`
   - `scripts/mpw_paid_aggregate_readonly_c31.py`
   - `scripts/mpw_runtime_flags_aggregate_readonly_c32.py`
3. Keep the aggregate paid count separate from Draft PR #2204's proposed
   trial-versus-configured-product classification. Neither is evidence of
   actual nontrial sales or successful customer downloads; Draft changes are
   **not** assumed deployed.
4. Grant the private directory `0700` and source files appropriate private
   read permission. Keep all output outside `public_html`, web roots, mail,
   and customer download directories.
5. Add **one** cPanel-local hourly cron entry after a single controlled
   observation of expected output:

   ```cron
   33 * * * * /home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python -B /home/zomorod2/.private_mojplaywin_main_agents/mpw_host_local_sales_health_20261109.py >/dev/null 2>&1
   ```

6. Keep the older GitHub audit unchanged until the local report is validated
   and an approved retirement decision is made. Do not overwrite or remove
   current reconciler cron. Avoid creating duplicate payment-processing jobs.

## Safety / limitations

- Private report is replaced atomically; no growing log or retained PII.
- Uses an exclusive lock to prevent overlapping collector runs.
- No production deployment, cron change, merge, purchase, payment, email, or
  personal-data transmission occurred as part of preparing this draft.
- A cPanel-host installation requires a separate explicit authorization.
- Unlike the Action, this monitor must be copied to cPanel with its probe
  sources. It cannot make existing SSH connectivity suddenly work.
- A stale or missing cron heartbeat is recorded as incomplete, not success.
- The heartbeat series is a log-derived heuristic, not a tamper-proof proof of
  the scheduler's origin; no commercial payment success is inferred.
- The cPanel host was reported at 91% disk usage. Do not create archives or
  unbounded monitoring logs on it.

