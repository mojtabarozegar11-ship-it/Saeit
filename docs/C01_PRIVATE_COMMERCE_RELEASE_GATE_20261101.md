# C-01 — Private book / storefront release preflight (2026-11-01)

This is a **standalone, offline, fail-closed tool**. It is for the two English mushroom volumes and other books only after B-01 supplies a real versioned Word/PDF bundle, rights evidence, scientific review and author decision. It does **not** publish, create a live SKU, send email, move money, touch a database, contact a wallet, restart the VPS factory or claim live acceptance.

## Run (private machine or authorized staging only)

```bash
python scripts/c01_release_gate.py /private/volume-release-manifest.json --artifact-root /private/book-package
python -m unittest tests.test_c01_release_gate -v
```

Keep the manifest and evidence **outside public GitHub**. The tool prints only non-sensitive flags, never the underlying evidence references. Exit code 2 means blocked; exit code 0 means **documented preflight only**, never permission to deploy.

## Manifest structure (schema v1)

```json
{
  "package_id": "PRIVATE-BOOK-PACKAGE-ID",
  "artifacts": {
    "docx": {"path": "volume.docx", "sha256": "64-lowercase-hex-characters"},
    "pdf": {"path": "volume.pdf", "sha256": "64-lowercase-hex-characters"}
  },
  "evidence": {
    "rights_review_ref": "PRIVATE_REFERENCE_TO_RIGHTS_REVIEW",
    "scientific_review_ref": "PRIVATE_REFERENCE_TO_FINAL_REVIEW",
    "author_approval_ref": "PRIVATE_REFERENCE_TO_AUTHOR_DECISION",
    "offhost_restore_ref": "PRIVATE_REFERENCE_TO_TESTED_OFFHOST_RESTORE",
    "rollback_drill_ref": "PRIVATE_REFERENCE_TO_TESTED_ROLLBACK",
    "effective_db_ref": "PRIVATE_REFERENCE_TO_EFFECTIVE_DB_CHECK",
    "mfa_csrf_ref": "PRIVATE_REFERENCE_TO_LOGIN_SECURITY_CHECK",
    "trx_invoice_ref": "PRIVATE_REFERENCE_TO_INVOICE_ACCEPTANCE",
    "trx_payment_acceptance_ref": "PRIVATE_REFERENCE_TO_AUTHORIZED_TRX_ACCEPTANCE",
    "entitlement_ref": "PRIVATE_REFERENCE_TO_ENTITLEMENT_ACCEPTANCE",
    "invoice_email_ref": "PRIVATE_REFERENCE_TO_EMAIL_ACCEPTANCE",
    "authorized_download_ref": "PRIVATE_REFERENCE_TO_DOWNLOAD_ACCEPTANCE"
  }
}
```

Replace all examples with actual private, auditable references and real SHA256 hashes. The script checks that Word is a DOCX container with the required entries and PDF has PDF markers; it checks both SHA256 values against local files, rejects paths outside the authorized artifact root, and rejects missing evidence. It does **not** render Word/PDF, verify source copyright, authenticate author identity, validate evidence content or independently check TRX payment. These remain separate human/technical acceptance gates.

The output separates `PRIVATE_READY`, `AUTHOR_APPROVED`, `JOURNAL_SUBMITTED_RECEIPT`, `STORE_LIVE_VERIFIED`, and `BLOCKED`. The journal and live flags always remain false in this offline tool; only R-01 and an independent real-live verification may substantiate those states. A true `commerce_preflight_ready` is only a cue for a **separate authorized release review**.

C-01 must not use this tool to bypass CI, off-host backup restore, rollback, effective Passenger/PHP database checks, MFA, author approval, payment acceptance or the existing release owner. No live SKU or paid traffic until independent evidence proves the purchase/invoice/entitlement/email/download chain.
