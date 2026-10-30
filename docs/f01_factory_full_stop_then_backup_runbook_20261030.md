# F-01 — Owner-approved full factory quiescence, then encrypted external recovery

Status: **RUNBOOK / OFFLINE REVIEW ONLY — NO LIVE STOP OR BACKUP PROVEN**

Scope: solely the factory's own scheduling, compute workers, private data and
snapshot/restore receipts on its VPS. Do not stop cPanel, public web sites,
payment routes, SSH relay, database services used by the web sites, or
unrelated users. No provider reboot is authorized at this phase.

## Gate 0 — Restore/rollback preparation

1. Operator with authorized **VPS console** session identifies which account,
   supervisor and timers actually own the factory. Do not assume all workers
   belong to the `githubops` user's crontab.
2. Export exact unmodified owner crontab, relevant factory-only systemd unit
   manifests/timer state and the source process/service inventory. Encrypt it
   **before** any changes with the verified owner public recovery key. Write
   it to storage **outside VPS** and read it back; verify SHA-256 and access
   by the owner. Do not publish raw cron or private keys to a public repo.
3. Confirm rollback path, source inventory, maintenance window, that sites
   remain operational, and that the external backup destination has verified
   *account-specific* free capacity, not only shared filesystem capacity.

If remote escrow cannot be **read back**: stop. Do not edit crontab.

## Gate 1 — Stop new factory intake (not websites)

1. Identify all factory entrypoints: `githubops` cron (last observed 22 factory
   entries), any factory-only systemd user/system units and timers, supervisor
   jobs, container restart policies, queue consumers, and remote automation
   triggers. Merely changing one crontab does not qualify as **100% stopped**.
2. Disable ONLY independently identified factory schedules and factory-only
   auto-restart units. Preserve unrelated cron rows byte-for-byte and
   save before/after SHA-256 with the rollback escrow.
3. Use application-specific graceful worker shutdown; prevent factory queue
   intake. Send SIGTERM only to exact, owner-verified factory executables
   after verifying PID start-time identity. Do not kill SSH/cPanel/site
   processes or arbitrary descendant trees. **Do not SIGKILL SQLite writers.**
4. If a job is blocked in D-state or can still write, record `PARTIAL_STOP`
   and do not copy live SQLite files as consistent backup.

## Gate 2 — Prove factory quiescence

From a privileged, authenticated console, run at least two independent
observations separated by at least one whole cron interval:

- No *enabled* factory cron, systemd timer, user service or supervisor
  auto-restart entry across the relevant owners.
- Zero factory writer/worker PIDs; no D-state factory tasks and no new workers
  created between snapshots; queues are not being consumed.
- DB main file and WAL remain unchanged, or an application-consistent
  snapshot API is available and independently verified.
- Public sites, cPanel and SSH remain responsive. Never infer worker
  liveness or absence merely from command-name substring counts.

Record `FULL_FACTORY_QUIESCED` only if **all** owner/other supervisor
sources are accounted for. The GitHub source-only pause script deliberately
reports `full_factory_stop_verified=false` because it cannot inspect all
supervisors and it has **not been executed**.

## Gate 3 — External encrypted recovery

- Do not use a new source-side backup file: as of 2026-10-30 the VPS has
  **0 writable bytes** for ordinary users. Take a consistent snapshot via
  verified application-native streaming or copy a completely quiesced SQLite
  database with its WAL/required sidecars; do not omit WAL or silently assume
  one file alone is current/consistent.
- Rate-limit source disk reads, preflight destination account free bytes
  (existing SQLite snapshots are about **1.396 GB each**), encrypt before
  any public GitHub artifact, and keep the private decryption key off-server.
- Upload the authenticated encrypted archive to owner-only external storage.
  Download it *back* independently, check pinned SHA-256, decrypt in isolated
  scratch, run SQLite `PRAGMA integrity_check`, count critical tables and
  check evidence timestamps and application-specific restore procedures.
- If any step fails, status is `BACKUP_UNVERIFIED`; do not delete/rotate local
  backups or reboot.

## Gate 4 — Subsequent operations (separate approval)

Only after verified external restore and stable source resources should the
owner decide whether to install the separately tested pressure guard,
restore capacity, and reboot once to apply the paid 8 GiB RAM. Compare
post-reboot memory, processes, site health and restore receipts.

**Current receipts (2026-10-30):** last read-only VPS run #40967277997
observed 205 factory command matches, 22 factory cron entries, load 128.24
on 3 CPUs, ordinary-user free 0; **not stopped**. Encrypted synthetic-only
Drive round trip passed previously; production offhost recovery **NOT_PROVEN**.
Live stop workflow creation was blocked by platform safety controls; do not
circumvent that via another tool.

Refs:
- Read-only source evidence: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40967277997
- Local scoping safety tests: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/workflows/f01-factory-stop-offline-test-20261030.yml
- Operational evidence log: https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514
