#!/usr/bin/env python3
"""Evidence-bound owner backlog -> real F28 technical products.

Only three explicitly specified, mathematically checkable items are admitted
from the 500-demand register. Unknown product families remain unimplemented.
No storefront changes, QA-1000 signatures, demand verification or fake release.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile

FAMILY = "F28"
SCHEMA = "saeit.factory.owner-500-real-pilot.v1"
TARGETS = {
    "PD-0193": {
        "title": "Food Batch Ingredient Scaling Tool",
        "problem": "Calculate scaled ingredient grams from known baseline recipe mass, baseline serving count and target serving count.",
        "expression": "(baseline_ingredient_g * target_servings) / baseline_servings",
        "output_unit": "g",
        "inputs": [
            {"name": "baseline_ingredient_g", "unit": "g", "minimum": 1, "maximum": 10000},
            {"name": "target_servings", "unit": "servings", "minimum": 1, "maximum": 1000, "integral": True},
            {"name": "baseline_servings", "unit": "servings", "minimum": 1, "maximum": 1000, "integral": True},
        ],
    },
    "PD-0196": {
        "title": "Greenhouse Ventilation Volume Estimator",
        "problem": "Calculate the geometric interior volume of a rectangular greenhouse using the measured internal dimensions only; not an airflow recommendation.",
        "expression": "(room_length_m * room_width_m) * room_height_m",
        "output_unit": "m3",
        "inputs": [
            {"name": "room_length_m", "unit": "m", "minimum": 1, "maximum": 1000},
            {"name": "room_width_m", "unit": "m", "minimum": 1, "maximum": 1000},
            {"name": "room_height_m", "unit": "m", "minimum": 1, "maximum": 100},
        ],
    },
    "PD-0197": {
        "title": "Irrigation Flow Rate Estimator",
        "problem": "Calculate average delivered water flow by dividing measured litres by elapsed minutes; no pressure or pump sizing claims.",
        "expression": "litres_delivered / minutes_elapsed",
        "output_unit": "litres/minute",
        "inputs": [
            {"name": "litres_delivered", "unit": "litres", "minimum": 1, "maximum": 1000000},
            {"name": "minutes_elapsed", "unit": "minutes", "minimum": 1, "maximum": 100000},
        ],
    },
}

def digest(content):
    return hashlib.sha256(content).hexdigest()

def read_json(path, limit=2_000_000):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("PILOT_UNSAFE_MISSING_OR_LARGE_INPUT")
    raw = path.read_bytes()
    item = json.loads(raw.decode("utf8"))
    if not isinstance(item, dict):
        raise ValueError("PILOT_EXPECTED_JSON_OBJECT")
    return raw, item

def load(name, scripts_dir):
    source = scripts_dir / (name + ".py")
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("PILOT_PINNED_MODULE_MISSING:" + name)
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def validated_targets(catalog, live_snapshot):
    if (catalog.get("schema") != "saeit.factory.verified-owner-demand-portfolio.v1"
            or catalog.get("count") != 500 or catalog.get("release_authorized") is not False
            or live_snapshot.get("schema") != "saeit.factory.production-instructions.v1"):
        raise ValueError("PILOT_OWNER_SOURCE_SCHEMA_INVALID")
    products = catalog.get("products")
    rows = live_snapshot.get("items")
    if not isinstance(products, list) or len(products) != 500 or not isinstance(rows, list):
        raise ValueError("PILOT_OWNER_500_INPUTS_NOT_VERIFIED")
    ids = {x.get("id") for x in products if isinstance(x, dict)}
    titles = {x.get("title") for x in products if isinstance(x, dict)}
    if len(ids) != 500 or len(titles) != 500:
        raise ValueError("PILOT_OWNER_500_DUPLICATE_OR_BAD_RECORD")
    by_id = {x.get("id"): x for x in products}
    by_order_id = {r.get("id"): r for r in rows if isinstance(r, dict)}
    if len(by_order_id) != len(rows):
        raise ValueError("PILOT_SNAPSHOT_DUPLICATE_ID")
    selected = {}
    for product_id, definition in TARGETS.items():
        product = by_id.get(product_id)
        if (not isinstance(product, dict)
                or product.get("family_id") != FAMILY
                or product.get("title") != definition["title"]
                or product.get("product_created") is not False
                or product.get("quality1000_certified") is not False
                or product.get("publication_approved") is not False):
            raise ValueError("PILOT_OWNER_ITEM_NOT_ELIGIBLE:" + product_id)
        num = int(product_id.split("-")[1])
        snapshot_id = "factory_500_%04d" % num
        row = by_order_id.get(snapshot_id)
        if (not isinstance(row, dict) or row.get("title") != product["title"]
                or product_id not in row.get("specification", "")
                or row.get("specification", "").find("Family F28;") < 0):
            raise ValueError("PILOT_LIVE_VPS_SOURCE_MISMATCH:" + product_id)
        selected[product_id] = (product, row)
    return selected

def save_once(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("PILOT_UNSAFE_RECEIPT_LOCATION")
    raw = (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("PILOT_EXISTING_RECEIPT_IMMUTABLE")
        return
    fd, name = tempfile.mkstemp(prefix=".pilot-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def produce(root, catalog_file, scripts_dir, limit=3):
    root = Path(root)
    scripts_dir = Path(scripts_dir)
    if root.is_symlink() or not root.is_dir() or limit not in (1, 2, 3):
        raise ValueError("PILOT_UNSAFE_ROOT_OR_LIMIT")
    catalog_raw, catalog = read_json(Path(catalog_file))
    live = root / "production-order-inputs" / "factory-invention-snapshot.json"
    live_raw, snapshot = read_json(live)
    selected = validated_targets(catalog, snapshot)
    intake = load("factory_design_intake", scripts_dir)
    designer = load("factory_recipe_designer", scripts_dir)
    maker = load("factory_product_maker", scripts_dir)
    customer = load("factory_verified_customer_cycle_20261021", scripts_dir)
    source_root = root / "generated-product-recipes"
    if source_root.is_symlink() or not source_root.is_dir():
        raise RuntimeError("PILOT_REAL_SOURCE_ROOT_REQUIRED")
    products = root / "digital-products"
    if products.is_symlink():
        raise RuntimeError("PILOT_PRODUCTS_ROOT_UNSAFE")
    products.mkdir(mode=0o700, exist_ok=True)
    area = root / "owner-demand-pilot"
    if area.is_symlink():
        raise RuntimeError("PILOT_AUDIT_ROOT_UNSAFE")
    area.mkdir(mode=0o700, exist_ok=True)
    lock = area / ".pilot.lock"
    if lock.is_symlink():
        raise RuntimeError("PILOT_LOCK_SYMLINK")
    outcomes = []
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(), 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        for item_id in list(TARGETS)[:limit]:
            definition = TARGETS[item_id]
            product, source = selected[item_id]
            brief = {"schema": intake.SCHEMA, "family_id": FAMILY,
                     "mathematical_definition": definition}
            spec = intake.expand_definition(brief, "factory_invention")
            # Binding the exact owner and VPS intake records to the GENERATED source.
            spec["upstream"] = {
                "origin": "factory_invention",
                "owner_portfolio_id": item_id,
                "owner_portfolio_sha256": digest(catalog_raw),
                "vps_owner_snapshot_sha256": digest(live_raw),
                "request_sha256": designer.digest(product),
                "live_request_sha256": designer.digest(source),
                "market_demand_verified": False
            }
            result = designer.compile_recipe(spec, source_root)
            recipe = result["recipe"]
            saved_raw, stored = read_json(source_root / recipe / "design_request.json")
            if stored != spec:
                raise RuntimeError("PILOT_EXISTING_FUNCTIONAL_RECIPE_NOT_SAME_REQUEST:" + item_id)
            built = maker.manufacture(recipe, source_root, products)
            if built["qa_status"] != "passed":
                raise RuntimeError("PILOT_MANUFACTURING_QA_FAILED:" + item_id)
            checked = customer.inspect_product(products / recipe, recipe)
            if checked["customer_zip_extract_test"] != "passed":
                raise RuntimeError("PILOT_CUSTOMER_ARCHIVE_QA_FAILED:" + item_id)
            customer.persist_pending(root, checked)
            receipt = {"schema": SCHEMA,
                       "owner_item_id": item_id, "owner_title": product["title"],
                       "family_id": FAMILY, "recipe": recipe,
                       "source_sha256": checked["source_sha256"],
                       "artifact_sha256": checked["artifact_sha256"],
                       "original_500_source_sha256": digest(catalog_raw),
                       "factory_snapshot_entry_sha256": designer.digest(source),
                       "design_created_this_run": result["created"],
                       "archive_rebuilt_this_run": built["changed"],
                       "customer_zip_tests": checked["customer_archive_tests_run"],
                       "technical_customer_qa": "passed",
                       "product_is_private": True,
                       "independent_domain_review": False,
                       "professional_quality_1000_certified": False,
                       "publication_approved": False,
                       "sites_modified": 0}
            # immutable per product+artifact; never rewrite old revision or claim sale
            filename = "%s-%s.json" % (item_id, checked["artifact_sha256"][:24])
            permanent = dict(receipt)
            # Creation/rebuild booleans are *run measurements*, not immutable
            # product properties: preserve original artifact receipt on replay.
            permanent.pop("design_created_this_run")
            permanent.pop("archive_rebuilt_this_run")
            save_once(area / filename, permanent)
            outcomes.append(receipt)
    return {"schema": SCHEMA,
            "owner_backlog_total": 500,
            "selected_owner_items": len(outcomes),
            "real_technical_product_packages_checked": len(outcomes),
            "new_source_recipes": sum(x["design_created_this_run"] for x in outcomes),
            "newly_built_or_updated_packages": sum(x["archive_rebuilt_this_run"] for x in outcomes),
            "independent_customer_qa_passed": len(outcomes),
            "product_receipts": outcomes,
            "remaining_unproven_or_unbuilt_needs": 500 - len(outcomes),
            "verified_market_demand_count": 0,
            "professional_quality_1000_certified": 0,
            "website_deployments": 0}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory-private", type=Path, required=True)
    p.add_argument("--owner-catalog", type=Path, required=True)
    p.add_argument("--scripts-dir", type=Path, required=True)
    p.add_argument("--limit", type=int, default=3)
    a = p.parse_args()
    result = produce(a.factory_private, a.owner_catalog, a.scripts_dir, a.limit)
    print("FACTORY_OWNER_500_FIRST_REAL_BUILD=" + json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["selected_owner_items"] != a.limit:
        raise RuntimeError("PILOT_NOT_ALL_SELECTED_PRODUCTS_COMPLETE")

if __name__ == "__main__":
    main()
