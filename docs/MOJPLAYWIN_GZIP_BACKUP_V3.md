# MojPlayWin GPGv2 v3 backup — safe roll-forward

## Confirmed fault

The October 17 primary encrypted backup timed out after exactly **1,300 seconds per stream** (MySQL and scoped site files). Incomplete GPGv2 encrypted `.partial` files remained on VPS, with no complete archive or restore proof. Separate October 20 tests confirmed 4 MiB raw MySQL/file source startup, an 8 MiB SSH relay, and VPS GPG-AES256 memory-only roundtrip. Full multi-gigabyte transfer was **not** verified.

## Fix on this branch

- `scripts/mojplaywin_backup_gzip_source_v3.py`: transactional MySQL dump / scoped main-site tar, gzip level 1 **on cPanel before SSH**, then append a footer only after complete source success. No temp plaintext archive.
- `scripts/mojplaywin_backup_encrypt_vps_gpg.py`: opt-in `source_encoding="gzip-with-footer-v1"`, GZIP CRC and bounded decompression tests during encryption, new `stem` for non-overwriting private backups, GPG roundtrip and SHA-256 manifest. Default legacy backup decoding is unchanged.
- `scripts/mojplaywin_backup_gzip_runner_v3.py`: operator runner requiring the **exact pinned SSH host identities and known-host SHA256 fingerprints**, private credentials, explicit approval and a bounded per-stream deadline. Before any transfer, it checks VPS destination readiness, existing key and vacant dated archive names. After the pair, it runs independent authenticated content validation without exporting SQL/TAR.
- `scripts/mojplaywin_backup_gzip_destination_preflight_v3.py`: metadata-only VPS destination check; requires >=10 GiB free at start, private recovery key, GPG and untouched dated target names. Old incomplete archives are preserved.
- `scripts/mojplaywin_backup_gzip_recovery_v3.py`: manifest-bound private decrypt/gzip test, with optional isolated decoded SQL/TAR streaming; **never point recovery to the production MySQL database or shared Passenger application**.

## Execution contract (only in an already trusted owner-authorized private runner)

1. Review and test the PR; create a fresh GitHub Actions run, isolated from public deploys. Establish the same pinned SSH configuration as the existing approved read-only cPanel inventory action. Never weaken host checks.
2. Run the no-network fixture first:
   `python3 scripts/mojplaywin_backup_gzip_runner_v3.py --ssh-config "$RUNNER_TEMP/mojplaywin-inventory-ssh/config" --date 20261020 --fixture`
3. After confirming backup-specific approval, no overlapping job and enough VPS capacity, run **one** bounded non-overwriting private backup:
   `python3 scripts/mojplaywin_backup_gzip_runner_v3.py --ssh-config "$RUNNER_TEMP/mojplaywin-inventory-ssh/config" --date 20261020 --owner-approved`
4. The runner checks two new-scoped outputs and validates both completed archives against GPG, SHA256 and gzip CRC; per-archive operation remains nonoverwriting and fails closed. If a `mojplaywin_20261020_...` partial is already present, **do not delete/overwrite it**. Investigate and use a distinct date/version after separate review. Runner will refuse an existing target.
5. On VPS (not GitHub runner), run the recovery script `check`, then `validate` against the exact dated pair. The runner already performs the encrypted+decompressed `validate` check; the second operator check is defense-in-depth. `validate` is safe to log: it never emits plaintext SQL or TAR, only aggregate byte counts.
6. Rehearse SQL import into a newly isolated database/container and TAR extraction into a newly isolated private scratch directory; validate schema, records, files and checksums. Never restore into the live shared Django/Passenger tree. Retain rollback instructions.
7. Securely escrow the decryption key **outside the VPS** through an owner-controlled process; never display, upload to repository, logs, or CI artifacts.
8. Verify independent child-site coverage, route isolation and rollback before any deployment or product registration. This backup covers only the two named main-site filesystem roots and the one verified MySQL database; it does NOT certify all tenant/subsite data.

**Fail closed:** green CI, one valid archive, private inbox receipt, synthetic restore and checksum alone do not prove a production-restorable backup. Unless both real encrypted archives and an isolated restore pass, release remains **NO-GO**.

## Tested fixture evidence (not a production restore)

- CI acceptance includes `test_mojplaywin_backup_pipeline_integration_v3.py`, which constructs synthetic SQL+TAR streams, compresses and encrypts them, and decodes both in a disposable temporary directory. No customer data, live DB or production site is accessed.
- Destination readiness tests cover pre-existing version files, historical partial preservation, low disk capacity, incorrect private key permissions, symlinks and invalid dates.
- The backup wrapper and the independent recovery validator explicitly accept tiny *compressed* GZIP envelopes when the verified **decompressed** content is large and CRC-valid.
- Because the original private backups took >1,300 seconds per raw source, initial compression and a bounded 7,200-second allowance per stream are used. Actual transfer speed and success depend on real production data and remain unverified until the owner-run job completes.
- The destination automatically requires >=8 GiB free on entry to each compressed stream, and fails at its existing 3 GiB free-space floor while writing. The 10 GiB initial probe is deliberately stricter.

## Protected owner-controlled activation

**This PR deliberately does not install or run a privileged backup workflow.** The operator must use an authorized runner with the previously verified SSH identities and protected GitHub secrets, explicitly start the backup, and preserve its status logs. Do not print SSH keys, backup passphrases, SQL, TAR or content-hash values. Review release-gate status separately; never mark a private backup as public publication.

## Operational hygiene

The historical October 17 `.partial` archives are intentionally retained. No production payment, product, shared app restart or protected child-site path is modified. Existing Django/MySQL schema is not migrated.
