"""C-01 offline, fail-closed preflight for private book storefront packages.

No network, DB, wallet, SKU, publication or payment side effects. A passing
preflight is NOT evidence of a successful live transaction or publication.
"""
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

MAX_ARTIFACT_BYTES = 200 * 1024 * 1024
RELEASE_REFS = (
    "offhost_restore_ref", "rollback_drill_ref", "effective_db_ref",
    "mfa_csrf_ref", "trx_invoice_ref", "trx_payment_acceptance_ref",
    "entitlement_ref", "invoice_email_ref", "authorized_download_ref",
)


def _evidence(value):
    """Evidence references must be explicit nonempty strings, not booleans."""
    return isinstance(value, str) and 8 <= len(value.strip()) <= 256


def _artifact_ok(spec, root, suffix):
    if not isinstance(spec, dict):
        return False
    raw, digest = spec.get("path"), spec.get("sha256")
    if not isinstance(raw, str) or not isinstance(digest, str):
        return False
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        return False
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != suffix:
        return False
    try:
        resolved = (root / relative).resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            return False
        if resolved.stat().st_size == 0 or resolved.stat().st_size > MAX_ARTIFACT_BYTES:
            return False
        if suffix == ".docx":
            if not zipfile.is_zipfile(resolved):
                return False
            with zipfile.ZipFile(resolved) as archive:
                names = set(archive.namelist())
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                    return False
        elif suffix == ".pdf":
            with resolved.open("rb") as stream:
                if stream.read(5) != b"%PDF-":
                    return False
                stream.seek(max(0, resolved.stat().st_size - 2048))
                if b"%%EOF" not in stream.read():
                    return False
        checksum = hashlib.sha256()
        with resolved.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                checksum.update(chunk)
        return checksum.hexdigest() == digest
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile):
        return False


def assess(manifest, artifact_root):
    """Return non-sensitive, auditable evidence flags; never certify live sales."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    root = Path(artifact_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("artifact root must be a directory")
    artifacts = manifest.get("artifacts")
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    evidence = manifest.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    checks = {
        "word_sha256": _artifact_ok(artifacts.get("docx"), root, ".docx"),
        "pdf_sha256": _artifact_ok(artifacts.get("pdf"), root, ".pdf"),
        "rights_review_ref": _evidence(evidence.get("rights_review_ref")),
        "scientific_review_ref": _evidence(evidence.get("scientific_review_ref")),
        "author_approval_ref": _evidence(evidence.get("author_approval_ref")),
    }
    for name in RELEASE_REFS:
        checks[name] = _evidence(evidence.get(name))
    private_ready = all(checks[key] for key in (
        "word_sha256", "pdf_sha256", "rights_review_ref", "scientific_review_ref"))
    author_approved = private_ready and checks["author_approval_ref"]
    commerce_ready = author_approved and all(checks[name] for name in RELEASE_REFS)
    return {
        "schema_version": "C01-2026-11-01-v1",
        "package_id": str(manifest.get("package_id", ""))[:80],
        "checks": checks,
        "states": {
            "PRIVATE_READY": bool(private_ready),
            "AUTHOR_APPROVED": bool(author_approved),
            "JOURNAL_SUBMITTED_RECEIPT": False,
            "STORE_LIVE_VERIFIED": False,
            "BLOCKED": not bool(commerce_ready),
        },
        "commerce_preflight_ready": bool(commerce_ready),
        "missing_checks": [key for key, ok in checks.items() if not ok],
        "note": "Offline document preflight only. References are not independently authenticated; no live purchase, delivery, journal submission or publication is certified.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Private JSON manifest; never commit private evidence")
    parser.add_argument("--artifact-root", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        with args.manifest.open("r", encoding="utf-8") as stream:
            manifest = json.load(stream)
        result = assess(manifest, args.artifact_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "decision": "BLOCKED"}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["commerce_preflight_ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
