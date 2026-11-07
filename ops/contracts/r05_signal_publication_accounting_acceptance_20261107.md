# R05 — Signal publication and Persian financial reporting acceptance contract
Date: 2026-11-07 | Owner: cycle 05 | State: SOURCE-ONLY / HOLD

## Scope and safety
This contract is a design artifact, not a deployment, financial instruction, live signal, or evidence of completed reporting. Do not activate trading, publish signals, send messages, alter production DB, or charge fees. No third-party destinations. Production requires verified Passenger/DB identity, recoverable independent backup and rollback, and explicit release approval.

## Independent record types
1. `signal_candidate`: internal research only; market, symbol, source data timestamp, timezone, methodology version, horizon, invalidation criteria, risk disclosure, source hash, validation outcome and reviewer.
2. `signal_publication`: immutable publication ID, candidate ID, owned-domain allowlist entry, exact page path, market, symbol, version, published_at Tehran ISO8601, content checksum, validation receipt, HTTP response and independent page readback checksum. Never publish when validation fails or page ownership is unverified. Idempotency key = SHA256(candidate ID + domain + page + version). No duplicate posts.
3. `trade_execution`: distinct execution ID, independently verified venue/order/settlement reference, executed_at, quantity, fees, and realized P&L. Research observation must never be recorded as execution.
4. `management_report` and `accounting_report`: private owner-controlled pages only, both referencing the same immutable report ID and source evidence. Report status must distinguish pending, written, readback_verified, and blocked.

## Persian report required fields
- شماره یکتا، تاریخ و ساعت تهران، کار انجام‌شده، تحلیل/سیگنال تولیدشده یا «تولید نشد»، بازار و نماد
- وب‌سایت و مسیر صفحه متعلق به مالک، اقدام انتشار، زمان و نسخه، نتیجه اعتبارسنجی و رسید بازخوانی
- معامله: «هیچ معامله‌ای انجام نشد» unless venue evidence independently verifies execution
- مبلغ، کارمزد، سود یا زیان تحقق‌یافته: «نامعلوم/فاقد سند» unless independently reconciled; never substitute zero for unknown
- خطا/مانع، شناسه فنی، اقدام بعدی، وضعیت ثبت و بازخوانی جداگانه در مدیریت و حسابداری
- terminology: observer = ناظر پژوهشی؛ payload = داده خروجی؛ rollback = بازگشت به نسخه سالم؛ settlement = تسویه قطعی

## Publication gates
1. Owned-domain and exact page authorization verified.
2. Source data fresh for declared horizon; no stale or untraceable data.
3. Signal validation deterministic and independently reviewable; risk language included; no guarantee of profit.
4. Version/content hash unique; reject duplicate or partial publication.
5. Explicit approval for public publication; absent approval: HOLD.
6. After publication, independently read back exact public page and checksum.
7. Write private management and accounting receipts atomically or record partial failure without claiming success.
8. Never interpret an HTTP 200, commit, PR, or source file as published signal or revenue.

## Current baseline — historical evidence only, not a new execution
- MojTrade VPS inventory GitHub Actions #42321531069: cron_entries=0, observer_operational_evidence=false, payload_fresh=false, orders_executed_by_audit=0.
- VPS root previously reported 98% used, 1.06 GiB free; independent restore and rollback unproven.
- cPanel Passenger/DB effective identity unproven; factory intake AttributeError unresolved.
- Signal publication: NOT VERIFIED; management/accounting write: NOT VERIFIED; executed trades: NONE VERIFIED BY AUDIT; revenue settled: UNKNOWN.
- Historical user-reported MojPlayWin purchases are separate from factory DB and must not be overwritten.

## Required acceptance evidence
A) Signed owner-controlled domain/page inventory; B) source-data and validation receipt; C) approved publication/version + independent page readback; D) two private report IDs and readbacks; E) trade and settlement reconciliation only if trades actually occur; F) independent restore and rollback receipt before any production changes.

## Accounting invariant
No transaction => write «هیچ معامله‌ای انجام نشد» and realized profit/fees as «بدون معامله؛ فاقد سند مالی جدید», not fabricated financial values. Reconcile independently verified orders, payment, delivery, fees and bank/chain settlement before recognizing revenue.
