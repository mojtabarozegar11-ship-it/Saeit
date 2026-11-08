#!/usr/bin/env python3
"""Private farm profitability / break-even service calculation.

No external network, database writes, email, payments, or live farm data.
Input is a private customer-authorized JSON; financial values are written to
an owner-private file only; stdout reveals no financial values. Figures are derived strictly from supplied data, not typical market values.
Not a tax/audit opinion or a substitute for full economic-cost accounting.
"""
from __future__ import annotations

import argparse
import json
import os
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from pathlib import Path

MAX_BYTES = 200_000
MAX_FINANCIAL_INPUT = Decimal("1e18")
MONEY = Decimal("0.01")
ZERO = Decimal("0")
getcontext().prec = 80
ALLOWED_CURRENCIES = {"IRR", "TOMAN", "USD", "EUR", "AED", "CAD"}


class InputError(Exception):
    pass


def amount(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise InputError(f"{name}: invalid decimal")
    if len(str(value)) > 32:
        raise InputError(f"{name}: decimal exceeds safe input bound")
    try:
        number = Decimal(str(value))
    except InvalidOperation as err:
        raise InputError(f"{name}: invalid decimal") from err
    if not number.is_finite() or number < ZERO or (positive and number <= ZERO):
        raise InputError(f"{name}: must be {'positive' if positive else 'nonnegative'}")
    if number > MAX_FINANCIAL_INPUT:
        raise InputError(f"{name}: exceeds bounded calculation range")
    return number


def costs(obj, name):
    if not isinstance(obj, dict):
        raise InputError(f"{name}: expected object")
    if len(obj) > 40:
        raise InputError(f"{name}: too many categories")
    result = {}
    for label, raw in obj.items():
        if not isinstance(label, str) or not (1 <= len(label) <= 64):
            raise InputError(f"{name}: invalid category")
        result[label] = amount(raw, f"{name}.{label}")
    return result


def rounded(value):
    return str(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def calculate(data):
    if not isinstance(data, dict):
        raise InputError("expected JSON object")
    currency = data.get("currency")
    if not isinstance(currency, str) or currency not in ALLOWED_CURRENCIES:
        raise InputError("currency not supported")
    area = amount(data.get("area_hectares"), "area_hectares", positive=True)
    harvested = amount(data.get("harvested_kg"), "harvested_kg")
    sold = amount(data.get("sold_kg"), "sold_kg", positive=True)
    if sold > harvested:
        raise InputError("sold_kg exceeds harvested_kg")
    price = amount(data.get("price_per_kg"), "price_per_kg", positive=True)
    fixed = costs(data.get("fixed_costs"), "fixed_costs")
    input_costs = costs(data.get("production_variable_costs"), "production_variable_costs")
    unit_costs = costs(data.get("per_sold_kg_costs"), "per_sold_kg_costs")
    if not fixed and not input_costs and not unit_costs:
        raise InputError("at least one cost category is required")
    full_costs = data.get("all_material_costs_documented")
    if not isinstance(full_costs, bool):
        raise InputError("all_material_costs_documented must be true or false")

    fixed_total = sum(fixed.values(), ZERO)
    production_total = sum(input_costs.values(), ZERO)
    per_sold_kg_total = sum(unit_costs.values(), ZERO)
    revenue = sold * price
    variable_cost = production_total + sold * per_sold_kg_total
    operating_contribution = revenue - fixed_total - variable_cost
    contribution_per_kg = price - per_sold_kg_total
    break_even_kg = None if contribution_per_kg <= ZERO else (
        fixed_total + production_total
    ) / contribution_per_kg
    return {
        "classification": "PRIVATE_CUSTOMER_SUPPLIED_FARM_ECONOMICS",
        "currency": currency,
        "cost_scope": "selected_documented_costs",
        "all_material_costs_documented_by_client": full_costs,
        "results_are_independent_audit": False,
        "economic_net_profit_computed": False,
        "area_hectares": rounded(area),
        "harvested_kg": rounded(harvested),
        "sold_kg": rounded(sold),
        "revenue": rounded(revenue),
        "fixed_cost_total": rounded(fixed_total),
        "production_variable_cost_total": rounded(production_total),
        "selling_variable_cost_total": rounded(sold * per_sold_kg_total),
        "selected_cost_total": rounded(fixed_total + variable_cost),
        "operating_contribution": rounded(operating_contribution),
        "contribution_per_sold_kg": rounded(contribution_per_kg),
        "break_even_sold_kg": (
            None if break_even_kg is None else rounded(break_even_kg)
        ),
        "break_even_possible_at_supplied_price": break_even_kg is not None,
        "margin_of_safety_percent": (
            None if break_even_kg is None else
            rounded((sold - break_even_kg) / sold * Decimal("100"))
        ),
        "method": (
            "break_even_kg=(fixed_costs+production_variable_costs)"
            "/(sale_price_per_kg-per_sold_kg_costs)"
        ),
        "decision_gate": (
            "CLIENT_QC_AND_PAYMENT_EVIDENCE_REQUIRED"
            if full_costs else "COST_DATA_INCOMPLETE_NO_COMMERCIAL_ACCEPTANCE"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_json", type=Path)
    args = parser.parse_args()
    path = args.private_json
    private_root = Path("/home/zomorod2/.private_zomorod_farm_reports")
    try:
        if (private_root.is_symlink() or not private_root.is_dir() or
                (hasattr(os, "geteuid") and private_root.stat().st_uid != os.geteuid())):
            raise InputError("private owner input directory unavailable")
        if (path.is_symlink() or path.parent.resolve(strict=True) != private_root.resolve(strict=True) or
                not path.is_file() or not path.name.startswith("input-") or
                not path.name.endswith(".json") or path.stat().st_size > MAX_BYTES or
                path.stat().st_mode & 0o077 or
                (hasattr(os, "geteuid") and path.stat().st_uid != os.geteuid())):
            raise InputError("customer input must be an owner-private input-*.json file")
        data = json.loads(path.read_text(encoding="utf-8"))
        result = calculate(data)
    except (InputError, OSError, UnicodeError, json.JSONDecodeError, ValueError):
        parser.exit(2, "FARM_PRIVATE_REPORT_BLOCKED: PRIVATE_INPUT_OR_DATA\n")
    # Financial values must never land in CI logs, public stdout, or an open webroot.
    try:
        private_root.mkdir(mode=0o700, exist_ok=True)
        if not private_root.is_dir() or private_root.is_symlink():
            raise InputError("private root unavailable")
        if hasattr(os, "geteuid") and private_root.stat().st_uid != os.geteuid():
            raise InputError("private root is not owned by current process")
        os.chmod(private_root, 0o700)
        dest = private_root / ("farm-" + uuid.uuid4().hex + ".json")
        fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
    except (InputError, OSError):
        parser.exit(2, "FARM_PRIVATE_REPORT_BLOCKED: PRIVATE_OUTPUT\n")
    print("FARM_PRIVATE_REPORT_SAVED=YES;OUTBOUND_EMAIL=NO;PAYMENT=NO")


if __name__ == "__main__":
    main()
