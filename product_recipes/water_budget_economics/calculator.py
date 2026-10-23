#!/usr/bin/env python3
"""Offline irrigation-water budget and gross-margin allocation for farm enterprises.

Continuous hectares are allocated in descending gross margin per cubic metre,
subject to each crop's maximum area and a total water budget. This is a
transparent linear planning *scenario*, not an agronomic prescription.
Python 3.8+ standard library only. No network or market-data claims.
"""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sys


ZERO = Decimal(0)


def number(value, field, *, strictly_positive=False):
    if isinstance(value, bool) or value is None:
        raise ValueError(field + ": number required")
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(field + ": invalid number")
    if not n.is_finite() or n < ZERO or (strictly_positive and n == ZERO):
        raise ValueError(field + ": must be finite and " + ("positive" if strictly_positive else "nonnegative"))
    return n


def string(value):
    return format(value.quantize(Decimal("0.000001")), "f")


def evaluate(data):
    if not isinstance(data, dict):
        raise ValueError("root object required")
    currency = data.get("currency")
    if not isinstance(currency, str) or not 1 <= len(currency) <= 12 or not currency.replace("_", "").isalnum() or not currency.isascii():
        raise ValueError("currency must be a short code")
    budget = number(data.get("water_available_m3"), "water_available_m3")
    crops = data.get("crops")
    if not isinstance(crops, list) or not 1 <= len(crops) <= 100:
        raise ValueError("provide 1 to 100 crops")
    checked, names = [], set()
    for c in crops:
        if not isinstance(c, dict):
            raise ValueError("each crop must be an object")
        name = c.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise ValueError("crop name required")
        name = name.strip()
        if name.casefold() in names:
            raise ValueError("duplicate crop name")
        names.add(name.casefold())
        area = number(c.get("max_area_ha"), name + ".max_area_ha")
        water = number(c.get("water_m3_per_ha"), name + ".water_m3_per_ha", strictly_positive=True)
        margin = number(c.get("gross_margin_per_ha"), name + ".gross_margin_per_ha")
        checked.append({"name": name, "max_area": area, "water": water,
                        "margin": margin, "rank": margin / water})
    ordered = sorted(checked, key=lambda c: (-c["rank"], c["name"]))
    remaining = budget
    rows = []
    unfilled_profitable = []
    for c in ordered:
        feasible = min(c["max_area"], remaining / c["water"])
        # Do not allocate scarce water to zero-margin crops.
        allocated = feasible if c["margin"] > 0 else ZERO
        consumed = allocated * c["water"]
        remaining -= consumed
        if c["margin"] > 0 and allocated < c["max_area"]:
            unfilled_profitable.append(c)
        rows.append({
            "crop": c["name"],
            "area_allocated_ha": string(allocated),
            "max_area_ha": string(c["max_area"]),
            "water_used_m3": string(consumed),
            "water_m3_per_ha": string(c["water"]),
            "gross_margin_per_ha": string(c["margin"]),
            "margin_per_water_m3": string(c["rank"]),
            "estimated_gross_margin": string(allocated * c["margin"]),
        })
    # Local shadow value of one additional m3 *only* for this fractional
    # linear scenario; no real water-access or land-use entitlement is implied.
    next_crop = unfilled_profitable[0] if unfilled_profitable else None
    water_used = budget - remaining
    total_margin = sum((Decimal(row["estimated_gross_margin"]) for row in rows), ZERO)
    return {
        "method": "fractional_greedy_gross_margin_per_water",
        "currency": currency,
        "water_budget_m3": string(budget),
        "water_used_m3": string(budget - remaining),
        "unused_water_m3": string(remaining),
        "estimated_total_gross_margin": string(total_margin),
        "estimated_margin_per_used_m3": string(total_margin / water_used) if water_used else None,
        "next_unfilled_profitable_crop": next_crop["name"] if next_crop else None,
        "marginal_gross_margin_per_additional_m3": string(next_crop["rank"] if next_crop else ZERO),
        "water_budget_binding": bool(next_crop is not None and remaining == 0),
        "allocations": rows,
        "limitations": [
            "Continuous area allocation assumes crops can be planted in fractions of a hectare.",
            "All per-hectare requirements and margins are user-supplied scenarios.",
            "Crop rotations, soil, seasonality, irrigation efficiency, quality, legal water rights, labor, capital and land adjacency are not modeled.",
            "Gross margin is not net profit; this model is not an agronomic or investment recommendation.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Water budget and farm gross-margin scenario")
    p.add_argument("input_json")
    p.add_argument("--json-output")
    p.add_argument("--csv-output")
    a = p.parse_args(argv)
    output = evaluate(json.loads(Path(a.input_json).read_text(encoding="utf-8")))
    if a.json_output:
        Path(a.json_output).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(output, indent=2, sort_keys=True))
    if a.csv_output:
        with Path(a.csv_output).open("w", encoding="utf-8", newline="") as fp:
            w = csv.DictWriter(fp, fieldnames=list(output["allocations"][0]))
            w.writeheader()
            w.writerows(output["allocations"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("INPUT_ERROR: " + str(exc), file=sys.stderr)
        sys.exit(2)
