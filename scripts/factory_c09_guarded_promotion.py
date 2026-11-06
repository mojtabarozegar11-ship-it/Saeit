#!/usr/bin/env python3
"""One-off F01 edition 1.4 VPS promotion, preserving v1.3 recovery evidence.

The native factory's existing single-product cron owns the same flock.  No
cron, commerce, approvals, cPanel files, or unrelated recipes are modified.
The prior source, ZIP, manifest, passport and safety gate remain in a private
recovery directory.  Do not enable this as a periodic factory scheduler.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time


RECIPE = "farm_enterprise_economics"
OLD_SOURCE = "83272f1244eb82ead82f9110c2cdd0fab31110ce7436aeadd2c70d90b28fc16b"
OLD_ARCHIVE = "701883a172a7daf32cce5cab806cafceeea8e99139c1e34256ee2306c42409ed"
NEW_SOURCE = "d75a687a0bb97529586b90dc91e4c75a5efa8e107f5a3110109159a78a87ff3b"
NEW_ARCHIVE = "04c0045d4610c2d15ef86146ec66d0baed5eebb475d57e8b6648152b56c7f335"
OLD_TEST_COUNT = 19
NEW_TEST_COUNT = 20


def require(condition, message):
    if not condition:
        raise RuntimeError("FACTORY_C09_" + message)


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, str(filename))
    require(spec is not None and spec.loader is not None, "MISSING_MODULE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_dir(path):
    return path.is_dir() and not path.is_symlink()


def readable_json(path):
    require(path.is_file() and not path.is_symlink(), "UNSAFE_JSON")
    document = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(document, dict), "INVALID_JSON")
    return document


def source_sha(maker, path, expected_files):
    require(safe_dir(path), "SOURCE_MISSING")
    _, files = maker.inspect_recipe(path)
    require(len(files) == expected_files, "SOURCE_FILE_COUNT_CHANGED")
    return maker.source_digest(path, files)


def archive_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def product_guard(folder, source, artifact, tests):
    require(safe_dir(folder), "PRODUCT_MISSING")
    manifest = readable_json(folder / "manufacturing_manifest.json")
    archive = folder / (RECIPE + "-internal-qa.zip")
    require(archive.is_file() and not archive.is_symlink(), "ARCHIVE_MISSING")
    require(manifest.get("recipe") == RECIPE
            and manifest.get("source_sha256") == source
            and manifest.get("artifact_sha256") == artifact
            and archive_sha(archive) == artifact,
            "PRODUCT_REVISION_MISMATCH")
    qa = manifest.get("qa_measurements") or {}
    require(manifest.get("qa_status") == "passed"
            and type(qa.get("successful_tests")) is int
            and qa["successful_tests"] == tests,
            "TEST_EVIDENCE_CHANGED")
    require(manifest.get("professional_quality_approved") is False
            and manifest.get("public_listing_enabled") is False
            and manifest.get("owner_publication_approval") is False,
            "COMMERCIAL_GATE_NOT_CLOSED")
    stop = folder / "professional_quality_release_stop.json"
    passport_name = manifest.get("private_passport_file")
    require(stop.is_file() and not stop.is_symlink()
            and isinstance(passport_name, str)
            and Path(passport_name).name == passport_name
            and (folder / passport_name).is_file()
            and not (folder / passport_name).is_symlink(),
            "QUALITY_STOP_OR_PASSPORT_MISSING")
    return manifest


def slot_guard(private, old_sha, old_artifact):
    slot = readable_json(private / "quality-excellence/product-flow/active-slots/current.json")
    state = readable_json(private / "production-state.json")
    proof = (slot.get("technical_exited") or {}).get(RECIPE) or {}
    require(slot.get("line_id") == 41 and slot.get("capacity") == 1
            and slot.get("active") == [] and slot.get("waiting") == []
            and proof.get("source_sha256") == old_sha
            and proof.get("artifact_sha256") == old_artifact,
            "SLOT_CHANGED_FROM_C05")
    require(state.get("active_product_slot_recipes") == []
            and state.get("publishable_product_count") == 0
            and state.get("commercial_quality_review_completed") is False,
            "PRODUCTION_STATE_CHANGED_FROM_C05")
    return slot, state


def acquire_lock(fd, seconds=55):
    deadline = time.monotonic() + seconds
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise RuntimeError("FACTORY_C09_NATIVE_CYCLE_LOCK_TIMEOUT")
            time.sleep(0.25)


def private_file(path, doc):
    with path.open("x", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), stat.S_IRUSR | stat.S_IWUSR)
        json.dump(doc, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def promote(base, stage, revision):
    require(re.fullmatch(r"[0-9a-f]{40}", revision) is not None,
            "INVALID_REVISION")
    base = Path(base)
    ops = base / "operations"
    private = base / "private/autonomous-product-cycle"
    runtime = ops / "single-product-runtime"
    current = runtime / "product_recipes" / RECIPE
    current_product = private / "digital-products" / RECIPE
    incoming = Path(stage) / "product_recipes" / RECIPE
    incoming_product = Path(stage) / "private-digital-products" / RECIPE
    stage_scripts = Path(stage) / "scripts"
    backups = ops / "backups"
    backup = backups / ("f01-c09-promotion-" + revision)
    runner = runtime / "run-single-product-cycle.sh"
    for directory in (base, ops, private, runtime, current.parent,
                      current_product.parent, backups, stage_scripts, Path(stage)):
        require(safe_dir(directory), "UNSAFE_BASE_DIRECTORY")
    require(not backup.exists() and not backup.is_symlink(), "BACKUP_ALREADY_EXISTS")
    require(runner.is_file() and not runner.is_symlink()
            and ".single-product-cycle.lock" in runner.read_text(encoding="utf-8"),
            "NATIVE_RUNNER_CONTRACT_CHANGED")
    require(shutil.disk_usage(ops).free >= 100 * 1024 * 1024,
            "INSUFFICIENT_RECOVERY_FREE_SPACE")
    require(ops.stat().st_dev == private.stat().st_dev,
            "NON_ATOMIC_CROSS_FILESYSTEM_MOVE")
    maker = load_module("c09_maker", stage_scripts / "factory_product_maker.py")
    customer = load_module("c09_customer", stage_scripts / "factory_verified_customer_cycle_20261021.py")
    require(source_sha(maker, incoming, 8) == NEW_SOURCE,
            "CANDIDATE_SOURCE_CHANGED")
    product_guard(incoming_product, NEW_SOURCE, NEW_ARCHIVE, NEW_TEST_COUNT)
    receipt = customer.inspect_product(incoming_product, RECIPE)
    require(receipt.get("customer_archive_tests_run") == NEW_TEST_COUNT
            and receipt.get("commerce_enabled") is False,
            "CANDIDATE_CUSTOMER_QA_FAILED")
    for member in incoming_product.rglob("*"):
        require(not member.is_symlink(), "CANDIDATE_PRODUCT_SYMLINK")
    backup.mkdir(mode=0o700)
    prepared_source_root = backup / "prepared-source"
    prepared_source_root.mkdir(mode=0o700)
    staged_source = prepared_source_root / RECIPE
    staged_product = backup / "incoming-product"
    shutil.copytree(incoming, staged_source, symlinks=False)
    shutil.copytree(incoming_product, staged_product, symlinks=False)
    require(source_sha(maker, staged_source, 8) == NEW_SOURCE,
            "COPIED_SOURCE_CHANGED")
    product_guard(staged_product, NEW_SOURCE, NEW_ARCHIVE, NEW_TEST_COUNT)
    private_file(backup / "customer-stage-receipt.json", receipt)
    lock = private / ".single-product-cycle.lock"
    require(not lock.is_symlink(), "UNSAFE_NATIVE_LOCK")
    fd = os.open(str(lock), os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        acquire_lock(fd)
        require(source_sha(maker, current, 8) == OLD_SOURCE,
                "CURRENT_SOURCE_CONFLICT")
        product_guard(current_product, OLD_SOURCE, OLD_ARCHIVE, OLD_TEST_COUNT)
        slot_guard(private, OLD_SOURCE, OLD_ARCHIVE)
        shutil.copy2(private / "production-state.json", backup / "production-state.before.json")
        shutil.copy2(private / "quality-excellence/product-flow/active-slots/current.json",
                     backup / "slots.before.json")
        private_file(backup / "preflight.json", {
            "previous_source_sha256": OLD_SOURCE,
            "previous_archive_sha256": OLD_ARCHIVE,
            "new_source_sha256": NEW_SOURCE,
            "new_archive_sha256": NEW_ARCHIVE,
            "commercial_release": False,
            "recovery": "previous-source and previous-product directories",
        })
        old_source = backup / "previous-source"
        old_product = backup / "previous-product"
        moved_old_source = moved_new_source = False
        moved_old_product = moved_new_product = False
        try:
            current.rename(old_source)
            moved_old_source = True
            staged_source.rename(current)
            moved_new_source = True
            current_product.rename(old_product)
            moved_old_product = True
            staged_product.rename(current_product)
            moved_new_product = True
            require(source_sha(maker, current, 8) == NEW_SOURCE,
                    "LIVE_SOURCE_READBACK_FAILED")
            product_guard(current_product, NEW_SOURCE, NEW_ARCHIVE, NEW_TEST_COUNT)
            live_acceptance = customer.inspect_product(current_product, RECIPE)
            require(live_acceptance.get("customer_archive_tests_run") == NEW_TEST_COUNT,
                    "LIVE_CUSTOMER_QA_FAILED")
            private_file(backup / "promotion-receipt.json", {
                "schema": "saeit.factory.c09.promotion.v1",
                "source_sha256": NEW_SOURCE,
                "archive_sha256": NEW_ARCHIVE,
                "customer_archive_tests": NEW_TEST_COUNT,
                "old_source_retained": True,
                "old_complete_private_product_retained": True,
                "native_cron_unchanged": True,
                "commercial_release": False,
            })
        except BaseException:
            # Quarantine new bytes; never erase old or newly built evidence.
            if moved_new_product:
                current_product.rename(backup / "quarantined-new-product")
            if moved_old_product:
                old_product.rename(current_product)
            if moved_new_source:
                current.rename(backup / "quarantined-new-source")
            if moved_old_source:
                old_source.rename(current)
            raise
    finally:
        os.close(fd)
    return {"schema": "saeit.factory.c09.promotion.v1",
            "live_source_sha256": NEW_SOURCE,
            "live_archive_sha256": NEW_ARCHIVE,
            "old_source_backed_up": True,
            "old_private_product_backed_up": True,
            "native_cron_unchanged": True,
            "commercial_release": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    print(json.dumps(promote(args.base, args.stage, args.revision), sort_keys=True))


if __name__ == "__main__":
    main()
