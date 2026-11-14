# P0 — Owner-only, real private file byte evidence for MojPlayWin (2026-11-14)

**Code-level capability, not production deployment or payment/delivery approval.**
The sole organization agent remains \`mojtaba.bot.ai\`.

## Why this is a real missing revenue prerequisite

Earlier delivery preflight checked that Product.metadata contained strings that
*resembled* SHA-256 hashes, without reading any private file bytes. A missing,
replaced, corrupted, symlinked or world-readable PDF could therefore pass the
metadata-only source gate. The buyer still cannot receive a usable product
simply because the metadata is syntactically valid.

This branch adds a **separately approved, bounded, read-only byte-and-manifest
inspection** to the existing \`EconomicMasterAgent\`. It does **not** enable
customer checkout or download.

## User-visible acceptance contract

1. Existing owner-private files are under a separately configured absolute
   \`MPW_PRIVATE_DELIVERY_ROOT\`; the directory must be owned by the runner's
   effective account and permit **no group/other access** (typically 0700).
2. \`MPW_PRIVATE_ASSET_AUDIT_APPROVED\` defaults to absent/false. An authorized
   operator must separately approve and explicitly enable it for a manual
   local audit. There is no customer-facing or remote endpoint.
3. Accept only product IDs that are integers 1..2147483647, and only active
   products owned by an active staff+superuser seller. A private byte check
   is NOT a substitute for product rights or settlement evidence.
4. Accept only metadata \`delivery_format\` in \`pdf\`, \`epub\`, \`zip\`;
   license keys and cosmetic entitlements are **different** evidence contracts
   and are never forced to have fake binary files.
5. A strict asset reference such as \`asset_1234567890123456\` points to only:
   \`<ref>.pdf\` (or \`.epub\` / \`.zip\`) and
   \`<ref>.manifest.json\`, **inside the private root**. Never allow URLs,
   absolute filenames, path separators, traversal or public asset guessing.
6. Both leaf files must be regular, non-symlink, single-link, owned by the
   runner account, and inaccessible to group/others (normally mode 0600).
   Open by a validated directory FD using \`O_NOFOLLOW\` and \`dir_fd\`;
   close all FDs on all paths.
7. Bound assets to 128 MiB and manifests to 8192 bytes. Stream the asset
   in 64 KiB blocks, fail if size or inode/mode/mtime/ctime change during read.
8. Check a **minimal claimed format signature** (\`%PDF-\` or ZIP header);
   this does not prove safe content, PDF validity or EPUB packaging.
9. The exact SHA256 bytes of both files must match the separate nonzero,
   lower-case SHA256 digests in Product metadata, and the two digests must
   be distinct.
10. The JSON manifest must use strict UTF-8, reject duplicate keys,
    \`NaN\`/\`Infinity\`, unknown fields, nested payloads and invalid schema.
    Its exact six keys and values must bind the asset ref, format, version,
    file SHA and byte size to the metadata and file just read.
11. Metadata must retain explicit rights clearance, independent QC review
    and buyer terms, each literally boolean true. These are still
    **self-asserted source flags**, NOT legal proof.
12. Return only a fixed-category, anonymized report. No paths, order IDs,
    buyer identities, customer emails, file bytes, provider references,
    source snippets, secret keys or download links are displayed.
13. The report must always say:
    \`delivery_allowed=false\`,
    \`independent_settlement_verified=false\`,
    \`buyer_email_verified=false\`,
    \`rights_independently_verified=false\`,
    \`customer_download_receipt_verified=false\`.
    Even a file-byte MATCH is only a local read-time observation and **must
    never** be labelled a paid sale, final settlement or delivery receipt.
14. No writes, file moves, file deletion, order edits, customer notifications,
    key issuance, downloads, token grants, transaction broadcasts, network
    calls, paid model use or new bot are added in this branch.
15. A manual audit invocation *after individual owner approval* is:
    \`python manage.py mojtaba_private_asset_readonly --product-id <internal-number>\`.
    The CLI returns JSON with fixed reasons only. No roots/paths are CLI args.
    This branch does NOT set either Django setting or invoke this command live.

### Manifest schema (synthetic example only)

~~~json
{
  "schema": "mojtaba.private-asset.v1",
  "asset_ref": "asset_1234567890123456",
  "format": "pdf",
  "version": "1.0.0",
  "asset_sha256": "<lower-case SHA256 of real private PDF bytes>",
  "asset_size": 12345
}
~~~

The SHA256 of the *exact* on-disk manifest JSON bytes is stored separately
under Product.metadata \`delivery_manifest_sha256\`. This is a file-integrity
assertion relative to stored metadata, **not a trusted third-party signature**.

## Evidence, limits, production release

- Branch is stacked on the already verified #2290 format-aware Draft, and
  inherits its requirements and security controls.
- Pure offline tests in \`tests/test_mojtaba_private_asset_bytes_20261114.py\`
  cover symlink/hardlink/permissions, byte/manifest hash tampering,
  malformed JSON and payload limits. Django tests in
  \`core/tests/test_mojtaba_private_asset_owner_gate_20261114.py\`
  prove disabled-by-default approval, seller ownership and no writes.
- Exact-head CI must finish successfully **before** this work is represented
  as source-tested. Unit tests use only synthetic temporary files and isolated
  Django test database.
- This patch does NOT prove the real cPanel/Passenger application root, the
  existence or safety of a commercial product, independent TRX settlement,
  legally-cleared third-party rights, buyer identity, a download token
  or a customer delivery receipt. Further approved integration is required.
- An independently authorized release must separately verify backups, active
  hosting source SHA, routing, legal rights and exact delivery contract.
  **NO-GO for live fulfillment or income claims.**
