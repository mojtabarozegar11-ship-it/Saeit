# MojPlayWin GPGv2 v3 backup — safe roll-forward

## Confirmed fault

The October 17 primary encrypted backup timed out after exactly **1,300 seconds per stream** (MySQL and scoped site files). Incomplete GPGv2 encrypted `.partial` files remained on VPS, with no complete archive or restore proof. Separate October 20 tests confirmed 4 MiB raw MySQL/file source startup, an 8 MiB SSH relay, and VPS GPG-AES256 memory-only roundtrip. Full multi-gigabyte transfer was **not** verified.

## Fix on this branch

- `scripts/mojplaywin_backup_gzip_source_v3.py`: transactional MySQL dump / scoped main-site tar, gzip level 1 **on cPanel before SSH**, then append a footer only after complete source success. No temp plaintext archive.
- `scripts/mojplaywin_backup_encrypt_vps_gpg.py`: opt-in `source_encoding="gzip-with-footer-v1"`, GZIP CRC and bounded decompression tests during encryption, new `stem` for non-overwriting private backups, GPG roundtrip and SHA-256 manifest. Default legacy backup decoding is unchanged.
- `scripts/mojplaywin_backup_gzip_runner_v3.py`: runner using an independently established and host-key-pinned SSH configuration, no embedded secrets, no shell execution of untrusted input, 2-hour-per-stream maximum. Explicit owner approval is required.
- `scripts/mojplaywin_backup_gzip_recovery_v3.py`: manifest-bound private decrypt/gzip test, with optional isolated decoded SQL/TAR streaming; **never point recovery to the production MySQL database or shared Passenger application**.

## Execution contract (only in an already trusted owner-authorized private runner)

1. Review and test the PR; create a fresh GitHub Actions run, isolated from public deploys. Establish the same pinned SSH configuration as the existing approved read-only cPanel inventory action. Never weaken host checks.
2. Run the no-network fixture first:
   `python3 scripts/mojplaywin_backup_gzip_runner_v3.py --ssh-config "$RUNNER_TEMP/mojplaywin-inventory-ssh/config" --date 20261020 --fixture`
3. After confirming backup-specific approval, no overlapping job and enough VPS capacity, run **one** bounded non-overwriting private backup:
   `python3 scripts/mojplaywin_backup_gzip_runner_v3.py --ssh-config "$RUNNER_TEMP/mojplaywin-inventory-ssh/config" --date 20261020 --owner-approved`
4. If a `mojplaywin_20261020_...` partial is already present, **do not delete/overwrite it**. Investigate and use a distinct date/version after separate review. Runner will refuse an existing target.
5. On VPS (not GitHub runner), run the recovery script `check`, then `validate` against the exact dated pair. `validate` is safe to log: it never emits plaintext SQL or TAR, only aggregate byte counts.
6. Rehearse SQL import into a newly isolated database/container and TAR extraction into a newly isolated private scratch directory; validate schema, records, files and checksums. Never restore into the live shared Django/Passenger tree. Retain rollback instructions.
7. Securely escrow the decryption key **outside the VPS** through an owner-controlled process; never display, upload to repository, logs, or CI artifacts.
8. Verify independent child-site coverage, route isolation and rollback before any deployment or product registration. This backup covers only the two named main-site filesystem roots and the one verified MySQL database; it does NOT certify all tenant/subsite data.

**Fail closed:** green CI, one valid archive, private inbox receipt, synthetic restore and checksum alone do not prove a production-restorable backup. Unless both real encrypted archives and an isolated restore pass, release remains **NO-GO**.

## Operational hygiene

The historical October 17 `.partial` archives are intentionally retained. No production payment, product, shared app restart or protected child-site path is modified. Existing Django/MySQL schema is not migrated.
