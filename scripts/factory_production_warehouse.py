#!/usr/bin/env python3
"""Independent Saeit VPS production warehouse (no websites, orders or network).

Input: locally manufactured artifacts that passed actual product QA.
Output: immutable, version-addressed factory stock and a private stock register.
Never approves commercial release, sends to a site, or discards failed goods.
Python 3.8+, stdlib only.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile

SCHEMA = "saeit.factory.production-warehouse.v1"
RECIPE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_ZIP = 25 * 1024 * 1024
MAX_MEMBERS = 100
MAX_MANIFEST = 64 * 1024


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def private_dir(path):
    if path.is_symlink():
        raise RuntimeError("WAREHOUSE_SYMLINK_DIRECTORY")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError("WAREHOUSE_UNSAFE_DIRECTORY")
    os.chmod(str(path), 0o700)


def read_json(path, *, max_size=MAX_MANIFEST):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > max_size:
        raise RuntimeError("WAREHOUSE_INVALID_JSON_FILE")
    value = json.loads(path.read_text(encoding="utf8"))
    if not isinstance(value, dict):
        raise RuntimeError("WAREHOUSE_BAD_JSON_OBJECT")
    return value


def write_json_atomic(path, document):
    private_dir(path.parent)
    raw = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf8")
    fd, tmp = tempfile.mkstemp(prefix=".warehouse-json-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def active_rework(root, recipe):
    path = root / "qa-rework" / recipe / "ledger.json"
    if not path.exists():
        return None
    state = read_json(path)
    if state.get("schema") != "saeit.factory.qa-rework.v1":
        raise RuntimeError("WAREHOUSE_INVALID_REWORK_LEDGER")
    status = str(state.get("current_status", ""))
    if status in ("needs_rework", "expert_review"):
        return status
    if status not in (
            "", "technically_recovered",
            "technical_qa_pass_only_owner_and_content_review_pending"):
        raise RuntimeError("WAREHOUSE_UNKNOWN_REWORK_STATE")
    return None


def valid_manufacturing_evidence(manifest):
    """Accept legacy evidence and schema-v3 evidence with a real test count."""
    evidence = manifest.get("qa_evidence")
    if evidence == "unit_tests_passed":
        return True
    if not isinstance(evidence, dict) or manifest.get("schema_version") != 3:
        return False
    count = evidence.get("tests_executed")
    minimum = evidence.get("minimum_tests_required")
    return (
        evidence.get("status") == "unit_tests_passed"
        and isinstance(count, int) and not isinstance(count, bool)
        and isinstance(minimum, int) and not isinstance(minimum, bool)
        and minimum >= 1 and count >= minimum
        and manifest.get("qa_test_count") == count
        and manifest.get("minimum_tests_required") == minimum
    )


def inspect_source(root, recipe):
    if not RECIPE.fullmatch(recipe):
        raise RuntimeError("WAREHOUSE_INVALID_PRODUCT_ID")
    folder = root / "digital-products" / recipe
    if not folder.is_dir() or folder.is_symlink():
        raise RuntimeError("WAREHOUSE_NO_MANUFACTURING_FOLDER")
    manifest = read_json(folder / "manufacturing_manifest.json")
    artifact = folder / (recipe + "-internal-qa.zip")
    if not artifact.is_file() or artifact.is_symlink():
        raise RuntimeError("WAREHOUSE_MISSING_ARTIFACT")
    if artifact.stat().st_size <= 0 or artifact.stat().st_size > MAX_ZIP:
        raise RuntimeError("WAREHOUSE_PACKAGE_TOO_LARGE")
    expected_files = manifest.get("files")
    if (
        manifest.get("recipe") != recipe or manifest.get("qa_status") != "passed"
        or not valid_manufacturing_evidence(manifest)
        or manifest.get("commercial_status") != "private_internal_qa_pass_not_published"
        or manifest.get("public_listing_enabled") is not False
        or manifest.get("customer_order_required") is not False
        or manifest.get("owner_publication_approval") is not False
        or not SHA.fullmatch(str(manifest.get("source_sha256", "")))
        or not SHA.fullmatch(str(manifest.get("artifact_sha256", "")))
        or not isinstance(expected_files, list)
        or not expected_files or len(expected_files) > MAX_MEMBERS
        or any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", n)
               or n in (".", "..") for n in expected_files)
        or len(set(expected_files)) != len(expected_files)
    ):
        raise RuntimeError("WAREHOUSE_MANUFACTURING_QA_NOT_APPROVED")
    checksum = digest(artifact)
    if checksum != manifest["artifact_sha256"]:
        raise RuntimeError("WAREHOUSE_ARTIFACT_SHA_MISMATCH")
    with zipfile.ZipFile(str(artifact), "r") as archive:
        wanted = [recipe + "/" + filename for filename in sorted(expected_files)]
        got = archive.namelist()
        if sorted(got) != wanted or archive.testzip() is not None:
            raise RuntimeError("WAREHOUSE_ZIP_CONTENT_QA_FAILED")
        for info in archive.infolist():
            if info.is_dir() or info.flag_bits & 0x1 or info.file_size > MAX_ZIP:
                raise RuntimeError("WAREHOUSE_UNSAFE_ZIP_ENTRY")
    return artifact, manifest


def verify_stored(version):
    saved = read_json(version / "warehouse_manifest.json")
    product_id = saved.get("product_id")
    if not isinstance(product_id, str) or not RECIPE.fullmatch(product_id):
        raise RuntimeError("WAREHOUSE_BAD_STORED_ID")
    if saved.get("schema") != SCHEMA or saved.get("manufacturing_qc") != "passed":
        raise RuntimeError("WAREHOUSE_STORED_QA_INVALID")
    sha = saved.get("source_sha256")
    if not isinstance(sha, str) or not SHA.fullmatch(sha) or version.name != sha:
        raise RuntimeError("WAREHOUSE_VERSION_ID_MISMATCH")
    if version.parent.name != product_id:
        raise RuntimeError("WAREHOUSE_PRODUCT_FOLDER_MISMATCH")
    file = version / "product.zip"
    if not file.is_file() or file.is_symlink() or digest(file) != saved.get("artifact_sha256"):
        raise RuntimeError("WAREHOUSE_STOCK_CORRUPTION")
    if file.stat().st_size != saved.get("bytes") or file.stat().st_size > MAX_ZIP:
        raise RuntimeError("WAREHOUSE_STOCK_SIZE_MISMATCH")
    if saved.get("site_transfer_state") != "not_transferred" or saved.get("commercial_release") is not False:
        raise RuntimeError("WAREHOUSE_STOCK_TRANSFER_POLICY_VIOLATION")
    return saved


def stock_one(root, recipe, warehouse):
    artifact, manifest = inspect_source(root, recipe)
    if active_rework(root, recipe):
        return {"product_id": recipe, "action": "held_for_rework", "source_sha256": manifest["source_sha256"]}
    container = warehouse / "finished" / recipe
    private_dir(container)
    version = container / manifest["source_sha256"]
    if version.exists() or version.is_symlink():
        saved = verify_stored(version)
        if saved["artifact_sha256"] != manifest["artifact_sha256"]:
            raise RuntimeError("WAREHOUSE_SAME_VERSION_CHANGED")
        return {"product_id": recipe, "action": "already_stocked", "source_sha256": manifest["source_sha256"]}
    payload = {
        "schema": SCHEMA,
        "product_id": recipe,
        "product_name": str(manifest.get("name", recipe))[:200],
        "source_sha256": manifest["source_sha256"],
        "artifact_sha256": manifest["artifact_sha256"],
        "bytes": artifact.stat().st_size,
        "manufacturing_qc": "passed",
        "qa_evidence": "unit_tests_and_zip_integrity",
        "qa_test_count": manifest.get("qa_test_count", 1),
        "minimum_tests_required": manifest.get("minimum_tests_required", 1),
        "production_state": "finished_goods_in_factory",
        "commercial_release": False,
        "content_rights_market_review": "pending",
        "site_transfer_state": "not_transferred",
        "receiving_site": None,
        "order_required": False,
        "external_api_required": False,
        "warehouse_origin": "vps_local_manufacturing",
    }
    tmp = Path(tempfile.mkdtemp(prefix=".stock-", dir=str(container)))
    try:
        os.chmod(str(tmp), 0o700)
        destination = tmp / "product.zip"
        with artifact.open("rb") as source, destination.open("xb") as target:
            shutil.copyfileobj(source, target, 1024 * 1024)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(str(destination), 0o400)
        write_json_atomic(tmp / "warehouse_manifest.json", payload)
        if digest(destination) != payload["artifact_sha256"]:
            raise RuntimeError("WAREHOUSE_COPY_QA_FAILED")
        if version.exists():
            raise RuntimeError("WAREHOUSE_VERSION_RACE")
        tmp.rename(version)
        verify_stored(version)
    finally:
        if tmp.exists():
            shutil.rmtree(str(tmp))
    return {"product_id": recipe, "action": "stocked", "source_sha256": manifest["source_sha256"]}


def stock_summary(warehouse):
    finished = warehouse / "finished"
    stocked = []
    if finished.is_dir():
        for product in sorted(finished.iterdir()):
            if product.is_symlink() or not product.is_dir() or not RECIPE.fullmatch(product.name):
                raise RuntimeError("WAREHOUSE_INVALID_FINISHED_FOLDER")
            for version in sorted(product.iterdir()):
                if version.is_symlink() or not version.is_dir() or not SHA.fullmatch(version.name):
                    raise RuntimeError("WAREHOUSE_BAD_VERSION_FOLDER")
                record = verify_stored(version)
                stocked.append({
                    "product_id": record["product_id"],
                    "version": record["source_sha256"],
                    "artifact_sha256": record["artifact_sha256"],
                    "bytes": record["bytes"],
                    "manufacturing_qc": record["manufacturing_qc"],
                    "commercial_release": False,
                    "site_transfer_state": "not_transferred",
                })
    return stocked


def cycle(root):
    root = Path(root).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError("WAREHOUSE_FACTORY_PRIVATE_ROOT_MISSING")
    private_dir(root / "production-warehouse")
    warehouse = root / "production-warehouse"
    with (warehouse / ".warehouse.lock").open("a+b") as lock:
        os.chmod(str(warehouse / ".warehouse.lock"), 0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "already_running", "stocked": 0, "warehouse_count": 0}
        source = root / "digital-products"
        if not source.is_dir() or source.is_symlink():
            raise RuntimeError("WAREHOUSE_MANUFACTURING_INPUT_NOT_READY")
        actions = []
        blocked = []
        for child in sorted(source.iterdir()):
            if child.is_symlink() or not child.is_dir() or not RECIPE.fullmatch(child.name):
                raise RuntimeError("WAREHOUSE_UNEXPECTED_MANUFACTURING_ENTRY")
            try:
                item = stock_one(root, child.name, warehouse)
                actions.append(item)
            except (RuntimeError, ValueError, OSError, zipfile.BadZipFile) as error:
                # No deletion: record exception and retain all input files.
                blocked.append({"product_id": child.name, "reason": str(error)[:160]})
        inventory = stock_summary(warehouse)
        register = {
            "schema": SCHEMA,
            "factory_site_dependency": False,
            "customer_order_dependency": False,
            "distribution_enabled": False,
            "sites_contacted": 0,
            "finished_goods_versions": len(inventory),
            "finished_goods_product_count": len(set(i["product_id"] for i in inventory)),
            "awaiting_commercial_review": len(inventory),
            "records": inventory,
            "last_cycle_actions": actions,
            "needs_rework_or_review": blocked,
        }
        write_json_atomic(warehouse / "stock-register.json", register)
        return {
            "status": "needs_rework" if blocked else "ok",
            "stocked": len([x for x in actions if x["action"] == "stocked"]),
            "warehouse_count": len(inventory),
            "held": len(blocked) + len([x for x in actions if x["action"] == "held_for_rework"]),
        }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.factory_private).expanduser().resolve()
    if args.verify_only:
        warehouse = root / "production-warehouse"
        value = stock_summary(warehouse)
        if (warehouse / "stock-register.json").exists():
            register = read_json(warehouse / "stock-register.json", max_size=4 * 1024 * 1024)
            if register.get("schema") != SCHEMA or register.get("finished_goods_versions") != len(value):
                raise RuntimeError("WAREHOUSE_REGISTER_MISMATCH")
        print("FACTORY_WAREHOUSE_VERIFIED_VERSIONS=" + str(len(value)))
        return 0
    result = cycle(root)
    print("FACTORY_WAREHOUSE_STATUS=" + result["status"])
    print("FACTORY_WAREHOUSE_NEW_STOCK=" + str(result["stocked"]))
    print("FACTORY_WAREHOUSE_TOTAL_VERSIONS=" + str(result["warehouse_count"]))
    print("FACTORY_WAREHOUSE_HELD_FOR_REWORK=" + str(result.get("held", 0)))
    print("FACTORY_SITE_DEPENDENCY=false")
    print("FACTORY_SITE_TRANSFER_ENABLED=false")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("FACTORY_WAREHOUSE_ERROR=" + type(error).__name__ + ":" + str(error)[:300], file=sys.stderr)
        sys.exit(1)
