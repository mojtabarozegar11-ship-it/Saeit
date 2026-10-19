#!/usr/bin/env python3
"""Offline, QA-first product manufacturer with an extensible recipe directory.

Any new product folder with a README heading and one or more test_*.py files
is discovered automatically. Tests pass before a private reproducible ZIP is
written. No orders, network calls, AI API, publication, or token use. Python 3.8+.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile


RECIPE_ID = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
MIN_TESTS_PER_RECIPE = 1
TEST_RUN_SUMMARY = re.compile(r"^Ran\s+(\d+)\s+tests?\b", re.MULTILINE)
DEFAULT_RECIPES = Path(__file__).resolve().parents[1] / "product_recipes"


def discover_recipes(recipes_root):
    """Discover every valid recipe folder; adding a folder needs no code edit."""
    root = Path(recipes_root).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError("RECIPE_ROOT_MISSING_OR_UNSAFE")
    recipes = {}
    for source in sorted(root.iterdir(), key=lambda item: item.name):
        if source.name.startswith("."):
            continue
        if source.is_symlink() or not source.is_dir() or not RECIPE_ID.fullmatch(source.name):
            raise RuntimeError("RECIPE_DIRECTORY_INVALID:" + source.name)
        files = []
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise RuntimeError("RECIPE_FILE_MISSING_OR_UNSAFE:" + path.relative_to(source).as_posix())
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            if any(part.startswith(".") or part == "__pycache__" for part in Path(relative).parts):
                continue
            files.append(relative)
        tests = [name for name in files if Path(name).name.startswith("test_") and name.endswith(".py")]
        if "README.md" not in files or not tests:
            raise RuntimeError("RECIPE_CONTRACT_INVALID:" + source.name)
        readme = (source / "README.md").read_text(encoding="utf-8")
        heading = next((line.lstrip("#").strip() for line in readme.splitlines()
                        if line.startswith("#") and line.lstrip("#").strip()), "")
        name = heading or source.name.replace("_", " ").title()
        recipes[source.name] = (name, tuple(files))
    if not recipes:
        raise RuntimeError("NO_VALID_PRODUCT_RECIPES")
    return recipes


# Compatibility/status view. Runtime cycles always rediscover from their supplied root.
RECIPES = discover_recipes(DEFAULT_RECIPES)


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
    """Require a successful suite and an explicit, non-zero unittest count."""
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py", "-v"],
        cwd=str(source), capture_output=True, text=True, timeout=timeout,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
    )
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    summaries = list(TEST_RUN_SUMMARY.finditer(output))
    test_count = int(summaries[-1].group(1)) if summaries else 0
    if result.returncode != 0 or test_count < MIN_TESTS_PER_RECIPE:
        raise RuntimeError(
            "PRODUCT_QA_FAILED:executed_tests=" + str(test_count)
            + ";minimum=" + str(MIN_TESTS_PER_RECIPE) + ";" + output[-1000:]
        )
    return {"status": "unit_tests_passed", "tests_executed": test_count,
            "minimum_tests_required": MIN_TESTS_PER_RECIPE}


def make_zip(path, source, recipe, files):
    ensure_private(path.parent)
    handle, temporary = tempfile.mkstemp(prefix=".release-", dir=str(path.parent))
    os.close(handle)
    try:
        with zipfile.ZipFile(temporary, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for filename in sorted(files):
                info = zipfile.ZipInfo(recipe + "/" + filename, date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, (source / filename).read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(temporary) as check:
            expected = [recipe + "/" + filename for filename in sorted(files)]
            if check.namelist() != expected or check.testzip() is not None:
                raise RuntimeError("PRODUCT_PACKAGE_QA_FAILED")
        os.chmod(temporary, 0o600)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def manufacture(recipe, recipes_root, private_root):
    catalog = discover_recipes(recipes_root)
    if recipe not in catalog:
        raise ValueError("UNSUPPORTED_RECIPE")
    name, files = catalog[recipe]
    source = Path(recipes_root).expanduser().resolve() / recipe
    root = Path(private_root).expanduser().resolve() / recipe
    checksum = source_digest(source, files)
    zip_path = root / (recipe + "-internal-qa.zip")
    manifest_path = root / "manufacturing_manifest.json"
    try:
        prior = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        prior = {}
    if (prior.get("source_sha256") == checksum and prior.get("qa_status") == "passed"
            and zip_path.is_file() and prior.get("artifact_sha256") == sha256_file(zip_path)):
        return {"recipe": recipe, "changed": False, "qa_status": "passed",
                "private_artifact": str(zip_path)}
    qa_status = verify_recipe(source)
    make_zip(zip_path, source, recipe, files)
    metadata = {
        "schema_version": 2, "recipe": recipe, "name": name,
        "source_sha256": checksum, "artifact_sha256": sha256_file(zip_path),
        "bytes": zip_path.stat().st_size, "files": list(sorted(files)),
        "qa_status": "passed", "qa_evidence": qa_status,
        "qa_test_count": qa_status["tests_executed"],
        "minimum_tests_required": MIN_TESTS_PER_RECIPE,
        "scientific_validity": "pending_independent_specialist_review",
        "economic_value": "pending_independent_review",
        "commercial_and_legal_review": "pending",
        "quality_scope": "software_tests_and_zip_integrity_only",
        "commercial_status": "private_internal_qa_pass_not_published",
        "factory_trigger": "inventory_and_scheduled_manufacturing",
        "customer_order_required": False, "price": None,
        "public_listing_enabled": False, "owner_publication_approval": False,
        "needs_content_and_market_review": True, "needs_storefront_adapter_verification": True,
    }
    atomic_text(manifest_path, json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return {"recipe": recipe, "changed": True, "qa_status": "passed",
            "private_artifact": str(zip_path)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipes", default=str(DEFAULT_RECIPES))
    ap.add_argument("--out")\n    ap.add_argument("--verify-only", action="store_true",
                    help="Run all discovered product suites without writing packages.")
    ap.add_argument("--recipe", default="all", help="Recipe slug or all (discovered automatically).")
    ap.add_argument("--max-builds", type=int, default=None,
                    help="Optional positive limit; by default build every discovered recipe.")
    args = ap.parse_args(argv)
    if args.max_builds is not None and args.max_builds < 1:
        raise ValueError("max-builds must be positive")
    if not args.verify_only and not args.out:
        ap.error("--out is required unless --verify-only is used")\n    recipes = discover_recipes(args.recipes)
    if args.recipe != "all" and args.recipe not in recipes:
        raise ValueError("UNSUPPORTED_RECIPE:" + args.recipe)
    selected = sorted(recipes) if args.recipe == "all" else [args.recipe]
    if args.max_builds is not None:
        selected = selected[:args.max_builds]
    if args.verify_only:
        for recipe in selected:
            evidence = verify_recipe(Path(args.recipes).expanduser().resolve() / recipe)
            print("FACTORY_RECIPE_TESTS=" + recipe + ":" + str(evidence["tests_executed"]))
        print("FACTORY_MIN_TESTS_REQUIRED=" + str(MIN_TESTS_PER_RECIPE))
        print("FACTORY_VERIFIED_RECIPE_COUNT=" + str(len(selected)))
        return 0
    results = [manufacture(recipe, args.recipes, args.out) for recipe in selected]
    for item in results:
        print("FACTORY_DIGITAL_PRODUCT_RECIPE=" + item["recipe"])
        print("FACTORY_DIGITAL_PRODUCT_QA=" + item["qa_status"])
        print("FACTORY_DIGITAL_PRODUCT_BUILT_OR_UPDATED=" + str(item["changed"]).lower())
    print("FACTORY_PRODUCTS_READY_FOR_PRIVATE_INTERNAL_REVIEW=" + str(len(results)))
    print("FACTORY_DISCOVERED_RECIPE_COUNT=" + str(len(recipes)))
    print("FACTORY_ORDER_DEPENDENCY=false")
    print("FACTORY_PUBLICATION_ENABLED=false")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print("FACTORY_MANUFACTURING_ERROR=" + str(error)[:1200], file=sys.stderr)
        sys.exit(1)
