#!/usr/bin/env python3
"""Independent customer-archive technical acceptance for each factory product.

Executes the tests FROM the exact shipped ZIP in a clean temporary directory.
Blocks any missing, unsafe, corrupted or non-running artifact. This does NOT
grant 1000-point professional clearance, usage rights or commercial release.
Python 3.8+, stdlib only.
"""
import hashlib
import json
import os
import resource
import signal
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

SCHEMA = "zomorodmelal.factory.customer-extracted-acceptance.v1"
RECIPE = re.compile(r"^[a-z][a-z0-9_]{1,65}$")
HASH = re.compile(r"^[0-9a-f]{64}$")
MAX_PACKAGE_BYTES = 25 * 1024 * 1024
MAX_UNPACKED_BYTES = 40 * 1024 * 1024
MAX_MEMBERS = 256
QUALITY_WEIGHTS = {
    "functional_accuracy": 250, "professional_domain_review": 200,
    "security_privacy_integrity": 150, "resilience_failure_modes": 100,
    "usability_accessibility": 100, "performance_resources": 75,
    "packaging_manual_delivery": 75, "rights_and_provenance": 50,
}
RUNNER = r"""
import json,sys,unittest
suite=unittest.defaultTestLoader.discover('.',pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=0).run(suite)
counts={'tests_run':result.testsRun,'failures':len(result.failures),
        'errors':len(result.errors),'skipped':len(result.skipped),
        'expected_failures':len(result.expectedFailures),
        'unexpected_successes':len(result.unexpectedSuccesses)}
with open(sys.argv[1],'x',encoding='utf8') as stream:json.dump(counts,stream)
sys.exit(0 if result.wasSuccessful() else 1)
"""


def require(test, reason):
    if not test:
        raise RuntimeError("PRODUCT_PACKAGE_QA_FAILED:" + reason)


def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_name(name, recipe):
    if not isinstance(name, str) or len(name) > 480 or "\\" in name or name.startswith("/"):
        return False
    parts = name.split("/")
    return (len(parts) >= 2 and parts[0] == recipe
            and all(p not in ("", ".", "..") and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", p)
                    for p in parts))


def read_manifest(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 100000,
            "MANIFEST_MISSING_OR_UNSAFE")
    try:
        doc = json.loads(path.read_text(encoding="utf8"))
    except (ValueError, UnicodeError, OSError) as error:
        raise RuntimeError("PRODUCT_PACKAGE_QA_FAILED:MANIFEST_INVALID") from error
    require(isinstance(doc, dict), "MANIFEST_NOT_OBJECT")
    return doc


def inspect_product(folder, recipe, *, timeout=90):
    """Return evidence only after fresh real ZIP extraction and a test subprocess."""
    folder = Path(folder)
    require(isinstance(recipe, str) and RECIPE.fullmatch(recipe), "INVALID_RECIPE")
    require(folder.is_dir() and not folder.is_symlink(), "MISSING_PRODUCT_DIRECTORY")
    manifest = read_manifest(folder / "manufacturing_manifest.json")
    artifact = folder / (recipe + "-internal-qa.zip")
    require(artifact.is_file() and not artifact.is_symlink()
            and 0 < artifact.stat().st_size <= MAX_PACKAGE_BYTES, "MISSING_CUSTOMER_ZIP")
    require(manifest.get("recipe") == recipe and manifest.get("qa_status") == "passed"
            and manifest.get("qa_evidence") == "unit_tests_passed"
            and manifest.get("professional_quality_approved") is False
            and manifest.get("public_listing_enabled") is False
            and manifest.get("commercial_status") == "private_internal_qa_pass_not_published"
            and manifest.get("owner_publication_approval") is False,
            "PRIVATE_MANUFACTURING_GATE_INVALID")
    sha = checksum(artifact)
    require(HASH.fullmatch(str(manifest.get("source_sha256", "")))
            and sha == manifest.get("artifact_sha256"), "CUSTOMER_ZIP_HASH_MISMATCH")
    files = manifest.get("files")
    require(isinstance(files, list) and 1 <= len(files) <= MAX_MEMBERS
            and len(set(files)) == len(files)
            and all(isinstance(p, str) and safe_name(recipe + "/" + p, recipe) for p in files)
            and any(Path(p).name.startswith("test_") and p.endswith(".py") for p in files),
            "INVALID_CUSTOMER_FILE_INDEX")
    measurements = manifest.get("qa_measurements")
    require(isinstance(measurements, dict)
            and type(measurements.get("tests_run")) is int and measurements["tests_run"] >= 1,
            "ORIGINAL_TEST_COUNTS_MISSING")
    with tempfile.TemporaryDirectory(prefix="factory-real-customer-") as temp:
        root = Path(temp)
        try:
            with zipfile.ZipFile(str(artifact)) as archive:
                entries = archive.infolist()
                require(len(entries) == len(files) and len(entries) <= MAX_MEMBERS,
                        "CUSTOMER_ZIP_MEMBER_COUNT")
                require(sorted(info.filename for info in entries)
                        == sorted(recipe + "/" + p for p in files),
                        "CUSTOMER_ZIP_FILE_INDEX_MISMATCH")
                require(archive.testzip() is None, "CUSTOMER_ZIP_CRC_FAILED")
                require(sum(info.file_size for info in entries) <= MAX_UNPACKED_BYTES,
                        "CUSTOMER_ZIP_INFLATION")
                for info in entries:
                    mode = (info.external_attr >> 16) & 0o170000
                    require(safe_name(info.filename, recipe)
                            and not info.is_dir() and not (info.flag_bits & 1)
                            and mode in (0, 0o100000), "CUSTOMER_ZIP_UNSAFE_MEMBER")
                    dest = root / info.filename
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with dest.open("xb") as out:
                        out.write(archive.read(info))
        except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
            raise RuntimeError("PRODUCT_PACKAGE_QA_FAILED:CUSTOMER_ZIP_UNUSABLE") from error
        extracted = root / recipe
        evidence = root / "test-result.json"
        def child_limits():
            resource.setrlimit(resource.RLIMIT_CPU, (30, 35))
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # Keep credentials and ambient PYTHONPATH out of the extracted product.
        safe_env = {"PATH": os.defpath, "LANG": "C.UTF-8",
                    "HOME": str(root), "PYTHONNOUSERSITE": "1",
                    "PYTHONDONTWRITEBYTECODE": "1"}
        with subprocess.Popen(
                [sys.executable, "-B", "-c", RUNNER, str(evidence)],
                cwd=str(extracted), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=safe_env, start_new_session=True,
                preexec_fn=child_limits) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as error:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                raise RuntimeError("PRODUCT_PACKAGE_QA_FAILED:CUSTOMER_TEST_TIMEOUT") from error
            result_code = process.returncode
        require(evidence.is_file() and not evidence.is_symlink(), "CUSTOMER_TEST_REPORT_MISSING")
        try:
            counts = json.loads(evidence.read_text(encoding="utf8"))
        except (ValueError, OSError) as error:
            raise RuntimeError("PRODUCT_PACKAGE_QA_FAILED:CUSTOMER_TEST_REPORT_INVALID") from error
        require(result_code == 0 and counts.get("tests_run") == measurements["tests_run"]
                and all(counts.get(key) == 0 for key in
                        ("errors", "failures", "skipped", "expected_failures", "unexpected_successes")),
                "CUSTOMER_EXTRACTED_TESTS_FAILED:" + (stderr or "")[-300:])
    return {"schema": SCHEMA, "recipe": recipe,
            "source_sha256": manifest["source_sha256"],
            "artifact_sha256": sha, "customer_zip_extract_test": "passed",
            "customer_archive_tests_run": counts["tests_run"],
            "original_manufacturer_tests_run": measurements["tests_run"],
            "independent_business_domain_oracle": False,
            "professional_quality_1000_approved": False,
            "public_listing_enabled": False, "commerce_enabled": False}


def persist_pending(private_root, receipt):
    """Durably bind actual technical evidence and an UNSCORED professional gate."""
    root = Path(private_root)
    require(not root.is_symlink() and root.is_dir(), "INVALID_PRIVATE_ROOT")
    recipe = receipt["recipe"]
    require(recipe and RECIPE.fullmatch(recipe), "INVALID_RECEIPT_RECIPE")
    sha = receipt["source_sha256"]
    require(HASH.fullmatch(sha), "INVALID_RECEIPT_HASH")
    from_file = root / "digital-products" / recipe / (recipe + "-internal-qa.zip")
    require(from_file.is_file() and checksum(from_file) == receipt["artifact_sha256"],
            "PRODUCT_CHANGED_AFTER_CUSTOMER_QA")
    target = root / "customer-extracted-acceptance" / recipe / sha / "technical-receipt.json"
    target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    require(not target.parent.is_symlink() and not target.is_symlink(), "UNSAFE_RECEIPT_TARGET")
    quality = root / "quality-excellence" / "customer-extracted-review" / recipe / sha / "pending.json"
    quality.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    require(not quality.parent.is_symlink() and not quality.is_symlink(), "UNSAFE_QUALITY_TARGET")
    ticket = {"schema": SCHEMA, "recipe": recipe,
              "source_sha256": sha, "artifact_sha256": receipt["artifact_sha256"],
              "technical_customer_qa": "passed", "professional_quality_1000_approved": False,
              "verified_total_score": None, "open_defects_may_remain": True,
              "rubric_maximum": 1000,
              "rubric": {key: {"maximum": value, "verified_score": None}
                        for key, value in QUALITY_WEIGHTS.items()},
              "expert_signature_verified": False, "owner_publication_approval": False,
              "status": "PENDING_INDEPENDENT_PROFESSIONAL_QUALITY_AND_DELIVERY",
              "commercial_release": False}
    for path, payload in ((target, receipt), (quality, ticket)):
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
        if path.exists():
            require(path.read_text(encoding="utf8") == raw, "RECEIPT_VERSION_CONFLICT")
        else:
            fd, temporary = tempfile.mkstemp(prefix=".customer-acceptance-", dir=str(path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf8") as out:
                    out.write(raw)
                    out.flush()
                    os.fsync(out.fileno())
                os.chmod(temporary, 0o600)
                os.replace(temporary, str(path))
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    return str(target)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--recipe", required=True)
    args = parser.parse_args()
    root = Path(args.private_root)
    try:
        result = inspect_product(root / "digital-products" / args.recipe, args.recipe)
        persist_pending(root, result)
        print("FACTORY_REAL_CUSTOMER_ARCHIVE_QA=" + json.dumps(result, sort_keys=True))
        return 0
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print("FACTORY_REAL_CUSTOMER_ARCHIVE_QA_REWORK=" + str(error)[:400], file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
