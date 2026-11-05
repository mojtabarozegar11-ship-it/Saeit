#!/usr/bin/env python3
"""Verify F01 technical receipts and, optionally, attach them to exact QA ZIP.

The default mode is read-only. --install only adds hash-pinned documentary
references to an existing PRIVATE manufacturing folder, never awards verified
QC1000 points, changes its manufacturing manifest, or enables a release.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile


PRODUCT = "farm_enterprise_economics"
SOURCES = (
    "calculator.py", "guided_start.py", "test_calculator.py", "test_guided_start.py",
    "README.md", "CUSTOMER_GUIDE.md", "example_inputs.json",
    "build_technical_evidence.py",
)
# A legacy ZIP without the new customer entry point is not the same product
# as a proof captured from source that includes that entry point.
PACKAGE_SOURCES = tuple(name for name in SOURCES if name != "build_technical_evidence.py")
TEST_MODULES = ("test_calculator.py", "test_guided_start.py")
EXPORTS = ("baseline.json", "scenarios.csv", "joint-stress.csv",
           "management-report.html")
CRITERIA = ("Q035", "Q036", "Q037", "Q061", "Q063", "Q064")
HEX = re.compile(r"[a-f0-9]{64}\Z")


def require(ok, why):
    if not ok:
        raise ValueError("F01_EVIDENCE_" + why)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def regular_file(path, limit=5_000_000):
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and 0 < p.stat().st_size <= limit,
            "FILE_MISSING_UNSAFE_OR_OVERSIZE:" + p.name)
    return p


def obj(path):
    value = json.loads(regular_file(path, 500_000).read_text(encoding="utf-8"))
    require(isinstance(value, dict), "JSON_NOT_OBJECT:" + Path(path).name)
    return value


def private_folder(path, name=None):
    p = Path(path)
    require(not p.is_symlink() and p.is_dir() and (name is None or p.name == name),
            "DIRECTORY_MISMATCH")
    return p.resolve(strict=True)


def verify(recipe_dir, evidence_dir):
    recipe = private_folder(recipe_dir, PRODUCT)
    evidence = private_folder(evidence_dir)
    manifest = obj(evidence / "manifest.json")
    source_hashes = {filename: digest(regular_file(recipe / filename)) for filename in SOURCES}
    require(manifest.get("schema") == "saeit.factory.f01-technical-evidence-manifest.v1"
            and manifest.get("product_id") == PRODUCT
            and manifest.get("source_sha256") == source_hashes
            and type(manifest.get("test_count")) is int
            and manifest["test_count"] >= 43
            and manifest.get("verified_quality_score") is None
            and manifest.get("independent_reviewer_approval") is False
            and manifest.get("receiver_acceptance") is False
            and manifest.get("commercial_release_allowed") is False,
            "MANIFEST_IDENTITY_OR_RELEASE_CLAIM")
    all_names = []
    for module in TEST_MODULES:
        tests = ast.parse((recipe / module).read_text(encoding="utf-8"))
        all_names.extend(node.name for node in ast.walk(tests)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and node.name.startswith("test_"))
    names = set(all_names)
    require(len(all_names) == len(names) == manifest["test_count"],
            "TEST_COUNT_SOURCE_MISMATCH")
    log_path = regular_file(evidence / "test_execution.log")
    log = log_path.read_text(encoding="utf-8")
    require(digest(log_path) == manifest.get("test_log_sha256")
            and re.search(r"Ran " + str(len(names)) + r" tests? in", log)
            and re.search(r"(?m)^OK\s*$", log)
            and "FAILED" not in log, "TEST_LOG_UNVERIFIED")
    exports = manifest.get("exports_sha256")
    require(isinstance(exports, dict) and set(exports) == set(EXPORTS), "EXPORT_SET_INVALID")
    for filename in EXPORTS:
        require(digest(regular_file(evidence / filename)) == exports[filename],
                "EXPORT_HASH_MISMATCH:" + filename)
    receipts = manifest.get("candidate_criteria")
    require(isinstance(receipts, dict) and set(receipts) == set(CRITERIA),
            "CRITERIA_MISMATCH")
    refs = {}
    for criterion in CRITERIA:
        ref = receipts[criterion]
        filename = "evidence-" + criterion + ".json"
        require(isinstance(ref, dict) and ref.get("path") == filename
                and isinstance(ref.get("sha256"), str)
                and HEX.fullmatch(ref["sha256"]), "RECEIPT_REFERENCE_INVALID:" + criterion)
        file = regular_file(evidence / filename)
        require(digest(file) == ref["sha256"], "RECEIPT_HASH_MISMATCH:" + criterion)
        record = obj(file)
        selected = record.get("selected_passing_tests")
        require(record.get("schema") == "saeit.factory.f01-internal-evidence.v1"
                and record.get("product_id") == PRODUCT
                and record.get("criterion_id") == criterion
                and record.get("evidence_class") == "internally_reproduced_technical_check"
                and record.get("product_source_sha256") == source_hashes
                and record.get("run_log_sha256") == manifest["test_log_sha256"]
                and record.get("generated_at_utc") == manifest.get("generated_at_utc")
                and record.get("complete_suite_passing_test_count") == len(names)
                and isinstance(selected, list) and bool(selected)
                and all(isinstance(n, str) and n in names for n in selected)
                and record.get("independent_specialist_verified") is False
                and record.get("professionally_validated_quality_points") is None
                and record.get("real_customer_data_used") is False
                and record.get("commercial_release_allowed") is False,
                "RECEIPT_PROVENANCE_OR_REVIEW_INVALID:" + criterion)
        refs[criterion] = {"sha256": ref["sha256"], "filename": filename}
    return {"recipe": recipe, "evidence": evidence,
            "manifest_sha256": digest(evidence / "manifest.json"), "source_hashes": source_hashes,
            "refs": refs}


def verify_manufactured(product_dir, validated):
    folder = private_folder(product_dir, PRODUCT)
    manifest = obj(folder / "manufacturing_manifest.json")
    archive = regular_file(folder / (PRODUCT + "-internal-qa.zip"), 25 * 1024 * 1024)
    require(manifest.get("recipe") == PRODUCT and manifest.get("qa_status") == "passed"
            and manifest.get("commercial_status") == "private_internal_qa_pass_not_published"
            and manifest.get("public_listing_enabled") is False
            and manifest.get("owner_publication_approval") is False
            and digest(archive) == manifest.get("artifact_sha256"),
            "MANUFACTURED_ARTIFACT_MISMATCH")
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        require(0 < len(members) <= 100, "MANUFACTURED_ZIP_INVALID")
        seen = set()
        uncompressed = 0
        for item in members:
            name = item.filename
            require(name not in seen and not item.is_dir() and not (item.flag_bits & 1)
                    and not (item.external_attr >> 16) & 0o170000 == 0o120000
                    and item.file_size <= 25 * 1024 * 1024
                    and name.startswith(PRODUCT + "/")
                    and all(re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", p)
                            and p not in (".", "..") for p in name.split("/")),
                    "MANUFACTURED_ZIP_MEMBER_UNSAFE")
            seen.add(name)
            uncompressed += item.file_size
            require(uncompressed <= 40 * 1024 * 1024,
                    "MANUFACTURED_ZIP_EXPANSION_LIMIT")
        require(bundle.testzip() is None, "MANUFACTURED_ZIP_CRC_INVALID")
        for filename in PACKAGE_SOURCES:
            member = PRODUCT + "/" + filename
            require(member in seen
                    and hashlib.sha256(bundle.read(member)).hexdigest()
                    == validated["source_hashes"][filename],
                    "SOURCE_NOT_IN_EXACT_MANUFACTURED_ZIP:" + filename)
    return folder


def install(product_dir, validated):
    folder = verify_manufactured(product_dir, validated)
    candidate = folder / "global_quality_candidate.json"
    require(not candidate.is_symlink(), "CANDIDATE_SYMLINK")
    existing = obj(candidate) if candidate.exists() else {}
    require(existing.get("recipe", PRODUCT) == PRODUCT
            and existing.get("schema", "saeit.factory.global-quality-candidate.v1")
            == "saeit.factory.global-quality-candidate.v1",
            "CANDIDATE_PRODUCT_OR_SCHEMA_MISMATCH")
    dossier = existing.get("criteria_evidence", {})
    require(isinstance(dossier, dict), "CANDIDATE_CRITERIA_INVALID")
    evidence_root = folder / "evidence-f01"
    version = evidence_root / validated["manifest_sha256"]
    require(not evidence_root.is_symlink() and not version.is_symlink(), "DESTINATION_SYMLINK")
    all_files = ("manifest.json", "test_execution.log") + EXPORTS + tuple(
        validated["refs"][id]["filename"] for id in CRITERIA)
    if version.exists():
        require(version.is_dir() and all(
            regular_file(version / name).read_bytes() ==
            regular_file(validated["evidence"] / name).read_bytes() for name in all_files),
            "IMMUTABLE_DESTINATION_CONFLICT")
    refs = {key: {"path": "evidence-f01/" + validated["manifest_sha256"] + "/" + item["filename"],
                  "sha256": item["sha256"]} for key, item in validated["refs"].items()}
    require(all(key not in dossier or dossier[key] == value for key, value in refs.items()),
            "EXISTING_EVIDENCE_CONFLICT")
    updated = dict(existing)
    updated["schema"] = "saeit.factory.global-quality-candidate.v1"
    updated["recipe"] = PRODUCT
    updated["criteria_evidence"] = dict(dossier, **refs)
    updated["f01_technical_evidence_import"] = {
        "manifest_sha256": validated["manifest_sha256"],
        "actual_manufactured_zip_source_verified": True,
        "independent_reviewer_approval": False,
        "verified_quality_points": None,
        "receiver_acceptance": False,
        "commercial_release_allowed": False}
    if not version.exists():
        evidence_root.mkdir(mode=0o700, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".f01-stage-", dir=str(evidence_root)) as stage:
            for name in all_files:
                shutil.copyfile(validated["evidence"] / name, Path(stage) / name)
                os.chmod(str(Path(stage) / name), 0o600)
            os.rename(stage, version)
    raw = (json.dumps(updated, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=".f01-candidate-", dir=str(folder))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, candidate)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return refs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe-dir", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--product-dir")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    result = verify(args.recipe_dir, args.evidence_dir)
    if args.install:
        require(bool(args.product_dir), "PRODUCT_DIRECTORY_REQUIRED")
        install(args.product_dir, result)
    elif args.product_dir:
        verify_manufactured(args.product_dir, result)
    print("F01_PRODUCT_EVIDENCE_BRIDGE=PASS")
    print("F01_EXACT_MANUFACTURED_SOURCE_BOUND=" + str(bool(args.product_dir)).lower())
    print("F01_DOCUMENTARY_CRITERIA=" + str(len(result["refs"])))
    print("F01_ATTACHED_TO_PRIVATE_QC=" + str(args.install).lower())
    print("F01_INDEPENDENT_QC1000=HOLD")
    print("F01_COMMERCIAL_RELEASE=FALSE")


if __name__ == "__main__":
    main()
