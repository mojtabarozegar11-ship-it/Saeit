# F-01 — Existing-relay VPS evidence collection (29 Oct 2026)

**Owner:** F-01. **State:** source-only, not deployed. This document is not authorization for filesystem repair, process changes, new costs or publication.

## Confirmed dated evidence

- [Authenticated guest check 40868814902](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40868814902): free available blocks 0 KiB, load average over 117. This was an observation at the run time, not a permanent state.
- [Existing full-hop proof 40869341387](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40869341387): authorized VPS and cPanel relay login succeeded intermittently.
- [Later failed pin acquisition 40871756022](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40871756022): no VPS host key retrieved; do not bypass StrictHostKeyChecking.
- Provider ticket 540436 and paid invoice 306466 cover the VPS RAM/CPU upgrade, **not** extra VPS disk. Delivery of RAM/CPU remains to be verified by the guest. No reboot or data deletion is authorized.

## Use only on the already-authorized guest

Run the companion script via the **existing pinned GitHub Actions → VPS relay** or a legitimately authenticated provider console. Do not create an alternate SSH bridge or loosen host-key pins.

```bash
python3 -B scripts/f01_vps_console_snapshot_readonly_20261029.py \
  --mount / --mount /home --mount /home/githubops/factory-runtime \
  --queue /home/githubops/factory-runtime/private/autonomous-product-cycle \
  --sqlite /VERIFIED/PRIVATE/DB/PATH \
  --backup /VERIFIED/PRIVATE/BACKUP/PATH \
  --lock /VERIFIED/PRIVATE/LOCK/PATH
```

Replace the three **placeholder paths** only after verifying them privately. The script writes **only to stdout**, never opens SSH or creates files. It returns a timestamped JSON snapshot with guest memory, filesystem, lsblk, redacted cron/worker counts and bounded metadata for queue/locks/SQLite/backup. Do not publish full private paths, raw customer data or secrets. It does not run SQLite integrity checks, verify backup restoration or establish worker health; `deployment_authorized` remains false.

## Decision gate

1. If SSH pin unavailable, **BLOCKED**. Do not substitute a different host key or pretend the guest was measured.
2. If available disk is zero, **NO-GO** for writes/worker starts. Diagnose `lsblk` versus mounted filesystem and CPU/load; no blind cleanup/resize.
3. Identify backup path and verify **off-host restoration** independently before any reversible repair.
4. Only after reserve, rollback and coordination with S-01 may the F owner consider staging repair, exact-head CI and a measured worker run. SKU879 remains excluded from autonomous production; existing stock/rights/orders are untouched.

**QA:** targeted source tests are in `tests/test_f01_vps_console_snapshot_readonly_20261029.py`. CI green alone is not VPS LIVE_VERIFIED. No Mainnet, payment or commercial approval is implied.
