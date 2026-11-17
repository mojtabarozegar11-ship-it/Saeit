# MOJ PROP v1.4.1 — private tenant DEMO statement + release controls

**Source-only, Draft PR #2690; not a production feature.** Parent #2688
depends on #2684; all three are Draft and NO-SALE. The first available
FA/EN buyer terms specify **ONE** total 28-day evaluation window for
both phases, not 28 days each.

## Actual implemented customer functionality

- `GET|HEAD /moj-prop-v141/statement/<slug:challenge_ref>/` is an HTML,
  mobile-responsive FA/EN, keyboard-friendly private virtual statement.
- It is **DEFAULT OFF** unless `MOJ_PROP_V141_PORTFOLIO_ENABLED`
  is explicitly Python `True`; this flag is NOT enabled here.
- Authenticated Django session, active HTTPS and allowlisted MojPlayWin
  host; opaque bounded slug; no query strings; `owner_id=request.user.pk`
  and exact `state__challenge_ref` must both match before database
  history is read. Missing/cross-tenant challenge gives 404.
- The view reads `PropV141VirtualBook` and at most 25
  `PropV141VirtualFill` rows, sorted by descending sequence.
- Only recorded realized **virtual** P&L, fully closed position count,
  event count, unlocked phase, and contract-wide UTC deadline are shown.
  Historic fill times are forced to UTC even when the site timezone is
  Asia/Tehran. It does not compute unrealized equity or grant funding.
- Existing private JSON path
  `/moj-prop-v141/portfolio/<slug:challenge_ref>/`
  is unchanged, retains the same owner-filter + flag restrictions.
- Response headers prevent caching, indexing, embedding and client data
  exfiltration through forms, frames, scripts, cross-site resources.
  No JS, wallet, checkout, form, external links, broker credential,
  automated execution or public user provisioning is introduced.
- HEAD sends no body. POST/PUT are rejected; there is no mutation endpoint.

## Exact demonstrable tests

- Original source baseline: 837 / 837 Python 3.11 checks on #2688
  [run #44156441327](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44156441327).
- This stacked PR adds **31** actual MariaDB/Django request tests to
  the original **13** MariaDB transactional checks. The complete **44**
  integration tests passed on head
  `ff569f0bfecf39077fcb01fdc2323d35a5302205` in
  [GitHub Actions #44157899387](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44157899387).
  They include actual session middleware and URL routing, ownership
  isolation, anonymous redirect, HTTPS and query denials, flag OFF,
  writer-to-template persistence, bilingual rendering, date boundaries,
  25-row limit, cache policies, and existing JSON separation.
- One earlier 35-case test execution failed because the stripped-down
  CI settings lacked a login-redirect URLconf. That failure was fixed
  by introducing isolated Django session middleware and real test URLs;
  it must not be misrepresented as a prior clean run.
- The next workflow revision adds re-execution of the 837-case source
  suite to the SAME isolated MariaDB CI. Report combined success only
  after checking its exact head SHA and run logs.

## Production NO-GO — independent evidence required

1. Existing actual production/factory MariaDB schema inspected with
   SELECT-only permissions: row lock, strict SQL, collision assessment,
   storage capacity, staged 0009/0010 migration and rollback with a
   separately verified **full off-host recoverable DB+files backup**.
   The disposable CI DB cannot demonstrate this.
2. Actual third-party/independent licensed source of timestamps,
   trade fills, price marks, floating equity and all day-open marks,
   plus a complete independently retained immutable raw source
   archive and verifiable identity; HMAC demonstrates sender possession
   of a key, not honest prices or completeness.
3. Proper session and HTTPS review at the actual reverse proxy:
   the production settings trust `X-Forwarded-Proto`; the TLS
   terminator must strip client-supplied forwarded headers, reject
   direct origin access, and serve correct cookie and CSRF policies.
   A local HTTPS flag test does **not** prove this proxy fact.
4. Legally cleared FA/EN signed buyer agreement, regional eligibility,
   KYC/AML/privacy/refunds, and whether a 672-hour public financial
   promotion condition is permissible. Broker written permission
   and company capital/risk review are separate before any real order.
5. Owner-authorized unique server-confirmed 30-native-TRX merchant
   settlement and verified provisioning; reject duplicate transactions
   and enforce buyer email/receipt, but do not expose these actions
   to anyone before the legal/backup/release gates.
6. Owner-authorized deploy from a deliberate production-specific
   commit, post-deploy HTTPS/HTML/login/tenant-isolation tests,
   rollback rehearsal and availability monitoring.
7. Never merge the new UI Draft alone when the underlying migration
   stack (#2684 -> #2688) is not integrated and verified; otherwise
   route would fail when the backing `0010` schema does not exist.

**No fee, real order, account funding, payout, production DB migration,
contract activation, PR merge or live deployment is performed here.**

## Live-site verification limitation

Two read-only attempts (web retrieval and container curl HEAD) to
`mojplaywin.com` from this environment failed to resolve/open the host.
This is a tool/network visibility limitation; it is NOT evidence the
customer's site is necessarily offline. Live route status remains UNKNOWN.
