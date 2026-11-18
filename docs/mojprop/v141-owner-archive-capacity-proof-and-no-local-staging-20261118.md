# MOJ-PROP-01: actual VPS backup archives and no-local-staging decision

**18 Nov 2026 · SOURCE/READONLY · NO DATA PURGE · NO COST · NO DEPLOY · NO TRX RECEIVED**

## Authenticated source evidence

The self-hosted `factory-vps` runner `githubrunner` entered `githubops@127.0.0.1` by existing OWNER SSH private-key secret and exact preapproved host-key fingerprint, with no sudo or chmod. [Actual successful GitHub Actions #44218536999](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44218536999) classified 18 immediate entries in the owner-only `~/.private-mojplaywin-offhost-backups`, **without reading ciphertext, manifests, key bytes, individual filenames or customer records**.

| Actual direct class | Files | Allocated bytes |
|---|---:|---:|
| Complete-format MySQL GPGv2 ciphertext candidates | 2 | 3,336,200,192 |
| Complete-format site-files GPGv2 ciphertext candidates | 2 | 971,497,472 |
| MySQL manifest JSON files | 2 | 8,192 |
| Site-files manifest JSON files | 2 | 8,192 |
| Incomplete `.partial` encrypted archive | 1 | 1,673,224,192 |
| Unclassified regular owner-private archive objects | 8 | 1,887,162,368 |
| Immediate child directories | 1 | 4,096 (directory inode only, **not recursive contents**) |
| Symlinks or unknown special file types | 0 | 0 |

18 direct entries. Sum of directly classified allocation: **7,868,104,704 bytes**. Independent low-priority `du -skx` on the full archive tree from the same runner found **8,191,012,864 bytes**. The **322,908,160-byte difference** is not safely assigned to a named file by this direct-only classifier; it may reflect the contents of nested folders or accounting differences, and must not be called extra disposable space.

The same **NEW** live audit measured owner VPS available bytes **4,505,399,296**; the unchanged producer requires **10,737,418,240** bytes (10 GiB) free BEFORE start. Current shortfall **6,232,018,944 bytes (~5.803 GiB)**. No independently mounted eligible private device on the existing VPS was observed in the earlier [owner filesystem scan #44183448692](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44183448692).

The earlier verified GPGv2 candidate SQL+files **pair** is ~**2,673,930,363 bytes of ciphertext** but ~15.5 days old and independently restored **zero times** ([real owner manifest audit #44172003842](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44172003842)). Counting two SQL+two file ciphertext candidates today does **not** establish two valid/restorable complete backup sets.

### Important mathematical limit

Even the extreme and **UNAUTHORIZED** hypothetical scenario of abandoning every other object in the archive tree while keeping the sole previously metadata-consistent ~2.674-GB pair would recover **at most approximately 5,517,082,501 bytes**, **less than the 6,232,018,944-byte deficit by ~714,936,443 bytes (~682 MiB)**. Because of filesystem allocated-vs-logical size differences, the upper bound is approximate. Real admissible deletion now is **ZERO bytes**, not this hypothetical limit.

**Conclusion:** "Delete old backups" is neither data-safe nor a sufficient standalone solution for passing the existing 10-GiB start gate. **Do not modify the 10-GiB threshold, delete/move the partial archive or modify existing backup permissions.**

## Separate remote storage/OAuth evidence

- The factory historical Nov5 twin-snapshot workflow [#44187109034](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44187109034) confirmed TWO **1,408,634,880-byte historical SQLite snapshots** with actual SHA/integrity checks, but **0 files uploaded**. It is not a current MojPlayWin 16.68-GB MariaDB+app+media backup.
- [#44187109098](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44187109098) found **NO existing persistent owner-only rclone OAuth config and no provider quota verification** on the authorized VPS owner runner.
- [#44187109069](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44187109069) validated a **real temporary rclone 1.76.0 binary** in a development context without system install, but **no authenticated Google Drive uploads**. Installed binary ≠ authenticated cloud connection.
- User-connected six Google Drive connector accounts had **zero files matching `mojplaywin_2026` filename search**; two dedicated `MojPlayWin-Private-Backups` folders exist, with Drive A `database`, `site-files`, `integrity-manifests` empty at inspection. Connected ChatGPT Drive credentials **must never be assumed exportable to a server**.
- Connected Dropbox account: title searches `MojPlayWin`, `mojplaywin_2026`, `backup` found zero; a separate root directory listing also returned zero entries. This proves only the connected account listing, not all historical cloud storage.

## Two genuine engineering options, neither yet operational

**Option A — Direct private encrypted multipart streams:** Build/validate the current-owner MySQL+app+media **consistent snapshot from cPanel** through authenticated pinned SSH *directly into a bounded-memory streaming authenticated encryption process*; send fixed-size AES-GCM ciphertext segments (e.g. 8 MiB) to TWO separately authenticated owner-controlled, private offsite object stores, with independent provider quota checks, per-chunk SHA readback, terminal canonical manifests, strict producer EOF/exit and independent isolated replay/restoration. This bypasses local 10-GiB backup staging **by a new, separately reviewed design**; it does **not** make the current GPGv2 producer safe at lower free space. Existing F01V2 design is factory-oriented and uses historic SQLite snapshots, not automatically current MojPlayWin full MariaDB+files. **Mandatory missing input:** authorized remote OAuth/ownership and sufficient quotas, recovery key escrow, consistency + independent restore evidence. No customer data transmitted here.

**Option B — Supply real new independent free disk:** At least **6,232,018,944 bytes extra actually free** on the correct owner-target filesystem, **plus** additional capacity for any restore workspace and safety margin, while preserving current ciphertext. Current observed `/mnt`, `/srv`, `/opt`, `/tmp`, `/var/tmp`, `/media`, `home` were on the same disk; no alternative available. Any purchased disk upgrade or provider quota expenditure needs case-specific owner approval (no spending authorized).

A future remote upload is **not** itself recovery proof. Require verified **fresh** complete SQL+app+media backup, owner-held decryption key outside single VPS, successful *independent isolated restoration*, tested rollback and individually approved release before the static-only MOJ-PROP-01 marketing page leaves Draft #2704. Never solicit 30 TRX or issue funded broker accounts before real contract and account-specific permission.

## Source artifacts and acceptance criteria

`scripts/mojprop_owner_archive_reclaim_planner_readonly_20261118.py` is a pure fail-closed planner; `tests/test_mojprop_owner_archive_reclaim_planner_20261118.py` contains **36 synthetic adverse conditions**. [Hosted CI #44218844636](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44218844636) **176/176 tests passed** (36 new planner + 36 old storage gates + 52 atomic release + 28 Plan1 page + 24 fixed public SHA). No file deletion, no backup upload, no client POST or live deploy.

**Operational summary: source backup architecture now has an accurate measured obstruction, NOT a workaround that spends money or removes its recovery assets.** Real client/revenue: 0 newly verified; no TRON receipt issued.
