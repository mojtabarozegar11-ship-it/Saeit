#!/usr/bin/env python3
"""Research-calibrated, OWNER-DISCOUNT-ONLY base-price proposals for AGRI200.

All prices are list-price proposals for a defined complete product, not
evidence of a finished publication or a verified checkout. The seller's
owner alone may authorize promotions through a separate authenticated,
audited administrative workflow. This generator never creates discounts.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/agri200_customer_store_allocation_20261024.py"
_spec = importlib.util.spec_from_file_location("agri200_alloc", SOURCE)
assert _spec and _spec.loader
_alloc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_alloc)

SCHEMA = "saeit.agri200.owner-only-fair-base-price.v1"

# Prices based on publicly listed comparable digital guides and worksheets;
# revise after independently verifying each finished deliverable's value.
# USD is decimal dollars; IRR is integer Iranian rials (NOT tomans).
PRICE_TABLE = {
    "USD": {"starter": "4.99", "practical": "7.99", "specialist": "11.99"},
    "IRR": {"starter": "390000", "practical": "690000", "specialist": "990000"},
}

# Expert and starter classification is an editorial, revisable assessment
# of the topic's expected value, NOT a claim about content that exists today.
USD_SPECIALIST = frozenset({40, 44, 58, 61, 73, 75, 79, 86, 92, 94, 96, 100})
USD_STARTER = frozenset({
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    21, 22, 23, 24, 25, 26, 29,
    34, 35, 36, 37, 38, 39, 41, 42, 49, 50,
    59, 70, 71, 80, 83, 84, 89, 90, 95,
})
IRR_SPECIALIST = frozenset({
    102, 108, 114, 116, 123, 124, 131, 133, 134, 140, 141,
    144, 145, 148, 156, 161, 162, 163, 164, 170, 172, 173,
    174, 175, 176, 177, 180, 184, 185, 186, 197, 200,
})
IRR_STARTER = frozenset({
    103, 104, 109, 110, 120, 139, 146, 150, 152, 154, 157,
    159, 165, 169, 171, 178, 179, 183, 187, 188, 189, 190,
    191, 192, 193, 194, 195, 196, 198, 199,
})
assert not USD_SPECIALIST & USD_STARTER
assert not IRR_SPECIALIST & IRR_STARTER
assert all(1 <= n <= 100 for n in USD_SPECIALIST | USD_STARTER)
assert all(101 <= n <= 200 for n in IRR_SPECIALIST | IRR_STARTER)

VALUE_REQUIREMENTS = {
    "starter": "Original, fact-checked guidance or functional planner; real examples, local applicability, verified file.",
    "practical": "Comprehensive non-repetitive guide; worked example, sources, decision checklist, usable deliverable.",
    "specialist": "Substantial expert material with limitations, cited evidence, worked calculations or original operational tool.",
}


class OwnerDiscountRequired(PermissionError):
    """No promotion can be issued by this ChatGPT price proposal generator."""


def quote_list_price(price_amount: str, *, discount_percent: int = 0) -> str:
    """No unauthenticated discount, coupon, crossed-out price, or promotion."""
    if type(discount_percent) is not int or discount_percent != 0:
        raise OwnerDiscountRequired("ONLY_OWNER_MAY_AUTHORIZE_DISCOUNT_VIA_AUDITED_ADMIN")
    if Decimal(price_amount) <= 0:
        raise ValueError("INVALID_LIST_PRICE")
    return price_amount


def tier_for(product_id: str, currency: str) -> str:
    n = int(product_id.split("-")[1])
    if currency == "USD" and 1 <= n <= 100:
        high, low = USD_SPECIALIST, USD_STARTER
    elif currency == "IRR" and 101 <= n <= 200:
        high, low = IRR_SPECIALIST, IRR_STARTER
    else:
        raise ValueError("PRODUCT_CURRENCY_MISMATCH")
    return "specialist" if n in high else "starter" if n in low else "practical"


def build_priced_drafts(catalog_path: Path) -> dict[str, Any]:
    allocation = _alloc.build_allocation(catalog_path)
    priced = []
    for original in allocation["products"]:
        if original["public_listing_enabled"] or original["sales_enabled"] or original["qc1000_approved"]:
            raise ValueError("BASELINE_CATALOG_MUST_BE_PRIVATE_AND_UNAPPROVED")
        currency = original["currency"]
        tier = tier_for(original["product_id"], currency)
        amount = quote_list_price(PRICE_TABLE[currency][tier])
        priced.append({
            **original,
            "suggested_base_price": {
                "currency": currency,
                "amount": amount,
                "unit": "USD_DOLLARS" if currency == "USD" else "IRANIAN_RIALS",
                "tier": tier,
                "basis": "MARKET_COMPARABLES_PLUS_EXPECTED_DELIVERABLE_NOT_ACTUAL_CONTENT_APPRAISAL",
                "minimum_expected_value": VALUE_REQUIREMENTS[tier],
                "conditional_on_real_qc1000_and_checkout": True,
            },
            "discount_policy": {
                "authority": "OWNER_ONLY",
                "discount_percent": 0,
                "automatic_promotions_allowed": False,
                "auto_coupon_allowed": False,
                "owner_authorization_record": None,
                "discount_displayed": False,
            },
        })
    assert len(priced) == 200
    assert len({entry["product_id"] for entry in priced}) == 200
    assert sum(item["currency"] == "USD" for item in priced) == 100
    assert sum(item["currency"] == "IRR" for item in priced) == 100
    return {
        "schema": SCHEMA,
        "catalog_sha256": allocation["catalog_sha256"],
        "product_count": 200,
        "customer_purchasable_count": 0,
        "owner_discount_policy": "Only the authenticated owner may separately authorize and audit promotions",
        "pricing_status": "BASE_PRICE_PROPOSED_PER_TOPIC_PENDING_ACTUAL_PRODUCT_VALUE_VALIDATION",
        "sources": [
            "https://www.etsy.com/market/homesteading_printable",
            "https://www.etsy.com/market/homestead_management_planner",
            "https://zeraatyar.com/pdf/کتاب-آموزش-گلخانه-داری",
            "https://zeraatyar.com/pdf/کتاب-pdf-آموزش-کاشت-هیدروپونیک",
        ],
        "products": priced,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=ROOT / "docs/agri200_p0_catalog.tsv")
    args = parser.parse_args()
    print(json.dumps(build_priced_drafts(args.catalog), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
