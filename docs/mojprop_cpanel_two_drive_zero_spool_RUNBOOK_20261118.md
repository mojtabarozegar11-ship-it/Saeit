# MOJ PROP: zero-local-spool cPanel → dual private Google Drives

**Status: DRAFT SOURCE-ONLY. NO LIVE BACKUP, NO OAuth, NO CUSTOMER DATA, NO DEPLOY, NO COST.**

## Scope and actual existing implementation
This integration reuses the previously implemented and independently tested code, rather than adding a competing backup mechanism:

- cPanel reviewed source [`scripts/mojplaywin_backup_stream_cpanel.py`](../scripts/mojplaywin_backup_stream_cpanel.py), exact Git blob `7b330168b4ca1d597616e8724bc634910e769ea5`; supports `mysql` / `files` and emits a completion footer only after verified source subprocess exit. It limits raw MariaDB to 48 GiB, scoped files to 12 GiB, and rejects incomplete/unapproved public symlinks.
- `scripts/factory_dual_stream_v2.py` (PR #2680): bounded-memory RSA-OAEP + AES-256-GCM with a different authenticated nonce for each ciphertext block and MAC-authenticated final manifest.
- `scripts/factory_rclone_dual_parts.py` (PRs #2686/#2689): authenticated **two owner-independent Drive** remotes with private owner proof, actual `rclone about` quota verification, unique backup namespace, bounded `rcat` upload, `cat` byte-for-byte readback of EVERY chunk and final manifest only upon successful source+gzip EOF. No customer data is logged.

The new `scripts/mojprop_cpanel_direct_dual_cloud.py` connects them without storing the full plaintext SQL archive or ciphertext on the 4.20 GiB-free VPS. GitHub-hosted runner is not a backup repository; the stream remains in pipes and bounded memory.

## Critical security and operational limits
1. The ordinary CLI `python scripts/mojprop_cpanel_direct_dual_cloud.py` is OFFLINE metadata only and **cannot** trigger a backup.
2. The full transfer exists as a separate Python function, `transfer_approved_scope`, requiring the exact owner approval phrase `OWNER_APPROVES_ONE_OFFSITE_BACKUP_SET_WITHOUT_DEPLOY`, verified source/SSH/active Passenger DB/full media scope and independently recoverable private key. These claims must be supported by external evidence before they are passed as true.
3. The only accepted source script is the *exact* reviewed Git blob, not arbitrary shell scripts, unexpected websites or parameters. The checked-out source file may be public mode 0644 but must be a same-user non-symlink, regular file. The SSH config and OAuth config remain privately owner-owned 0600.
4. The SSH config parser rejects `Match exec`, `ProxyCommand`, `Include`, unknown aliases, changes to known hostname/port/user/proxy, permissive host-key options, dynamic expansions, untrusted known-host paths. The existing cPanel + VPS SSH host fingerprints are **independently checked** against exact public pins (not acquired with `ssh-keyscan`).
5. The remote command is a fixed `ssh -T -F` invocation of the pinned cPanel exporter with a base64-encoded, reviewed Python source script. No MySQL credentials are embedded in argv, stdout or GitHub; the cPanel exporter reads its own on-host authorized configuration.
6. Each mode (`mysql` and `files`) receives its own **fresh unique 128-bit run namespace** because the existing transport is one-use. A complete backup *set* requires both, plus verified scope and a separate cross-stream consistency/restore attestation. Two uploaded ciphertext manifests alone do not prove a complete business restore.
7. The runner must independently prove **free bytes in each Drive account**, sufficient for the conservative admitted compressed-source upper bound + chunk overhead + reserve. If `rclone` binary or 0600 OAuth config is missing, both remotes are not independently authenticated, or quotas are unknown, NO SOURCE stream is opened.
8. Current Google Drive connectors inside ChatGPT do NOT supply reusable OAuth tokens to rclone on VPS. Tokens must be configured securely by the owner using official OAuth. Never paste access tokens, private RSA keys, passphrases, MySQL passwords or customer backup content in chat, GitHub, or CI logs.
9. Current public MojPlayWin production DB identity, all extra subdomains/sites/media, and an independent full SQL+media restore must be proven before marketing the system as "fully backed up" or publishing/deploying the paid Plan 1 challenge.
10. **No existing ciphertext chunks, backups, files, source code or DB rows may be deleted as part of this implementation.** Google Drive rclone does not provide a strict atomic no-overwrite guarantee, so abandoned partial namespaces must remain isolated, never be re-used.
11. An isolated recovery should use a separately available compatible MariaDB and Django environment. Import must never target the original cPanel/production database. Verify transaction history, request receipts, media, schema, integrity and customer entitlements with external network/payments/email disabled.
12. All operator actions require a per-case explicit approval and a rollback plan. **Do not invoke the function** simply because this PR is green, because the server has historically proven an actual 5.8 GiB local storage shortfall.

## What is verified versus unknown
| Evidence | Status |
|---|---|
| Existing cPanel streamer Git object and strict source modes | Code pinned; CI must reverify |
| Existing two-cloud encryption/readback transport | Code present on stacked PR #2689; 67 previous tests successful |
| Owner cPanel/VPS host public key fingerprints | Pinned in source; runtime SSH not invoked |
| VPS free bytes | 4.20 GiB free (actual Nov 18 read-only audit #44183448692) |
| Persistent owner rclone OAuth remotes + cloud free quota | **NOT verified** |
| Complete current production DB/media backup to two external Drives | **0/2 verified** |
| Separately recoverable owner RSA private key and passphrase | **NOT verified** |
| Independent current SQL+media service restore | **0/1 verified** |
| Production deploy / payment authorization | **NO** |

## Next actionable steps
1. Obtain actual provider-quota evidence from both accounts and configure the two separate owner rclone remotes at the backup runner under 0600, without sharing their tokens in chat.
2. Establish exact active Passenger DB and media coverage including all relevant subsites from a read-only source inventory, and preserve the cross-stream snapshot consistency window.
3. Prove owner holds two independently recoverable copies of the matching RSA private key, outside the compromised-server blast radius.
4. Collect each distinct source/transport admission, approve a one-time window, and use **new** random run IDs for SQL and scoped files; never overwrite previous offsite F-01.
5. Read back both current archives and restore into a fresh isolated environment, then verify domain coverage, database referential integrity, challenge CRM and application media.
6. Only mark `RESTORABLE=TRUE` once complete restore and function checks actually succeed; then reconsider release gates for MojProp.

**All source-only unit tests and workflow on this PR are non-network/non-production.**

## Real read-only result and exact-head CI — 18 November 2026
- [GitHub Actions #44189240265](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44189240265): **93/93 tests green** (26 source/SSH/admission/dispatch cases + 67 existing real-core/mock-Drive encryption/readback cases), exact source head `b692d2c23a0cd074252de03b4466a73e79a03081` at the recorded run.
- **Actual self-hosted runner** metadata in the same run: `OWNER_RUNNER_OFFLINE_RCLONE_PRESENT=false` and `OWNER_RUNNER_PRIVATE_RCLONE_CONFIG_PRESENT=false`. No OAuth was read, no Drive quota queried, no current DB/media data streamed.
- Additional hardening on source head: both cPanel and relay SSH private-key files must exist, be regular, same-owner, link-count 1, mode 0600. Four adversarial tests confirm missing, world-readable, symlinked or unknown identity files deny startup.
- **Preflight decision right now: NO-GO to transfer.** Do not bypass owner authentication or Drive quota by lowering safety thresholds. The connector OAuth inside ChatGPT is separate from an owner-owned server-side rclone config.
- Manual authorization phrase by itself is not a cryptographically signed or single-use approval token; human operator must independently verify per-case authorization and distinct 128-bit run IDs. No unattended production execution workflow is wired here.
- References: [MariaDB consistent snapshot and DDL limitations](https://mariadb.com/docs/server/clients-and-utilities/backup-restore-and-import-clients/mariadb-dump), [rclone stdin streaming](https://rclone.org/commands/rclone_rcat/), [Google Drive quota via rclone](https://rclone.org/drive/).


### Supply-chain-safe rclone without permanent VPS installation — verified
- Official stable `rclone v1.76.0`, released **6 Nov 2026**, is available as a fixed URL, `https://downloads.rclone.org/v1.76.0/rclone-v1.76.0-linux-amd64.zip`. Independently recorded ZIP SHA-256: `b00f00b3266c3764413afe599d3ec316f6f43b3e0ea8a0bc1d186d2133e46df7`.
- [Actual self-hosted run #44190136228](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44190136228) **SUCCESS**: downloaded it only into a newly created disposable `$RUNNER_TEMP` directory, matched SHA256 byte-for-byte, extracted only the selected rclone executable, validated `rclone v1.76.0`, and cleaned the job's own temporary files. This **did not install it system-wide** or touch existing backup files.
- This resolves **availability of a verified temporary binary for a single backup job**; it does **not** prove a server-owned OAuth credential, free Drive quota, current backup or restore.
- On the same run the owner's actual rclone private config still returned `false`. **OAuth and quota remain the blocking external prerequisites**. Do not supply ChatGPT connector tokens as a substitute for official owner-authorized runner credentials. Any future backup runner must deliberately pass the verified ephemeral binary path as `rclone_exe` and run dual-account `preflight()` BEFORE opening cPanel source.
