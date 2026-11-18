# MOJ-PROP-01 — no-10GiB-local-staging, private two-provider encrypted backup core

**Date:** 2026-11-18. **Current status:** Code + real offline encryption/recovery tests PASS; **NOT connected to any live Google Drive, NOT capturing a production backup**. Product is the proposed REAL prop challenge MOJ-PROP-01 (30 native TRX FUTURE price), not the Starter30 educational report. This does not approve payments.

## Why this was built

Owner-authenticated VPS evidence [#44218536999](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44218536999) found **4,505,399,296 bytes free**, **6,232,018,944 bytes below** the existing GPGv2 backup producer's unchanged 10-GiB prerequisite. No separate adequately free disk was found. The private archive occupies ~8.19GB; safe deletion now **0 bytes**, and removing all archive objects except one metadata-valid ~2.674-GB pair still leaves ~715MB of deficit, even hypothetically. Existing historic files are **not** a proven fresh or independently restorable site backup. Do not lower the old GPGv2 producer's 10-GiB gate.

The current cPanel backup source `scripts/mojplaywin_backup_stream_cpanel.py` uses MariaDB `--single-transaction --quick` and scoped TAR, streams bytes over stdout, and emits its fixed `MJWP-RECOVERY-20261017-COMPLETE-F91D7C40` marker **only after successful producer exit**. A real MySQL stream's length is not known beforehand.

## Implemented NEW source-only software

1. `scripts/mojprop_direct_dual_offsite_stream_core_20261118.py` — **bounded-memory, no local archive file**, RSA-3072 OAEP-SHA256 public-key wraps ephemeral random AES-256 key; each up-to-8MiB part gets independent AES-256-GCM nonce/AAD bound to exact set, content kind, part order and previous ciphertext digest. Each part is written **once**, to BOTH independent private cloud sink interfaces, then byte-readback checked from both before proceeding. A terminal per-kind manifest is emitted ONLY after exact EOF/size and every part readback.
2. For **unknown-length** live stdout: `stream_verified_cpanel_unknown_size` bounds total input, requires the exact pinned cPanel end marker (including when split across SSH reads) and a **separately authenticated, literal boolean TRUE remote producer/SSH process exit confirmation**. Missing marker, source truncation, extra data, failed exit or cloud readback => **NO terminal manifest**. A partial failure may leave orphan encrypted chunks in cloud; **NO automatic cleanup/deletion**.
3. `isolated_restore_from_two_private_sinks` reads both manifests/parts, refuses cloud divergence/reorder/truncation, uses the OWNER'S **offline** encrypted RSA private key to decrypt and verifies all GCM tags, full plaintext SHA and chained ciphertext hashes. Its output must be a private isolated quarantine destination, **never a production database**.
4. `scripts/mojprop_direct_dual_offsite_pair_manifest_20261118.py` makes a **separate technical two-kind receipt** only after BOTH `mysql` and `files` kinds have independently matching manifests, part sizes, ciphertext SHA chain and readback from two stores. **Technical receipt is NOT a signed source snapshot, independent full SQL import, restored media, escrow or legal release.**
5. No CLI or GitHub workflow here executes VPS, cPanel, real Drive/Dropbox, production backups, payment, key escrow or user messages. The cloud `PrivateSink` is an *abstract injected interface*, not a completed authenticated Drive implementation. The `ProviderReview` values are independently obtained evidence requirements, NOT proof by themselves.

## Actual independent CI evidence

- [Actions #44220441983](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44220441983): **48/48 cryptographic adversarial tests + 176/176 previous Plan1/rollback/storage-source tests = 224/224 PASS**. Genuine RSA-3072/AES-GCM synthetic encryption and end-to-end recovery in memory.
- [Actions #44221144700](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44221144700): **70/70 cryptographic + unknown-size producer EOF/tail and exit tests, plus 176/176 previous = 246/246 PASS**.
- [Actions #44221617463](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44221617463): **90/90 crypto/stream/pair receipt + 176/176 previous = 266/266 PASS**. ALL tests use synthetic noncustomer bytes in disposable/in-memory stores. No real data touched.

## Operational preconditions — ALL still unmet for a real backup

**A. Authenticate owner-controlled remote storage from the actual VPS.** The earlier factory owner runner [#44187109098](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44187109098) had **NO persistent private rclone/OAuth config**, no trusted Drive quota. An ephemeral real rclone binary was verified in [#44187109069](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44187109069) but **not connected**. ChatGPT Google Drive OAuth connections are **not exportable or interchangeable with VPS credentials**; do not ask the owner to post secrets in chat or GitHub.

**B. Check per-provider quota, private ACLs and two independent accounts BEFORE streaming.** The encrypted stream is **not compressed**; two complete replicas require each remote logical destination to support the actual **whole MySQL stream plus media**, not merely a few-GiB compressed historic archive. A normal individual free 15GB Google account **may be too small for raw ~16.68GB MySQL alone**; its specific actual free quota has NOT been checked. Six connected ChatGPT Drive accounts are NOT proof of six empty/usable VPS-authenticated provider stores. If two accounts cannot each hold one complete encrypted copy, use an independently reviewed **two disjoint multi-account striped storage groups** or eligible existing private space; not a silently fake full-copy guarantee. A separate pooling implementation and private readback plan would be required; neither is claimed here.

**C. Check live Passenger/WSGI app identity and all site + subsite media.** The current source streamer scopes `/home/zomorod2/Saeit-staging` and `/home/zomorod2/mojplaywin.com`, and only one configured cPanel MariaDB connection. A full MOJ-PROP-01 recovery must independently confirm all actually served roots, attached products, downloadable assets, other DBs, and a transactionally consistent SQL snapshot. A technical two-kind receipt cannot prove that.
 
**D. Independent private recovery-key custody.** RSA **private key** must be generated/stored securely OFF VPS and OFF both cloud destinations, preferably password-encrypted and with separately validated offline copies. Only public key and independently pinned SHA are on sender. Existing owner's GPGv2 key is a different format; don't silently swap or publish it.

**E. Owner-reviewed, isolated real SQL+media restore.** Restore ciphertext from BOTH owner-private destinations to a quarantined, non-production worker; independently decrypt, SHA verify, import the relevant MySQL data, inspect schema and count/foreign-key integrity, restore all scoped media, and demonstrate emergency rollback. Never log SQL, customer rows, wallet keys or raw ciphertext in Actions.

**F. Separate approval of actual source streaming/deployment/payment.** Implement a reviewed, pinned SSH process wrapper and owner OAuth provider adapters, using no secret in CI logs, configure strict retry/partial upload semantics, prove quota readbacks, and obtain case-specific authorization before running any live 16GB stream. **NO production operation is authorized by this PR.**

## Current revenue and gates

The legal/onboarding/backend conditions of real funded trading remain unresolved, as do real consented customers and a production 30-native-TRX settlement. The page-contact Draft #2704 remains uninstalled; the existing public contact page is available for voluntary *unpaid* inquiries. **Zero new TRX income and zero verified new buyer enrollment** in this implementation cycle.

**Engineering progress:** from *local-only GPG backup blocked by 10GiB* to a demonstrated **bounded-memory two-private-sink cryptographic core** with verified unknown-source streaming and independent two-kind technical receipts. **Remaining irreducible external blocker:** actual VPS cloud ownership/OAuth + quota, current-consistent live capture and independently restored output. Preserve all old backups; authorize no cost or deletion without owner approval.
