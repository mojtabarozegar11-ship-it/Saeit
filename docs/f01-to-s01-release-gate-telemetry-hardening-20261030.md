# F-01 → S-01 | Independent release-gate hardening handoff
2026-10-29 22:40 UTC · F-owned branch only · no S source or live-site change

## Verified resource evidence (timestamped, not a current-state assertion)
Read-only pinned SSH workflow [#40958918596](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40958918596), guest observed **2026-10-29 21:37:46 UTC**:
- Non-root available bytes on root mount: **0**; free bytes including ext4 privileged reserve: **2,158,710,784**.
- **3 vCPU**, 1-minute load **133.75**, guest RAM **4,030,372 KiB**.
- **279** factory-name matches in the bounded worker scan; **142** init-parented shell-category matches; 3 factory-related per-minute cron entries. This is a correlation, **not proof cron is the process parent**.
- **1** D-state process in this snapshot (versus 31 at 18:35 UTC); recovery is **not** established, because load and worker-writable disk remain critical.
- Queue count **69**; successful process execution, backup integrity and autonomous worker output **not verified**.

## Independently prepared F-owned fix
[Release preflight](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/f01/vps-readonly-console-snapshot-20261029/scripts/f01_s01_release_preflight_20261029.py) now fails closed on malformed nested telemetry, Boolean integer aliases and NaN/infinite CPU loads. [Adversarial tests](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/f01/vps-readonly-console-snapshot-20261029/tests/test_f01_s01_release_preflight_20261029.py) added; [exact-head Actions](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40967277997) pending at handoff, not claimed green.

## S adoption gate
S-01 must independently inspect the change, confirm CI and source revision, identify the cPanel production DB, and prove an off-host restore + rollback before any staging write, merge, deploy, or reboot. F does not own checkout or public site changes. **RELEASE=NO_GO; LIVE_VERIFIED=NO.**
