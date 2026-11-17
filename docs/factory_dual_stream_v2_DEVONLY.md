# F01V2 — source-only dual-Drive encrypted streaming transport

**Status: DEV-ONLY / NO COMMERCIAL RELEASE / NO DATA UPLOADED.**

This package is a complete, standalone Python encryption/read-back/isolated-decryption module and its 40 independent synthetic unit tests. It does **not** include Google Drive OAuth upload adapters, a production-compatible MySQL/MariaDB snapshot implementation, owner-held private key custody, cloud quota verification, a consistency proof, or an independently restored current factory database.

It addresses one precisely observed deficiency in the legacy F-01 workflow: `scripts/f01_encrypted_stream_v1.py` accepts only a regular file no larger than 3 GiB, while the legacy GitHub workflow staged an entire compressed archive on a hosted runner before encrypting local chunks. The current cPanel MariaDB footprint is ~16.68 GB, and neither large on-host staging nor unapproved paid hosted runner execution is acceptable.

## Design

- Reads a **binary stream** (intended future source: a separately authenticated consistent `mariadb-dump` plus app/media archive piped through a verified compressor), with bounded buffer chunks of 4 MiB by default; no large plaintext filesystem file required by the encryptor.
- Uses a newly generated AES-256-GCM session key and fresh nonce prefix per archive. Each chunk is authenticated with a run ID, monotonic chunk index, final flag and plaintext length as associated data.
- Wraps the session key with the owner's **pre-approved RSA-3072+ public key** using OAEP-SHA256 and verifies a separately configured public-key SHA-256 fingerprint. The existing legacy F-01 public recipient can only be reused after its **matching private key and passphrase have been recovered and tested offline**. This package contains no actual keys.
- Requires two distinct private store owner identities and independent upload/read-back callbacks. Each encrypted part must pass **read-back byte SHA-256 equality in both destinations** before proceeding. The authenticated manifest is uploaded last. A receipt is returned only if both stores verified every ciphertext part and the final manifest. Uploaded partial ciphertext may remain after interrupted transfer: no deletion is performed.
- The public manifest contains no email identifiers (store identifiers are keyed pseudonyms), and explicitly records `source_consistency_external=false` and `restore_verified=false`.
- Supports offline isolated decryption to a **new, owner-only-permission file**, validating the manifest HMAC and every chunk's SHA-256/AES-GCM authentication before linking the finished file into place. Never overwrites an existing destination.

## Mandatory admission gates before touching the current factory

1. Establish provider-verified **actual** free quota for both Google Drive accounts; a free Google Account usually has **up to 15 GB shared** across Drive, Gmail and Photos. The present raw live MariaDB is 16.68 GB before application/media. A safe compressed ciphertext upper bound must be measured, including both full independent copies.
2. Verify the actual private RSA recovery key and password under owner custody **without ever disclosing either to GitHub, the assistant transcript, or a remote upload**; prove a decryption rehearsal on an isolated encrypted test fixture.
3. Verify actual MariaDB snapshot consistency and full application/media inventory, upstream data-change windows, external compression compatibility and a sufficiently sized isolated restoration machine (>23.83 GB for current MariaDB alone plus app/media).
4. Supply audited, authenticated Google Drive A/B *resumable* upload/read-back adapters with strict folder privacy, size quota admission, retries that do not replay/create contradictory terminal manifests, and independent provider account identity assertions. **No such adapters or OAuth tokens are included.**
5. Before treating a manifest as two independent backups, independently retrieve and compare both provider manifests/parts and actually restore the full source in an isolated environment. A manifest in only A does **not** prove dual redundancy.
6. Release paid prop funding is a separate legal/merchant/KYC/broker/capital/transaction-finality decision. No callback in this module handles any customer or payment data.

## Local synthetic verification

```
PYTHONPATH=scripts python -B -m unittest -v tests.test_factory_dual_stream_v2
```

At packaging time: **40/40 pass** with locally generated, ephemeral RSA keys and synthetic bytes (no real bank data). Correctness on a live MariaDB backup, Google Drive API and independent restore remains **unverified**.

## Files

- `scripts/factory_dual_stream_v2.py` — transport and offline restore source
- `tests/test_factory_dual_stream_v2.py` — 40 negative/positive synthetic tests
- `docs/factory_dual_stream_v2_DEVONLY.md` — actual scope and gates
- For isolated execution install the existing open-source Python package `cryptography>=41` only if already available or separately approved

**No costs, wallet/TRON transfers, orders, customer contacts, deletions of existing files, live site deploys or live DB writes.**
**Development-only branch:** `feature/factory-f01v2-direct-dual-offsite-devonly-20261117`. Not merged into `main` or deployed. The Python implementation has no cPanel/Drive adapter, so it cannot start a backup by itself.
