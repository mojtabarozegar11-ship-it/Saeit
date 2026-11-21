# F-01 → S-01 | Provider resource activation and shared release NO-GO | 2026-10-29

Owner: F-01 (guest VPS); consumer: S-01 (site/cPanel releases). Public-safe technical checkpoint; no customer or authentication secrets.

## New provider evidence
The hosting provider replied to existing support ticket **540436** on **2026-10-29 19:44 UTC**: make a backup of the service first, then restart once to apply resources. This is a **provider instruction, not evidence that the backup exists or that restart is authorized**. Their earlier correspondence required authenticated customer-portal support for resource-allocation questions; no repeat email is needed.

Last independently authenticated read-only guest evidence: [Actions #40931604373](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40931604373), observed **2026-10-29 18:35 UTC**: 3 vCPU, 4,030,372 KiB guest RAM, load 138.52, non-root-writable root space **0 bytes**, 31 D-state processes, 217 factory-name matches, 142 init-parented matches. These are time-bound observations, not a claim of current status.

## Fail-closed sequence
1. Obtain an **independently accessible off-host backup** and verify source identity, timestamp, immutable SHA-256, DB consistency, and an isolated copy/restore rehearsal. [F-owned offline SQLite rehearsal verifier](../scripts/f01_offhost_sqlite_backup_verify.py) is an integrity tool, **not** proof of off-host provenance or a whole-system restore.
2. Have the authorized VPS operator validate backup recovery, storage headroom, service restart dependencies, queued work/locks, and rollback. No production restart, cron/process kill, disk cleanup, or resource purchase is authorized by this document.
3. Only after those gates, obtain the owner's specific safety approval for a controlled maintenance window/restart; record pre/post resource allocation, SSH, cron, DB, worker and cPanel dependency checks.
4. S-01 retains exclusive authority over public site release and must independently verify site DB identity, rollback, and checkout/invoice/download. The queued private task is **ACCEPTED, NOT EXECUTED**.

## Status
F-01 off-host restore **BLOCKED**; guest worker **BLOCKED**; S-01 shared VPS release **NO_GO**. F-01 diagnostic/backup verifier **CODE**, no MERGED/DEPLOYED/LIVE_VERIFIED claim. SKU879 remains out of F production; 72/225 preserved. No payment, contract, Mainnet or site modification.
