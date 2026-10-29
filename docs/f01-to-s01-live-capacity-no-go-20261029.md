# F-01 → S-01: measured VPS capacity NO-GO handoff — 2026-10-29

**Owners:** F-01 infrastructure; S-01 site releases. **Status:** FILE DELIVERED / S adoption READY_FOR_REVIEW; **production change: none**.

## Fresh authenticated evidence

[Existing pinned GitHub Actions→VPS guest run #40912524551](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40912524551), guest timestamp **2026-10-29 16:34:10 UTC**; SSH host fingerprint verified and login succeeded on attempt **2/5**. Read-only remote Python script, no guest writes.

| Observation | Guest value | Interpretation |
|---|---:|---|
| CPU count | 3 | Not evidence of completed paid upgrade |
| MemTotal | 4,030,372 KiB | Approximately 3.84 GiB; paid 8GB not reflected in guest |
| MemAvailable | 2,465,044 KiB | Snapshot only; not durable headroom |
| Load average (1/5/15m) | 134.65 / 134.07 / 134.48 | Severe process pressure versus 3 vCPUs |
| Root filesystem | 42,184,536,064 bytes | ~39.29 GiB ext4; not 30GB cPanel quota |
| **Available to nonroot** | **0 bytes** | **NO-GO for any write, worker activation, backup or deployment** |
| Filesystem free including reserved blocks | 2,159,210,496 bytes | Reserved blocks are **not** application write headroom |
| Free inodes | 2,212,611 | Byte availability, not inode count, is limiting |
| Active cron entries | 24 (22 factory-name matches) | Cron listing alone does not prove tick execution |
| Process name matches | 234 / 427 scanned | Not 234 healthy workers; possible process storm |
| Factory queue directory entries | 69 | Queue metadata only; no job completion proof |
| SQLite / off-host restore | Not verified | Hard release gate remains closed |

**Immediate S-01 release boundary:** Do not stage or deploy checkout, game, or site updates against this shared VPS on the basis of green CI or successful SSH alone. Keep existing site layout and production untouched. No crontab, process, disk, queue, DB or payment mutation is authorized by this handoff.

**F-01 next:** Collect aggregate-only process state/parent/CPU evidence via the same pinned read-only workflow; establish actual root disk topology and verify independent off-host backup restoration before any reversible remediation. Provider ticket **540436** concerns paid RAM/CPU delivery and SSH stability; disk capacity is separate. No paid upgrade or destructive cleanup is authorized.

**S-01 next:** Re-evaluate backup/rollback and effective Passenger DB only after F records a fresh safe write margin and working guest; S alone owns site release.

## Second authenticated guest confirmation — 16:38:26 UTC

[Pinned read-only process-pressure run #40913117141](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40913117141) completed successfully after SSH authentication on attempt 4/5. Nonroot available disk remained **0 bytes**. Load increased to **142.19 / 138.31 / 135.90** with **3 vCPU**; guest RAM still **4,030,372 KiB**. Of 482 scanned PIDs, 275 matched factory/master-agent names: 147 shell, 65 Python, 63 other executable categories; 60 runnable (R), 4 uninterruptible (D); one parent had up to **142** matching children. This indicates severe process fanout, but no parent command or actual worker health was verified. S release remains **NO-GO**. No remote writes, process termination, cron changes, or backup operations occurred.
