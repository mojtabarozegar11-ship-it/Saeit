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
import html
import json
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
    break_even_unit_price_unrounded = None
    if quantity > 0 and price_denominator > 0:
        required = (variable + fixed / quantity) / price_denominator
        break_even_unit_price = str(required.quantize(Decimal("0.01"), rounding=ROUND_CEILING))
        break_even_unit_price_unrounded = format(required, "f")
    safety_units = quantity - Decimal(break_even) if break_even is not None else None
    safety_percent = (
        (safety_units * 100 / quantity).quantize(Decimal("0.01"))
        if safety_units is not None and quantity > 0 else None
    )
    return {
        "name": name,
        "units_sold": str(quantity),
        "unit_price": money(unit_price),
        "unit_price_exact": format(unit_price, "f"),
        "variable_cost_per_unit": money(variable),
        "variable_cost_per_unit_exact": format(variable, "f"),
        "allocated_fixed_cost": money(fixed),
        "selling_fee_percent": str(fee_pct),
        "sales_revenue": money(revenue),
        "selling_fees": money(fees),
        "variable_cost_total": money(total_variable),
        "total_cost": money(total_cost),
        "contribution_margin_total": money(contribution),
        "contribution_per_unit": money(contribution_unit),
        "contribution_per_unit_exact": format(contribution_unit, "f"),
        "operating_profit": money(operating_profit),
        "break_even_units": break_even,
        "break_even_reachable": contribution_unit > 0,
        "break_even_unit_price_at_planned_volume": break_even_unit_price,
        "break_even_unit_price_unrounded": break_even_unit_price_unrounded,
        "margin_of_safety_units": str(safety_units) if safety_units is not None else None,
        "margin_of_safety_percent": str(safety_percent) if safety_percent is not None else None,
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
    # Aggregate the raw Decimal metrics and round once for each portfolio KPI.
    # Adding the already-rounded per-enterprise display fields can lose
    # significant money when many commodity transactions are sub-cent.
    raw_totals = {
        "sales_revenue": Decimal(0),
        "total_cost": Decimal(0),
        "operating_profit": Decimal(0),
        "contribution_margin_total": Decimal(0),
    }
    for obj in rows:
        item = enterprise(obj)
        if item["name"].casefold() in names:
            raise ValueError("enterprise names must be unique")
        names.add(item["name"].casefold())
        results.append(item)
        quantity = Decimal(item["units_sold"])
        unit_price = Decimal(item["unit_price_exact"])
        variable_unit = Decimal(item["variable_cost_per_unit_exact"])
        fixed = decimal_number(obj["allocated_fixed_cost"],
                               item["name"] + ".allocated_fixed_cost", min_value=0)
        fee_rate = Decimal(item["selling_fee_percent"]) / Decimal(100)
        revenue = quantity * unit_price
        selling_fees = revenue * fee_rate
        variable_total = quantity * variable_unit
        contribution = revenue - selling_fees - variable_total
        raw_totals["sales_revenue"] += revenue
        raw_totals["total_cost"] += selling_fees + variable_total + fixed
        raw_totals["contribution_margin_total"] += contribution
        raw_totals["operating_profit"] += contribution - fixed
    def total(key):
        return money(raw_totals[key])
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
    # Apply each correlated shock to the entire farm portfolio, rather than
    # evaluating enterprises in isolation and double counting their fixed costs.
    portfolio_scenarios = []
    for quantity_factor in (Decimal("0.80"), Decimal("1.00"), Decimal("1.20")):
        for price_factor in (Decimal("0.90"), Decimal("1.00"), Decimal("1.10")):
            total_profit = Decimal(0)
            for row in rows:
                units = decimal_number(row["units_sold"], "units_sold", min_value=0)
                unit_price = decimal_number(row["unit_price"], "unit_price", min_value=0)
                unit_cost = decimal_number(row["variable_cost_per_unit"], "variable_cost_per_unit", min_value=0)
                fixed_cost = decimal_number(row["allocated_fixed_cost"], "allocated_fixed_cost", min_value=0)
                fee_rate = decimal_number(row.get("selling_fee_percent", 0),
                                          "selling_fee_percent", min_value=0, max_value=100) / 100
                total_profit += (units * quantity_factor *
                                 (unit_price * price_factor * (1 - fee_rate) - unit_cost)
                                 - fixed_cost)
            portfolio_scenarios.append({
                "volume_multiplier": str(quantity_factor),
                "price_multiplier": str(price_factor),
                "modeled_operating_profit": money(total_profit),
            })
    return {
        "version": "1.3",
        "currency": currency,
        "accounting_scope": "contribution_profit_before_depreciation_financing_tax",
        "input_values_independently_validated": False,
        "assumptions": [
            "All prices, quantities and costs must be entered by the user.",
            "Fixed costs are allocated per enterprise, not counted again in totals.",
            "This is a deterministic planning model, not a prediction of actual sales.",
            "Scenario changes affect only sold quantity and unit selling price.",
            "Tax, financing, capital expenditure, depreciation, working capital, and seasonality are excluded.",
        ],
        "results": results,
        "portfolio": {
            "sales_revenue": total("sales_revenue"),
            "total_cost": total("total_cost"),
            "operating_profit": total("operating_profit"),
            "contribution_margin_total": total("contribution_margin_total"),
        },
        "scenario_results": scenarios,
        "portfolio_scenario_results": portfolio_scenarios,
    }


def render_html_report(report):
    """Self-contained, accessible offline management report with escaped labels."""
    e = lambda value: html.escape(str(value), quote=True)
    def table(columns, data, keys):
        header = "".join("<th scope=\"col\">" + e(label) + "</th>" for label in columns)
        body = "".join(
            "<tr>" + "".join("<td>" + e("N/A" if row[key] is None else row[key]) + "</td>" for key in keys) + "</tr>"
            for row in data
        )
        return "<div class=\"scroll\"><table><thead><tr>" + header + (
            "</tr></thead><tbody>" + body + "</tbody></table></div>"
        )
    rows = report["results"]
    portfolio = report["portfolio"]
    summary = "".join(
        "<div class=\"kpi\"><span>" + e(label) + "</span><strong>" + e(portfolio[key])
        + "</strong></div>"
        for label, key in (
            ("Revenue", "sales_revenue"),
            ("Total operating costs", "total_cost"),
            ("Operating profit", "operating_profit"),
            ("Total contribution margin", "contribution_margin_total"),
        )
    )
    enterprise_table = table(
        ("Enterprise", "Sold units", "Unit price (input precision)", "Variable cost/unit (input precision)",
         "Contribution/unit (model precision)", "Operating profit", "Break-even units",
         "Margin of safety (%)"),
        rows,
        ("name", "units_sold", "unit_price_exact", "variable_cost_per_unit_exact",
         "contribution_per_unit_exact", "operating_profit",
         "break_even_units", "margin_of_safety_percent"),
    )
    stress_table = table(
        ("Volume factor", "Selling-price factor", "Portfolio operating profit"),
        report["portfolio_scenario_results"],
        ("volume_multiplier", "price_multiplier", "modeled_operating_profit"),
    )
    assumptions = "".join("<li>" + e(s) + "</li>" for s in report["assumptions"])
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Farm Enterprise Economics — Offline Report</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,sans-serif;color:#14352e;background:#f5f8f5}
body{margin:0 auto;max-width:1100px;padding:2rem 1rem;line-height:1.55}
header{padding:1.6rem;border-radius:1rem;background:#124537;color:white}
header p{margin-bottom:0}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:.8rem;margin:1rem 0}
.kpi{background:white;padding:1.2rem;border:1px solid #d3ded9;border-radius:.7rem;display:grid;gap:.5rem}
.kpi span{font-size:.9rem;color:#3c5b51}.kpi strong{font-size:1.5rem;overflow-wrap:anywhere}
section{background:white;padding:1.2rem;border-radius:.7rem;margin:1rem 0;border:1px solid #d3ded9}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:620px}
th,td{text-align:left;padding:.7rem;border-bottom:1px solid #d3ded9}th{background:#e7f0eb}
aside{border-left:4px solid #a05b22;padding:1rem;background:#fff7e9}
@media print{body{max-width:none;padding:0}header{print-color-adjust:exact}section{break-inside:avoid}}
</style></head><body>
<header><h1>Farm Enterprise Economics</h1><p>Private offline management report · Currency: """ + e(report["currency"]) + """</p></header>
<main><div class="kpis">""" + summary + """</div>
<section><h2>Enterprise operating results</h2>""" + enterprise_table + """</section>
<section><h2>Whole-portfolio sensitivity</h2><p>Correlated volume and selling-price changes are applied to all enterprises at once. These are scenarios, not probabilities or forecasts.</p>""" + stress_table + """</section>
<section><h2>Model boundaries</h2><ul>""" + assumptions + """</ul>
<aside>Pre-tax, pre-financing contribution model. Per-unit figures retain input/model decimal precision; displayed money totals are rounded to 0.01 currency units. Results are not forecasts or investment recommendations. Verify all entered quantities, costs, allocations and market assumptions.</aside></section>
</main><footer><small>Generated locally. No accounts, telemetry or network connection.</small></footer></body></html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description="Farm enterprise economics and sensitivity analysis")
    ap.add_argument("input_json", help="Local input JSON with user-supplied assumptions")
    ap.add_argument("--json-output", help="Write results to a local JSON file")
    ap.add_argument("--csv-output", help="Write all scenario results to local CSV file")
    ap.add_argument("--html-output", help="Write a self-contained offline management report")
    args = ap.parse_args(argv)
    source = Path(args.input_json)
    # Protect the customer's source data and prevent multiple formats from
    # silently replacing one another when a CLI argument repeats a path.
    output_paths = [Path(path) for path in (args.json_output, args.csv_output, args.html_output) if path]
    canonical_paths = [source.resolve()] + [path.resolve() for path in output_paths]
    if len(canonical_paths) != len(set(canonical_paths)):
        raise ValueError("input and output file paths must be distinct")
    data = json.loads(source.read_text(encoding="utf-8"))
    output = evaluate(data)
    body = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        Path(args.json_output).write_text(body, encoding="utf-8")
    else:
        print(body, end="")
    if args.html_output:
        Path(args.html_output).write_text(render_html_report(output), encoding="utf-8")
    if args.csv_output:
        with Path(args.csv_output).open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=[
                "enterprise", "volume_multiplier", "price_multiplier", "modeled_operating_profit"
            ], quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(output["scenario_results"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("INPUT_ERROR: " + str(error), file=sys.stderr)
        sys.exit(2)
