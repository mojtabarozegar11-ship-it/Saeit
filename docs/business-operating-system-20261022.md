# Zomorod + MojPlayWin — Evidence-led Business Operating System

**Release boundary:** this is a first, additive management-control slice, not a
claim that the factory, stores, financial rails, or websites are autonomous.
It does not publish, deploy, spend, trade, issue tokens, or bypass approvals.

## Scientific management contract

- **PDCA / OODA:** observe timestamped facts, prioritize a testable constraint,
  perform only authorized reversible work, verify the outcome, then replan.
- **Theory of Constraints:** improve the constraint limiting verified customer
  outcomes and settled cash, not the count of tools, lines, agents or drafts.
- **Lean validation:** document buyer, problem, alternative, actual demand,
  delivery promise, price and cost *before* calling a product commercially ready.
- **Unit economics:** reconcile **settled** cash by currency; subtract attributable
  fulfillment, acquiring, provider and refund costs. Orders are not revenue.
- **Evidence policy:** unknown != zero != verified. An internal inventory count
  cannot independently prove demand, competitive fit or customer acceptance.

## Implemented in this change

1. `core.business_management.review_business`: deterministic priority review;
   every observation needs a source and timestamp, missing adapters stay unknown.
2. `python manage.py business_operating_review`: JSON report for local Django
   tasks, products, orders and approvals. Does not infer VPS/CPANEL/web health.
3. `python manage.py business_operating_review --record`: optional audit receipt;
   no external side effects. Do **not** schedule every 10 seconds before
   setting cost, retention and freshness limits.
   Staff can also read the non-cached JSON view at
   `/staff/command-center/api/business-operating/` (after an authorized deployment).
4. Blocked economic tasks are distinct from queued/running tasks. A blocked
   permission gate emits `BRAIN_PENDING_APPROVAL` and is not duplicated or
   counted as a work item that can proceed automatically.
5. Python policy tests and Django command tests protect these distinctions.

## Operational data contracts to connect next

| Department | Required authoritative facts | Acceptance gate |
| --- | --- | --- |
| Strategy | Named buyer, independent demand signals, competitor sources | Attribution, sample and date |
| Factory | Order ID, stage transition, build hash, specialist/device result, repair outcome | Independently reproducible deliverable |
| Websites | Site URL, HTTP/UX probes, origin revision, timestamps | Staging then production smoke check |
| Commerce | Offer, session, order, fulfilled download/customer outcome | End-to-end test order |
| Payments | Network, exact address, transaction ID, confirmations, settled ledger | Independent on-chain/provider reconciliation |
| Finance | Same-currency collected cash, refunds and attributable costs | Positive contribution after reconciliation |
| Security/governance | Scoped permissions, incidents, approvals and audit | Risk review and exact owner grant when required |

## Deployment and automation sequence

1. Run PR CI, review code and merge **without** automatic website deployment.
2. Stage on the existing VPS, using GitHub Actions only as the approved SSH
   transport. Back up the active Django database/config; never expose secrets.
3. Run the read-only command against the correct database and compare sample
   counts with direct source queries. Check other sites separately.
4. Connect signed/dated VPS factory receipts, cPanel health and payment
   reconciliation *as read-only adapters* before making quantitative claims.
5. Put one supervised operating-review run on a 90-second cadence; persist
   diagnostics at a much lower rate, with locking, quotas and alert dedupe.
6. Permit low-risk remediation only via the existing capabilities, task runtime,
   idempotency keys, rollback and pre/postcondition checks. Keep external
   publication, legal commitments, irreversible edits and money behind grants.
7. Accept autonomy only after stage-by-stage shadow runs, fault injection,
   restoration drills and real delivery/customer acceptance evidence.

## Actual success scorecard (not currently established)

- Accepted, independently usable outputs / started factory orders.
- Median age and failure/repair rate per factory stage.
- Verified checkout-to-delivery conversion (each site separately).
- Settled cash, refunds, net contribution and cash burn **by currency**.
- Incident recovery time and false-positive/duplicate-action rate.
- Owner time spent only on decisions requiring human authority.

An internally generated report, successful CI job, created token, product
metadata flag or simulated order **does not** itself count as commercial success.

## 2026-10-22 private decision and bounded monitoring extension

- A separate private decision file is written on each server, with strict
  origin and freshness checks; missing cPanel data on the VPS is unknown.
- A real active `moj_1ro_1` agent identity is checked in the existing
  factory Django runtime without creating extra AgentTasks or capabilities.
- Once both scheduled commands pass a live read-only preflight, a uniquely
  marked cron entry may run every 15 minutes on each host. It changes only
  private reports, leaves a recoverable crontab backup, and is removed by
  `bash scripts/business_os_private_cron.sh --uninstall vps|cpanel` from
  that exact staged release.
- This is distributed autonomous observation/diagnosis, **not** a verified
  cPanel-to-VPS private data transport, a payment settlement adapter, a
  master task execution capability, or independently accepted production.
- No cross-server data or financial observations are copied through CI.
  Those integrations remain blocked pending tested authenticated transport,
  reconciliation evidence and a dedicated scoped master capability.
