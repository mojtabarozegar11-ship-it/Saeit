#!/usr/bin/env python3
"""Greenhouse crop margin and break-even planner using user-supplied inputs.

This is a deterministic planning aid. It makes no market-price, yield, or
agronomic claims and uses only Python's standard library.
"""
import argparse
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
import sys


def number(value, field, *, minimum=None, maximum=None):
    if value is None or isinstance(value, bool):
        raise ValueError(field + ": a finite number is required")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(field + ": invalid number")
    if not result.is_finite():
        raise ValueError(field + ": must be finite")
    if minimum is not None and result < Decimal(str(minimum)):
        raise ValueError(field + ": below minimum")
    if maximum is not None and result > Decimal(str(maximum)):
        raise ValueError(field + ": above maximum")
    return result


def money(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate(data):
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    area = number(data.get("area_m2"), "area_m2", minimum="0.000001")
    yield_rate = number(data.get("expected_yield_kg_per_m2"),
                        "expected_yield_kg_per_m2", minimum=0)
    price = number(data.get("price_per_kg"), "price_per_kg", minimum=0)
    variable_cost_rate = number(data.get("variable_cost_per_m2"),
                                "variable_cost_per_m2", minimum=0)
    fixed_cost = number(data.get("fixed_cost_total"), "fixed_cost_total", minimum=0)
    rejection = number(data.get("rejection_rate_percent", 0),
                       "rejection_rate_percent", minimum=0, maximum=100)
    currency = str(data.get("currency") or "").strip().upper()
    if not currency or len(currency) > 12 or not currency.isascii() or not currency.replace("_", "").isalnum():
        raise ValueError("currency must be an ISO code or clearly labeled unit")

    gross_yield = area * yield_rate
    saleable_yield = gross_yield * (Decimal(1) - rejection / Decimal(100))
    revenue = saleable_yield * price
    variable_cost = area * variable_cost_rate
    total_cost = variable_cost + fixed_cost
    margin = revenue - total_cost
    break_even_price = None if saleable_yield == 0 else money(total_cost / saleable_yield)
    return {
        "version": "1.0",
        "currency": currency,
        "assumptions": [
            "Area, yield, price, cost, and rejection rate are supplied by the user.",
            "Yield and price are treated as constant across the entered growing area.",
            "Taxes, financing, depreciation, labor not included in cost inputs, and seasonality are excluded.",
            "Results are scenarios, not guaranteed production or profitability.",
        ],
        "inputs": {
            "area_m2": str(area),
            "expected_yield_kg_per_m2": str(yield_rate),
            "price_per_kg": money(price),
            "variable_cost_per_m2": money(variable_cost_rate),
            "fixed_cost_total": money(fixed_cost),
            "rejection_rate_percent": str(rejection),
        },
        "results": {
            "gross_yield_kg": str(gross_yield),
            "saleable_yield_kg": str(saleable_yield),
            "sales_revenue": money(revenue),
            "variable_cost_total": money(variable_cost),
            "total_cost": money(total_cost),
            "net_margin": money(margin),
            "net_margin_per_m2": money(margin / area),
            "break_even_price_per_kg": break_even_price,
            "break_even_reachable": saleable_yield > 0,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Greenhouse crop margin and break-even calculator")
    parser.add_argument("input_json", help="Local JSON file with user-provided assumptions")
    parser.add_argument("--json-output", help="Write results to a local JSON file")
    args = parser.parse_args(argv)
    data = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    result = calculate(data)
    body = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        Path(args.json_output).write_text(body, encoding="utf-8")
    else:
        print(body, end="")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("INPUT_ERROR: " + str(error), file=sys.stderr)
        sys.exit(2)
