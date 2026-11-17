# MOJ PROP — exact live/static release and fresh full-backup capacity decision

**Date:** 18 Nov 2026. **Product:** real proposed MOJ-PROP-01, not educational Starter30. **Codebase:** safe main-based #2701 plus its backup/capacity audit child. **Status: NO DEPLOY, NO PAYMENT, NO FUNDED ACCOUNT.**

## 1. Proven live-public and reviewed replacement identity

- Current public URL: https://mojplaywin.com/moj-prop/
- Independently verified on **actual cPanel over pinned owner SSH** in [Actions #44169388709](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44169388709): fixed source file `/home/zomorod2/mojplaywin.com/moj-prop/index.html`, **23,869 bytes**, SHA256 `76918c5129ff669ef02f82435a68f61a32d70141800712100d4a7fe9e8554895`.
- [GitHub Actions #44184729312](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44184729312): bounded external **HTTPS GET** of public `/moj-prop/` was HTTP 200 `text/html` and **byte-exact SHA256/size MATCH** to independently authenticated cPanel source. This proves the public current page is still the originally approved candidate for future *review*, not that backend or deployment gate is open.
- Corrected HTML source at branch `fix/mojprop-main-first-prospect-truthful-contact-20261118` and child: `templates/moj-prop-v4/index.html`, **46,455 bytes**, SHA256 `13bd45c1d6b62f03058428b3086e71b17de4f2776238e8ab85a49d648fce49b0`. The updated content prioritizes the nonpayable real two-stage Plan 1 and the already-live first-party contact.
- Two independent fixed-hash source guards now refuse **unknown original** or **modified candidate**. This is a strictly read-only preflight; **no live HTML was replaced**.
- [CI #44184729312](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44184729312) **36/36 storage-admission + 24/24 exact static-identity regressions passed**, plus live GET matching exact file hashes. [CI #44181082793](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44181082793) **28/28** main-based Plan1 contact regressions passed.

## 2. Physical capacity and backup constraints

**Latest authentically observed (previous owner-authenticated Actions runs):**
- cPanel account quota **30 GiB**, used ~28.96 GiB, with **~1.04 GiB quota remaining**; ignore shared-filesystem `statvfs` ~188 GB free as an account quota claim.
- cPanel MySQL **16,680,812,544 bytes** across three databases, largest one **16,679,239,680 bytes**.
- VPS owner `githubops` filesystem **~4,543,619,072 bytes** free at prior run; today's new authenticated alternate-volume inventory is **queued**, not successfully run at the time of writing. Do not call this old number a live refreshed measurement.
- Existing GPGv2 producer `scripts/mojplaywin_backup_encrypt_vps_gpg.py` and `scripts/mpw_vps_backup_runtime_gate_readonly_20261101.py` require **exactly 10 GiB minimum free BEFORE starting**; streaming encryption maintains a **3 GiB hard safety floor** and 12 GiB ciphertext cap. At prior observed free space, shortfall to admission = **6,193,799,168 bytes (~5.77 GiB)**. Do **not** reduce this guard to force a green run.
- Private VPS `~/.private-mojplaywin-offhost-backups` has 3 candidate set identities, 1 structurally consistent GPGv2 SQL+files pair (~2,673,930,363 ciphertext bytes) ~15.5 days old, 1 `.partial` file. Owner key metadata is private and valid (32 bytes). NO current (<72h) consistent pair; NO independent isolated restore; key content NEVER read by the audit. **Existing ciphertext isn't a fresh full site backup.**
- In authenticated owner-connected Google Drive `MojPlayWin-Private-Backups`, the `database`, `site-files`, and `integrity-manifests` folders are presently **empty**. Two checked Drive accounts have 59-file *source-only* Moj Prop bundles; these do NOT constitute DB+media full backups. No upload/copy or encryption occurred.
- Storage admission code `scripts/mojprop_backup_release_admission_readonly_20261118.py` reports no automatic deployment/restore/payment even when hypothetical disks clear 10 GiB. An alternate private storage mount must be independent, secure, owner-controlled, **and** the actual GPG producer explicitly adapted, verified and authorized to use it; merely seeing an untrusted `/tmp` with disk free is not enough.

**New run:** [Actions #44183448692](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44183448692) was **queued** for self-hosted `factory-vps` at last inspection. The workflow does not checkout repo to live factory, does not write any backup, scans only low-priority directory allocations and sanitized disk mounts over pinned owner loopback SSH. Its execution must be checked from GitHub; **do not treat queued as executed**.

## 3. Strict operations path to first genuine MOJ-PROP-01 lead

1. First obtain real fresh free-capacity evidence from existing authenticated `githubrunner→githubops@127.0.0.1` route and determine whether a **distinct owner-private volume** truly meets the current producer's 10 GiB admission. No file deletion or chmod; old archives retained.
2. Require an explicit owner case confirmation for `BACKUP_AND_ISOLATED_RESTORE` on the existing main-only protected workflow. Only if capacity and both cPanel/VPS pinned SSH identities pass should the workflow create a current encrypted SQL+files pair and perform an independent isolated DB+scoped-media restore. No backup script should be run until its full requirements pass.
3. Independently secure recovery-key escrow under authorized, proven owner-controlled offline storage; currently no verified second recovery-key location was observed. Do not print or transmit key via chat/logs.
4. Independently reconcile true Passenger/WSGI/backend routing, code/schema and current DB+media restoration. The latest forms and private receipt endpoint remain absent from live host. Publish only after exact source preflight and verified rollback plan, **separate case-specific owner approval** and ideally fresh complete backup proof.
5. For static-only reviewed release, the current observed public file must still equal SHA256 `76918c...` and exact size 23869. The replacement must equal SHA256 `13bd45c1...` size 46455. Create a **private byte-for-byte rollback copy** on the cPanel owner filesystem, ensure cPanel account quota headroom and non-symlink owner-only directory, then use an atomically durable swap with exact post-release HTTP hash check. Do not silently reuse old C127 script because it is only pinned to the old 23812→23869 horizon patch and **cannot deploy this new 46455-byte page**.
6. Confirm live Plan1 contact remains nonpayable, its first-party `mailto:` reaches connected owner Gmail, and prospect data is not assigned as a fake CRM order. Only real voluntary emails or consented POSTs become qualified leads.
7. Remain blocked on payment until supported country/jurisdiction, customer KYC, signed challenge terms and clear refunds, independent real XAUUSD data/ledger, full capitalization and broker **written delegated trading authorization** are proven. Proposed price 30 native TRX = 30,000,000 SUN, not payable now.

**Current outcome:** SOURCE FIX AND LIVE-ORIGINAL HASH CONFIRMED, but full new backup/restore, release approval, live page publication, real customer and 30 TRX receipt **not confirmed**. No production SQL, files, credentials or invoices modified; no broker order sent; no paid campaign published.
