#!/usr/bin/env python3
"""Source-bound PRIVATE product identity declarations; NEVER a commercial license.

Person/roles are OWNER-DECLARED, not an independent authorship verification.
Each artifact revision receives its own immutable, mode-0600 sidecar.
No public listing, checkout, or payment code is touched. Python 3.8+.
"""
import hashlib
import json
import os
from pathlib import Path
import re

PERSON = "مجتبی روزگار"
ROLES = ("author", "researcher", "scientific_researcher", "compiler", "producer", "maker", "seller")
LABELS = ("نویسنده", "محقق", "پژوهشگر", "گردآورنده", "تهیه‌کننده", "سازنده", "فروشنده")
SCHEMA_VERSION = "2.0"
SHA = re.compile(r"^[0-9a-f]{64}$")
PRODUCT = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_passport(product_id, verified_roles=None, ownership=None, evidence=None,
                   source_sha256=None, artifact_sha256=None):
    """Keep declarations separate from verified provenance and financial splits."""
    if not isinstance(product_id, str) or not PRODUCT.fullmatch(product_id):
        raise ValueError("PASSPORT_PRODUCT_ID_INVALID")
    verified_roles = verified_roles or []
    if not isinstance(verified_roles, list) or any(role not in ROLES for role in verified_roles):
        raise ValueError("PASSPORT_VERIFIED_ROLE_INVALID")
    if verified_roles and (not isinstance(evidence, dict) or
                           any(not evidence.get(role) for role in verified_roles)):
        raise ValueError("PASSPORT_ROLE_EVIDENCE_REQUIRED")
    if ownership is not None:
        if (not isinstance(ownership, list) or not ownership or any(
                not isinstance(x, dict) or not isinstance(x.get("party"), str)
                or not x["party"].strip()
                or type(x.get("percent")) not in (int, float)
                or not 0 <= x["percent"] <= 100 for x in ownership)
                or abs(sum(x["percent"] for x in ownership) - 100) > 0.00001):
            raise ValueError("PASSPORT_OWNERSHIP_SHARES_INVALID")
    for digest in (source_sha256, artifact_sha256):
        if digest is not None and (not isinstance(digest, str) or not SHA.fullmatch(digest)):
            raise ValueError("PASSPORT_SOURCE_BINDING_INVALID")
    return {
        "schema": "saeit.factory.private-product-passport.v2",
        "schema_version": SCHEMA_VERSION,
        "product_id": product_id,
        "source_sha256": source_sha256,
        "artifact_sha256": artifact_sha256,
        "visibility": "private_passport_only",
        "declared_person": PERSON,
        "declared_roles": dict(zip(ROLES, LABELS)),
        "declared_roles_evidence_status": "owner_statement_not_independently_verified",
        "verified_roles": verified_roles,
        "role_evidence": evidence or {},
        "economic_rights": ownership,
        "economic_rights_status": "pending_product_specific_evidence" if ownership is None else "declared_requires_signed_evidence",
        "sales_receipts_destination": "seller_personal_account_as_declared_unverified",
        "exclusive_sales_license": {
            "proposed_licensee": PERSON,
            "exclusive": True,
            "duration": "indefinite_until_contractual_termination",
            "cure_period_calendar_days": 15,
            "executed_agreement_verified": False,
        },
        "third_party_rights_cleared": False,
        "commercial_release_allowed": False,
        "public_store_role_display": False,
    }


def write_passport(path, passport):
    """Create only; reject overwrites and symlinks; preserve revision evidence."""
    target = Path(path)
    if target.parent.is_symlink() or not target.parent.is_dir():
        raise ValueError("PASSPORT_PRIVATE_DIRECTORY_UNSAFE")
    payload = (json.dumps(passport, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if target.exists() or target.is_symlink():
        if (target.is_symlink() or not target.is_file()
                or target.stat().st_mode & 0o077
                or target.read_bytes() != payload):
            raise ValueError("PASSPORT_EXISTING_EVIDENCE_MISMATCH")
        return "existing_verified"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(target), flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            target.unlink()
        except OSError:
            pass
        raise
    return "created"


def ensure_private_passport(product_directory, manifest):
    """Generate/validate one immutable private sidecar for this exact QA artifact."""
    folder = Path(product_directory)
    if folder.is_symlink() or not folder.is_dir() or not isinstance(manifest, dict):
        raise ValueError("PASSPORT_PRODUCT_DIRECTORY_UNSAFE")
    product_id = folder.name
    if (not PRODUCT.fullmatch(product_id) or manifest.get("recipe") != product_id
            or manifest.get("qa_status") != "passed"
            or manifest.get("commercial_status") != "private_internal_qa_pass_not_published"
            or manifest.get("public_listing_enabled") is not False
            or manifest.get("owner_publication_approval") is not False
            or manifest.get("price") is not None):
        raise ValueError("PASSPORT_PRODUCT_NOT_PRIVATE_QA_PASSED")
    source_sha = manifest.get("source_sha256")
    archive_sha = manifest.get("artifact_sha256")
    if not isinstance(archive_sha, str) or not SHA.fullmatch(archive_sha):
        raise ValueError("PASSPORT_ARTIFACT_SHA_INVALID")
    # Historical stock may lack an original-source digest. Such goods can
    # receive a clearly INCOMPLETE identity record, never rights clearance.
    source_missing = source_sha is None
    if not source_missing and (not isinstance(source_sha, str) or not SHA.fullmatch(source_sha)):
        raise ValueError("PASSPORT_SOURCE_SHA_MALFORMED")
    archive = folder / (product_id + "-internal-qa.zip")
    if (archive.is_symlink() or not archive.is_file() or not
            0 < archive.stat().st_size <= 25 * 1024 * 1024
            or sha256_file(archive) != archive_sha):
        raise ValueError("PASSPORT_ARTIFACT_SHA_MISMATCH")
    record = build_passport(product_id, source_sha256=source_sha, artifact_sha256=archive_sha)
    if source_missing:
        record["source_provenance_status"] = "missing_original_source_sha_must_rework"
    suffix = ".source_missing.private.json" if source_missing else ".private.json"
    path = folder / ("product_passport." + archive_sha + suffix)
    status = write_passport(path, record)
    # No modified public web content, store database, original ZIP, or payment state.
    return {"status": status, "product_id": product_id,
            "passport_file": path.name, "passport_sha256": sha256_file(path),
            "commercial_release_allowed": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Private QA passport for ONE local product")
    parser.add_argument("product_directory")
    args = parser.parse_args()
    folder = Path(args.product_directory)
    manifest_path = folder / "manufacturing_manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > 100000:
        raise ValueError("PASSPORT_MANIFEST_UNSAFE")
    doc = json.loads(manifest_path.read_text("utf-8"))
    result = ensure_private_passport(folder, doc)
    print("FACTORY_PRIVATE_PRODUCT_PASSPORT=" + json.dumps(result, sort_keys=True))
