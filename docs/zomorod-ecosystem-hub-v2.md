# زمرد ملل | معماری مرکز یکپارچه اکوسیستم و دستیارها (فاز ۲)

## Scope and protection
A separate Django \`ecosystem_hub\` app extends the private \`enterprise_portal\`
draft for \`/company/office/ecosystem/\`. It **does not modify the public
website**, corporate texts or media, stores or crypto/bank gateways, or
protected independent sub-sites. PR base: \`feature/zomorod-private-erp-20261017\`.
No merge to main, no production migrations and no live deployment while
Passenger/LiteSpeed is unhealthy.

## Domain model
- BusinessUnit remains the ledger/stock isolation key. Organization expresses
  legal entity hierarchy, including intercompany boundaries. Access is via
  UnitMembership plus Django app permissions; only the superuser can grant
  cross-unit membership.
- ManagedSite tracks protected paths as metadata only. **No URL is crawled,
  overwritten or deployed by the hub.**
- WorkCenter, BillOfMaterials, MaterialRequirement, ProductionOrder:
  engineering recipe, consumption estimates, capacity and planned work; all
  remain **plan data** until authorized existing stock services record movements.
- ProcurementNeed is **not** a bank debit or supplier purchase. QualityInspection,
  MaintenanceTicket, StaffAssignment, Timesheet, ManagementRisk, PerformanceIndicator
  and ReferenceEvidence track operations with source references.
- ReviewApproval is *only a human decision record*, not a generic executor;
  accepting it does not cause payment/production/inventory mutations.
- AssistantRun is a frozen unit-specific draft analysis record.
  ProposedAutomation is a configuration proposal; \`active\` alone is **not**
  evidence of a real worker, queue or schedule being operational.

## Assistants
\`ecosystem_hub/catalog.py\` contains categorized role definitions across CEO
and strategy, accounting, treasury, trade, factory operations, crop/livestock/
greenhouse/fishery, genetics and research, personnel, office, legal and digital
website/social teams.

Only entries with \`handler\` use implemented deterministic internal read-only
queries; entries without handlers clearly say **specialist engine not connected**.
The assistant POST endpoint verifies login, office access, app permission, active
membership and selected company unit; it cannot reach the network, pay an
invoice, update stock, send an email, publish content or issue a legally binding
approval. Draft findings include evidence, calculation method and time.

## Accounting and multi-entity requirements
The original private ERP owns the accounting journals and posted stock
movements. This extension does **not** create a competing ledger. Its analysis
scopes every source query to selected units and preserves separate currencies.
Before *true consolidated financial statements* go live, implement audited
chart mappings, intercompany elimination, FX policy, legal reporting periods,
tax compliance, payroll policy, bank reconciliation and auditor review.
A dashboard showing multiple unit KPIs is not a legal financial consolidation.

## Security and rollout
- Authorize staff with *existing Django permissions* plus active UnitMembership;
  membership assignment can only be performed by owner/superuser.
- HTTPS, CSRF on assistant requests, noindex/no-store for private pages.
  Passwords, API keys and financial source files must never be in GitHub.
- No external services, autonomous bot execution, unattended real financial
  approval, account creation or public publishing.
- Run isolated CI migrations and both suites
  \`python manage.py test enterprise_portal ecosystem_hub\`.
- Never merge to production unless live \`/admin/login/\` and \`/api/health/\`
  pass (currently HTTP 503), a tested rollback exists, MFA and ingress
  rate-limiting are configured, cross-unit reporting and permission reviews pass,
  and the owner authorizes controlled release.

## Next integrations (not falsely claimed active)
1. Multi-company financial consolidation with auditor-approved entity and FX
   policies; monthly close, tax and payroll adapters.
2. Per-project BOM costing, labor and overhead capture; purchasing approval
   workflow, quality sampling and preventive maintenance scheduling.
3. SSO/MFA, centralized permission policy, confidential HR and audit retention.
4. Controlled queues/workers for allowed assistant tasks with heartbeats,
   quotas, retries, evidence logs and explicit action approval.
5. Read-only bridges to independent websites and stores; preservation of
   existing payment gateways, products and external API contracts.

## Human recommendation review workflow
The authenticated author of a draft report, if granted add_reviewapproval, can
POST to the explicit review-request route, choosing an assigned approver with
active UnitMembership(can_approve) or company superuser. This creates one
pending review record and one audit event per report; it does not alter
journals, inventory, invoices, external sites or any money transfer. CSRF,
unit scoping and assigned approver checks apply. The final decision is a
separate office record, not an execution instruction.


## Private ERP tenant isolation hardening
ERP finance, trial balance, CSV and inventory views now filter through active
UnitMembership. Django admin list/detail/add/foreign-key selectors for the
unit-linked finance, trade and inventory models similarly respect unit scope.
Journal posting and final stock confirmations verify both Django permissions and
unit membership. Company superusers retain a verified organization-wide view.
Non-unit-scoped legacy office letters/meeting records still require separate
entity-level isolation before general cross-company delegation: avoid granting
these permissions to unrelated staff until this is resolved.


## Documented manufacturing-cost scenarios
The extension adds manual, documentary MaterialPriceReference in exactly one
currency, with source evidence and review status, plus ProductionCostScenario
covering labor and overhead for a specific unit/order. The read-only costing
engine computes all BOM quantities and scrap, then requires a verified
same-currency rate for every component; missing rates produce incomplete state
and NO total. It never silently translates FX or posts inventory/accounting
transactions. An authorized user can view each scenario inside the production
module. An implemented cost-accountant assistant reads the same evidence.


## Source-permission matrix for assistants
Even after authorized membership and add_assistantrun permission, assistant
execution checks *every read permission* required by its query handler. Financial,
personnel, customer, vendor, trial-balance and material-cost source data are not
visible to generic analysts without their corresponding per-model view grants.
This is enforced in generate_report, not only by template visibility.
Approved documentary input prices are immutable after verification; corrections
must create a new source-backed price reference so past reports remain auditable.


## Explicit production MRP draft workflow
A staff member with relevant production/stock view permissions, add_procurementneed,
and active unit membership in an operational role can POST a manual request
to convert confirmed-stock shortages into **idempotent, unit-scoped, draft**
ProcurementNeed rows. Their reference is stable for each production-order /
material pair and the first creation appends an AuditEvent. Cancelled and closed
orders are blocked. Repeated POSTs do not multiply requests. No supplier,
bank, external site or confirmed inventory is mutated.


## Opt-in read-only report runner (not yet a deployed 24/7 worker)
The command \`python manage.py run_ecosystem_assistants\` has safe *preview-only*
behavior by default. It lists due internal-report runs using local calendar
daily/7-day/week/month rules and cannot mutate real financial or company data.
To authorize creation of draft-only internal reports, the server operator must
set \`ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=True\` and explicitly execute
\`python manage.py run_ecosystem_assistants --commit\`. A real cron/scheduler
must separately invoke this command; the existence of source code or an
"active" ProposedAutomation row is not evidence of scheduled 24/7 execution.
A limited batch, owner identity, active unit membership, module permissions,
source-read permissions and an atomic due-date compare-and-update are all
validated per rule. All successful actions create draft AssistantRun + AuditEvent,
without sending messages, calling any LLM/API, changing existing journals/stock,
publishing content or paying suppliers. Specialists without implemented
read-only handlers are excluded from the command rather than misrepresented.
The enable flag defaults to **False**. Test backups, security and scheduler
health before enabling it on a separate environment.

## Phase 3: management income and expense overview
The private path `/company/office/ecosystem/finance/income/` and CSV
export `/company/office/ecosystem/finance/income.csv` report posted
journal income and expense account movements over an explicitly validated
date range, with optional permitted-unit and currency filters. Access
requires both ledger-journal and account-view permissions plus ecosystem
membership. All results keep **unit and currency as separate keys**.
Income is (credit - debit) and expense (debit - credit); net result is
their difference. Negative correcting entries remain negative and draft
entries are excluded. Reports create no financial events and are
**not audited P&L financial statements**: period closing, cost of sales,
tax, depreciation, opening balances, FX and intercompany eliminations
need accountant approval.
