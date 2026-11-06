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

## Read-only production evidence already available

The separately executed VPS workflow
[`42198456618`](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/42198456618)
completed at approximately 09:54 UTC on 2026-11-06. It inspected the scoped
VPS Django database **without changing it**. It found:

- 20 registered active Django agent identities and 240 open tasks.
- 145 queued factory research/validation tasks and 95 blocked research tasks.
  Of the queued tasks, 33 research tasks reference an active run with no
  Django Product; 112 validation tasks reference active runs whose Products
  are inactive. Three queued research tasks had exhausted attempt budgets.
- Four legacy newsletter identities were preliminary *review candidates*;
  their successors' live coverage and external integrations were not proven.
- In the trailing 30 days, 5,502 `income_profit_optimize` tasks were marked
  completed, nearly all recording internal catalog baselines. In this *scoped
  database*, active Django Products, Orders, payment events and settlement
  candidates all counted zero. This does not characterize separately hosted
  MojPlayWin orders or the independent factory's private product ledger.

Do not bulk-execute the 145 tasks: active `FactoryRun` flags did **not** prove
one authorized native active product. Binding, recipe and single-product
checks are mandatory. The historical profit-baseline count is not 5,502
independent gains and does not certify customer revenue.

The later read-only VPS audit
[`42235124206`](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/42235124206)
identified **zero** `online_income_cycle` or `autonomous_master_loop` processes,
no economic-worker user cron entry, four factory-related processes, and an
installed native factory gateway ABI distinct from the source economic runner.
It did not verify an operative bridge from the cPanel customer-inquiry database
to the VPS Django database. These are activation blockers, not sales outcomes.

## Agreed organization: four executive engines, five domains

The owner-approved conceptual organization is one central commander and three
specialized engines: evolution/repair, `MojTrade AI`, and content/product.
Weather, news and market data are shared services, **not** automatically
additional privileged agents. The five organizational domains are factory,
Zomorod Melal, MojPlayWin, shared services and central command. This policy is
not permission to automatically retire 20 existing Django identities or merge
their incompatible financial/factory executors.

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
   mismatches, stale running tasks, queued tasks older than a day, exhausted
   retry budgets, repeated internal profit baselines, recent receipts,
   exact mission/capability overlap and conservative retirement candidates;
   it cannot certify live cron or cash. Even an exact role overlap is a
   **review candidate**, not permission to remove an external integration.
3. **Internal activity is not revenue:** `income_market_research` measures
   inventory; `income_offer_design` writes an inactive draft; `income_mvp_build`
   creates a private asset; `income_revenue_verify` deliberately withholds
   externally unconfirmed settlement. Treat these as bounded internal outputs,
   not sales or independent market validation.
4. **Executor families remain separated:** the economic master allows only
   economic handlers, and factory-specific handlers stay outside its normal
   worker selector. Do not merge their deployment paths or grant financial
   authority through a tool name change.
5. **Revoked-grant queue starvation:** economic dispatch now requires a
   currently active `AgentCapability` on the assigned agent, in addition to
   an exact task action/capability match and a registered tool. Tasks without
   this grant remain queued, preserve attempt counts, and are reported as
   requiring policy review; they do not block later authorized tasks.
   `online_income_cycle` no longer calls an unroutable queued task ongoing
   productive work. Exhausted task retry budgets are also excluded from
   dispatch and reported for review instead of attempted every cycle. This
   does not silently regrant a revoked capability or reset retry budgets.
6. **Single-task failure starvation:** bounded `--drain` processing can advance
   to later eligible tasks after a failed task, without retrying an ID twice
   in the same invocation. Failures remain visible via nonzero exit status;
   handler error text is not printed in shared logs. Master-loop replanning
   also records a safe error type instead of persisting raw exception text.
7. **Seeder revocation bypass:** repeated execution of the initial seeder no
   longer reactivates manually disabled agents/capabilities, resets owner risk
   policy, or silently restores removed grants. Existing factory identity and
   permissions remain untouched. Newly created internal capabilities are
   assigned to the economic master only when created by the trusted seeder.
8. **Real inbound demand handoff:** the existing economic master can now
   discover a persisted `CompanyInquiry` of commercial/project/technology type,
   create one idempotent `income_inbound_lead_review` task, and mark a new
   inquiry as `reviewing` with a privacy-preserving internal note. No customer
   name, email, message or payment claim is copied into the task evidence;
   there is no outbound contact, public publication or payment. The record is
   an inquiry, **not** evidence of verified demand, a quote, a sale or cash.
9. **Factory ABI-safe economic execution:** a dedicated
   `EconomicGateway`/`EconomicWorkerRunner` binds every action to the one
   economic master, its active capability, its execution identity and current
   risk policy. It requires concrete internal evidence and rejects any nonzero
   execution cost. The existing `build_economic_gateway` and shared factory
   `ToolGateway`/`WorkerRunner` are left intact for factory native adapters.
   The VPS master activation bundle no longer overwrites
   `core/tool_gateway.py`, `core/worker_runner.py` or `core/task_runtime.py`,
   and checks their hashes unchanged before finishing. A separate preflight
   verifies the installed task lifecycle signature; failed initial cycle
   restores prior modules and cron rather than claiming activation. This is
   a deployment-safety improvement, not evidence that a live economic scheduler
   has been installed or produces revenue.

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
worker lifecycle, revoked-grant queue behavior, and audit read-only behavior. Tests exercise isolated
databases only. They do not establish production readiness or authorize deploy.
