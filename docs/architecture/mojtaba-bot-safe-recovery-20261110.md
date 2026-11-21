# Mojtaba.bot — bounded recovery of interrupted economic work

Status: local source change on 2026-11-10. Not deployed or proven on a live VPS.

The retained `economic-master-agent` is an internal execution lane of the
single owner-facing `Mojtaba.bot`, not permission to run a second commander.
Its tasks are serialized through the shared `TaskRuntime.claim` gate. Both the
master loop and economic worker report a running task and yield rather than
dispatching a second economic task.

## Why stale work cannot simply be retried

An expired heartbeat means that completion is **unknown**; it does not prove
that the previous handler had no effects. On a stale economic task with
remaining retry budget, `TaskRuntime.recover_stale` now transitions from
`running` to `blocked`, retaining the prior execution ID for reconciliation.
It records `requires_review=true` and `automatic_replay_allowed=false` in
task output and an audit event. Repeating the recovery command does not
requeue the blocked task.
The owner-facing economic cycle reports `BRAIN_RECONCILIATION_REQUIRED`, not
an ordinary recovered/ready-to-retry result, when this boundary is reached.

An exhausted economic task remains `failed`. Existing recovery behavior of
non-economic tasks stays unchanged; no global migration or production data
modification is implied. The recovery command reports a separate `blocked`
count; blocked tasks are never reported as successfully recovered work.

Before manually authorizing a retry, an operator must reconcile the original
task's output, artifacts, any remote action receipt, and the claimed
execution ID. This change does not implement external reconciliation or
grant any automatic transaction, email, trade, payment or deployment rights.

## Evidence and limitations

- Local automated tests cover stale blocking, exhausted retry budgets,
  audit preservation, idempotent recovery calls, ordinary research recovery,
  single economic task claim, and scheduler waiting.
- The implementation uses transactional Django row locking on databases that
  support `SELECT FOR UPDATE`; multi-process MariaDB behavior must still be
  verified on a real configured database.
- The current working branch was recreated from public remote `main` at
  `666134d`. Previous unpublished local one-bot commits such as `90c101e`,
  `67010b9`, and `6abac52` are unavailable after the cloud environment
  reset. This branch reconstructs **only** the execution serialism and stale
  recovery safeguards described above, not their other features.
- No GitHub push, merge, VPS/cPanel change, broker connection, paid action,
  live trade, or outbound communication was performed.
