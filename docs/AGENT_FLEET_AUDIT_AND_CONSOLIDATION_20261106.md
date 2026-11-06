# Agent fleet: source audit and controlled consolidation

Date: 2026-11-06. Repository: `Saeit` (the inspected `main` source, not an
attestation of the current VPS/cPanel process image).

## Observed execution topology

| Concern | Observed implementation | Evidence limit |
| --- | --- | --- |
| Economic coordination | `economic-master-agent`, `online_income_cycle`, `autonomous_master_loop`, `run_economic_worker` | Registered/queued is not dispatched or paid |
| Private factory | `moj_1ro_1`, `factory_native_review`, `factory_f41_private_build` | Separate VPS and factory gates; no shared economic worker permission |
| Knowledge content | `knowledge_agent_cycle` plus specialist knowledge models | Cycle queues a run; downstream execution needs separate verification |
| Weather/newsroom | `weather_agent_cycle`, `company_activity_agent_cycle` | Data/publication or review records do not prove customer demand |
| Agent governance | `AgentRegistry`, `TaskRuntime`, `ToolGateway`, `ApprovalRequest`, audit log | Approval, capability, task and tool must agree at the last execution boundary |
| Legacy newsletter identities | `consolidate_legacy_agents` | Retirement only after successor receipts and dependency checks |

There are multiple task ledgers. `AgentTask` is not the complete activity
history for the knowledge, newsletter, company-activity, factory and external
workers. Do not mass-retire identities for lack of one ledger's receipts.

## Findings and implemented controls

1. **Authorization mismatch:** a running low-risk research task could invoke a
   different registered tool if a runner supplied its code. An unrelated
   `ApprovalRequest` could satisfy the tool-level check. The gateway now binds
   the tool to the task's active capability, checks policy drift and agent
   activation again, and requires an explicitly declared tool alias. Approval
   must be for the actual task action. Higher-risk sensitive tools require a
   task planned at the corresponding risk rather than a post-hoc alias.
2. **Unobservable queue health:** the existing legacy consolidation preview
   proves only a limited set of dependencies. The new read-only
   `audit_agent_fleet` command exposes inactive pending work, known-executor
   mismatches, stale running tasks, recent Django task/newsletter receipts and
   conservative retirement candidates; it cannot certify live cron or cash.
3. **Internal activity is not revenue:** `income_market_research` measures
   inventory; `income_offer_design` writes an inactive draft; `income_mvp_build`
   creates a private asset; `income_revenue_verify` deliberately withholds
   externally unconfirmed settlement. Treat these as bounded internal outputs,
   not sales or independent market validation.
4. **Executor families remain separated:** the economic master allows only
   economic handlers, and factory-specific handlers stay outside its normal
   worker selector. Do not merge their deployment paths or grant financial
   authority through a tool name change.

## Safe operational sequence (no automatic external writes)

1. Run `python manage.py audit_agent_fleet` against an independently verified,
   current runtime and retain the timestamped JSON. This is read-only.
2. Run `python manage.py consolidate_legacy_agents` without `--apply`; compare
   every proposed successor and required content type with live receipts.
3. Resolve `inactive_agent_has_pending_tasks`, stale tasks and known-executor
   unmapped tasks individually; preserve every historical row and audit trail.
4. Verify *separately* the scheduled process identity, runtime source hash,
   database identity, connector permissions, kill switches and real output
   receipts for each specialized family. No source-only test can establish this.
5. Only then apply evidenced safe legacy retirement with
   `consolidate_legacy_agents --apply`. Do not activate purchases, trading,
   outbound email, public publication or factory rollout as a side effect.
6. Measure one real end-to-end customer action and externally reconciled
   settlement before counting an agent as revenue-producing. Treat reports and
   internal database changes as intermediate milestones.

## Validation

Focused Django tests cover cross-capability denials, revoked/inactive agent
checks, explicit adapter aliases, risk-policy drift, stale execution identity,
worker lifecycle and audit read-only behavior. Tests exercise isolated
databases only. They do not establish production readiness or authorize deploy.
