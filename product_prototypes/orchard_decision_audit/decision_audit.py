#!/usr/bin/env python3
"""Orchard Decision Audit: transparent, offline, source-led investment comparison.

Reference MVP only. Never a substitute for accountant/agronomist review.
All numbers, scenarios and source labels originate from the operator;
the software invents NO current commodity price, yield, cost or probability.
Run: python3 decision_audit.py --input example_synthetic.json --out report.json
"""
import argparse
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_EVEN
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

MONEY_FIELDS = ("revenue", "variable_cost", "fixed_cost", "capital_cost", "terminal_value")
SCALE_FIELDS = ("price_factor", "yield_factor", "variable_cost_factor")
CENT = Decimal("0.01")
MAX_MONEY = Decimal("1000000000000000")
MAX_YEARS = 30


class InputError(ValueError):
    pass


def number(value, name, *, upper=MAX_MONEY, allow_zero=True):
    """Avoid binary float precision and NaN/Infinity/overflow in money inputs."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise InputError(name + " must be a decimal string or integer")
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0 or n > upper or (not allow_zero and n == 0):
            raise InputError(name + " out of permitted range")
    except (InvalidOperation, ValueError) as exc:
        raise InputError(name + " invalid decimal") from exc
    return n


def display(value, digits=CENT):
    return str(value.quantize(digits, rounding=ROUND_HALF_EVEN))


def validate(payload):
    if not isinstance(payload, dict):
        raise InputError("input must be a JSON object")
    currency = payload.get("currency")
    if not isinstance(currency, str) or not re.fullmatch("[A-Z]{3}", currency):
        raise InputError("currency must be one ISO-like 3-letter currency code")
    unit = payload.get("unit")
    if unit not in ("per_hectare", "per_acre", "whole_farm"):
        raise InputError("unit must be per_hectare, per_acre or whole_farm")
    regime = payload.get("money_basis")
    if regime not in ("real", "nominal"):
        raise InputError("money_basis must be real or nominal")
    horizon = payload.get("horizon_years")
    if type(horizon) is not int or not 1 <= horizon <= MAX_YEARS:
        raise InputError("horizon_years must be 1..30")
    rate = number(payload.get("discount_rate_pct"), "discount_rate_pct", upper=Decimal("100")) / 100
    options = payload.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 5:
        raise InputError("require 2..5 investment options")
    parsed = []
    seen = set()
    for option in options:
        if not isinstance(option, dict):
            raise InputError("option must be an object")
        name = option.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 80 or name in seen:
            raise InputError("option names must be distinct and nonempty")
        seen.add(name)
        yearly = option.get("years")
        if not isinstance(yearly, list) or len(yearly) != horizon + 1:
            raise InputError("every option needs exactly years 0..horizon")
        entries = []
        for y, row in enumerate(yearly):
            if not isinstance(row, dict) or set(row) != set(MONEY_FIELDS) | {"year"}:
                raise InputError("yearly rows require year plus exactly the five money fields")
            if type(row["year"]) is not int or row["year"] != y:
                raise InputError("year must follow exact sequence 0..horizon")
            fields = {field: number(row[field], name + " " + field) for field in MONEY_FIELDS}
            entries.append(fields)
        parsed.append((name, entries))
    baseline = payload.get("reference_option")
    if baseline not in seen:
        raise InputError("reference_option must match a named option")
    stress = payload.get("stress_scenarios")
    if not isinstance(stress, dict) or set(stress) != {"downside", "upside"}:
        raise InputError("explicit downside and upside scenarios are mandatory")
    scenarios = {"base": {k: Decimal(1) for k in SCALE_FIELDS}}
    for name in ("downside", "upside"):
        scenario = stress[name]
        if not isinstance(scenario, dict) or set(scenario) != set(SCALE_FIELDS):
            raise InputError(name + " requires exactly three stress factors")
        scales = {k: number(scenario[k], name + " " + k, upper=Decimal(4))
                  for k in SCALE_FIELDS}
        scenarios[name] = scales
    ledger = payload.get("assumptions", [])
    if not isinstance(ledger, list) or len(ledger) > 1000:
        raise InputError("assumptions must be a bounded list")
    references = set()
    for item in ledger:
        if not isinstance(item, dict) or set(item) != {
            "option", "field", "source_reference", "evidence_status"
        }:
            raise InputError("assumption ledger must specify source and status")
        if item["option"] not in seen or item["field"] not in MONEY_FIELDS:
            raise InputError("assumption option/field unknown")
        ref = item["source_reference"]
        if not isinstance(ref, str) or not ref.strip() or len(ref) > 300:
            raise InputError("source_reference must be nonempty 1..300")
        if item["evidence_status"] not in ("operator_record", "operator_estimate"):
            raise InputError("evidence_status unrecognized")
        references.add((item["option"], item["field"]))
    return currency, unit, regime, horizon, rate, parsed, baseline, scenarios, references


def _cashflows(years, scales):
    rows, flows = [], []
    with localcontext() as ctx:
        ctx.prec = 42
        for y, v in enumerate(years):
            revenue = v["revenue"] * scales["price_factor"] * scales["yield_factor"]
            variable = v["variable_cost"] * scales["variable_cost_factor"]
            cashflow = revenue + v["terminal_value"] - variable - v["fixed_cost"] - v["capital_cost"]
            rows.append((y, cashflow, revenue, variable))
            flows.append(cashflow)
    return rows, flows


def _npv(flows, discount):
    with localcontext() as ctx:
        ctx.prec = 42
        return sum((cf / ((Decimal(1) + discount) ** y)
                    for y, cf in enumerate(flows)), Decimal(0))


def _breakeven_revenue_factor(years, discount, cost_factor):
    """Multiplier on all baseline revenue; not a price forecast or guarantee."""
    with localcontext() as ctx:
        ctx.prec = 42
        inflows = Decimal(0)
        other_net = Decimal(0)
        for y, row in enumerate(years):
            divisor = (1 + discount) ** y
            inflows += row["revenue"] / divisor
            other_net += (row["variable_cost"] * cost_factor + row["fixed_cost"]
                          + row["capital_cost"] - row["terminal_value"]) / divisor
        if not inflows:
            return None
        return max(Decimal(0), other_net / inflows)


def analyze(payload):
    currency, unit, regime, horizon, rate, options, baseline, scenarios, ledger = validate(payload)
    warnings = [
        "OPERATOR_INPUTS_NOT_INDEPENDENTLY_VERIFIED",
        "NO_TAX_DEBT_FINANCING_INFLATION_OR_FUNDING_MODEL",
        "STRESS_FACTORS_ARE_DETERMINISTIC_NOT_PROBABILITIES",
        "NPV_RANKING_IS_NOT_INVESTMENT_ADVICE",
        "THIS_MVP_HAS_NOT_PASSED_COMMERCIAL_QUALITY_REVIEW",
    ]
    for name, years in options:
        for field in MONEY_FIELDS:
            if any(row[field] > 0 for row in years) and (name, field) not in ledger:
                warnings.append("UNSOURCED_INPUT:" + name + ":" + field)
        if not years[0]["capital_cost"]:
            warnings.append("NO_YEAR_ZERO_CAPITAL_OUTLAY:" + name)
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    input_sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    summary = {}
    with localcontext() as ctx:
        ctx.prec = 42
        for label, scales in scenarios.items():
            summary[label] = []
            for name, years in options:
                lines, flows = _cashflows(years, scales)
                net_present = _npv(flows, rate)
                cumulative = Decimal(0)
                yearly = []
                for y, cf, revenues, variable in lines:
                    cumulative += cf
                    yearly.append({
                        "year": y,
                        "cashflow": display(cf),
                        "discounted_cashflow": display(cf / ((1 + rate) ** y)),
                        "cumulative_undiscounted_cashflow": display(cumulative),
                        "stressed_revenue": display(revenues),
                        "stressed_variable_cost": display(variable),
                    })
                be = _breakeven_revenue_factor(
                    years, rate, scales["variable_cost_factor"])
                summary[label].append({
                    "option": name, "npv": display(net_present),
                    "npv_unrounded": str(net_present),
                    "breakeven_total_revenue_multiplier": (
                        display(be, Decimal("0.0001")) if be is not None else None),
                    "years": yearly,
                })
        base_all_negative = all(Decimal(x["npv_unrounded"]) < 0 for x in summary["base"])
        for label, outputs in summary.items():
            outputs.sort(key=lambda x: (-Decimal(x["npv_unrounded"]), x["option"]))
            reference = next(Decimal(x["npv_unrounded"]) for x in outputs
                             if x["option"] == baseline)
            for item in outputs:
                delta = Decimal(item["npv_unrounded"]) - reference
                item["delta_npv_vs_reference"] = display(delta)
                del item["npv_unrounded"]
    base_winner = summary["base"][0]
    all_negative = base_all_negative
    return {
        "schema_version": 1,
        "tool": "orchard_decision_audit_private_reference_mvp",
        "input_sha256": input_sha256,
        "currency": currency,
        "unit": unit,
        "money_basis": regime,
        "discount_rate_pct": display(rate * 100, Decimal("0.0001")),
        "horizon_years": horizon,
        "reference_option": baseline,
        "leading_option_by_base_npv_not_advice": base_winner["option"],
        "all_base_npvs_negative": all_negative,
        "scenarios": summary,
        "warnings": sorted(set(warnings)),
        "source_ledger_entries_operator_supplied": len(payload.get("assumptions", [])),
        "sources_independently_verified": False,
        "market_demand_verified": False,
        "commercial_quality_verified": False,
        "new_public_product": False,
        "store_listing_authorized": False,
        "payments_enabled": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    raw = Path(args.input).expanduser()
    if raw.is_symlink():
        raise InputError("input symlinks forbidden")
    source = raw.resolve(strict=True)
    if not source.is_file() or source.stat().st_size > 2_000_000:
        raise InputError("missing/oversized input")
    raw_out = Path(args.out).expanduser()
    if raw_out.is_symlink():
        raise InputError("output symlinks forbidden")
    out = raw_out.resolve()
    if source == out or out.exists() or not out.parent.is_dir():
        raise InputError("output must be a new path in an existing folder")
    report = analyze(json.loads(source.read_text(encoding="utf-8")))
    fd, temp = tempfile.mkstemp(prefix=".decision-audit-", dir=str(out.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        # Atomic exclusive creation; another process cannot be clobbered.
        os.link(temp, out)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    print("ORCHARD_DECISION_AUDIT_STATUS=PRIVATE_REFERENCE_MVP")
    print("ORCHARD_DECISION_AUDIT_MARKET_VERIFIED=false")
    print("ORCHARD_DECISION_AUDIT_STORE_AUTHORIZED=false")


if __name__ == "__main__":
    main()
