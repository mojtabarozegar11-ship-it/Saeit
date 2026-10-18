# MojPlayWin Resumable Encrypted Backups — Engineering gates (2026-10-18)

**Not approved to run against production.** This document describes an offline
encrypted chunk format and synthetic VPS transfer rehearsal, NOT proof that any
live site has been backed up or restored.

## Observed blockers

* GitHub Actions → pinned VPS relay → cPanel SSH works, but source-to-VPS pipes
  suffered an intermittent 16MiB stall after other successful runs.
* MySQL candidate metadata: 95 InnoDB tables, roughly 3.21 GB of data plus
  indexes. Django shared application directory is about 3.31 GB. Neither figure
  guarantees archive byte size, or full tenant/subsite inventory.
* GPGv2 prior backup has two incomplete encrypted partials, without signed final
  manifests. **Do not rename/accept partials as backups, overwrite them, or use
  their presence as proof of recoverability.**
* Production Passenger and some child sites share a Django root. MojPlayWin-only
  deployment isolation has not been verified. No automated production migrations,
  application restart, payment enablement or writes are allowed.

## Implemented (synthetic / experimental)

* `scripts/mojplaywin_transport_stage_diagnostic.py`: separate source and
  receiver SSH exit statuses, two bounded memory-only transport runs.
* `scripts/mojplaywin_chunked_encrypted_snapshot.py`: AES-256-GCM per chunk
  with independent random 96-bit nonces, snapshot-and-index bound AEAD data,
  SHA-256 checksums, HMAC-signed plan and final manifest. Completed pieces
  are authenticated on resume rather than retransmitted or replaced.
* `tests/test_mojplaywin_chunked_encrypted_snapshot.py`: fake-data roundtrip,
  interruption simulation, resume, tamper/wrong key, and overwrite rejection.
* `scripts/mojplaywin_synthetic_encrypted_chunk_relay.py`: VPS receives ONLY
  synthetic ciphertext; the ephemeral throwaway key remains on GitHub runner.
  Temporary VPS fixtures are deleted after the test.

## Required next release gates, in strict order

1. **Enumerate all live sites and all data owners.** Collect authoritative
   Passenger, Django, .htaccess, domain, alias, DB, upload, media, payment
   storage and dynamic routes. Validate with independent smoke tests. Never
   infer coverage from fixed app and docroot directory sizes.
2. **Produce a consistent MySQL snapshot.** Use a reviewed
   `--single-transaction --quick` capture of verified all-InnoDB tables,
   no global locks, no customer rows to GitHub logs. Establish what external
   file writes can happen concurrently and coordinate database/file snapshots.
   A source snapshot cannot be considered resumable until it is durably
   materialized at a private path and its content hash is stable.
3. **Encrypt at the source before retransmission.** No unencrypted personal
   data may be sent to the VPS or stored in GitHub Actions artifacts/logs.
   The offline chunking algorithm currently accepts an existing source file;
   source-side snapshot creation/encryption and VPS transport are NOT yet
   integrated for real tenant data.
4. **Resume only immutable verified ciphertext.** Use authenticated
   per-chunk receipt, size/hash comparison, bandwidth throttling, retry
   bounds, partial manifest rejection, and atomic finalization. Stop on
   mismatches; do not reinterpret a new dump as the same snapshot.
5. **Key custody.** Random 256-bit recovery key and signed manifest must be
   protected and independently escrowed outside the VPS, with a documented
   replacement/recovery procedure; keys must never go into GitHub source,
   tool messages, chats, webroots, environment dumps or logs.
6. **Prove independent restoration.** Decrypt on an isolated, nonproduction
   GitHub runner with disposable database and private file sandbox, verify
   schemas/data counts, link boundaries, protected sites, and downloads.
   Repeat negative tests for missing parts, reordered chunks and wrong keys.
7. **Only then** design a host-scoped production deployment that does not
   modify/restart the Django runtime of any protected child site. Protect
   branch/release permissions and require human approval for any real
   money acceptance.
8. **Only after publication gates** configure the merchant-owned public
   ETH/TRX addresses, trusted full nodes, abuse protection, financial policy,
   and supervised very small real transactions.

## Security caveats

AES-GCM stage/verify/restore code is a development component, not a backup
service. It does not freeze the source DB, enumerate child sites, transport
any real production data, independently escrow decryption keys, or prove
production recovery. CI green is NOT release permission.

Both `MOJPLAYWIN_CRYPTO_ENABLED=False` and the disabled production deployment
workflow must remain in force. Keep crypto PR #473 draft and Issue #475 open.
