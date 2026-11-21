# Zomorod Melal — ERP development handoff and release gates

**Status:** DEVELOPMENT HANDOFF ONLY. Not approved for production installation, and not an assertion of 100% ERP completion.

## What is in this package
- The isolated Persian management panel's repository version.
- Basic double-entry journal, invoices, parties, inventory quantities, personnel and projects.
- Executive insights; owner command center; task quality review; read-only operations planner.
- A new private workflow desk for purchasing requests, proposed contracts, leave, administration, maintenance, projects and research.
- A CLI-only signed task receiver. It does not provide an authenticated ChatGPT signing or transport channel.
- Synthetic test suites and a deterministic SHA-256 package manifest.

## What is NOT included
- Production databases, keys, password receipts, SSH credentials, environment files, user sessions or payments.
- Live host-only private extensions `site_agents.php` and `site_store.php`. These must be inventoried and reconciled before any deployment.
- Complete statutory accounting, tax, payroll, cash management, procurement commitments or external e-signature.
- Real agricultural operations, LIMS, genetics, livestock, manufacturing/MES and maintenance integrations.
- A fully autonomous master agent, actual ChatGPT-to-private-signing transport or any recurring one-hour task.

## Minimal safe deployment sequence
1. Confirm cPanel and VPS SSH identity using **already trusted** pinned keys, not a new unverified host key.
2. Identify the exact effective live PHP entrypoint and database. Read the actual private `app.php`; never replace the live file wholesale with this repository's copy.
3. Read current private extensions, record hashes and PHP compatibility, and enumerate their dependencies.
4. Take a consistent online SQLite backup using the SQLite backup API; verify an offline restore, table integrity and foreign keys. Safely back up the private PHP code and configuration.
5. Deploy a **staged** module to a separate private directory first. Reconcile only surgical, unique route/navigation anchors; preserve independent live extensions.
6. Run PHP lint, synthetic tests, authenticated owner/admin/manager/accountant/viewer regression, CSRF and source-vs-live drift checks.
7. For high-impact requests, ensure the requester cannot approve their own transaction. Approval in the workflow desk is **internal only**: never treat it as evidence of bank payment or a signed contract.
8. Run independent public unauthenticated access checks. A visit to the private route must show login only. Verify no source files or private DBs are reachable from public_html.
9. Audit actual accounting balances, payment constraints, backup restore success, logging/retention and per-role access. Only then consider owner-supervised release.
10. On any failed gate, restore the specific prior files and check the database has not been modified. Never silently weaken access gates.

## Required acceptance before declaring company-wide readiness

| Domain | Gate |
| --- | --- |
| Accounting | Complete journal, closing periods, reporting, tax, reconciliation, corrective entries, ledger audit and independent balance tests |
| Treasury | Internal cash controls, bank reconciliation, approved payment workflows and authorized bank integration |
| HR | Records, leave, permissions, attendance, payroll validation, privacy and audit |
| Procurement | RFQ, approved orders, receiving, invoices, returns, supplier controls |
| Contracts & correspondence | Internal approvals, controlled templates, retention, legally valid signatures when necessary |
| Projects & production | Costs, milestones, assets, capacity, inventory valuation and acceptance |
| Agricultural industry | Crop, land, greenhouse, lab, genetics, livestock and manufacturing flows with validated data |
| Intelligence | Agent scopes, authenticated transport, durable work queue, evidence-based outcomes, no unsafe autonomous spending |
| Security & continuity | MFA, permission matrix, tested disaster recovery, incident response, logging, no secret leakage |
| Transfer | Immutable bundle hashes, dependency lock, dry-run, staging verification, source/live reconciliation, explicit owner signoff |

## Release rule
If **any** gate above is absent or unverified, the package must remain labeled DEVELOPMENT / NOT PRODUCTION READY. Do not schedule the one-hour agent until the owner reauthorizes it after end-to-end acceptance. Do not expose a signing key or an administrative command endpoint publicly.
