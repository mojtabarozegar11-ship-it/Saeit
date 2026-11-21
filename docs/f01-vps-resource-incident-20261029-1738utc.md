# F-01 | VPS capacity incident evidence | 2026-10-29 17:38:41 UTC

**Scope:** Read-only guest measurement from [pinned SSH run 40922792824](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40922792824). This is a support and cross-team handoff, **not** proof of repair or permission to deploy. No customer data, credentials, process IDs, private paths or command lines are included.

| Measurement | Observed | Interpretation |
|---|---:|---|
| Root filesystem total | 42,184,536,064 bytes | 40 GiB class virtual disk |
| Free blocks (including reserved) | 2,159,091,712 bytes | **Not** equal to writable non-root capacity |
| Available to non-root | **0 bytes** | Factory/backup/rollback writes must remain blocked |
| Memory total | 4,030,372 KiB | About 3.84 GiB guest-reported; verify against paid plan independently |
| vCPU / 1-minute load | 3 / 154.34 | Severe scheduling and/or uninterruptible I/O pressure |
| Process states (sample) | 100 D, 44 I, 1 R, 354 S | High D-state pressure; do not equate with CPU-only contention |
| Factory/master-agent name matches | 299 / 499 scanned | **Not** worker-health proof |
| Largest shared parent | 142 matches; parent is init | Orphaned/reparented fanout; original spawning mechanism **not established** |
| Factory cron entries | 22 total, 3 every minute | Correlation with process fanout; **not proof** of causation |
| Queue entries | at least 69 | Inventory count only, no execution or completion proof |
| SSH | Authenticated on attempt 3 after two banner timeouts | Intermittent connectivity remains |

## Required next safe operations

1. Hosting provider: confirm the effective guest RAM allocation and any pending paid-plan resize for ticket **540436**; do not purchase additional capacity or reboot without owner approval.
2. Provider or authorized operator: diagnose ext4 reserved blocks, actual I/O saturation, and the source of init-parented processes without deleting files, killing processes or changing cron blindly.
3. F-01: obtain a fresh pinned-SSH snapshot with aggregate age buckets and read-only lock/SQLite/backup path evidence using pre-approved paths, never printing those paths.
4. F-01: independently demonstrate **off-host** backup restoration and staging rollback before any factory repair, worker restart, merge or deployment.
5. S-01/G-01: treat this incident as a shared-VPS **NO_GO** for deployment until the release owner independently verifies capacity, backup, effective DB and rollback.

**Stage:** read-only evidence = LIVE OBSERVATION VERIFIED; worker restore = BLOCKED; factory fix = CODE; production deployment = NOT DONE; revenue = NOT VERIFIED. SKU879 remains excluded from factory processing; SKU72 and SKU225 must not be impacted.
