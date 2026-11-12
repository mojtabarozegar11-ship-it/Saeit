#!/usr/bin/env python3
"""Farm Enterprise Economics Toolkit: reproducible scenario and break-even calculations.

Uses only Python standard library and user-provided inputs. No market prices,
third-party sources, financial advice, network traffic, or subscription required.
Compatible with Python 3.8+.
"""
import argparse
import csv
from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
from functools import wraps
import json
import math
from pathlib import Path
import sys


def bounded_model_precision(function):
    """Keep portfolio and sensitivity arithmetic exact for large local currencies."""
    @wraps(function)
    def run(*args, **kwargs):
        with localcontext() as context:
            context.prec = 80
            return function(*args, **kwargs)
    return run


def decimal_number(value, field, *, min_value=None, max_value=None):
    if isinstance(value, bool) or value is None:
        raise ValueError(field + ": a finite number is required")
    raw = str(value)
    if len(raw) > 64:
        raise ValueError(field + ": numeric input too long")
    try:
        x = Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(field + ": invalid number")
    if not x.is_finite():
        raise ValueError(field + ": must be finite")
    if abs(x) > Decimal("1e20"):
        raise ValueError(field + ": above supported magnitude (1e20)")
    if min_value is not None and x < Decimal(str(min_value)):
        raise ValueError(field + ": below minimum")
    if max_value is not None and x > Decimal(str(max_value)):
        raise ValueError(field + ": above maximum")
    return x


def money(value):
    return str(value.quantize(Decimal("0.01")))


def optional_resource(entry, field, *, positive=False):
    """Keep absent resource observations distinct from measured zero usage."""
    if field not in entry:
        return None
    amount = decimal_number(entry[field], field, min_value=0)
    if positive and amount == 0:
        raise ValueError(field + ": must be positive when supplied")
    return amount


CASH_FIELDS = (
    "cash_receipts", "operating_payments", "asset_purchases",
    "loan_receipts", "loan_repayments", "other_payments",
)


@bounded_model_precision
def cashflow_plan(plan):
    """Twelve independent monthly liquidity periods; never infer cash from profit.

    Values are monetary cash movements supplied by the user, restricted to
    exact hundredths so every displayed balance reconciles with shown rows.
    This does not project profitability, taxation, debt balances or financing.
    """
    if not isinstance(plan, dict):
        raise ValueError("cashflow_plan must be an object")
    opening = decimal_number(plan.get("opening_cash"), "cashflow.opening_cash", min_value=0)
    if opening != opening.quantize(Decimal("0.01")):
        raise ValueError("cashflow.opening_cash: at most two monetary decimal places")
    periods = plan.get("months")
    if not isinstance(periods, list) or len(periods) != 12:
        raise ValueError("cashflow.months must contain exactly twelve months")
    balance = opening
    minimum_balance = None
    first_negative = None
    output = []
    operating_total = Decimal(0)
    for index, raw in enumerate(periods, 1):
        if not isinstance(raw, dict):
            raise ValueError("cashflow month must be an object")
        amounts = {}
        for field in CASH_FIELDS:
            value = decimal_number(raw.get(field), "cashflow.month_%s.%s" % (index, field), min_value=0)
            if value != value.quantize(Decimal("0.01")):
                raise ValueError("cashflow.month_%s.%s: at most two monetary decimal places" % (index, field))
            amounts[field] = value
        operating_total += amounts["cash_receipts"] - amounts["operating_payments"]
        change = (amounts["cash_receipts"] + amounts["loan_receipts"]
                  - amounts["operating_payments"] - amounts["asset_purchases"]
                  - amounts["loan_repayments"] - amounts["other_payments"])
        balance += change
        minimum_balance = balance if minimum_balance is None else min(minimum_balance, balance)
        if first_negative is None and balance < 0:
            first_negative = index
        output.append(dict(month=index, **{key: money(value) for key, value in amounts.items()},
                           net_cash_change=money(change), closing_cash_balance=money(balance)))
    return {
        "opening_cash": money(opening), "ending_cash": money(balance),
        "minimum_month_end_cash": money(minimum_balance),
        "additional_cash_needed_at_month_ends": money(max(Decimal(0), -minimum_balance)),
        "first_negative_month": first_negative,
        "net_operating_cashflow_before_other_uses": money(operating_total),
        "months": output,
    }


@bounded_model_precision
def enterprise(entry):
    if not isinstance(entry, dict):
        raise ValueError("enterprise must be an object")
    name = str(entry.get("name") or "").strip()
    if not name or len(name) > 120:
        raise ValueError("enterprise name must contain 1 to 120 characters")
    # Defense in depth for CSV users. Spreadsheet applications can interpret
    # user-supplied labels beginning with =, +, -, @ or Unicode variants as
    # formulas; nested line controls can also conceal a new spreadsheet row.
    # Require a Unicode letter/digit at the beginning and no C0 control codes.
    if not name[0].isalnum() or any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise ValueError("enterprise name must start with a letter or digit and contain no control characters")
    quantity = decimal_number(entry.get("units_sold"), name + ".units_sold", min_value=0)
    unit_price = decimal_number(entry.get("unit_price"), name + ".unit_price", min_value=0)
    variable = decimal_number(entry.get("variable_cost_per_unit"), name + ".variable_cost_per_unit", min_value=0)
    fixed = decimal_number(entry.get("allocated_fixed_cost"), name + ".allocated_fixed_cost", min_value=0)
    fee_pct = decimal_number(entry.get("selling_fee_percent", 0), name + ".selling_fee_percent", min_value=0, max_value=100)
    fee_rate = fee_pct / Decimal(100)
    contribution_unit = unit_price * (Decimal(1) - fee_rate) - variable
    revenue = quantity * unit_price
    fees = revenue * fee_rate
    total_variable = variable * quantity
    contribution = revenue - fees - total_variable
    operating_profit = contribution - fixed
    total_cost = fees + total_variable + fixed
    break_even = None
    if contribution_unit > 0:
        break_even = int((fixed / contribution_unit).to_integral_value(rounding=ROUND_CEILING))
    # These are planning thresholds, not predictions. A fee of 100% makes a
    # positive break-even unit price impossible at the selected sales volume.
    price_denominator = Decimal(1) - fee_rate
    break_even_unit_price = None
    if quantity > 0 and price_denominator > 0:
        required = (variable + fixed / quantity) / price_denominator
        break_even_unit_price = str(required.quantize(Decimal("0.01"), rounding=ROUND_CEILING))
    safety_units = quantity - Decimal(break_even) if break_even is not None else None
    safety_percent = (
        (safety_units * 100 / quantity).quantize(Decimal("0.01"))
        if safety_units is not None and quantity > 0 else None
    )
    hectares = optional_resource(entry, "land_area_hectares", positive=True)
    water = optional_resource(entry, "irrigation_water_m3")
    return {
        "name": name,
        "units_sold": str(quantity),
        "unit_price": money(unit_price),
        "variable_cost_per_unit": money(variable),
        "allocated_fixed_cost": money(fixed),
        "selling_fee_percent": str(fee_pct),
        "sales_revenue": money(revenue),
        "selling_fees": money(fees),
        "variable_cost_total": money(total_variable),
        "total_cost": money(total_cost),
        "contribution_margin_total": money(contribution),
        "contribution_per_unit": money(contribution_unit),
        "operating_profit": money(operating_profit),
        # Distinguish operating margin from contribution: fixed costs affect
        # profitability but not contribution, and zero-revenue scenarios have
        # no meaningful percentage denominator.
        "contribution_margin_percent": (
            str((contribution / revenue * 100).quantize(Decimal("0.01")))
            if revenue > 0 else None
        ),
        "operating_profit_margin_percent": (
            str((operating_profit / revenue * 100).quantize(Decimal("0.01")))
            if revenue > 0 else None
        ),
        "break_even_units": break_even,
        "break_even_reachable": contribution_unit > 0,
        "break_even_unit_price_at_planned_volume": break_even_unit_price,
        "margin_of_safety_units": str(safety_units) if safety_units is not None else None,
        "margin_of_safety_percent": str(safety_percent) if safety_percent is not None else None,
        "land_area_hectares": str(hectares) if hectares is not None else None,
        "irrigation_water_m3": str(water) if water is not None else None,
        "units_sold_per_hectare": (
            str((quantity / hectares).quantize(Decimal("0.0001")))
            if hectares is not None else None
        ),
        "operating_profit_per_hectare": (
            money(operating_profit / hectares) if hectares is not None else None
        ),
        "units_sold_per_irrigation_m3": (
            str((quantity / water).quantize(Decimal("0.0001")))
            if water is not None and water > 0 else None
        ),
        "operating_profit_per_irrigation_m3": (
            money(operating_profit / water)
            if water is not None and water > 0 else None
        ),
    }


@bounded_model_precision
def evaluate(data):
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    currency = str(data.get("currency") or "").strip().upper()
    if not currency or len(currency) > 12 or not currency.isascii() or not currency.replace("_", "").isalnum():
        raise ValueError("currency must be an ISO code or clearly labeled unit")
    rows = data.get("enterprises")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError("enterprises must be a list of 1 to 100 items")
    names = set()
    results = []
    for obj in rows:
        item = enterprise(obj)
        if item["name"].casefold() in names:
            raise ValueError("enterprise names must be unique")
        names.add(item["name"].casefold())
        results.append(item)
    def total(key):
        return money(sum((Decimal(r[key]) for r in results), Decimal(0)))
    resource_coverage = {}
    for field in ("land_area_hectares", "irrigation_water_m3"):
        recorded = [Decimal(r[field]) for r in results if r[field] is not None]
        resource_coverage[field] = {
            "provided_enterprises": len(recorded),
            "complete_for_portfolio": len(recorded) == len(results),
            # Never present partial observations as the whole portfolio's usage.
            "portfolio_total": (format(sum(recorded, Decimal(0)).normalize(), "f")
                                if len(recorded) == len(results) else None),
        }
    scenarios = []
    for r in rows:
        name = str(r["name"]).strip()
        base = decimal_number(r["units_sold"], name + ".units_sold", min_value=0)
        price = decimal_number(r["unit_price"], name + ".unit_price", min_value=0)
        cost = decimal_number(r["variable_cost_per_unit"], name + ".variable_cost_per_unit", min_value=0)
        fixed = decimal_number(r["allocated_fixed_cost"], name + ".allocated_fixed_cost", min_value=0)
        fee = decimal_number(r.get("selling_fee_percent", 0), name + ".selling_fee_percent", min_value=0, max_value=100) / 100
        for quantity_factor in (Decimal("0.80"), Decimal("1.00"), Decimal("1.20")):
            for price_factor in (Decimal("0.90"), Decimal("1.00"), Decimal("1.10")):
                volume = base * quantity_factor
                selling_price = price * price_factor
                profit = volume * (selling_price * (1 - fee) - cost) - fixed
                scenarios.append({
                    "enterprise": name,
                    "volume_multiplier": str(quantity_factor),
                    "price_multiplier": str(price_factor),
                    "modeled_operating_profit": money(profit),
                })
    result = {
        "version": "2.0",
        "currency": currency,
        "accounting_scope": "contribution_profit_before_depreciation_financing_tax",
        "input_values_independently_validated": False,
        "assumptions": [
            "All prices, quantities and costs must be entered by the user.",
            "Fixed costs are allocated per enterprise, not counted again in totals.",
            "This is a deterministic planning model, not a prediction of actual sales.",
            "Scenario changes affect only sold quantity and unit selling price.",
            "Enterprise profit excludes tax, financing, capital expenditure, depreciation and working capital.",
            "Optional monthly cash flow is separate from enterprise profit and uses only the user's cash timing inputs.",
            "Resource intensity uses only user-provided land and irrigation amounts for the same accounting period.",
            "A negative profit per unit of land or water is a loss rate, not a marginal productivity estimate.",
        ],
        "results": results,
        "portfolio": {
            "sales_revenue": total("sales_revenue"),
            "total_cost": total("total_cost"),
            "operating_profit": total("operating_profit"),
            "contribution_margin_total": total("contribution_margin_total"),
        },
        "resource_coverage": resource_coverage,
        "scenario_results": scenarios,
    }
    if "cashflow_plan" in data:
        result["cashflow"] = cashflow_plan(data["cashflow_plan"])
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Farm enterprise economics and sensitivity analysis")
    ap.add_argument("input_json", help="Local input JSON with user-supplied assumptions")
    ap.add_argument("--json-output", help="Write results to a local JSON file")
    ap.add_argument("--csv-output", help="Write all scenario results to local CSV file")
    ap.add_argument("--cashflow-csv-output", help="Write the twelve monthly cash balances to local CSV file")
    args = ap.parse_args(argv)
    source = Path(args.input_json)
    data = json.loads(source.read_text(encoding="utf-8"))
    output = evaluate(data)
    body = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        Path(args.json_output).write_text(body, encoding="utf-8")
    else:
        print(body, end="")
    if args.csv_output:
        with Path(args.csv_output).open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=[
                "enterprise", "volume_multiplier", "price_multiplier", "modeled_operating_profit"
            ], quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(output["scenario_results"])
    if args.cashflow_csv_output:
        if "cashflow" not in output:
            raise ValueError("--cashflow-csv-output requires a cashflow_plan with twelve months")
        columns = ["month", *CASH_FIELDS, "net_cash_change", "closing_cash_balance"]
        with Path(args.cashflow_csv_output).open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=columns, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(output["cashflow"]["months"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("INPUT_ERROR: " + str(error), file=sys.stderr)
        sys.exit(2)
