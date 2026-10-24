#!/usr/bin/env python3
"""Exact AGRI200 -> VPS work order -> storefront private readiness ledger.

This is a read-only, fail-closed production handoff. Presence of a JSON receipt,
a ZIP, a suggested price, or an internal QC result is *not* proof of independent
scientific clearance, trusted rights, live payment or buyer delivery. No products
are published, charged, discounted or marked approved by this program.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import zipfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRICE_PATH = ROOT / "scripts/agri200_fair_pricing_owner_only_20261024.py"
INDEX_SCHEMA = "saeit.factory.owner-agri200-p0-index.v1"
SCHEMA = "saeit.agri200.exact-private-readiness.v1"
ORDER = re.compile(r"WO-[0-9]{8}\Z")
REVISION = re.compile(r"WO-[0-9]{8}--r[0-9]{3}\.json\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
# Technical byte ceiling is independent of product quality, sales and approval.
MAX_ARCHIVE_BYTES = 16_000_000
MAX_UNCOMPRESSED_BYTES = 32_000_000
PRODUCT_STORAGE_ALERT_BYTES = 1_000_000_000
ARCHIVE_VARIANTS = {
    "navigator": ("stage-05", "downloadable-candidates"),
    "source_grounded_v003": ("stage-05", "source-grounded-v003"),
}


def read_json(path: Path, maximum: int = 2_000_000) -> dict[str, Any]:
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= maximum):
        raise ValueError("UNSAFE_EVIDENCE_FILE:" + path.name)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("EVIDENCE_NOT_OBJECT:" + path.name)
    return value


def safe_dir(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink()


def source_digest(product_id: str, fa: str, en: str) -> str:
    payload = {"id": product_id, "fa": fa, "en": en}
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def private_receipt(area: Path, subdirectory: str, order: str) -> dict[str, Any] | None:
    folder = area / subdirectory
    if not safe_dir(folder):
        return None
    matches = sorted(
        p for p in folder.iterdir()
        if p.name.startswith(order + "--r")
        and REVISION.fullmatch(p.name)
        and p.is_file() and not p.is_symlink()
    )
    if not matches:
        return None
    # The latest file is a *signal*, not trusted clearance.
    return read_json(matches[-1], 1_000_000)



def physical_archive(area: Path, receipt: dict[str, Any] | None,
                     order_id: str, variant: str) -> dict[str, Any]:
    """Validate measured ZIP bytes, not claims of scientific/commercial quality.

    Path traversal and symlinks are rejected; bytes are hashed from the
    actual file. Missing or invalid artifacts remain non-saleable, and this
    routine never creates, modifies, extracts, or deletes an archive.
    """
    if receipt is None:
        return {"status": "MISSING", "bytes": 0}
    try:
        if not isinstance(receipt, dict) or receipt.get("order_id") != order_id:
            raise ValueError("ARCHIVE_ORDER_MISMATCH")
        relative = receipt.get("archive_relative_path")
        if not isinstance(relative, str) or not 0 < len(relative) <= 240:
            raise ValueError("ARCHIVE_PATH_INVALID")
        part = Path(relative)
        prefix = ARCHIVE_VARIANTS[variant]
        if (part.is_absolute() or ".." in part.parts or
                len(part.parts) != 4 or tuple(part.parts[:2]) != prefix or
                not part.parts[2].startswith(order_id + "--r") or
                not part.name.endswith(".zip")):
            raise ValueError("ARCHIVE_PATH_OUTSIDE_PRODUCT_STAGE")
        path = area
        for component in part.parts:
            path = path / component
            if path.is_symlink():
                raise ValueError("ARCHIVE_SYMLINK_REJECTED")
        if not path.is_file():
            raise ValueError("ARCHIVE_NOT_FOUND")
        file_size = path.stat().st_size
        expected_size = receipt.get("zip_bytes")
        expected_sha = receipt.get("zip_sha256")
        if (type(expected_size) is not int or not 0 < expected_size <= MAX_ARCHIVE_BYTES or
                file_size != expected_size or not isinstance(expected_sha, str) or
                HEX.fullmatch(expected_sha) is None):
            raise ValueError("ARCHIVE_SIZE_OR_RECEIPT_INVALID")
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(block)
        if hasher.hexdigest() != expected_sha:
            raise ValueError("ARCHIVE_CHECKSUM_MISMATCH")
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if (not members or len(members) > 80 or
                    sum(m.file_size for m in members) > MAX_UNCOMPRESSED_BYTES or
                    archive.testzip() is not None):
                raise ValueError("ARCHIVE_CONTENT_CORRUPT_OR_OVERSIZED")
            seen = set()
            for member in members:
                inner = member.filename
                components = Path(inner).parts
                if (not inner or inner in seen or member.is_dir() or
                        inner.startswith("/") or ".." in components or
                        "\\\\" in inner or member.flag_bits & 1):
                    raise ValueError("ARCHIVE_UNSAFE_MEMBER")
                seen.add(inner)
        return {"status": "VERIFIED_TECHNICAL_ZIP", "bytes": file_size,
                "sha256": expected_sha}
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        return {"status": "INVALID", "bytes": 0,
                "reason": type(exc).__name__ + ":" + str(exc)[:80]}


def archive_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate only actually verified ZIP sizes; flag anomalous capacity."""
    result = {}
    total = 0
    for variant in ARCHIVE_VARIANTS:
        states = [row["physical_artifacts"][variant] for row in rows]
        sizes = [state["bytes"] for state in states
                 if state["status"] == "VERIFIED_TECHNICAL_ZIP"]
        consumed = sum(sizes)
        total += consumed
        result[variant] = {
            "verified_archives": len(sizes),
            "verified_bytes": consumed,
            "largest_zip_bytes": max(sizes, default=0),
            "missing_or_invalid_archives": len(states) - len(sizes),
        }
    result["total_verified_zip_bytes"] = total
    result["storage_alert_bytes"] = PRODUCT_STORAGE_ALERT_BYTES
    result["capacity_anomaly"] = total > PRODUCT_STORAGE_ALERT_BYTES
    result["commercial_quality_inferred_from_size"] = False
    return result

def policy():
    if PRICE_PATH.is_symlink() or not PRICE_PATH.is_file():
        raise ValueError("PRICE_POLICY_MISSING")
    spec = importlib.util.spec_from_file_location("agri200_private_price_policy", PRICE_PATH)
    if spec is None or spec.loader is None:
        raise ValueError("PRICE_POLICY_NOT_LOADABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate(catalog: Path, factory_private: Path) -> dict[str, Any]:
    if (catalog.is_symlink() or not catalog.is_file()
            or catalog.stat().st_size > 70_000):
        raise ValueError("CATALOG_UNSAFE")
    factory_private = Path(factory_private)
    if not safe_dir(factory_private):
        raise ValueError("FACTORY_PRIVATE_ROOT_MISSING")
    area = factory_private / "production-instructions"
    if not safe_dir(area):
        raise ValueError("FACTORY_PRODUCTION_AREA_MISSING")
    index = read_json(area / "owner-agri200-p0-index.json", 100_000)
    catalog_sha = hashlib.sha256(catalog.read_bytes()).hexdigest()
    ids = index.get("order_ids_ranked")
    if (index.get("schema") != INDEX_SCHEMA
            or index.get("catalog_sha256") != catalog_sha
            or index.get("topic_count") != 200
            or index.get("edition_goal_count") != 400
            or not isinstance(ids, list) or len(ids) != 200
            or len(set(map(str, ids))) != 200
            or any(not isinstance(x, str) or not ORDER.fullmatch(x) for x in ids)):
        raise ValueError("P0_EXACT_CATALOG_LINEAGE_FAILED")
    prices = policy().build_priced_drafts(catalog)
    if prices.get("product_count") != 200 or prices.get("catalog_sha256") != catalog_sha:
        raise ValueError("PRICING_CATALOG_LINEAGE_FAILED")
    products = prices["products"]
    orders_path = area / "orders"
    if not safe_dir(orders_path):
        raise ValueError("FACTORY_ORDERS_DIRECTORY_MISSING")

    rows = []
    for rank, (entry, order_id) in enumerate(zip(products, ids), 1):
        expected_id = f"AGRI-{rank:03d}"
        if entry.get("product_id") != expected_id or entry.get("priority_rank") != rank:
            raise ValueError("CATALOG_RANK_MISMATCH")
        order = read_json(orders_path / (order_id + ".json"))
        locales = order.get("editions")
        if (order.get("id") != order_id
                or order.get("source_product_id") != expected_id
                or order.get("priority_rank") != rank
                or order.get("priority") != "P0"
                or order.get("source_sha256") != source_digest(
                    expected_id, entry["catalog_title_fa"], entry["catalog_title_en"])
                or not isinstance(locales, list) or len(locales) != 2):
            raise ValueError("ORDER_CATALOG_IDENTITY_MISMATCH:" + expected_id)
        editions = {i.get("locale"): i for i in locales if isinstance(i, dict)}
        if (set(editions) != {"en-US", "fa-IR"}
                or editions["en-US"].get("title") != entry["catalog_title_en"]
                or editions["fa-IR"].get("title") != entry["catalog_title_fa"]
                or editions["en-US"].get("site") != "mojplaywin.com"
                or editions["fa-IR"].get("site") != "zomorodmelal.ir"):
            raise ValueError("BILINGUAL_EDITION_IDENTITY_MISMATCH:" + expected_id)
        if (entry["currency"] != ("USD" if rank <= 100 else "IRR")
                or entry["locale"] != ("en-US" if rank <= 100 else "fa-IR")
                or entry["storefront"] != ("mojplaywin.com" if rank <= 100 else "zomorodmelal.ir")):
            raise ValueError("STORE_CURRENCY_LOCALE_MISMATCH")

        source = private_receipt(area, "stage-02/receipts", order_id)
        manuscript = private_receipt(area, "stage-05/completed-drafts", order_id)
        archive = private_receipt(area, "stage-05/downloadable-receipts", order_id)
        revised = private_receipt(area, "stage-05/source-grounded-v003-manifests", order_id)
        files = {
            "navigator": physical_archive(area, archive, order_id, "navigator"),
            "source_grounded_v003": physical_archive(area, revised, order_id, "source_grounded_v003"),
        }
        qc = private_receipt(area, "stage-06/strict-qc1000", order_id)
        rework = private_receipt(area, "stage-05/strict-qc-rework", order_id)
        blockers = []
        if source is None:
            blockers.append("SOURCE_RESEARCH_NOT_RECEIPTED")
        if manuscript is None:
            blockers.append("ORIGINAL_MANUSCRIPT_NOT_RECEIPTED")
        if archive is None:
            blockers.append("BUYER_ARCHIVE_NOT_RECEIPTED")
        if qc is None:
            blockers.append("STRICT_QC_NOT_RECEIPTED")
        for package in files.values():
            if package["status"] != "VERIFIED_TECHNICAL_ZIP":
                blockers.append("STORED_PRODUCT_ARCHIVE_NOT_VERIFIED")
        if rework is not None:
            blockers.append("REWORK_RETURNED_FOR_CORRECTION")
        # Internal JSON flags cannot substitute for executed, signed independent QC1000.
        blockers.extend((
            "TRUSTED_INDEPENDENT_QC1000_NOT_VERIFIED_HERE",
            "PUBLISHING_RIGHTS_NOT_VERIFIED_HERE",
            "ACTUAL_PRODUCT_VALUE_NOT_REVIEWED_HERE",
            "LIVE_SETTLED_CHECKOUT_AND_EMAIL_DELIVERY_NOT_VERIFIED_HERE",
        ))
        if entry["sales_enabled"] is not False or entry["public_listing_enabled"] is not False:
            raise ValueError("UNSAFE_PREEXISTING_COMMERCE_STATE")
        discount = entry["discount_policy"]
        if (discount["authority"] != "OWNER_ONLY"
                or type(discount["discount_percent"]) is not int
                or discount["discount_percent"] != 0
                or discount["owner_authorization_record"] is not None):
            raise ValueError("UNAUTHORIZED_DISCOUNT")
        rows.append({
            "product_id": expected_id, "source_order_id": order_id,
            "storefront": entry["storefront"], "locale": entry["locale"],
            "currency": entry["currency"], "title": entry["title"],
            "suggested_base_price": entry["suggested_base_price"]["amount"],
            "price_basis": "PROPOSAL_NOT_CONTENT_APPRAISAL",
            "physical_artifacts": files,
            "factory_signals": {
                "source_receipt_present": source is not None,
                "manuscript_receipt_present": manuscript is not None,
                "archive_receipt_present": archive is not None,
                "internal_qc_receipt_present": qc is not None,
                "rework_receipt_present": rework is not None,
            },
            "blockers": blockers, "discount_percent": 0,
            "publication_state": "PRIVATE_NOT_SALE_READY",
            "qc1000_approved": False, "sales_enabled": False,
            "public_listing_enabled": False,
        })
    counters = Counter()
    for row in rows:
        counters.update(row["blockers"])
    return {
        "schema": SCHEMA, "catalog_sha256": catalog_sha,
        "products_total": 200, "mojplaywin_usd": 100, "zomorod_irr": 100,
        "factory_work_orders_mapped": len(rows),
        "commercially_releasable": 0, "discounts_created": 0,
        "sites_changed": False, "payments_initiated": 0,
        "blockers_by_type": dict(sorted(counters.items())),
        "physical_zip_inventory": archive_totals(rows), "products": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=ROOT / "docs/agri200_p0_catalog.tsv")
    parser.add_argument("--factory-private", type=Path, required=True)
    options = parser.parse_args()
    try:
        result = evaluate(options.catalog, options.factory_private)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("AGRI200_READINESS_BLOCKED:" + type(exc).__name__ + ":" + str(exc)[:180],
              file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
