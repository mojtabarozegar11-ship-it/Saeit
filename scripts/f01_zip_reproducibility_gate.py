#!/usr/bin/env python3
"""Verify two separately built F01 private candidate archives without publishing.

This is a technical repeatability/integrity check, not a professional quality
review, an external signature, or a commercial delivery authorization.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import zipfile


RECIPE = "farm_enterprise_economics"
ZIP_NAME = RECIPE + "-internal-qa.zip"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _digest(payload):
    return hashlib.sha256(payload).hexdigest()


def _source_digest(archive, names):
    checksum = hashlib.sha256()
    for name in names:
        relative = name[len(RECIPE) + 1:]
        checksum.update(relative.encode("utf-8") + b"\x00")
        checksum.update(archive.read(name))
    return checksum.hexdigest()


def verify_build(directory):
    directory = Path(directory).resolve(strict=True)
    archive_path = directory / ZIP_NAME
    manifest_path = directory / "manufacturing_manifest.json"
    if not directory.is_dir() or archive_path.is_symlink() or manifest_path.is_symlink():
        raise ValueError("UNSAFE_PRODUCT_BUILD_PATH")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("recipe") != RECIPE:
        raise ValueError("WRONG_RECIPE")
    files = manifest.get("files")
    if (not isinstance(files, list) or not files or
            any(not isinstance(name, str) or not name or
                name.startswith("/") or "\\" in name or
                any(part in ("", ".", "..") for part in name.split("/"))
                for name in files) or files != sorted(set(files))):
        raise ValueError("INVALID_PACKAGE_INVENTORY")
    data = archive_path.read_bytes()
    digest = _digest(data)
    if (manifest.get("artifact_sha256") != digest or
            manifest.get("bytes") != len(data) or
            not isinstance(manifest.get("source_sha256"), str) or
            SHA256.fullmatch(manifest["source_sha256"]) is None):
        raise ValueError("ARTIFACT_MANIFEST_MISMATCH")
    with zipfile.ZipFile(archive_path, "r") as archive:
        expected = [RECIPE + "/" + item for item in files]
        if archive.namelist() != expected or archive.testzip() is not None:
            raise ValueError("PACKAGE_INVENTORY_OR_CRC_FAILED")
        if any((info.external_attr >> 16) & 0o170000 != 0o100000
               for info in archive.infolist()):
            raise ValueError("NON_REGULAR_PACKAGE_FILE")
        source_sha256 = _source_digest(archive, expected)
    if source_sha256 != manifest["source_sha256"]:
        raise ValueError("PACKAGE_SOURCE_DIGEST_MISMATCH")
    qa = manifest.get("qa_measurements")
    if (manifest.get("qa_status") != "passed" or not isinstance(qa, dict) or
            type(qa.get("successful_tests")) is not int or qa["successful_tests"] < 1 or
            any(qa.get(k) != 0 for k in ("failures", "errors", "skipped", "unexpected_successes"))):
        raise ValueError("TECHNICAL_QA_NOT_PASSED")
    if (manifest.get("commercial_status") != "private_internal_qa_pass_not_published" or
            manifest.get("professional_quality_approved") is not False or
            manifest.get("professional_quality_score") is not None or
            manifest.get("public_listing_enabled") is not False):
        raise ValueError("RELEASE_GATE_NOT_CLOSED")
    return {"artifact_sha256": digest, "manifest_sha256": _digest(manifest_bytes),
            "source_sha256": source_sha256, "bytes": len(data),
            "file_count": len(files), "successful_tests": qa["successful_tests"]}


def verify_reproducibility(build_a, build_b, expected_sha256=None):
    first, second = Path(build_a).resolve(strict=True), Path(build_b).resolve(strict=True)
    if first == second:
        raise ValueError("BUILDS_ARE_NOT_SEPARATE")
    a, b = verify_build(first), verify_build(second)
    if a != b:
        raise ValueError("NONREPRODUCIBLE_BUILD")
    if expected_sha256 is not None and a["artifact_sha256"] != expected_sha256:
        raise ValueError("WRONG_EXPECTED_ARTIFACT")
    return {
        "schema": "saeit.factory.f01-internal-reproducibility-evidence.v1",
        "recipe": RECIPE,
        "technical_candidate_criteria": ["Q023", "Q068"],
        "scope": "two_separate_local_private_manufacturing_runs",
        "reproducible_zip": True,
        "manifest_reproducible": True,
        "zip_inventory_crc_and_source_digest_verified": True,
        "measurements": a,
        "professional_quality_points": None,
        "independently_reviewed": False,
        "externally_signed": False,
        "customer_acceptance": False,
        "commercial_release_allowed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-a", required=True, type=Path)
    parser.add_argument("--build-b", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    result = verify_reproducibility(args.build_a, args.build_b, args.expected_sha256)
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.receipt:
        if args.receipt.is_symlink() or args.receipt.parent.is_symlink():
            raise ValueError("UNSAFE_RECEIPT_PATH")
        args.receipt.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=".f01-evidence-", dir=args.receipt.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, args.receipt)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print("F01_REPRODUCIBILITY_GATE_FAILED:" + str(error), file=sys.stderr)
        sys.exit(1)
