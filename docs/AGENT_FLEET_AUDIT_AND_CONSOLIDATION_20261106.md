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
   mismatches, stale running tasks, recent Django task/newsletter receipts,
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


## 2026-11-13: only one operational bot — no fallback to old task owners

The owner has required the complete end-state: **`mojtaba.bot.ai` is
the only operational bot**. All other agent identities must become
internal, non-executable modules under `mojtaba-bot-ai` or be retired
after all dependencies and external process ownership are verified.
Historical Agent rows with foreign-key references are retained as
**inactive provenance**, not treated as running robots. Destructive SQL
deletions are NOT an acceptable shortcut for FK preservation.

**Source-side enforcement introduced on the review branch:**

1. `AgentRegistry.resolve` has **no noncanonical fallback whatsoever**.
   Newly planned tasks for any registered capability — including unknown or
   otherwise unmapped specialist actions — must be owned by the active
   canonical Agent row with the exact capability association. When that
   association is missing, planning is denied; old agents cannot win by ID,
   lower risk or mission. Existing historical tasks are not relabelled.
2. `newsletter_engine.create_draft` refuses any
   `agent_code != mojtaba-bot-ai`, including direct calls from an old
   newsletter cron. This does not delete, retire or silently reassign
   pre-existing scheduled/publication records.
3. `consolidate_legacy_agents` now explicitly inventories **nine known
   retireable identities**, including content-director, content-research,
   knowledge-content-director and company-activity-intelligence.
   The content/report successors require actual recent canonical
   published content with editorial-quality receipt. Knowledge
   retirement instead requires a recent canonical completed matching
   `AgentTask` + `KnowledgeAgentRun` + nonempty book, **and** an
   independently reviewed live handoff. All nine continue to require an
   exact scoped owner approval grant per identity and a fresh live receipt.
4. The two former *economic/factory* executor identities follow the existing
   separate approved `seed_online_income_agents --apply-legacy-merge`
   route. The currently protected economic/factory identities must **not**
   be declared deleted or consolidated merely because canonical ownership
   exists in source.

**Completion gates, all required simultaneously:** no active alternative
Agent identity in the live database; no unreconciled pending tasks or
newsletter distributions; all specialist capabilities mapped to the
canonical owner; every VPS/cPanel/systemd/cron/PHP/remote scheduler and
mobile/connector-triggered legacy process accounted for and stopped or
rerouted; one verified canonical running executor; exact owner-approved
cutover and rollback evidence; historical ledgers preserved; no duplicate
orders/publications across the cutover.

**Current limitation:** this branch implements source policy and guarded
retirement routes only. It does not itself run a live database migration,
stop VPS/cPanel processes, edit remote cron jobs, disable external accounts,
or delete files on live hosts. A successful offline test does NOT mean the
completion gates above have been met. Live consolidation percentage remains
**unknown**, never 100% by inference.


## 2026-11-13: legacy running-task and recovery lifecycle containment

The earlier source change stopped **new** task claims by noncanonical
agents and blocked their ToolGateway calls, but a previously running task
could still be heartbeated or directly marked complete, and a failed or
stale legacy task could automatically return to the queue. Those paths
undermine the "one bot" requirement and risk duplicate external effects.

**The source runtime now fails closed at all four lifecycle boundaries:**

- `claim()`: noncanonical queued tasks cannot receive an execution token.
- `heartbeat()`: old execution tokens cannot prolong an independent
  runtime; task status/timestamp are left unchanged.
- `complete()`: old worker callbacks cannot mark work complete after
  cutover, even with a matching old token. No cost or success receipt is
  recorded through this path.
- `fail()` and `recover_stale()`: **all** tasks, including old-agent
  work, become `blocked`, not `queued` or automatically `failed`.
  Original owner, prior execution token, attempt budget and audit history
  are retained. Old-agent outputs explicitly identify
  `legacy_agent_code`, `migration_target=mojtaba-bot-ai`,
  `requires_review=true` and `automatic_replay_allowed=false`.

The general recovery scheduler may now safely inventory historical stale
tasks because recovering them quarantines rather than re-dispatches.
Repeated stale recovery is rejected after the first transition to
`blocked`; nothing is duplicated. The CI now exercises the management
command and direct TaskRuntime callback paths.

**This deliberately DOES NOT** stop old systemd processes, cron entries,
cPanel jobs or broker terminals on VPS, change already published external
effects, or migrate old pending work without a verified receipt. It is a
source-level cutover barrier; real runtime closure requires inspecting and
disabling every external launcher, then reconciling queued, running and
blocked tasks to the sole canonical Agent. The PR remains Draft until
those facts are confirmed. No file, historic task, approval or financial
record should be deleted to fake a zero-legacy count.
