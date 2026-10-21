#!/usr/bin/env python3
"""Private, hash-bound F28 central-warehouse intake. No commercial release.

Receives the actual F28 candidate built and independently CLI-tested on VPS.
Holds professional QA at NOT APPROVED and never touches stores or orders.
Python 3.8+, stdlib only; reuses the central warehouse's validated stock_one.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

RECIPE = "greenhouse_crop_margin"
SCHEMA = "zomorodmelal.factory.f28-central-private-intake.v1"
WEIGHTS = {"functional_accuracy": 250, "professional_domain_review": 200,
           "security_privacy_integrity": 150, "resilience_failure_modes": 100,
           "usability_accessibility": 100, "performance_resources": 75,
           "packaging_manual_delivery": 75, "rights_and_provenance": 50}


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def json_file(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 200000,
            "F28_INTAKE_UNSAFE_RECEIPT")
    doc = json.loads(path.read_text(encoding="utf8"))
    require(isinstance(doc, dict), "F28_INTAKE_RECEIPT_NOT_OBJECT")
    return doc


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_warehouse(path):
    require(path.is_file() and not path.is_symlink(), "F28_INTAKE_WAREHOUSE_MODULE_MISSING")
    spec = importlib.util.spec_from_file_location("f28_verified_warehouse", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_private(path):
    require(not path.is_symlink(), "F28_INTAKE_SYMLINK_PATH")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    require(path.is_dir() and not path.is_symlink(), "F28_INTAKE_INVALID_DIRECTORY")
    # Do not chmod shared factory ancestors: only the new leaf is our own.


def stable_ticket(warehouse, path, payload):
    if path.exists() or path.is_symlink():
        require(not path.is_symlink() and json_file(path) == payload,
                "F28_INTAKE_EXISTING_REVIEW_CONFLICT")
    else:
        warehouse.write_json_atomic(path, payload)


def acquire_warehouse_lock(handle, *, wait_seconds=70, interval_seconds=0.5):
    """Wait a bounded time for the existing cooperative warehouse lock.

    Never break, delete or bypass the shared warehouse lock: other writers
    retain exclusive access while holding it.
    """
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("F28_INTAKE_WAREHOUSE_LOCKED_RETRY")
            time.sleep(min(interval_seconds, remaining))


def accept(candidate, factory_root, warehouse_module):
    candidate = Path(candidate).absolute()
    factory_root = Path(factory_root).absolute()
    require(candidate.is_dir() and not candidate.is_symlink(),
            "F28_INTAKE_CANDIDATE_MISSING")
    require(factory_root.is_dir() and not factory_root.is_symlink(),
            "F28_INTAKE_FACTORY_ROOT_MISSING")
    receipt = json_file(candidate / "private-cycle-receipt.json")
    source = candidate / "private-stock" / RECIPE
    require(source.is_dir() and not source.is_symlink(), "F28_INTAKE_SOURCE_MISSING")
    artifact = source / (RECIPE + "-internal-qa.zip")
    manifest_file = source / "manufacturing_manifest.json"
    manifest = json_file(manifest_file)
    require(artifact.is_file() and not artifact.is_symlink(), "F28_INTAKE_PRODUCT_MISSING")
    checks = receipt.get("independent_black_box_checks")
    tests = receipt.get("technical_tests")
    require(receipt.get("schema") == "zomorodmelal.factory.f28-private-build-cycle.v1"
            and receipt.get("recipe") == RECIPE
            and receipt.get("status") == "private_technical_candidate_verified"
            and receipt.get("commercial_release_authorized") is False
            and receipt.get("independent_professional_quality_1000_passed") is False
            and receipt.get("public_listing_enabled") is False
            and type(tests) is int and tests >= 10
            and isinstance(checks, dict)
            and checks.get("customer_scenarios_verified") == 2
            and checks.get("independent_arithmetic_oracle") is True
            and checks.get("zip_integrity_verified") is True
            and checks.get("customer_cli_from_extracted_zip") is True,
            "F28_INTAKE_INDEPENDENT_TECHNICAL_EVIDENCE_MISSING")
    require(manifest.get("recipe") == RECIPE
            and manifest.get("professional_quality_approved") is False
            and manifest.get("public_listing_enabled") is False
            and manifest.get("source_sha256") == receipt.get("source_sha256")
            and manifest.get("artifact_sha256") == receipt.get("artifact_sha256")
            and isinstance(manifest.get("qa_measurements"), dict)
            and manifest["qa_measurements"].get("successful_tests") == tests
            and sha(artifact) == receipt.get("artifact_sha256"),
            "F28_INTAKE_SOURCE_OR_ARTIFACT_MISMATCH")
    require(sum(WEIGHTS.values()) == 1000, "F28_INTAKE_INVALID_QUALITY_RUBRIC")
    module = load_warehouse(Path(warehouse_module))
    warehouse = factory_root / "production-warehouse"
    make_private(warehouse)
    lockpath = warehouse / ".warehouse.lock"
    require(not lockpath.is_symlink(), "F28_INTAKE_UNSAFE_LOCK")
    with lockpath.open("a+b") as lock:
        os.chmod(str(lockpath), 0o600)
        acquire_warehouse_lock(lock)
        # A pre-existing live QA/rework hold is never bypassed.
        active = module.active_rework(factory_root, RECIPE)
        require(active is None, "F28_INTAKE_REWORK_HOLD_" + str(active))
        with tempfile.TemporaryDirectory(prefix=".f28-intake-", dir=str(candidate)) as temp:
            isolated = Path(temp)
            intake_source = isolated / "digital-products" / RECIPE
            make_private(intake_source)
            shutil.copyfile(str(artifact), str(intake_source / artifact.name))
            shutil.copyfile(str(manifest_file), str(intake_source / manifest_file.name))
            require(sha(intake_source / artifact.name) == sha(artifact)
                    and sha(intake_source / manifest_file.name) == sha(manifest_file),
                    "F28_INTAKE_STAGING_COPY_MISMATCH")
            result = module.stock_one(isolated, RECIPE, warehouse)
        require(result["action"] in ("stocked", "already_stocked"),
                "F28_INTAKE_PRODUCT_NOT_STOCKED")
        version = warehouse / "finished" / RECIPE / receipt["source_sha256"]
        saved = module.verify_stored(version)
        require(saved["artifact_sha256"] == receipt["artifact_sha256"]
                and saved["commercial_release"] is False
                and saved["site_transfer_state"] == "not_transferred",
                "F28_INTAKE_STORED_PRODUCT_NOT_VERIFIED")
        inventory = module.stock_summary(warehouse)
        register_path = warehouse / "stock-register.json"
        if register_path.exists():
            register = module.read_json(register_path, max_size=4 * 1024 * 1024)
            require(register.get("schema") == module.SCHEMA,
                    "F28_INTAKE_STOCK_REGISTER_INVALID")
        else:
            register = {"schema": module.SCHEMA, "factory_site_dependency": False,
                        "customer_order_dependency": False,
                        "distribution_enabled": False, "sites_contacted": 0,
                        "last_cycle_actions": [], "needs_rework_or_review": [],
                        "strict_build50_enabled": False, "build_quality": None}
        register.update(finished_goods_versions=len(inventory),
                        finished_goods_product_count=len(set(i["product_id"] for i in inventory)),
                        awaiting_commercial_review=len(inventory), records=inventory)
        module.write_json_atomic(register_path, register)
        # Review is a request, not an approval or a fabricated numeric score.
        ticket = {"schema": SCHEMA, "family_id": "F28", "recipe": RECIPE,
                  "source_sha256": receipt["source_sha256"],
                  "artifact_sha256": receipt["artifact_sha256"],
                  "manufacturing_manifest_sha256": sha(manifest_file),
                  "technical_tests_passed": tests,
                  "independent_customer_blackbox_scenarios_passed": 2,
                  "quality_standard": "1000_points_strict",
                  "rubric_maximum": 1000,
                  "rubric": {key: {"maximum": value, "verified_score": None}
                            for key, value in WEIGHTS.items()},
                  "verified_total_score": None,
                  "professional_reviewer_evidence": None,
                  "professional_quality_1000_approved": False,
                  "owner_release_approval": False,
                  "status": "awaiting_independent_professional_and_rights_review",
                  "delivery_verified_by_customer": False,
                  "commerce_enabled": False, "public_listing_enabled": False}
        review = (factory_root / "quality-excellence" / "private-intake-review"
                  / RECIPE / receipt["source_sha256"] / "pending.json")
        make_private(review.parent)
        stable_ticket(module, review, ticket)
        output = {"schema": SCHEMA, "family_id": "F28", "recipe": RECIPE,
                  "action": result["action"], "source_sha256": receipt["source_sha256"],
                  "artifact_sha256": receipt["artifact_sha256"],
                  "stock_version_verified": True,
                  "warehouse_versions_verified": len(inventory),
                  "quality_ticket_created_or_confirmed": True,
                  "professional_quality_1000_approved": False,
                  "commerce_enabled": False, "public_listing_enabled": False}
        module.write_json_atomic(candidate / "private-central-intake-receipt.json", output)
        return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", required=True)
    p.add_argument("--factory-root", required=True)
    p.add_argument("--warehouse-module", required=True)
    args = p.parse_args()
    try:
        result = accept(args.candidate, args.factory_root, args.warehouse_module)
        print("F28_CENTRAL_PRIVATE_WAREHOUSE_INTAKE=" + json.dumps(result, sort_keys=True))
        return 0
    except (RuntimeError, ValueError, OSError, KeyError) as exc:
        print("F28_CENTRAL_PRIVATE_INTAKE_BLOCKED=" + str(exc)[:320], file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
