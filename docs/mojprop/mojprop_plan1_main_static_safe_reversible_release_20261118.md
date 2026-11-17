# MOJ-PROP-01: exact-pinned nonpayable public contact static release — safe execution and blockers

**Date:** 18 Nov 2026 · **Status:** Draft/source + verified read-only live inspection, **NOT DEPLOYED**.  
**Product:** actual proposed MOJ-PROP-01 two-stage simulated proprietary evaluation, not MOJPROP-STARTER30 educational report.  
**Mainline parent:** [PR #2701](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/2701) → [backup/SHA audit #2702](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/2702). This child adds a ready exact-byte reversible **static HTML** transaction; does not touch the divergent v1.4 backend.

## Actual independently recorded production state

**[Authenticated cPanel SSH #44188884709](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44188884709) succeeded:**
- `zomorod2` owner identity and pinned SSH host-key fingerprint match.
- Actual static `/home/zomorod2/mojplaywin.com/moj-prop/index.html` exists, is owned by the expected account, is an actual regular file, and matches approved current size **23,869 bytes** and SHA256 **`76918c5129ff669ef02f82435a68f61a32d70141800712100d4a7fe9e8554895`**. It is readable by webserver (NOT 0600); this is normal for a public asset.
- Existing generic `/home/zomorod2/.backups` is owner-owned, a real directory, **NOT owner-private 0700**; do **not** change its mode or store private rollback bytes directly in it.
- No pre-existing rollback file or lock for this exact new release. No files created in this read-only inspection.
- Initial UAPI query produced NULL totals because the new wrapper used the wrong provider field labels. The parser was fixed to proven cPanel fields `data.bytes_used` and `data.byte_limit`, checks `result.status == 1` and nonnegative range, and **actually rerun via pinned cPanel SSH** in [Actions #44189768241](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44189768241): total **32,212,254,720 bytes (30 GiB)**, used **31,100,866,560 bytes**, remaining **1,111,388,160 bytes (~1.035 GiB)**. These are owner account quotas, not the 188GB shared-filesystem free space. This is enough for a reviewed static HTML backup only, NOT a fresh full 16.68GB MariaDB+media backup.
- No buyer PII, SQL, app secrets or customer email was read; no deploy or delete occurred.

**[Public web + source exact SHA #44184729312](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44184729312):** HTTPS GET page content was byte-identical to cPanel original 23,869 bytes; improved reviewed source at `templates/moj-prop-v4/index.html` is **46,455 bytes** with SHA256 `13bd45c1d6b62f03058428b3086e71b17de4f2776238e8ab85a49d648fce49b0`, and priority CTA to already functioning `/moj-prop/contact/` — **no active checkout**.

## New code: bounded exact-byte atomic release and private nested rollback

`scripts/mojprop_plan1_static_atomic_release_20261118.py` implements:
1. Fixed account `zomorod2`; fixed live page and SHA/size of both original and proposal; rejects all unrecognized bytes.
2. O_NOFOLLOW + fd inode/dev/uid/size revalidation, hardlink and world-write refusal, bounded memory and stale/concurrent update refusal.
3. **Read-only preflight** from account owner's CLI; no lock, backup or directory creation in that mode.
4. EXACT required marketing disclaimers: real challenge SKU, free contact and no payments now, private receipt token safety, reject known-404 new interest link.
5. Distinct owner-only private **nested** directory `/home/zomorod2/.backups/mojprop-plan1-private-20261118` created at mode **0700** only *after a separately approved install*. Do not chmod, remove, rename or modify the existing generic `.backups` folder. Original rollback payload must be private **0600**, byte-exact, immutable under repeated install.
6. Atomic same-directory temporary file + fsync + conditional O_EXCL lock, recheck original inode/mtime after lock, os.replace and directory fsync, verified final bytes+mode.
7. Strict original-file rollback if explicit separate owner rollback ack, actual private backup SHA and exact new-page SHA match. Never rollback an unexpected third-party-modified page.
8. Public CLI **only supports READ-ONLY preflight**; neither install nor rollback available by CLI. Install requires a trusted, separately reviewed owner executor with 5 independently attested conditions and the **case-specific typed approval**; passing local booleans is not proof of actual independent restoration. There is intentionally **NO auto-deploy GitHub Action** in this PR.

**[Source-only Actions #44189393715](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44189393715) SUCCESS:** **52/52 isolated atomic release/rollback adversarial checks** and **88/88 companion source/storage/public-hash checks**, total **140 PASS**. All install and rollback examples took place only in disposable synthetic temp folders; no live cPanel payload changed.

## Critical business and data-protection NO-GO

- **[VPS owner authenticated #44183448692](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44183448692):** only **4,511,453,184 bytes (~4.20 GiB)** free on the only discovered existing VPS device, while existing owner-armed GPG producer requires minimum **10,737,418,240 bytes** before starting. Deficit **6,225,965,056 bytes (~5.80 GiB)**. No independent owner-private mounted volume with 10 GiB free observed. Do not lower the threshold, delete or overwrite historical archives.
- Encrypted old SQL+files pair ~15.5 days old, ~2.67GB ciphertext, one incomplete partial, 8.19GB private archive directory allocation; **no proven fresh full DB+app+media backup, no independent isolated restoration, no independently escrowed recovery key**.
- Owner-connected Google Drive `MojPlayWin-Private-Backups` has empty `database`, `site-files`, `integrity-manifests` folders. Separate source-only code archives DO NOT satisfy full offhost restoration.
- The old C127 static patch is pinned only to 23,812→23,869 bytes and **must not be reused** for the current 46,455-byte Plan1 landing.
- The new public static page is *only* a voluntary contact funnel, **not** working backend lead enrollment, funded account or payment. Production Django/Passenger route of v1.4 is not proven live. Full KYC/legal/country, customer terms/refunds, independent XAUUSD risk feed and signed broker delegation remain outstanding.

## Owner-reviewed full execution order (not performed)

A. Preserve all existing live SQL/media, backup and encrypted key. Verify independent free capacity; the current 10-GiB admission is blocked. A future **direct private encrypted multipart stream to an authenticated provider** might avoid local staging, but needs independently proven owner OAuth, Drive quota, cryptography, uninterrupted EOF/hash/GPG readback and isolated restore; **not currently available as a verified MojPlayWin backup**.

B. After owner case confirmation and adequate secure destination, create fresh offhost **full MySQL+app+media** backup with authenticated per-part integrity and independently exercise isolated restore, source consistency and actual rollback. No passwords/keys printed or copied to the assistant.

C. Independently re-read cPanel quota field schema, exact current live SHA and ownership. Review legal prelaunch disclosure and actual media/contract implications. Stage *only* exact candidate file privately with mode/ownership check, not at live path.

D. Obtain separate owner explicit approval for **a static-only production release** after B/C. Execute the reviewed `transact("install")` through its separately guarded operator after proof, preserving original rollback byte-for-byte. Recheck HTTP 200 content SHA and voluntary mailto contact; have a case-specific rollback authority available if the output differs. Do not call a test suite green a live release.

E. Only after a genuine voluntary prospect request, verify delivery to the connected owner Gmail and any CRM persistence before recording a sale. **No customer POST should be fabricated**. Do NOT enable proposed 30 native TRX settlement, live broker trades, funded account promises or paid advertising without their own approved legal/technical gates.

**Evidence boundary:** Source/isolated QA complete, live target and backend preflight observed; **no production modifications or new revenue**. This document is neither a release approval nor authorization to spend, delete, email, deploy or trade.
