#!/usr/bin/env python3
"""C-01 offline publication handoff gate; no storefront or journal side effects.

A verified SHA-256 establishes byte identity, NOT scientific merit, ownership,
validity of a signature, journal submission, payment, or customer acceptance.
The tool intentionally never returns JOURNAL_SUBMITTED_RECEIPT or
STORE_LIVE_VERIFIED; those require independent external evidence.
"""
import argparse
import hashlib
import hmac
import json
import os
import re
import stat
import sys
import zipfile
from pathlib import Path

MAX_BYTES = 200 * 1024 * 1024
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
EVIDENCE_DECISIONS = {"review": "passed", "rights": "cleared", "author_approval": "approved"}


class GateError(ValueError):
    pass


def _read_json(path):
    if path.is_symlink() or not path.is_file():
        raise GateError("MANIFEST_MISSING_OR_SYMLINK")
    if path.stat().st_size > 65536:
        raise GateError("MANIFEST_TOO_LARGE")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError):
        raise GateError("MANIFEST_INVALID_JSON")
    if not isinstance(result, dict):
        raise GateError("MANIFEST_NOT_OBJECT")
    return result


def _safe_file(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative:
        raise GateError("PATH_INVALID")
    path = Path(relative)
    if path.is_absolute() or any(part in (".", "..") for part in path.parts):
        raise GateError("PATH_ESCAPE_BLOCKED")
    target = root
    for part in path.parts:
        target = target / part
        if target.is_symlink():
            raise GateError("SYMLINK_BLOCKED")
    if not target.is_file():
        raise GateError("FILE_MISSING")
    info = target.stat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_BYTES:
        raise GateError("FILE_TYPE_OR_SIZE_BLOCKED")
    if not str(target.resolve()).startswith(str(root.resolve()) + os.sep):
        raise GateError("PATH_ESCAPE_BLOCKED")
    return target


def _verify(root, record, kind=None):
    if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
        raise GateError("RECORD_SCHEMA_INVALID")
    expected = record["sha256"]
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        raise GateError("SHA256_INVALID")
    path = _safe_file(root, record["path"])
    h = hashlib.sha256()
    with path.open("rb") as stream:
        header = stream.read(8)
        stream.seek(0)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != expected:
        raise GateError("SHA256_MISMATCH")
    if kind == "pdf":
        if not header.startswith(b"%PDF-"):
            raise GateError("PDF_SIGNATURE_INVALID")
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 2048))
            if b"%%EOF" not in stream.read():
                raise GateError("PDF_EOF_INVALID")
    elif kind == "docx":
        if not zipfile.is_zipfile(str(path)):
            raise GateError("DOCX_CONTAINER_INVALID")
        with zipfile.ZipFile(str(path)) as archive:
            names = set(archive.namelist())
            if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                raise GateError("DOCX_STRUCTURE_INVALID")
            if archive.testzip() is not None:
                raise GateError("DOCX_CRC_INVALID")
    return expected


def evaluate(manifest, root, approval_key=None):
    """Return privacy-safe gate result; no writes, external calls, or side effects."""
    if manifest.get("schema_version") != 1 or manifest.get("kind") not in ("book", "article"):
        raise GateError("SCHEMA_VERSION_OR_KIND_INVALID")
    ident = manifest.get("id")
    if not isinstance(ident, str) or not IDENTIFIER.fullmatch(ident):
        raise GateError("IDENTIFIER_INVALID")
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise GateError("ROOT_INVALID")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {"docx", "pdf"}:
        raise GateError("ARTIFACT_SET_INCOMPLETE")
    verified = {}
    for kind in ("docx", "pdf"):
        verified[kind] = _verify(root, artifacts[kind], kind)
    evidence = manifest.get("evidence", {})
    if not isinstance(evidence, dict) or set(evidence) - set(EVIDENCE_DECISIONS):
        raise GateError("EVIDENCE_SCHEMA_INVALID")
    missing = []
    authenticated_author = False
    for key, decision in EVIDENCE_DECISIONS.items():
        item = evidence.get(key)
        if item is None:
            missing.append(key)
            continue
        fields = {"decision", "file", "hmac_sha256"} if key == "author_approval" else {"decision", "file"}
        if not isinstance(item, dict) or set(item) != fields:
            raise GateError("EVIDENCE_RECORD_INVALID")
        receipt_digest = _verify(root, item["file"])
        if item["decision"] != decision:
            missing.append(key)
        elif key == "author_approval":
            if not isinstance(item["hmac_sha256"], str) or not SHA256.fullmatch(item["hmac_sha256"]):
                raise GateError("AUTHOR_APPROVAL_SIGNATURE_INVALID")
            if approval_key is None:
                missing.append("author_approval_trusted_key")
            else:
                if not isinstance(approval_key, bytes) or len(approval_key) < 32:
                    raise GateError("APPROVAL_KEY_INVALID")
                payload = json.dumps({"id": ident, "docx": verified["docx"],
                                      "pdf": verified["pdf"], "approval_receipt": receipt_digest},
                                     sort_keys=True, separators=(",", ":")).encode("utf-8")
                signature = hmac.new(approval_key, payload, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(signature, item["hmac_sha256"]):
                    raise GateError("AUTHOR_APPROVAL_SIGNATURE_MISMATCH")
                authenticated_author = True
    # Owner-managed key is provisioned privately, never from the manifest/repository.
    ready = not any(x in missing for x in ("review", "rights"))
    status = "BLOCKED" if not ready else ("AUTHOR_APPROVED" if authenticated_author else "PRIVATE_READY")
    return {"id": ident, "kind": manifest["kind"], "status": status,
            "verified_artifact_sha256": verified, "missing_gates": missing,
            "journal_submitted_receipt": False, "store_live_verified": False,
            "financial_actions": 0, "external_actions": 0,
            "note": "Offline byte/evidence verification only; no live or submission attestation."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="Private JSON manifest path")
    parser.add_argument("--root", required=True, help="Private directory containing artifacts and evidence")
    parser.add_argument("--approval-key-file", help="Owner-provisioned private HMAC key (mode 0600), optional")
    args = parser.parse_args(argv)
    try:
        key = None
        if args.approval_key_file:
            keypath = Path(args.approval_key_file)
            if keypath.is_symlink() or not keypath.is_file() or keypath.stat().st_mode & 0o077:
                raise GateError("APPROVAL_KEY_FILE_PERMISSIONS_BLOCKED")
            if not 32 <= keypath.stat().st_size <= 4096:
                raise GateError("APPROVAL_KEY_FILE_SIZE_BLOCKED")
            key = keypath.read_bytes()
        report = evaluate(_read_json(Path(args.manifest)), Path(args.root), approval_key=key)
    except (GateError, OSError, zipfile.BadZipFile) as exc:
        # No filesystem paths or exception details in public logs.
        report = {"status": "BLOCKED", "reason": str(exc) if isinstance(exc, GateError) else "FILE_READ_FAILED",
                  "financial_actions": 0, "external_actions": 0}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] in ("PRIVATE_READY", "AUTHOR_APPROVED") else 2


if __name__ == "__main__":
    sys.exit(main())
