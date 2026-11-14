# C04 — one customer lead inbox, no silent dual-write (2026-11-14)

**Scope:** ZomorodMelal.ir, six nonbinding service requests and sole organisational bot \`mojtaba.bot.ai\`. This is a source-only change, stacked on C03. No real customer intake, payment, quote, mail, host configuration or delivery is claimed.

## Reason / proven source defect

C03 introduced a second service-specific Django lead form while \`config/urls.py\` already routes \`/contact/\` to legacy \`/ask-master/index.php?service=1\`. Two different stores could receive sales interest independently. The legacy PHP code and production records for this **Zomorod** form were not available in GitHub; internet retrieval from the current environment did not independently verify its live status. The MojPlayWin PHP inquiry in another source module is **not** this Zomorod company form and must not be conflated with it.

**Critical correction:** adding a new Django URL cannot silently switch customer capture away from a pre-existing source of truth. The C04 default is the known pre-existing site path, documented as **unverified**, not a proven live working form.

## Safe routing decisions
- \`core/service_intake_routing.py\` defines exactly one canonical URI for all six services, default \`/ask-master/index.php?service=1\`.
- When migration is not independently approved, all six service cards on \`/services/\` link to that single path. Service code context is not guaranteed preserved by PHP (no fabricated cross-system attribution).
- Direct GET to \`/services/request/<SERVICE_CODE>/\` redirects to the existing path if Django is disabled, after valid service-code and host checks.
- Direct POST to disabled Django intake returns **503**, a safe human-clickable link to the legacy form, \`Retry-After: 3600\`, no-store/noindex and **never stores/forwards submitted PII**.
- Django intake can only be active if **all** these environment-backed booleans are exactly true and the expected source label matches:
  - \`SERVICE_INTAKE_DJANGO_ENABLED\`
  - \`SERVICE_INTAKE_SINGLE_SOURCE_APPROVED\`
  - \`SERVICE_INTAKE_ROLLBACK_VERIFIED\`
  - \`SERVICE_INTAKE_PRIVACY_REVIEWED\`
  - \`SERVICE_INTAKE_SOURCE_OF_TRUTH=django_company_inquiry_v1\`
- All flags default **false** and source defaults \`legacy_ask_master_unverified\`. Merely merging the code does not activate Django capture.
- These flags are operator declarations, **not independently verified receipts or proof of real PHP/Django parity**. External approval, site inspection, rollback and lawful data processing must be verified separately.
- If all gates are set deliberately, the previously tested C03 Django form remains available. It still creates a nonbinding \`CompanyInquiry\`, not a payment or contract.

## Sole bot inspection
- Owner-only GET API (superuser + cookie): \`/staff/command-center/api/bot/service-intake-source/\`.
- Local read-only CLI: \`python manage.py mojtaba_intake_source_readonly\`.
- \`EconomicMasterAgent.inspect_intake_source_configuration_readonly()\` uses the identical snapshot; it is not a second agent.
- API and CLI disclose only boolean release flags, source label, known fallback path, six-service count and UNKNOWN external evidence. No raw environment variables, customer email, message, wallet or secrets.
- Access boundary: the method/CLI require a trusted owner/operator context; the owner-only HTTP wrapper is the authoritative web authorization boundary.
- HTTP response: GET only, private/no-store, noindex, Vary: Cookie, nosniff.
- All six existing cards retain scientific limitations, no price approval, no accepted order and no real cash confirmation.

## Tests and non-production acceptance
The scoped C04 GitHub Actions workflow uses exact-commit Python 3.11 and isolated SQLite with no production credentials. It compiles source files, runs Django system checks, 43 economic math regressions, 25 service rights tests, 130 previous Django+CRM+CLI tests, plus **41 new C04 tests**: expected **239** total targeted checks if all pass. It tests disabled GET redirect, blocked POST not saving, recovery link, no PII, no fake cash, six fallback URLs, each enabling flag separately, rejection of truthy strings/ints, wrong source, previously enabled C03 tests, owner-only API and CLI. It does not simulate a real PHP/MariaDB or payment platform.

Do not report pass before exact final-head run confirms it. A passing CI is still not an operational deployment.

## Live cutover acceptance criteria (not performed)
1. Verify current Passenger/cPanel effective code root and PHP \`ask-master\` endpoint, status, and private backing storage using authorized read-only access; confirm no unrelated MojPlayWin form is mistaken for it.
2. With appropriate access and lawful scope, reconcile pending lead counts, verified receipt IDs, dates and privacy handling; **do not export PII into GitHub or CI**.
3. Verify owner-approved data retention policy, backups, restoration, legal basis and customer contact permissions.
4. Confirm the single source-of-truth decision and any required safe migration; never dual-write customer data without a documented policy.
5. Check official quote, legal ability to accept payment, independent settlement and actual service delivery.
6. Request case-specific owner approval for any production deployment and additional financial or contractual commitments.
7. Inspect conversion from real, consented demand to actual settled and delivered orders, not telemetry events.
8. Preserve a reversible deployment and evidence ledger; verify live source SHA before and after any separately approved deployment.

## No-go caveats
The older PHP route may itself be unavailable; the source code alone cannot verify its behavior. This work **prevents accidental introduction of a second active Django intake**, but does not fix or certify the PHP service or deliver new paid customers. Concurrency-safe deduplication, coordinated data migration, anti-abuse rate limiting, sales qualification, cross-system reconciliation, and independent finance proof remain outside this change.

**Cash revenue settled through this cycle:** UNKNOWN/NOT VERIFIED. **Real host deploy:** not performed. **New financial expenditure or obligation:** none requested or authorized.
