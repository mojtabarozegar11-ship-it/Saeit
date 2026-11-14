#!/usr/bin/env python3
"""Produce an actual calculated FARM SAMPLE, never a fictitious customer result.

Uses the existing standard-library farm enterprise economic engine. Rejects
personal data; accepts only a clearly marked synthetic input specimen.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from product_recipes.farm_enterprise_economics.calculator import evaluate

ENTERPRISE_KEYS = frozenset({
    "name", "units_sold", "unit_price", "variable_cost_per_unit",
    "allocated_fixed_cost", "selling_fee_percent", "land_area_hectares",
    "irrigation_water_m3",
})
REQUIRED_ENTERPRISE = frozenset({
    "name", "units_sold", "unit_price", "variable_cost_per_unit",
    "allocated_fixed_cost",
})


def generate(data):
    if type(data) is not dict or set(data) != {"currency", "enterprises", "synthetic_example"}:
        raise ValueError("SYNTHETIC_FARM_SCHEMA_INVALID")
    if data["synthetic_example"] is not True:
        raise ValueError("CUSTOMER_DATA_NOT_ALLOWED_IN_PUBLIC_SAMPLE")
    enterprises = data["enterprises"]
    if type(enterprises) is not list or not (1 <= len(enterprises) <= 3):
        raise ValueError("SAMPLE_ENTERPRISE_COUNT_INVALID")
    for item in enterprises:
        if type(item) is not dict or not REQUIRED_ENTERPRISE.issubset(item):
            raise ValueError("SAMPLE_ENTERPRISE_FIELDS_MISSING")
        if set(item) - ENTERPRISE_KEYS:
            raise ValueError("PERSONAL_OR_UNKNOWN_FIELD_REJECTED")
    calculated = evaluate({"currency": data["currency"], "enterprises": enterprises})
    return {
        "schema": "mojtaba.bot.ai.synthetic-farm-deliverable.v1",
        "canonical_bot": "mojtaba.bot.ai",
        "sample_only": True,
        "customer_data_used": False,
        "market_data_independently_verified": False,
        "paid_order": False,
        "actual_revenue": None,
        "currency": calculated["currency"],
        "accounting_scope": calculated["accounting_scope"],
        "portfolio": calculated["portfolio"],
        "enterprise_results": [
            {key: row[key] for key in (
                "name", "units_sold", "sales_revenue", "total_cost",
                "operating_profit", "break_even_units",
                "break_even_unit_price_at_planned_volume", "margin_of_safety_percent",
            )}
            for row in calculated["results"]
        ],
        "scenario_results": calculated["scenario_results"],
        "limitations": [
            "All figures are synthetic assumptions, not market or customer facts.",
            "Profit excludes tax, finance, depreciation and capital expenditure.",
            "Scenario outcomes are calculations, not predictions or guarantees.",
        ],
        "delivery_status": "sample_not_delivered_to_customer",
    }


def main(argv=None):
    from mojtaba_revenue_safeio import read_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample_json", type=Path)
    args = parser.parse_args(argv)
    try:
        result = generate(read_json(args.sample_json, limit=16384))
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
        print("FARM_SAMPLE=BLOCKED", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
