# Farm Economics — CRM order-inquiry and signed receipt release boundary

**14 November 2026 | branch-only source change | sole agent `mojtaba.bot.ai`**

## Actual defect eliminated in proposed source
The existing `/company/` POST path stored a `CompanyInquiry` but redirected the browser to the company landing page without a durable receipt; invalid submissions were redirected too, losing the visitor's inputs. The public farm product landing page only produced a local JSON/mailto and did **not** create a server-side lead.

This change reuses the **same existing** `CompanyInquiry` model, database and Django admin. It does **not** introduce a duplicate customer database, a new organization bot, a merchant gateway or a second live inbox.

## Delivered source integration
1. New farm-specific Django entry `/company/farm-economics/request/` (GET and POST): real CSRF-protected input form, kind/subject normalized on server, binding to the *existing* Django CRM.
2. Successful valid POST persists the existing CompanyInquiry and redirects to a signed receipt URL; a receipt shows only the allowed coarse stage, never name, email, phone, messages or farm economics.
3. Signed receipt verified using Django signing + secret key and a maximum age of 30 days; forgery/expiry/deleted records produce 404; receipt only allows GET and uses no-store, noindex, no-referrer. The URL does **not** prove contract, price or payment.
4. Invalid POST returns a 400 correction page with bound form values and errors and retains the farm-specific action; no 302 fake success.
5. Explicit consent, honeypot and existing Django CSRF are mandatory; a 15-minute salted-HMAC session retry guard reuses the saved lead receipt for identical submissions. **This is not global atomic de-duplication across browsers.**
6. Existing `/services/` Django template now advertises item 16 linking to the specialized intake route; the existing company-page form also asks for consent. `CompanyInquiryAdmin` displays a farm service classification, while the read-only `python manage.py farm_inquiry_pipeline --days 30` command aggregates saved ZM-FARM CRM leads by stage without disclosing PII.
7. New Django regression tests cover signed status, PII protection, consent, bot form, invalid retries, session duplicates, source-of-truth CRM, farm-specific route, and coarse status; existing six validation tests updated for 400-invalid behavior.

## Real-world boundary and testing honesty
- **89/89 source-level structural assertions** passed after correcting a false-positive checker that flagged a harmless documentation mention of the word 'email'. The final corrected check verifies the exact signed token payload contains only version and record ID. All source writes were read back from connected GitHub. This is **not** Django integration, CI, or MariaDB execution.
- **43 new Django ORM/client tests written, 0/43 executed**: 22 signed receipt, 13 farm-specific CRM intake and consent/rate-limit, 8 read-only funnel. Six older Django validation tests adapted, all six also unexecuted: **0/49 changed/new Django tests executed** because Django is unavailable locally and the production database is not accessible. No CI green assertion.
- No production code, PHP source, cPanel path, MariaDB schema, Django migration or real buyer lead was modified. No new payment/order/contract/revenue created. Source-only branch has no approved merge or deployment.
- Live `https://zomorodmelal.ir/company/` and PHP `/ask-master/` could not be independently fetched in this cycle. The actual active host implementation is UNKNOWN. The existing PHP intake must not be silently disabled or redirected.

## Safe deploy and revenue acceptance gates
1. Identify effective Passenger/cPanel and PHP routing read-only, determine which service forms the real canonical inbox; preserve all existing valid requests and entitlements.
2. Run `python manage.py check` and the actual CRM regression files against the matching Django 5.x/MariaDB test environment, validate routing order, signed token expiration and cross-browser duplicate behavior. Do not send a fake production customer lead.
3. Confirm `/company/farm-economics/request/` GET status and CSRF, POST a genuinely consented customer request only, verify one CompanyInquiry row, receipt URL, admin display and no exposure of contact details in public response.
4. Confirm PHP and Django don't compete for the *same* buyer's inquiry; use one authoritative source of truth and an explicit migration plan if changing canonical route.
5. Independently confirm outbound response policy and company mailbox receipt; never mark mailto click or draft as delivered.
6. Once buyer has consented, prepare exact commercial scope, delivery timeline and approved quote; no sample values represented as customer metrics.
7. Reconcile any eventual authorized payment against an independently confirmed merchant account; only then mark received cash and issue reviewed deliverables.
8. Only after owner-specific approval perform scoped live code release and verify rollback/monitoring. No unauthorized spending, deployment, message sending or signing.

## Real nonbinding commercial progress
A genuine supplier reply was read in the company Gmail mailbox and a **non-sent** threaded reply draft requesting written legal product documents and commercial terms was created. This supplier correspondence is a procurement opportunity, **not** a paying farm economics customer or received revenue.

## Metrics
The number of operationally received ZM-FARM leads, paid contracts, confirmed collected cash, and global company completion are presently **unverified/unknown**. Source changes are not equivalent to live company revenue.


## Resume-after-interruption source corrections
- The *existing* `CompanyInquiry.internal_note` now records a minimal server-generated `INTAKE_CONSENT_V1` marker, UTC-aware timestamp and `source=farm|company`, without adding a speculative migration or storing customer PII in the marker. It is editable administrative evidence, **not an immutable legal consent log**.
- New lead creation is bounded to 6 distinct valid submissions/hour per browser session, after the 15-minute identical-request replay check. The seventh receives HTTP 429 with Retry-After, without creating a CRM record. This is **not a global IP/account anti-spam control**.
- `farm_inquiry_pipeline` now indicates that the command reads the *configured Django database*, logs observation time and explicitly marks financial certification false. No real database scan was run during this cycle.
- No tests using a compatible Django runtime, MariaDB, actual customer data or live site were executed during the recovery turn.


## 2026-11-14 — source integrity / dedup / revenue-source correction

The first receipt branch required a *material* remediation before any release:

- The old `_inquiry_fingerprint` used default `salted_hmac`, while robust history logic requires a **64-character lowercase SHA-256 HMAC**. The code now explicitly passes `algorithm="sha256"`; otherwise all valid requests would have failed the new session-history input validation.
- The old session guard remembered only the last lead. Pattern A→B→A could create three saved rows. A **bounded, six-entry same-browser session history** now retains fingerprints and actual persisted CRM IDs for an hour, reuses existing rows for 15-minute replays and migrates the previous single-record session key. It is **not** global idempotence, account/IP throttling or protection against cross-session concurrent writes.
- A customer could submit an arbitrary `ZM-FARM` subject to the generic `/company/` form and have it counted as a farm-service lead by the old report/admin classification. A dependency-free `provenance` function now requires the exact server-written `INTAKE_CONSENT_V1` first line, `source=farm`, type `commercial` and exact farm subject. Staff notes appended on later lines do not invalidate the source marker.
- Existing CRM admin display and `farm_inquiry_pipeline` command now use the same server-provenance predicate; a defensive Python filter additionally protects against case-insensitive DB collations. Funnel reads only the relevant candidate records in bounded database iterator chunks and emits aggregate counts without buyer PII.
- **37/37 dependency-free policy tests were actually executed locally** against a byte-identical GitHub source module (Git blob `b388c020d0216aca4b9d474e7e3f8ab93526ef4e`). **61/61 source-level connector readback checks** passed. These are not a Django runtime, business delivery or an authoritative live customer receipt.
- Current branch has **51 authored new Django DB/client tests (22 receipt + 17 farm + 12 funnel) and six adapted existing tests**. **0/57 Django tests executed** in this cycle; Django isn't installed locally. The existing CI workflow may run on a main PR, but no PR/CI run or deploy was triggered automatically to avoid unreviewed workflow side effects.
- Current company Gmail inspection found **no `ZM-FARM` inquiry matches** in bounded inbound subject/content queries. It also found a **sent follow-up to supplier DarooGostar** at timestamp 2026-11-14T13:21:08 in the company Sent folder. This cycle did **not** initiate its send. A sent message is not a supplier acceptance, a farm client contract, or received funds.
- Effective `https://zomorodmelal.ir/company/`, `/services/` and PHP `/ask-master/` route behavior could not be validated from the current browsing environment. **No production changes, financial transactions or expenses have been initiated here.**

**Launch status: NO-GO for live claims until tested in the real Django/MariaDB configuration and separately authorized/deployed.** Do not call source checks 'production ready'; do not convert a public link, mail draft, or sent supplier request into collected revenue.


## Final source-integrity gate — same-day continuation

**Authoritative latest check:** **54/54** actual local stdlib policy tests passed; the exact `core/company_inquiry_policy.py` source has Git blob **`c49ae0c0eb718c8f358b9eb9f3f35cf91e77fe0a`**, independently matched by local `git hash-object`. In the GitHub branch, **82/82 read-only structural integration assertions** passed across 17 fetched files. These results supersede the earlier 37/37 and 61/61 checkpoints, not add to them.

The policy now validates/normalizes customer names and organizations, Persian/English text, line endings and bidi controls, contact email domains without changing email local-part case, and optional 7–15-digit telephone formats. Existing `CompanyInquiryForm` calls the same validated pure functions. Main company form now shows a concrete data-use disclosure and a 5000-character input bound. **No claims of external delivery, payment or runtime Django success.**

**Django tests awaiting actual execution:** 51 authored new Django test cases (22 receipt, 17 farm intake, 12 aggregate funnel), plus 10 adapted existing tests. **0/61 executed.** A 54-case portable Python suite is committed and was executed locally against the matching pure implementation, but it is not the Django ORM test environment.

**Concurrency/merge blocker discovered:** Independent open draft PR **#2306** (`fix/commercial-intake-and-ci-rootcauses-20261114`) also changes `core/company_content_views.py` and `core/templates/core/platform_page.html`, introducing contact canonicalization and a different lead-admission policy. Useful compatible normalization was carried forward into this branch, but PR #2306's older tests lack the now-mandatory `consent` field and cannot be merged/declared green blindly. Reconcile exact changes and test fixtures on a single integration branch; no merge or CI-triggering PR has been initiated here.

**Live reality:** incoming `ZM-FARM` customer inquiries remain unverified in the connected company inbox; effective live PHP/Django intake and MariaDB are not accessible for proof. Company Gmail shows a **sent supplier follow-up** to DarooGostar, but this cycle did not send it and it is not a paying farm buyer or collected income. **Do not flip payment or deployment gates.**

**Deployment readiness: NO-GO.** Requires CI/DB integration, lead routing proof, owner-scoped release approval, genuine consented customer, real order/contract and independent bank/merchant reconciliation.
