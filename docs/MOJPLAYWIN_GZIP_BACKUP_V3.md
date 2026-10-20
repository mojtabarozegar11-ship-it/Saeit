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

## October 20 verified readiness and actual limitations

- **VPS read-only readiness:** https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39369175197 . Private backup directory, existing recovery key, GPG, >=10 GiB free, and unused `mojplaywin_20261020` names verified. It also definitively reported no complete archive pair.
- **Isolated recovery runtime probe:** https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39369594141 . The current VPS user account has no Docker, Podman, MariaDB client/server or MySQL server binaries. Available memory >=2 GiB and free disk >=10 GiB; free disk was below 16 GiB at that probe. Hence an actual isolated SQL import **cannot be claimed on this VPS**.
- **Temporary network-disabled MariaDB fixture:** https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39370013330 . Synthetic GPG SQL/TAR archives were decrypted; a disposable MariaDB instance restored a verified 160-row test table; safe TAR extraction and path-traversal rejection passed. Docker container had no network connectivity and was removed. No customer data was handled.
- **Owner-only workflow staged:** `.github/workflows/mojplaywin-v3-owner-manual-backup.yml`. It only responds to GitHub **workflow_dispatch**, checks the exact repository, `main` ref, owner actor, and `APPROVE-PRIVATE-BACKUP-NO-PUBLISH` confirmation. It has no automatic push, scheduled, or PR backup trigger. Until reviewed and added to the default branch, GitHub's manual Run workflow interface does not expose it. Do not force-merge this PR in a way that triggers shared production deployments.
- The manual workflow creates an encrypted, versioned **pair of scoped backup files**, runs GPG/gzip pair verification, and explicitly outputs `V3_REAL_ISOLATED_RESTORE_COMPLETED=false` and `V3_PUBLIC_RELEASE_AUTHORIZED=false`. A green job is not proof of real isolated database restoration.
- Restoring the real SQL dump requires an owner-approved isolated MariaDB runtime. Because the VPS lacks one, prepare a private controlled VM/container outside the active cPanel tenants before any real restore. Do not route sensitive customer SQL to public CI logs or synthetic CI services; this would require an explicitly approved private-processing arrangement.

### Operator safety checkpoints

1. Read the latest PR checks and verify no cross-subsite main-branch workflow will deploy or restart shared Passenger solely because backup files merge.
2. Obtain owner authorization to activate the manual backup workflow. Confirm the destination check still finds sufficient free disk, existing private recovery key, and no conflicting dated archives.
3. Run the private backup once. If either stream fails, preserve historical and current `.partial` files and do not retry with the same date.
4. Verify both GPG manifests and their recovered content. Export a **secure copy of the decryption key outside the VPS** through an owner-approved secret-management channel; never expose it in chat or GitHub artifacts.
5. Import into an isolated DB and safely reconstruct site files, then compare records, routes and required data. Document proof of the **actual** isolated restore and affected scopes before authorizing public store changes.
