# Factory F-01 historical restore admission — NO LIVE RESTORE

This adds a *read-only admission gate*, **not** an archive extractor or an
approval to restore services. The reviewed 2026-10-30 encrypted F-01 backup has
43 ciphertext transport objects and identical off-site copies under **two
independent owner Google Drive identities**. A separate offline audit verified
3/3 AES-256-GCM tags, plaintext archive SHA-256, gzip CRC/trailer and tar
traversal **without extracting data**.

## Observed HOLD

The 2026-11-17 private Library audit
`/Factory/F01_Recovery/F01_TAR_LINK_TARGET_AND_CONTENT_SCOPE_2026-11-17.json`
found exactly **three absolute symlink targets** among 3,273 tar symlinks.
The historical archive must **not** be unpacked onto a production host, nor
blindly unpacked into a supposedly isolated directory. Symlink-chain behavior,
filesystems, capacity, active processes, UID/GID mapping, service configuration
and database consistency must be reviewed separately.

The metadata-only decision tool is:

```bash
python3 -B scripts/f01_tar_restore_admission_readonly.py \
  --audit-json /path/to/owner-private-F01-audit.json \
  --expected-audit-sha256 286f47d86f75bc50acc2c868534fe62d653661b8152ec2b82a964bb2e60ca299 \
  --expected-archive-sha256 fbf2153da30e01842b84a6a068c50051ea49839a5f4a567073f771cac30952b8
```

The audit SHA must come from an **independent, trusted operator record**.
A matching SHA checks file identity, not the truth of the original auditor's
assertions. This is **not** a signed report; no public or private secret is
required by the tool. It only reads a local bounded JSON file and prints a
minimal decision with no archive member names or secret paths. It rejects
symlink audit files, invalid or duplicate JSON keys, missing/mismatched hashes,
malformed counters, non-clean archive metadata and any hazardous link targets.

The **expected** result for the above real audit is `HOLD` / exit code **2**
with `UNSAFE_LINK_TARGETS` and count **3**. Exit code 0 only means the metadata
might be *considered* for an independent isolation review; **even then the
output always states that extraction and production restore are unauthorized**.

## Offline regression tests

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest -q \
  tests.test_factory_f01_tar_restore_admission_readonly
```

The 31 tests use synthetic audit metadata only and require no cloud account,
runner credentials, private key, password, live database or archived client data.

## Entirely separate, still open, new-backup gates

- C168 owner cPanel metadata-only workflow run #44098181498 found the configured
  staging database **101/101 InnoDB**. It did **not** prove Passenger's live
  database identity, a transaction-consistent snapshot, or a backup.
- C161 found Django FileSystemStorage but `MEDIA_ROOT` *not configured*;
  complete user-upload and subsite media coverage remains unknown.
- Google Drive OAuth connection and historical F-01 copies are proven, but
  available `storageQuota` for both accounts has **not** been authenticated.
- Existing full-export GitHub workflows remain `if: false` because a full SQL
  dump cannot be staged safely within previously measured VPS/cPanel headroom.
- Current MariaDB + application + media **0/2** independently verified encrypted
  offsite copies; no full isolated operational restore; no release authority.

**No cleanup of backups, no secret handling, no production deploy, no full DB
export, no billing and no automatic background action is part of this PR.**
