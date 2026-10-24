#!/usr/bin/env python3
"""Allocate the existing 200 unique agriculture topics to the two paid storefronts.

This generates PRIVATE commercial drafts, NOT products for sale. No product
may be activated from a title alone or a mechanically passing QC receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ID_PATTERN = re.compile(r"AGRI-(\d{3})\Z")
EXPECTED_COUNT = 200
SPLIT = 100
SCHEMA = "saeit.agri200.customer-store-allocation.v1"


def load_catalog(path: Path) -> list[tuple[str, str, str]]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 70_000:
        raise ValueError("CATALOG_UNSAFE")
    records = []
    for text in path.read_text(encoding="utf-8").splitlines():
        if not text.strip() or text.lstrip().startswith("#"):
            continue
        parts = [part.strip() for part in text.split("|")]
        if len(parts) != 3:
            raise ValueError("CATALOG_COLUMNS")
        product_id, title_fa, title_en = parts
        match = ID_PATTERN.fullmatch(product_id)
        if not match or not (7 <= len(title_fa) <= 160 and 7 <= len(title_en) <= 160):
            raise ValueError("CATALOG_INVALID_PRODUCT")
        records.append((product_id, title_fa, title_en))
    expected = [f"AGRI-{number:03d}" for number in range(1, EXPECTED_COUNT + 1)]
    if [record[0] for record in records] != expected:
        raise ValueError("CATALOG_NOT_EXACTLY_200_SEQUENTIAL_PRODUCTS")
    if len({record[1] for record in records}) != EXPECTED_COUNT:
        raise ValueError("CATALOG_REPEATED_PERSIAN_TITLES")
    if len({record[2].casefold() for record in records}) != EXPECTED_COUNT:
        raise ValueError("CATALOG_REPEATED_ENGLISH_TITLES")
    return records


def build_allocation(catalog_path: Path) -> dict:
    records = load_catalog(catalog_path)
    digest = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    entries = []
    for rank, (product_id, fa, en) in enumerate(records, 1):
        english = rank <= SPLIT
        entries.append({
            "product_id": product_id,
            "priority_rank": rank,
            "storefront": "mojplaywin.com" if english else "zomorodmelal.ir",
            "locale": "en-US" if english else "fa-IR",
            "currency": "USD" if english else "IRR",
            "title": en if english else fa,
            "catalog_title_fa": fa,
            "catalog_title_en": en,
            "price_minor_units": None,
            "publication_state": "PRIVATE_AWAITING_REAL_QC_PRICE_AND_CHECKOUT",
            "qc1000_approved": False,
            "owner_rework_cleared": False,
            "rights_verified": False,
            "download_after_payment_verified": False,
            "sales_enabled": False,
            "public_listing_enabled": False,
        })
    assert len(entries) == EXPECTED_COUNT
    assert sum(x["currency"] == "USD" for x in entries) == 100
    assert sum(x["currency"] == "IRR" for x in entries) == 100
    return {
        "schema": SCHEMA,
        "catalog_sha256": digest,
        "policy": "100 distinct English USD paid drafts for MojPlayWin, 100 distinct Persian IRR paid drafts for Zomorod Melal",
        "product_count": EXPECTED_COUNT,
        "customer_purchasable_count": 0,
        "pricing_required": True,
        "products": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("docs/agri200_p0_catalog.tsv"))
    args = parser.parse_args()
    print(json.dumps(build_allocation(args.catalog), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
