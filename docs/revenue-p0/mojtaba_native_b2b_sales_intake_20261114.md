# Mojtaba.bot.ai — native B2B request capture, quote preflight and private CRM pipeline
2026-11-14 | **Draft source changes only; not deployed**.

## Commercial problem proven in source
- Zomorod Melal `/contact/` redirected to an external PHP `/ask-master/index.php?service=1` rather than the existing CompanyInquiry CRM. Whether that PHP route works in production is **not verified**.
- `/company/` had an existing HTML inquiry form and `CompanyInquiry` model, but lacked specific consent checkbox, honeypot, duplicate throttling and a per-request error view, and submitted directly to CRM.
- Status `new` was stored, but the sole `mojtaba.bot.ai` had no private summary of leads by actual status/kind and aging. The existence of this model does **not** prove any real customers have submitted it.

## 20 separate changes/controls with observable source evidence
1. Replace legacy PHP redirect on canonical `/contact/` with a native Django GET/POST form.
2. Reuse **existing** `core.CompanyInquiry` model; no shadow CRM, no migration or second bot.
3. Keep public quote capture limited to company-host domains, excluding MojPlayWin.
4. Reject non-GET/POST methods.
5. Enforce CSRF for form POSTs.
6. Require an explicit visitor consent checkbox with clear narrow purpose (no marketing consent).
7. Record a successful checkbox, fixed version and exact statement SHA-256 in `AuditLog` atomically with CRM row.
8. Do not store customer email/name/message in the consent audit event; the original inquiry stays in protected CRM.
9. Trap filled hidden honeypot to reject many automated bot submissions.
10. Bound request body to 14,000 bytes before parsing.
11. Validate name, subject and organization lengths, line breaks and control characters.
12. Validate email and canonicalize domain without claiming ownership verification.
13. Validate optional phone number while accepting no phone.
14. Validate actual message minimum/maximum length and reject excessive links.
15. Restrict inquiry kind to five existing configured CRM categories.
16. Suppress an exact duplicate email+kind+subject+message for 24 hours (best-effort DB check; concurrency not proven).
17. Throttle a single email to three accepted inquiries per hour (best-effort DB check).
18. Bring legacy `/company/` POST through **the same** validation and consent path, with visible 422 errors.
19. Persist new submissions as `status=new` only, without sending email, opening an order, marking approved or charging money; use one-time session acknowledgement and private/no-store output.
20. Add owner-only and PII-redacted status/kind/age CRM dashboard and CLI accessible from the **existing** `EconomicMasterAgent`; forbid nonowner CRM admin access and deletion.

## Operational interfaces (not live until separately deployed)
- Public Persian no-charge native form: `/contact/`.
- Existing company form, now with consent and same checks: `/company/`.
- The services page has a real quote/request CTA to the native form.
- Private owner summary: `/staff/command-center/api/bot/sales-pipeline/`.
- Management CLI: `python manage.py mojtaba_sales_pipeline_readonly`.
- Single bot method: `EconomicMasterAgent().inspect_sales_pipeline_readonly()`.
- The buyer can submit an inquiry, but a valid email address is **not** verified email ownership. No SMTP, spam campaigns, outbound message, invoice, payment or commitment is initiated.

## Evidence, privacy and hard release gates
- New `core/tests/test_native_company_sales_intake_20261114.py`: 65 isolated Django tests for core business-flow security and data retention.
- Existing `tests/test_company_inquiry_validation_20261106.py` updated to preserve rejection tests with explicit consent.
- CI additionally runs 50 prior revenue reconciliation cases and legacy funnel tests.
- Consent event proves only **server acceptance of a checked form flag**, not independently verified real visitor identity or jurisdiction-specific legal entitlement to marketing.
- Best-effort duplicate/rate limiting via DB lookup is not a globally atomic spam quota. No distributed abuse defense is claimed without live infrastructure checks.
- `inquiries_received` is a count of actual CRM rows **on the DB inspected**, not verified contacts, accepted quotations, settled revenue or customer success.
- HTTPS deployment, host routing, spam flood handling, form accessibility and performance under actual production conditions require independent verification.
- Production contact and CRM are still unverified; this Draft has no real visitor data, sales, SMTP, payment, trading or deployment side effects. No approval checks were disabled.
