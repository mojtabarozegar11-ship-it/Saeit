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
