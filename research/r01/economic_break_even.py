#!/usr/bin/env python3
"""R01 economic break-even sensitivity, not a field-effect or profit estimator.

Reads an author-supplied JSON parameter file, never uses fabricated defaults.
Outputs a deterministic scenario table. All quantities must be independently
sourced before any publication or commercial claim. Standard library only.

Example input schema (illustrative names; NO assumed values):
{"delta_water_m3": 0, "delta_events": 0, "delta_drainage_mm": 0,
 "water_tariff_per_m3": 0, "event_labor_cost": 0,
 "drainage_cost_per_mm": 0, "annualized_capital_delta": 0,
 "energy_cost_delta": 0, "crop_price_per_kg": 0}
The zeros above illustrate schema, NOT measured or plausible inputs.
"""
import argparse
import json
import math
from pathlib import Path

FIELDS = (
    "delta_water_m3", "delta_events", "delta_drainage_mm",
    "water_tariff_per_m3", "event_labor_cost", "drainage_cost_per_mm",
    "annualized_capital_delta", "energy_cost_delta", "crop_price_per_kg",
)
NONNEGATIVE = {
    "water_tariff_per_m3", "event_labor_cost", "drainage_cost_per_mm",
    "crop_price_per_kg",
}

def calculate(record):
    if not isinstance(record, dict):
        raise ValueError("input must be a JSON object")
    missing = sorted(set(FIELDS) - set(record))
    extra = sorted(set(record) - set(FIELDS))
    if missing or extra:
        raise ValueError(f"missing={missing}; unknown={extra}")
    values = {}
    for field in FIELDS:
        value = record[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field}: numeric value required")
        if not math.isfinite(value):
            raise ValueError(f"{field}: nonfinite value")
        if field in NONNEGATIVE and value < 0:
            raise ValueError(f"{field}: negative unit price/cost")
        values[field] = float(value)
    v = values
    incremental_cost = (
        v["delta_water_m3"] * v["water_tariff_per_m3"]
        + v["delta_events"] * v["event_labor_cost"]
        + v["delta_drainage_mm"] * v["drainage_cost_per_mm"]
        + v["annualized_capital_delta"] + v["energy_cost_delta"]
    )
    price = v["crop_price_per_kg"]
    # Yield increase needed for nonnegative incremental margin.
    # With zero crop price, no finite break-even yield is identifiable
    # when incremental cost is positive.
    required_yield_kg = max(0.0, incremental_cost / price) if price > 0 else None
    return {
        "incremental_cost_currency_per_period": incremental_cost,
        "break_even_additional_yield_kg_per_period": required_yield_kg,
        "break_even_identifiable": price > 0,
        "input_status": "user_supplied_unverified",
        "evidence_class": "conditional_algebra_not_empirical",
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parameters", type=Path)
    args = parser.parse_args()
    record = json.loads(args.parameters.read_text(encoding="utf-8"))
    print(json.dumps(calculate(record), indent=2, sort_keys=True, allow_nan=False))

if __name__ == "__main__":
    main()
