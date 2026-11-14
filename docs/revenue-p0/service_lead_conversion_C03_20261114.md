# Cycle C03 — nonbinding service inquiry and private lead follow-up (2026-11-14)
**Agent identity:** mojtaba.bot.ai, the one existing organisation manager.  
**Repository:** Saeit, stacked on C02, source-only.  
**Business aim:** measurable transition from anonymous interest to a consented, internally reviewed CompanyInquiry. No payment, sale, price, delivery, contract or external messaging is created by this change.

## Paths and ownership
- Existing Persian company services landing: \`/services/\`; six additional proposal/request CTAs are rendered from \`SERVICE_CARDS\`.
- Canonical intake path: \`/services/request/<SERVICE_CODE>/\`, one per AGR-01, RS-01, RS-02, RS-03, WEB-01, SEO-01. No per-service URL is available on MojPlayWin host. The six services are **candidate scopes** with explicit limits, not guaranteed capacity or published prices.
- Internal owner-only queue API: \`/staff/command-center/api/bot/lead-workqueue/?status=new&kind=research&page=1\`; returns queue IDs, internal admin paths and age, no customer contact fields. Staff without superuser privilege cannot access.
- Existing Django admin model remains authoritative for manual contact details, audit and stage edits (subject includes \`[SERVICE_CODE]\` prefix); admin list shows service type and age.
- Owner-run, local-only CLI: \`python manage.py mojtaba_lead_queue_readonly --status new --kind research\`; and \`python manage.py mojtaba_offer_catalog_readonly --service-code AGR-01\`.
- Existing \`EconomicMasterAgent.inspect_lead_workqueue_readonly\` delegates to the same queue-builder. Caller must enforce owner/trusted operator authorization. It creates no other agent.

## Source-implemented protections
1. A single checked consent field is mandatory for storing the customer's submitted request, with a notice version in internal note. No opt-in to marketing blasts is implied.
2. Django forms validate name/email/subject/message lengths, lowercase canonical email and preserve optional phone/organization.
3. Service code is read from a known explicit allowlist in the URL; customer POST data cannot select an arbitrary company status or \`kind\` and cannot approve a contract.
4. Only \`zomorodmelal.ir\` and \`www.zomorodmelal.ir\` are eligible company hosts. Local test hosts are accepted only when DEBUG=True. Other hosts produce 404.
5. Normal Django CSRF checks remain active; request body cap 24,576 bytes is checked without re-reading a multipart stream already consumed by CSRF middleware.
6. Submitted files, JSON API posts, invalid type and non-GET/POST methods do not create records.
7. A hidden honeypot field rejects basic automated spam; this is not a full distributed anti-abuse defense.
8. Identical requests from the same email, service and text within 15 minutes receive idempotent-like user experience using DB readback, **best-effort only**: a concurrent race can still create two rows without a unique DB constraint.
9. Success message is set only by the session after a confirmed creation or detected recent duplicate; \`?submitted=1\` cannot manufacture an acknowledgement.
10. No email, SMS, WhatsApp, contact, payment, blockchain action or customer fulfilment is performed. Saved \`CompanyInquiry.status\` starts \`new\`, never \`approved\`.
11. Only ID/age/kind/service code are returned by the owner queue; no name, email, phone, subject, message, or source text. Max 25 rows/page, pages 1..100, oldest-first, no-store and noindex.
12. Queue counts and \`status=approved\` remain internal stages only, never receipts, sales conversions, external settlements or fulfilled orders.
13. Price remains unknown until separate costs, rights, legal capacity, delivery readiness and owner case-by-case approvals are documented.

## Explicit known gaps (NO-GO)
- Two distinct public intake paths may coexist: PHP \`/ask-master/index.php?service=1\` and new Django requests. Their source-of-truth, reconciliation and duplicate prevention across systems **are not proved**. This PR does not reroute the PHP site, send external leads or claim cross-system deduplication.
- The new Django route and template are **not deployed**. Production Passenger mapping, cPanel effective source hash, host filtering, real MariaDB migrations, DNS and real delivery capacity must be independently checked.
- Best-effort duplicate suppression is not concurrency-safe and not a replacement for rate limiting, CAPTCHA or ingress security.
- Phone/email validity does not establish customer identity, valid legal consent under every applicable jurisdiction, sales qualification or marketing opt-in.
- A 200 service landing page does not prove audience reach, paid conversion, SEO indexation or live TRX settlement.
- No external contact, binding offer, invoices, refunds, payment, migration, worker restart, merge, host update or trade has been made.
- Before launch: verify privacy/legal text against applicable jurisdiction, quality assurance of pricing, delivery capacity, provenance of each SKU, and backup/restore/rollback.
- This feature relies on existing \`CompanyInquiry\` schema; no migration introduced. Final source-to-runtime equivalence remains unknown.

## Isolated QA protocol / measurement
Use an exact-commit GitHub-hosted Python 3.11 runner without privileged secrets or external network side effects. Test with isolated Django SQLite:
- 43 financial regressions (previous C02).
- 25 service policy regressions (previous C02).
- 42 previous CRM/Django regressions.
- 42 new consented service intake regressions.
- 36 new staff/owner lead-workqueue regressions.
- 10 new local operator CLI regressions.
**198 targeted automated checks total** if all pass in the last exact-head CI (43+25+42+42+36+10). Failures must be preserved in run history, not rewritten as success. Do not claim PASS until the last CI log confirms.
Django \`manage.py check\` and py_compile of changed Python modules must also pass.

## Business conversion acceptance
For a future legal live release, record independently:
1. a real incoming **consented** lead in the effective production DB,
2. manual/authorised human review of scope and lawful contact permissions,
3. an individually approved nonbinding or binding quote per policy,
4. payment verification only through independently reconciled bank/on-chain provider evidence,
5. delivery to purchaser with independent evidence and refund support,
6. actual gross margin = settled receipts − actual variable costs, not traffic or \`payment_confirmed\` event counts.
No attempt in this cycle reaches stages 3..6 in production.
