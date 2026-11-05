#!/usr/bin/env python3
"""Read-only VPS probe of the existing F01 manufactured archive.

The seven expected SHA-256 values are supplied by a reviewed GitHub checkout,
not by any manifest on the VPS. This script never creates an evidence receipt,
modifies a product dossier, or grants release approval.
"""

import hashlib
import json
from pathlib import Path
import re
import stat
import sys
import zipfile


PRODUCT = "farm_enterprise_economics"
FILES = (
    "calculator.py", "guided_start.py", "test_calculator.py",
    "test_guided_start.py", "README.md", "CUSTOMER_GUIDE.md",
    "example_inputs.json",
)
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
ROOT = Path.home() / "factory-runtime/private/autonomous-product-cycle"
MAX_ARCHIVE = 25 * 1024 * 1024
MAX_UNPACKED = 40 * 1024 * 1024


def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_file(path, limit):
    if path.is_symlink() or not path.is_file():
        return False
    info = path.stat()
    return stat.S_ISREG(info.st_mode) and 0 < info.st_size <= limit


def json_object(path):
    if not safe_file(path, 500_000):
        raise ValueError("MISSING_OR_UNSAFE_MANIFEST")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("MANIFEST_NOT_OBJECT")
    return data


def probe(base, hashes):
    result = {
        "schema": "saeit.factory.f01-exact-zip-readonly.v1",
        "read_only": True,
        "product_id": PRODUCT,
        "manifest_present": False,
        "zip_present": False,
        "zip_sha256": None,
        "manifest_artifact_sha_matches": False,
        "seven_source_files_match_reviewed_commit": False,
        "missing_or_mismatched_source_files": list(FILES),
        "candidate_import_claim_present": False,
        "attached_eight_receipts_cryptographically_verified": False,
        "quality_1000_approved": False,
        "commercial_release_allowed": False,
        "error": None,
    }
    folder = base / "digital-products" / PRODUCT
    if any(path.is_symlink() for path in (base, folder, folder.parent)):
        result["error"] = "UNSAFE_PRODUCT_FOLDER_SYMLINK"
        return result
    if not folder.is_dir():
        result["error"] = "PRODUCT_FOLDER_MISSING"
        return result
    manifest_path = folder / "manufacturing_manifest.json"
    archive_path = folder / (PRODUCT + "-internal-qa.zip")
    result["manifest_present"] = safe_file(manifest_path, 500_000)
    result["zip_present"] = safe_file(archive_path, MAX_ARCHIVE)
    if not result["manifest_present"] or not result["zip_present"]:
        result["error"] = "PRODUCT_MANIFEST_OR_ZIP_MISSING_UNSAFE"
        return result
    try:
        manifest = json_object(manifest_path)
        actual_sha = file_sha(archive_path)
        result["zip_sha256"] = actual_sha
        result["manifest_sha256"] = file_sha(manifest_path)
        result["manifest_artifact_sha_matches"] = (
            manifest.get("recipe") == PRODUCT
            and manifest.get("qa_status") == "passed"
            and manifest.get("commercial_status") == "private_internal_qa_pass_not_published"
            and manifest.get("public_listing_enabled") is False
            and manifest.get("owner_publication_approval") is False
            and actual_sha == manifest.get("artifact_sha256")
        )
        mismatched = []
        with zipfile.ZipFile(archive_path) as bundle:
            members = bundle.infolist()
            if not 0 < len(members) <= 100:
                raise ValueError("ZIP_MEMBER_COUNT_UNSAFE")
            seen = set()
            total = 0
            for member in members:
                name = member.filename
                mode = member.external_attr >> 16
                if (member.is_dir() or member.flag_bits & 1 or
                        (mode & 0o170000) == 0o120000 or name in seen or
                        not name.startswith(PRODUCT + "/") or
                        any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", part)
                            or part in (".", "..") for part in name.split("/"))):
                    raise ValueError("ZIP_MEMBER_UNSAFE")
                seen.add(name)
                total += member.file_size
                if member.file_size > MAX_ARCHIVE or total > MAX_UNPACKED:
                    raise ValueError("ZIP_UNPACKED_SIZE_UNSAFE")
            if bundle.testzip() is not None:
                raise ValueError("ZIP_CRC_FAILURE")
            for filename, expected in zip(FILES, hashes):
                member_name = PRODUCT + "/" + filename
                if member_name not in seen or hashlib.sha256(
                    bundle.read(member_name)
                ).hexdigest() != expected:
                    mismatched.append(filename)
        result["missing_or_mismatched_source_files"] = mismatched
        result["seven_source_files_match_reviewed_commit"] = (
            result["manifest_artifact_sha_matches"] and not mismatched
        )
        candidate_path = folder / "global_quality_candidate.json"
        if safe_file(candidate_path, 500_000):
            candidate = json_object(candidate_path)
            evidence_import = candidate.get("f01_technical_evidence_import")
            result["candidate_import_claim_present"] = (
                candidate.get("recipe") == PRODUCT
                and isinstance(evidence_import, dict)
                and evidence_import.get("actual_manufactured_zip_source_verified") is True
                and isinstance(evidence_import.get("manifest_sha256"), str)
                and bool(SHA256.fullmatch(evidence_import["manifest_sha256"]))
            )
    except (OSError, UnicodeError, ValueError, KeyError, zipfile.BadZipFile,
            RuntimeError) as exc:
        result["error"] = type(exc).__name__ + ":" + str(exc)[:80]
    return result


def main():
    if len(sys.argv) != len(FILES) + 1 or any(
        not SHA256.fullmatch(value) for value in sys.argv[1:]
    ):
        raise SystemExit("F01_PROBE_EXPECTED_SOURCE_HASHES_INVALID")
    result = probe(ROOT, sys.argv[1:])
    print("F01_ZIP_READONLY_PROBE=" + json.dumps(result, sort_keys=True))
    print("F01_EXACT_MANUFACTURED_SOURCE_BOUND=" + str(
        result["seven_source_files_match_reviewed_commit"]
    ).lower())
    print("F01_EIGHT_RECEIPTS_ATTACHED_AND_VERIFIED=NOT_PROVEN")
    print("F01_COMMERCIAL_RELEASE=FALSE")


if __name__ == "__main__":
    main()
