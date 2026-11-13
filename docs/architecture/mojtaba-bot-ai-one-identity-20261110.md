# Mojtaba.bot.ai — one bot, internal modules

Owner policy (10 November 2026): there is exactly **one** public/autonomous
bot product, `Mojtaba.bot.ai`. Economic work, content, factory, games, research,
news/weather, messaging, and trading are **capabilities or internal worker
lanes**, not separately marketed bots.

## Implemented in this branch

1. Canonical Django task owner: `mojtaba-bot-ai`, named `Mojtaba.bot.ai`.
2. Economic and factory capabilities seeded onto this single owner. The seed
   does **not** grant payment, broker trade, external publication, deployment,
   or unreviewed code-promotion privileges.
3. Existing `economic-master-agent` and `moj_1ro_1` records, when present,
   require `seed_online_income_agents --apply-legacy-merge`; they are then
   deactivated and their tasks retain PKs and states under the new owner.
   The old Agent records and AuditLog evidence remain for historical review;
   the seeder is idempotent.
4. Merge fails atomically if a legacy task is running or if a pending legacy
   task cannot be mapped to one of the seeded capabilities.
5. The economic worker, autonomous planning loop, private factory bridges and
   stale-task recovery now use the canonical owner. Only one task may be running
   under that owner at a time. A stale master task is blocked for evidence
   reconciliation, never automatically replayed.
   Factory work blocked for specialist review does not starve economic planning;
   unknown queued owner work is still surfaced and must not be silently skipped.
6. `audit_agent_fleet` reports `noncanonical_active_agent_rows`, unknown
   capability mappings and `full_consolidation_attested=false` to avoid false
   100% claims.

## Canonical worker failure / retry contract (review branch)

Every failed or stale **running** `mojtaba-bot-ai` task is placed in
`blocked`, even if the normal retry budget is exhausted. A gateway may have
made a real-world change before returning an exception or losing its
acknowledgement. Therefore:

- Preserve the original `execution_id` and `attempt_count` for forensics.
- Mark `requires_review=true` and `automatic_replay_allowed=false`.
- Do not treat a blocked task as failed/no-effect or completed/revenue.
- Reconcile external receipts, payment/order IDs and the original effect before
  a separately authorized and idempotent retry or replacement.
- Retain the previous retry policy of noncanonical agents while their source
  processes are inventoried; this does not approve their continued execution.

Unit tests and the isolated PR runner prove the source-level rule only. It is
**not deployed** and requires MariaDB locking, VPS scheduler, and real delivery
verification before any production cutover. No automatic deactivation,
database deletion, paid action or external order is authorized.

## Sensitive tool execution: one-shot, payload-bound owner grants (review branch)

On the canonical `mojtaba-bot-ai` owner only, an approved task request is
**necessary but not sufficient** for a tool requiring owner approval. After
the selected `AgentTask` has a real execution token, the designated owner
must issue a short-lived `ApprovalGrant` with an exact scope:

- `action`: normalized task action
- `agent_task_id`: actual database task primary key (integer)
- `execution_id`: current TaskRuntime claim token
- `tool_code`: actual registered adapter code (not just an alias)
- `payload_sha256`: SHA-256 of the reviewed task input **excluding**
  `owner_approval_grant_id`, encoded as canonical JSON with sorted keys,
  compact separators, `ensure_ascii=True`, and no nonfinite numbers.

Store the resulting integer grant id in the task's private
`input_data.owner_approval_grant_id`. Before any handler dispatch,
`ToolGateway` locks the task, verifies that the grant's issuing approval
belongs to the exact task/action and designated owner, checks the unchanged
payload, consumes the one-time grant, and reserves the invocation in one
database transaction. Invalid/expired/used/cross-task grants **fail closed**;
the grant ID is stripped from the adapter payload.

The agent policy also treats named broker trades, withdrawals, transfers,
funding, outbound SMS/email/messages, destructive changes and legal commitments
as sensitive **regardless of an adapter's claimed low risk**. General-manager
approval names and tool-gateway approval names use one shared policy list.
Unknown external integrations must still be audited: no exact-name allowlist
can substitute for adapter-level threat modeling and genuine host-side gates.

This is a *code-review contract*, not approval to deploy, pay, withdraw, trade,
publish, rotate credentials or edit production. The registered canonical
capabilities in this branch still do not include a live deployment or broker
order adapter. Real owner sign-off, MariaDB concurrency tests, verified
rollback and host-specific runtime receipts remain mandatory.

## Approval decision and claim boundaries (review branch)

An approved request for an `AgentTask` is not interchangeable with an
approval for another action, task or project. Both **approval** and **rejection**
of an existing task now verify its normalized action and, when the task
belongs to a project, the designated project owner. A sensitive task claim
requires an approved request scoped to that exact action and project owner.
Mismatched requests fail atomically without consuming an attempt or
changing task status.

A normal owner approval may release a **clean, not-yet-executed** blocked
task. It must never requeue a `mojtaba-bot-ai` task marked
`requires_review=true` or `automatic_replay_allowed=false`. Such a
task might have already made an external change. Rejecting a new approval
also preserves the unresolved incident's blocked state and evidence, rather
than silently hiding it as cancelled. This is fail-closed until a separate,
verified reconciliation procedure is designed, approved and tested.

Synthetic regression tests assert no unauthorized dispatch or task claim.
They are not proof of MariaDB production concurrency, external delivery,
broker transactions, or revenue. Production merge/deploy is separately
gated and remains unapproved.

## Expanded root / scheduler disposition coverage (review branch)

The earlier read-only, two-host preview only classified **nine** source groups,
even though the VPS/cPanel route collector could already recognize MojTrade,
MojCoin and the separate canonical/legacy cycle coordinator entrypoints.
Absence from the nine-group report was **not** evidence of retirement.

The source ledger and read-only disposition preview now enumerate **14 logical
source groups**. The five additions cover MojTrade observer/broker integration,
MojCoin/game/token schedulers, master/coordinator cycle entrypoints, Android
Termux/Automate/SMS, and independent third-party/connected-app automations.
The first three reuse *existing* pinned host route tags. The latter two are
explicitly marked **outside VPS/cPanel observation**, not silently counted as
absent or disabled. The report retains six outstanding external inventory
scopes, rejects unknown/duplicate manifest groups, and records incomplete
coverage instead of a fictitious 100% score.

These 14 groups are logical audit categories, **not 14 confirmed live bots**.
The known Django and private PHP code roster is also not a census of all
running services. No independent scheduler has been stopped, no real agent
identity retired, no root code deleted, and no new live host attestation was
produced by this source-only change. To prove cleanup, reconcile each site,
phone, broker, game server and connector schedule against an execution receipt
and a verified canonical successor, then perform an owner-approved cutover.
Retain historical database identities and audit evidence.

## Remaining dependencies / not yet unified

- Legacy `core_research`, newsletter worker roles, content director, knowledge
  director, company activity, weather/forecasts, SMS/Termux, MojTrade,
  Moj Coin and independent factory services need inventory of their actual
  schedulers, database jobs and external adapters **before** disabling them.
- Existing migrations and older worker scripts can still create separate
  technical `Agent` rows. These are not proof of independently running AI
  products; however, one owner row alone does not prove all processes are
  consolidated. Until their call sites are migrated, active technical roles
  are dependency-review blockers.
- Old private factory receipts may mention `moj_1ro_1` as a historical issuer;
  never rewrite immutable evidence to change the label.
- Deleting historical identities would break traceability and is unnecessary
  for achieving a single active bot. They stay inactive instead.
- Running this updated seeder on a live VPS before all launch scripts are
  updated may make old scheduler invocations fail. The normal seed refuses to
  migrate pre-existing active legacy records without the explicit flag.
  **Do not deploy or run the migration in production without an audited rollout plan.**
- Database locking behavior was tested locally on SQLite, not verified against
  the production MariaDB or VPS worker concurrency.

## Verification / release gate

Run `audit_agent_fleet` read-only first; record every active noncanonical role,
pending/blocked task, and adapter. Inventory cPanel/Passenger, VPS, GitHub
Actions and the app-specific schedulers by their actual process identifiers.
For each role, implement a tested internal adapter under `Mojtaba.bot.ai`,
verify end-to-end deliveries and receipts, move safely queued tasks, disable the
old scheduler, and only then retire the technical identity. Preserve the old
record and task/audit history. A complete migration has zero unapproved
noncanonical external executors, zero unknown integration ownership, and
tested site/factory/message delivery. An HTTP 200, green unit suite, or a bot
brand change does not establish commercial readiness.

Do not infer settled sales, profitability, live broker execution, owner payment
authorization or self-modifying code promotion from these repository changes.
