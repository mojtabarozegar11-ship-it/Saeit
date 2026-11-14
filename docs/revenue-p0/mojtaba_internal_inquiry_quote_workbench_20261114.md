# mojtaba.bot.ai — private inquiry review and nonbinding proposal workbench
2026-11-14 | source-only Draft; not deployed. Parent #2293 is itself a Draft.

## Problem identified in existing production-model source
`core.CompanyInquiry` offered `new / reviewing / approved / closed` and stored actual inbound request data. There was no owner-only qualification-to-priced-proposal workflow or durable internal draft quote event on the inspected branch. A customer inquiry is not a quote or paid contract.

## Implemented operational controls — 20 concrete source actions
1. Reuse the existing `core.CompanyInquiry` and `core.AuditLog` (no new migration or CRM).
2. Create an owner-only, paginated, first-party inbox at `/staff/command-center/sales-cases/`.
3. Create owner-only individual case detail with protected private customer context.
4. Connect the inbox from the existing single-agent staff dashboard, not a parallel bot.
5. Enforce active superuser authorization in both HTML endpoints and service layer.
6. Enforce company-host domain isolation on the owner-only workbench.
7. Require CSRF, POST and small bounded form bodies before recording any action.
8. Prevent browser/shared-cache storage and web indexing of customer case pages.
9. Show native validation and stale-version conflict errors, rather than silently losing sales inputs.
10. Permit review only for active `new` and `reviewing` cases; reject `approved` and `closed` edits.
11. Verify the existing intake consent AuditLog has exactly the current form version, statement SHA-256, narrow purpose and checked flag.
12. Bind internal review and quote service selectors to each inquiry's actual category.
13. Store explicit owner qualification `eligible / needs_details / out_of_scope` in AuditLog with real actor and outcome.
14. Move `new → reviewing`, or close out-of-scope leads, without marking a deal accepted or contacting customers.
15. Require unchanged `CompanyInquiry.updated_at` revision before a new action (optimistic concurrency).
16. Generate a one-use 128-bit random action key and perform per-case row locking plus existing-event idempotent replay.
17. Bind that idempotency key to the exact chosen qualification, scope and quote-price payload digest so changed-parameter replay fails.
18. Permit a draft price only after a current `eligible` owner review with a matching service code and unaltered inquiry.
19. Validate explicit currency, manually chosen positive Decimal unit price, bounded quantity, gross total, delivery/validity day ranges; no fabricated prices or account charges.
20. Persist a typed internal draft proposal in AuditLog with amount, price, dates and explicit `private_and_nonbinding=true`, `sent=false`, `invoice_issued=false`, `cash_collected=null`. Show a bounded real draft history to owner, and aggregate drafts to the sole `EconomicMasterAgent` summary without exposing buyer PII.

## Source artifacts / exact routes
- `core/company_quote_workflow.py`: forms, category-scoped offer choices, owner checks, consent/optimistic-version gate, `select_for_update`, internally priced quote drafts.
- `command_center/company_quote_desk.py`: owner-only 200/302/403/404/405/409/413/422 view contract.
- `command_center/templates/command_center/sales_cases.html`, `sales_case_detail.html`: usable owner review/quote screens (no actual message send button).
- `command_center/urls.py`: routes `sales-cases/`, `sales-cases/<id>/`, `sales-cases/<id>/<operation>/`.
- `command_center/templates/command_center/dashboard.html`: link only for active superuser.
- `core/company_sales_pipeline.py`: PII-free count `internal_nonbinding_quote_drafts`, emphatically not settled cash.
- `core/tests/test_mojtaba_internal_quote_workbench_20261114.py`: 69 isolated Django DB/HTTP checks.
- New scoped CI also runs 69 prior new CRM tests, 6 legacy inquiry tests, 50 existing revenue evidence tests and 4 commerce funnel tests (**198 scoped tests expected**, before verifying CI).

## Safety and commercial reality
No outbound email, SMS, newsletter, marketing contact, checkout link, payment provider call, bank/crypto action, approved binding legal offer, invoice or access grant is issued. `internal_draft` is a priced *internal estimate*, not a quote delivered to a customer. Every actual price must be chosen by the owner. Currency USD is purely an internal scenario: no lawful international payment rail or payment acceptance is implied.

The audit log event and SHA-256 values prove only **internal field consistency**, not a signature from the buyer or an independent contract. Per-case DB row locking and idempotency checks are meaningful for normal Django transaction isolation, but `AuditLog.trace_id` has no unique index; no global multi-worker exactly-once guarantee is claimed. This source does not bypass any final release/financial consent barriers. AuditLog is an internal event journal, not a legal immutable accounting ledger.

Next operational blocker: live deployment evidence for #2293 and this stacked Draft, and real consent-bearing inquiries from the owned company site, after case-specific owner authorization. Until then, signed client agreement, invoiced sale, delivered service, paid invoice, settled cash and verified profit all remain unknown.

NO-GO: Merge to main, deploy to VPS/cPanel, send real proposals or messages, start billing or spend funds without separately confirmed authorization.
