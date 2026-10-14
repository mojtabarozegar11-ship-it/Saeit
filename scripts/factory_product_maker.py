#!/usr/bin/env python3
"""Independent Saeit digital-product manufacturer, QA-first and order-free.

Creates actual working downloadable ZIP artifacts from vetted versioned recipes,
entirely on the host. Never reads customer orders, processes payments, calls an
AI API, sets product active, or publishes to any marketplace. Python 3.8+.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


RECIPES = {
    "farm_enterprise_economics": (
        "Farm Enterprise Economics Toolkit",
        ("calculator.py", "test_calculator.py", "README.md", "example_inputs.json"),
    ),
    "water_budget_economics": (
        "Agricultural Water Budget Economics Planner",
        ("calculator.py", "test_calculator.py", "README.md", "example_inputs.json"),
    ),
}


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_private(directory):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(str(directory), 0o700)


def atomic_text(path, content):
    ensure_private(path.parent)
    handle, temporary = tempfile.mkstemp(prefix=".stage-", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def source_digest(source, files):
    checksum = hashlib.sha256()
    for filename in files:
        path = source / filename
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("RECIPE_FILE_MISSING_OR_UNSAFE:" + filename)
        checksum.update(filename.encode("utf-8") + b"\x00")
        checksum.update(path.read_bytes())
    return checksum.hexdigest()


def verify_recipe(source, *, timeout=60):
    """Run the real product tests; failure is a hard manufacturing stop."""
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", "test_calculator.py"],
        cwd=str(source),
        capture_output=True, text=True,
        timeout=timeout,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
    )
    if result.returncode != 0 or "OK" not in result.stderr:
        raise RuntimeError("PRODUCT_QA_FAILED:" + (result.stderr or result.stdout)[-1200:])
    return "unit_tests_passed"


def make_zip(path, source, recipe, files):
    ensure_private(path.parent)
    handle, temporary = tempfile.mkstemp(prefix=".release-", dir=str(path.parent))
    os.close(handle)
    try:
        with zipfile.ZipFile(temporary, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zip_file:
            for filename in sorted(files):
                info = zipfile.ZipInfo(recipe + "/" + filename, date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                zip_file.writestr(info, (source / filename).read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(temporary) as check:
            expected = [recipe + "/" + f for f in sorted(files)]
            if check.namelist() != expected or check.testzip() is not None:
                raise RuntimeError("PRODUCT_PACKAGE_QA_FAILED")
        os.chmod(temporary, 0o600)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def manufacture(recipe, recipes_root, private_root):
    if recipe not in RECIPES:
        raise ValueError("UNSUPPORTED_RECIPE")
    name, files = RECIPES[recipe]
    source = Path(recipes_root).expanduser().resolve() / recipe
    root = Path(private_root).expanduser().resolve() / recipe
    checksum = source_digest(source, files)
    zip_path = root / (recipe + "-internal-qa.zip")
    manifest_path = root / "manufacturing_manifest.json"
    try:
        prior = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        prior = {}
    if (prior.get("source_sha256") == checksum
            and prior.get("qa_status") == "passed"
            and zip_path.is_file()
            and prior.get("artifact_sha256") == sha256_file(zip_path)):
        return {"recipe": recipe, "changed": False, "qa_status": "passed",
                "private_artifact": str(zip_path)}
    qa_status = verify_recipe(source)
    make_zip(zip_path, source, recipe, files)
    metadata = {
        "schema_version": 1,
        "recipe": recipe,
        "name": name,
        "source_sha256": checksum,
        "artifact_sha256": sha256_file(zip_path),
        "bytes": zip_path.stat().st_size,
        "files": list(sorted(files)),
        "qa_status": "passed",
        "qa_evidence": qa_status,
        "commercial_status": "private_internal_qa_pass_not_published",
        "factory_trigger": "inventory_and_scheduled_manufacturing",
        "customer_order_required": False,
        "price": None,
        "public_listing_enabled": False,
        "owner_publication_approval": False,
        "needs_content_and_market_review": True,
        "needs_storefront_adapter_verification": True,
    }
    atomic_text(manifest_path, json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return {"recipe": recipe, "changed": True, "qa_status": "passed",
            "private_artifact": str(zip_path)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipes", default=str(Path(__file__).resolve().parents[1] / "product_recipes"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--recipe", choices=["all"] + sorted(RECIPES), default="all")
    ap.add_argument("--max-builds", type=int, default=2)
    args = ap.parse_args(argv)
    if not 1 <= args.max_builds <= 20:
        raise ValueError("max-builds must be between 1 and 20")
    selected = sorted(RECIPES) if args.recipe == "all" else [args.recipe]
    results = [manufacture(recipe, args.recipes, args.out) for recipe in selected[:args.max_builds]]
    for item in results:
        print("FACTORY_DIGITAL_PRODUCT_RECIPE=" + item["recipe"])
        print("FACTORY_DIGITAL_PRODUCT_QA=" + item["qa_status"])
        print("FACTORY_DIGITAL_PRODUCT_BUILT_OR_UPDATED=" + str(item["changed"]).lower())
    print("FACTORY_PRODUCTS_READY_FOR_PRIVATE_INTERNAL_REVIEW=" + str(len(results)))
    print("FACTORY_ORDER_DEPENDENCY=false")
    print("FACTORY_PUBLICATION_ENABLED=false")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print("FACTORY_MANUFACTURING_ERROR=" + str(error)[:1200], file=sys.stderr)
        sys.exit(1)
