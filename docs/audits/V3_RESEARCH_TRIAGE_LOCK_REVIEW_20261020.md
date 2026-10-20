# V3 private research triage overlap remediation

Run label: `v3-20261020-research-triage-lock-01` (branch-only; **not** a VPS receipt).

## Confirmed code defect

The existing `scripts/factory_research_triage.py` accepts overlapping invocations and writes private per-product plans and a status summary without a process lock. Two concurrent invocations can interleave and produce a misleading last-writer-wins status.

## Isolated change

`scripts/factory_research_triage_locked_v3.py` provides an opt-in Linux-only, nonblocking, symlink-resistant file lock around the original triage function. It does not change evidence requirements, approve research, or publish products. The existing script remains unchanged until a VPS scheduler review verifies a safe switch.

## Verification

Run `python3 -m unittest tests.test_factory_research_triage_lock_v3 tests.test_factory_research_triage -v`. Four new regression cases cover idempotency, concurrent lock denial, symlink denial, and root symlink denial. CI must pass before any merge.

## Rollout blockers

1. Identify the exact VPS cron/worker entry point and persistent private research ledger path.
2. Prove an isolated recoverable backup and rollback of the script entry point.
3. Verify all existing overlapping schedules are switched to the same locked runner; otherwise this lock protects only its own invocations.
4. Check logs for real Stage 4 capacity/budget failures; do not increase budget or bypass scientific QA without evidence.
5. No public product listing, live article, storefront, payment, cursor advance, or cPanel change is claimed by this branch.
