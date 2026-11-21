# C-01 private publication handoff gate — v1

**Scope:** books (including Mushroom EN Volumes I/II) and articles. This is an **offline, read-only** gate for the exact B-01/R-01 handoff; it never creates SKUs, modifies a store, sends email, files a journal submission, processes TRX, or starts VPS workers. No owner documents or approval keys belong in GitHub.

## Private manifest format

Store the following as `manifest.json` **outside the repository**, in a private directory alongside the referenced files. Replace illustrative digests with the **actual** SHA-256 of each file; all paths must be relative to `--root` and must not contain symlinks.

```json
{
  "schema_version": 1,
  "kind": "book",
  "id": "MUSHROOM-EN-V1",
  "artifacts": {
    "docx": {"path": "book/volume.docx", "sha256": "<actual 64 lowercase hex characters>"},
    "pdf": {"path": "book/volume.pdf", "sha256": "<actual 64 lowercase hex characters>"}
  },
  "evidence": {
    "review": {"decision": "passed", "file": {"path": "evidence/review.txt", "sha256": "<actual digest>"}},
    "rights": {"decision": "cleared", "file": {"path": "evidence/rights.txt", "sha256": "<actual digest>"}}
  }
}
```

For `AUTHOR_APPROVED`, an independent owner-provisioned HMAC key (32+ random bytes, permission mode `0600`) must verify the author approval receipt bound to **the exact document digests and publication ID**. `author_approval` has `decision: "approved"`, a `file` record and `hmac_sha256` calculated over the canonical JSON payload `{"approval_receipt": SHA256_OF_RECEIPT, "docx": SHA256_OF_DOCX, "id": PUBLICATION_ID, "pdf": SHA256_OF_PDF}` (serialized with sorted keys and compact separators). A receipt without a trusted key does **not** produce `AUTHOR_APPROVED`. Key provenance and the author's real consent must be verified outside this program; HMAC alone is not a legal signature or proof of authorship.

Run on an authorized private machine:

```bash
python3 -B scripts/c01_private_publication_gate.py /private/publishing/manifest.json --root /private/publishing
# Optional, only after owner-authorized key provisioning and receipt verification:
python3 -B scripts/c01_private_publication_gate.py /private/publishing/manifest.json --root /private/publishing --approval-key-file /private/keys/author-approval.key
```

Exit code `0`: `PRIVATE_READY` or cryptographically authenticated `AUTHOR_APPROVED`; exit code `2`: `BLOCKED`. Output contains publication ID, verified artifact digests, missing gates and zero-action assertions, not private file paths or document contents. A `PRIVATE_READY` result is **not** author approval or a storefront release.

`JOURNAL_SUBMITTED_RECEIPT` and `STORE_LIVE_VERIFIED` are deliberately **never** emitted by this offline gate. Those states require independent journal/checkout/entitlement/invoice/email/download acceptance and actual external receipts under the responsible workstream, plus rollback, DB identity, rights and backup verification. Never promote a release from a test, PR, or stage result. Use separate manifests for each volume or article.

Regression: `python3 -B -m unittest discover -s tests -p test_c01_private_publication_gate.py -v`. The existing repository CI also collects the tests with pytest. No deployment workflow or production database is touched.
