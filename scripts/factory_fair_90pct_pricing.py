"""Conservative factory valuation quotes; no fabricated regular-sale price.

Reads a dated, auditable pricing decision. Does not change the website,
database, factory, order, payment, wallet, or a product's publication state.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / "pricing/factory_2026-10-14_valuation.json"
CENT=Decimal("0.01")
DISCOUNT=Decimal("0.90")


def amount(v):
    value=Decimal(str(v))
    if not value.is_finite() or value<0 or value>Decimal("10000"):
        raise ValueError("NON_FINITE_OR_UNFAIR_BASE_PRICE")
    if value != value.quantize(CENT):
        raise ValueError("PRICE_NOT_IN_CENTS")
    return value


def quote(record):
    if record.get("recipe") not in {"farm_enterprise_economics", "water_budget_economics"}:
        raise ValueError("UNKNOWN_FACTORY_PRODUCT_REQUIRES_NEW_REVIEW")
    fair=amount(record["fair_normal_price_usd"])
    sale=amount(record["introductory_price_usd"])
    if sale!=(fair*(Decimal("1")-DISCOUNT)).quantize(CENT,rounding=ROUND_HALF_UP):
        raise ValueError("PROMOTION_MATHEMATICS_INVALID")
    if record["recipe"]=="farm_enterprise_economics":
        if fair != 0 or record.get("prior_public_access")!="free_download_available":
            raise ValueError("ALREADY_FREE_PRODUCT_MUST_REMAIN_FREE")
    else:
        if fair>Decimal("19.90") or fair<Decimal("2.00") or record.get("prior_public_access")!="private_internal_qa_only":
            raise ValueError("PRIVATE_PRODUCT_PRICE_OUTSIDE_JUSTIFIED_BAND")
    if record.get("payment_gate")=="verified" and record.get("license_and_owner_verification")!="verified":
        raise ValueError("CANNOT_SELL_UNLICENSED_PRODUCT")
    return {
        "recipe":record["recipe"],
        "currency":"USD",
        "fair_value_reference":str(fair),
        "launch_quote":str(sale),
        "launch_reduction_percent":"90" if fair>0 else "not_applicable_free",
        "allow_fake_former_price_claim":False,
        "eligible_to_activate_paid_checkout":False,
        "publication_gate":record["publish_gate"],
        "paid_quote_only":fair>0,
    }


def assess(policy):
    if policy.get("schema_version") != 1 or policy.get("currency")!="USD":
        raise ValueError("UNSUPPORTED_PRICING_POLICY")
    rule=policy["pricing_rule"]
    if rule["discount_percent"]!="90.00" or rule["reference_price_display_allowed"] is not False:
        raise ValueError("DECEPTIVE_REFERENCE_PRICE_CLAIM")
    if not isinstance(policy.get("market_evidence"),list) or len(policy["market_evidence"])<2:
        raise ValueError("UNSUBSTANTIATED_FAIR_VALUE")
    rows=policy.get("assessments",[])
    ids=[p["recipe"] for p in rows]
    if len(ids)!=len(set(ids)) or set(ids)!={"farm_enterprise_economics","water_budget_economics"}:
        raise ValueError("RECIPE_INVENTORY_MISMATCH")
    return [quote(r) for r in rows]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--policy",type=Path,default=DEFAULT)
    opts=parser.parse_args()
    data=json.loads(opts.policy.read_text("utf-8"))
    print(json.dumps({"quoted_products":assess(data), "production_db_writes":False,
                       "public_promotional_badge_enabled":False},indent=2,sort_keys=True))


if __name__=="__main__":
    main()
