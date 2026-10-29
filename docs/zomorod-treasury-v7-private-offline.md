# Zomorod Melal | Offline Treasury Approval Control (V7)

## Verified code scope

This is a private, isolated **internal request and approval** subsystem, not a bank integration, cash management package or evidence of actual payment.
- Propose a payable/receivable transaction in integer minor units for IRR, USD, EUR or AED.
- Prevent duplicate request keys; reject inconsistent replay.
- Create and submit draft, approve/reject by another authorized admin, cancel draft.
- Preserve immutable audit history and prohibit editing amounts/references or deleting requests.
- Test direct SQL attempts to self-approve, mutate approved amounts or purge history.
- Support authenticated private ERP routes with CSRF and role validation; render escaped user-provided fields.
- No transaction settlement, money transfer, invoice posting, accounting journal or external communication.
- Installed only as source code in an isolated GitHub development branch. The live cPanel app.php is not overwritten.

## Offline verification

GitHub Actions: `.github/workflows/zomorod-treasury-offline-ci.yml` runs PHP 8.2 and 8.3 with PDO_SQLite. In each version, run:
- `scripts/zomorod_treasury_synthetic_qa.php`
- `scripts/zomorod_payroll_control_synthetic_qa.php`
- `scripts/zomorod_workflow_desk_synthetic_qa.php`
- `scripts/zomorod_workflow_web_synthetic_qa.py` (real PHP login/CSRF and independent review using isolated synthetic users).

## Engineering and deployment blockers

The V6 offline bundle in the conversation contains additional industry, finance and period-lock code that has **not yet been synchronized to this GitHub branch**. V7 treasury CI proves the above-listed files only, not full V6 or overall ERP readiness.

Before production approval: reconcile existing host-only PHP extensions, test true restored backups, validate role security against live dependencies, implement legal payroll/tax/financial requirements, verify industry/LIMS/MES integrations and obtain owner acceptance. No recurring automation is permitted before full system acceptance.
