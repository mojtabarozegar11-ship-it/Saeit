#!/usr/bin/env python3
"""Fail-closed, artifact-bound rights evidence gate for all new factory releases.

This verifies that a privately staged evidence package exists, is byte-bound to
the exact ZIP and all of its members, and carries separate trusted signatures
from an identity-verified rights reviewer and the owner. It does not determine
whether a contract is legally valid or authenticate its signatories beyond the
configured trust registry.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import zipfile

HEX = re.compile(r"^[a-f0-9]{64}$")
SCHEMA = "saeit.factory.product-rights-manifest.v1"
DECISION_SCHEMA = "saeit.factory.product-rights-clearance.v1"
MAX_MEMBERS = 2500
MAX_TOTAL = 150 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_member(name):
    p = PurePosixPath(name) if isinstance(name, str) else None
    return bool(name and p and not name.startswith("/") and "\\" not in name
                and all(part not in ("", ".", "..") for part in p.parts))


def _archive_inventory(package):
    actual = {}
    total = 0
    try:
        with zipfile.ZipFile(package, "r") as archive:
            members = archive.infolist()
            if not members or len(members) > MAX_MEMBERS:
                raise ValueError("RIGHTS_ARCHIVE_MEMBER_LIMIT")
            for item in members:
                name = item.filename
                if (item.is_dir() or not _safe_member(name) or name in actual
                        or ((item.external_attr >> 16) & 0o170000) == 0o120000):
                    raise ValueError("RIGHTS_ARCHIVE_MEMBER_UNSAFE")
                if item.file_size < 0 or total + item.file_size > MAX_TOTAL:
                    raise ValueError("RIGHTS_ARCHIVE_SIZE_INVALID")
                data = archive.read(item)
                total += len(data)
                if len(data) != item.file_size or total > MAX_TOTAL:
                    raise ValueError("RIGHTS_ARCHIVE_SIZE_INVALID")
                actual[name] = {"path": name, "sha256": hashlib.sha256(data).hexdigest(),
                                "size": len(data)}
    except (zipfile.BadZipFile, OSError, EOFError) as exc:
        raise ValueError("RIGHTS_ARCHIVE_INVALID") from exc
    return actual


def require_rights_clearance(inbox, recipe, artifact_sha256, package_path,
                             *, commercial_distribution=False):
    if (not isinstance(recipe, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,65}", recipe)
            or not isinstance(artifact_sha256, str) or not HEX.fullmatch(artifact_sha256)):
        raise ValueError("RIGHTS_PRODUCT_IDENTITY_INVALID")
    package = Path(package_path)
    if (package.is_symlink() or not package.is_file()
            or digest_file(package) != artifact_sha256):
        raise ValueError("RIGHTS_ARTIFACT_HASH_MISMATCH")

    root = Path(inbox)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("RIGHTS_PRIVATE_INBOX_INVALID")
    directory = root / "rights-clearance" / recipe / artifact_sha256
    manifest_path = directory / "rights-manifest.json"
    decision_path = directory / "signed-clearance.json"
    registry_path = root / "quality-trust" / "trusted-reviewers.json"
    approval_path = Path(__file__).resolve().with_name("factory_quality_signed_approval_v1.py")
    evidence_root = root / "rights-evidence"
    if (directory.is_symlink()
            or (root / "rights-clearance").is_symlink()
            or (root / "quality-trust").is_symlink()
            or evidence_root.is_symlink()):
        raise ValueError("RIGHTS_PRIVATE_EVIDENCE_PATH_UNSAFE")
    for path in (manifest_path, decision_path, registry_path, approval_path):
        if path.is_symlink() or not path.is_file():
            raise ValueError("RIGHTS_CLEARANCE_EVIDENCE_MISSING")
    if manifest_path.stat().st_size > 2_000_000 or decision_path.stat().st_size > 500_000:
        raise ValueError("RIGHTS_CLEARANCE_EVIDENCE_TOO_LARGE")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        receipt = json.loads(decision_path.read_text(encoding="utf-8"))
        trust = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("RIGHTS_CLEARANCE_EVIDENCE_INVALID_JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ValueError("RIGHTS_MANIFEST_SCHEMA_INVALID")
    if (manifest.get("recipe") != recipe
            or manifest.get("artifact_sha256") != artifact_sha256
            or manifest.get("public_distribution") is not True
            or not isinstance(manifest.get("territory"), str)
            or not manifest["territory"].strip()
            or not isinstance(manifest.get("term"), str)
            or not manifest["term"].strip()):
        raise ValueError("RIGHTS_MANIFEST_SCOPE_OR_VERSION_INVALID")
    if commercial_distribution and manifest.get("commercial_distribution") is not True:
        raise ValueError("COMMERCIAL_DISTRIBUTION_RIGHTS_NOT_GRANTED")

    actual = _archive_inventory(package)
    components = manifest.get("components")
    if not isinstance(components, list) or len(components) != len(actual):
        raise ValueError("RIGHTS_COMPONENT_INVENTORY_INCOMPLETE")
    seen = set()
    for row in components:
        if (not isinstance(row, dict)
                or set(row) != {"path", "sha256", "size", "rights_holder", "rights_basis",
                                "evidence_sha256"}
                or not isinstance(row.get("path"), str)
                or not isinstance(row.get("sha256"), str)
                or not HEX.fullmatch(row["sha256"])
                or type(row.get("size")) is not int or row["size"] < 0
                or not isinstance(row.get("rights_holder"), str) or not row["rights_holder"].strip()
                or not isinstance(row.get("rights_basis"), str) or not row["rights_basis"].strip()
                or not isinstance(row.get("evidence_sha256"), list) or not row["evidence_sha256"]):
            raise ValueError("RIGHTS_COMPONENT_RECORD_INVALID")
        name = row["path"]
        if name in seen or actual.get(name) != {
                "path": name, "sha256": row["sha256"], "size": row["size"]}:
            raise ValueError("RIGHTS_COMPONENT_HASH_MISMATCH")
        seen.add(name)
        for evidence_sha in row["evidence_sha256"]:
            if not isinstance(evidence_sha, str) or not HEX.fullmatch(evidence_sha):
                raise ValueError("RIGHTS_EVIDENCE_HASH_INVALID")
            evidence = evidence_root / (evidence_sha + ".pdf")
            if (evidence.is_symlink() or not evidence.is_file()
                    or digest_file(evidence) != evidence_sha):
                raise ValueError("RIGHTS_SOURCE_DOCUMENT_MISSING_OR_HASH_MISMATCH")
    if seen != set(actual):
        raise ValueError("RIGHTS_COMPONENT_INVENTORY_INCOMPLETE")

    manifest_sha = hashlib.sha256(canonical(manifest)).hexdigest()
    if not isinstance(receipt, dict):
        raise ValueError("RIGHTS_DECISION_INVALID")
    signed = receipt.get("decision")
    if (receipt.get("schema") != DECISION_SCHEMA or not isinstance(signed, dict)
            or signed.get("recipe") != recipe
            or signed.get("artifact_sha256") != artifact_sha256
            or signed.get("manifest_sha256") != manifest_sha
            or signed.get("decision") != "approved_for_public_distribution"
            or signed.get("commercial_distribution") is not manifest.get("commercial_distribution")):
        raise ValueError("RIGHTS_DECISION_NOT_BOUND_TO_ARTIFACT_AND_MANIFEST")
    spec = importlib.util.spec_from_file_location("factory_rights_signed_approval", str(approval_path))
    if spec is None or spec.loader is None:
        raise ValueError("RIGHTS_SIGNATURE_VERIFIER_UNAVAILABLE")
    approval = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(approval)
    try:
        keys = approval.validate_key_registry(trust)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("RIGHTS_TRUST_REGISTRY_INVALID") from exc
    signers = {}
    payload = canonical(signed)
    for row in receipt.get("approvals", []):
        if not isinstance(row, dict) or set(row) != {"reviewer_id", "role", "signature_hex"}:
            continue
        signer = row["reviewer_id"]
        if signer in signers or signer not in keys or row["role"] != keys[signer].get("role"):
            continue
        if row["role"] not in ("rights_reviewer", "owner"):
            continue
        if approval.verify_sig(keys[signer]["public_key_pem"], payload, row["signature_hex"]):
            signers[signer] = row["role"]
    if set(signers.values()) != {"rights_reviewer", "owner"}:
        raise ValueError("RIGHTS_REVIEWER_AND_OWNER_SIGNATURES_REQUIRED")
    return {"status": "VERIFIED_SIGNED_ARTIFACT_RIGHTS",
            "artifact_sha256": artifact_sha256,
            "manifest_sha256": manifest_sha,
            "component_count": len(actual),
            "rights_reviewer_and_owner_signed": True,
            "commercial_distribution": manifest.get("commercial_distribution") is True}


if __name__ == "__main__":
    raise SystemExit("Import require_rights_clearance from the release gate.")
