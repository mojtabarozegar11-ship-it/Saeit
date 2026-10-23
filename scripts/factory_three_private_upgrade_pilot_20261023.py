#!/usr/bin/env python3
"""Build exactly three genuine source upgrades as private, noncommercial VPS candidates.

The original stock ZIP and QA manifest are read-only. Missing original provenance,
unchanged executable calculator code, failed measured tests or unbound ZIP hashes
are hard failures, never called independent human/1000-point certification.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import zipfile

RECIPES = (
    "farm_enterprise_economics",
    "greenhouse_crop_margin",
    "water_budget_economics",
)
HEX = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SCHEMA = "saeit.factory.genuine-source-upgrade-private.v1"


def load_maker(stage):
    path = stage / "scripts" / "factory_product_maker.py"
    passport = stage / "scripts" / "factory_personal_owner_passport_policy_20261020.py"
    if any(p.is_symlink() or not p.is_file() for p in (path, passport)):
        raise RuntimeError("STAGED_MANUFACTURER_OR_PASSPORT_POLICY_MISSING")
    spec = importlib.util.spec_from_file_location("factory_private_pilot_maker", str(path))
    maker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maker)
    return maker


def checked_manifest(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("PRIOR_MANUFACTURING_EVIDENCE_MISSING")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("PRIOR_MANUFACTURING_EVIDENCE_INVALID")
    return data


def upgrade_one(recipe, source_root, private_root, commit, maker):
    if recipe not in RECIPES:
        raise RuntimeError("PILOT_RECIPE_NOT_ALLOWED")
    source = source_root / recipe
    if source.is_symlink():
        raise RuntimeError("STAGED_RECIPE_SYMLINK")
    _, files = maker.inspect_recipe(source)
    if "calculator.py" not in files:
        raise RuntimeError("REAL_EXECUTABLE_CODE_MISSING")
    new_source = maker.source_digest(source, files)
    new_code = (source / "calculator.py").read_bytes()
    old = private_root / "digital-products" / recipe
    if old.is_symlink():
        raise RuntimeError("UNSAFE_ORIGINAL_PRODUCT")
    original_manifest = checked_manifest(old / "manufacturing_manifest.json")
    original_archive = old / (recipe + "-internal-qa.zip")
    if original_archive.is_symlink() or not original_archive.is_file():
        raise RuntimeError("PRIOR_ARCHIVE_MISSING")
    original_archive_sha = maker.sha256_file(original_archive)
    if not (original_manifest.get("recipe") == recipe
            and original_manifest.get("qa_status") == "passed"
            and original_manifest.get("commercial_status") == "private_internal_qa_pass_not_published"
            and original_manifest.get("public_listing_enabled") is False
            and original_manifest.get("artifact_sha256") == original_archive_sha
            and HEX.fullmatch(str(original_manifest.get("source_sha256", "")))):
        raise RuntimeError("PRIOR_QA_PROVENANCE_OR_PRIVATE_STATUS_INVALID")
    if new_source == original_manifest["source_sha256"]:
        raise RuntimeError("NO_NEW_PRODUCT_SOURCE")
    with zipfile.ZipFile(original_archive) as old_zip:
        if old_zip.testzip() is not None:
            raise RuntimeError("ORIGINAL_ARCHIVE_CORRUPT")
        old_code = old_zip.read(recipe + "/calculator.py")
    if old_code == new_code:
        raise RuntimeError("PRODUCT_EXECUTABLE_CODE_NOT_UPGRADED")
    # New candidate is scoped to a single immutable Git SHA, outside current
    # warehouse, runtime recipes, customer orders, storefronts and production.
    out = private_root / "quality-excellence" / "source-upgrade-pilot-v1" / commit
    if out.is_symlink() or (out / recipe).is_symlink():
        raise RuntimeError("UNSAFE_PRIVATE_CANDIDATE_PATH")
    outcome = maker.manufacture(recipe, source_root, out)
    candidate = out / recipe
    manifest = checked_manifest(candidate / "manufacturing_manifest.json")
    archive = candidate / (recipe + "-internal-qa.zip")
    qa = manifest.get("qa_measurements")
    if (outcome.get("qa_status") != "passed"
            or manifest.get("qa_status") != "passed"
            or manifest.get("source_sha256") != new_source
            or manifest.get("artifact_sha256") != maker.sha256_file(archive)
            or manifest["artifact_sha256"] == original_archive_sha
            or not isinstance(qa, dict)
            or type(qa.get("successful_tests")) is not int
            or qa["successful_tests"] < 1
            or manifest.get("public_listing_enabled") is not False
            or manifest.get("professional_quality_approved") is not False):
        raise RuntimeError("CANDIDATE_REAL_QA_OR_HASH_FAILED")
    with zipfile.ZipFile(archive) as new_zip:
        if new_zip.testzip() is not None or new_zip.read(recipe + "/calculator.py") != new_code:
            raise RuntimeError("CANDIDATE_ZIP_EXECUTABLE_MISMATCH")
    # Detect incidental changes to the original stock during manufacturing.
    if maker.sha256_file(original_archive) != original_archive_sha:
        raise RuntimeError("ORIGINAL_STOCK_MUTATED")
    if checked_manifest(old / "manufacturing_manifest.json") != original_manifest:
        raise RuntimeError("ORIGINAL_MANIFEST_MUTATED")
    receipt = {
        "schema": SCHEMA, "commit": commit, "recipe": recipe,
        "prior_source_sha256": original_manifest["source_sha256"],
        "new_source_sha256": new_source,
        "prior_artifact_sha256": original_archive_sha,
        "new_artifact_sha256": manifest["artifact_sha256"],
        "prior_calculator_sha256": hashlib.sha256(old_code).hexdigest(),
        "new_calculator_sha256": hashlib.sha256(new_code).hexdigest(),
        "measured_successful_tests": qa["successful_tests"],
        "private_candidate": True,
        "commercial_publication_allowed": False,
        "independent_specialist_qualification_verified": False,
        "professional_1000_quality_grade": None,
    }
    receipt_path = candidate / "source_upgrade_receipt.json"
    content = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if receipt_path.is_symlink():
        raise RuntimeError("CANDIDATE_RECEIPT_UNSAFE")
    if receipt_path.exists() and receipt_path.read_text(encoding="utf-8") != content:
        raise RuntimeError("CANDIDATE_RECEIPT_IMMUTABILITY_FAILED")
    if not receipt_path.exists():
        # Fail closed on concurrent writers instead of silently overwriting.
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(receipt_path), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
    return receipt


def run(stage, private_root, commit):
    if not COMMIT.fullmatch(commit):
        raise RuntimeError("INVALID_GIT_COMMIT")
    if stage.is_symlink() or private_root.is_symlink() or not stage.is_dir() or not private_root.is_dir():
        raise RuntimeError("UNSAFE_PILOT_ROOT")
    maker = load_maker(stage)
    for recipe in RECIPES:
        receipt = upgrade_one(recipe, stage / "product_recipes", private_root, commit, maker)
        print("FACTORY_REAL_UPGRADED_PRODUCT=" + receipt["recipe"])
        print("FACTORY_REAL_PRODUCT_NEW_ARTIFACT_SHA256=" + receipt["new_artifact_sha256"])
        print("FACTORY_REAL_PRODUCT_TESTS_PASSED=" + str(receipt["measured_successful_tests"]))
    print("FACTORY_REAL_SOURCE_UPGRADES_COMPLETED=3")
    print("FACTORY_INDEPENDENT_EXPERTS_VERIFIED=0")
    print("FACTORY_COMMERCIAL_RELEASE_ENABLED=false")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-root", required=True, type=Path)
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args(argv)
    run(args.stage_root, args.private_root, args.commit)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        print("FACTORY_PRIVATE_SOURCE_UPGRADE_BLOCKED=" + str(exc), file=sys.stderr)
        sys.exit(1)
