#!/usr/bin/env python3
"""Greenhouse crop margin and break-even planner using user-supplied inputs.

This is a deterministic planning aid. It makes no market-price, yield, or
agronomic claims and uses only Python's standard library.
"""
import argparse
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
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


def minimum_threshold(value, unit):
    """Round required break-even thresholds up so the displayed value is safe."""
    return str(value.quantize(Decimal(unit), rounding=ROUND_CEILING))


def granular_costs(data, area):
    """Use explicit greenhouse cost drivers without double-counting legacy totals."""
    required = (
        "crop", "season", "water_liters_per_m2", "water_cost_per_liter",
        "energy_kwh_per_m2", "energy_cost_per_kwh",
        "labor_hours_per_m2", "labor_cost_per_hour",
        "climate_control_kwh_per_m2", "climate_control_cost_per_kwh",
        "other_variable_cost_per_m2",
    )
    if not any(key in data for key in required):
        return None
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError("granular resource model requires all fields: " + ", ".join(missing))
    if "variable_cost_per_m2" in data:
        raise ValueError("remove legacy variable_cost_per_m2 to prevent cost double counting")
    for key in ("crop", "season"):
        value = data[key]
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100 or not value.isprintable():
            raise ValueError(key + ": a bounded crop/season label is required")
    rates = {
        key: number(data[key], key, minimum=0, maximum="100000000")
        for key in required if key not in ("crop", "season")
    }
    unit_costs = {
        "water": rates["water_liters_per_m2"] * rates["water_cost_per_liter"],
        "energy": rates["energy_kwh_per_m2"] * rates["energy_cost_per_kwh"],
        "labor": rates["labor_hours_per_m2"] * rates["labor_cost_per_hour"],
        "climate_control": rates["climate_control_kwh_per_m2"] * rates["climate_control_cost_per_kwh"],
        "other": rates["other_variable_cost_per_m2"],
    }
    breakdown = {name: area * amount for name, amount in unit_costs.items()}
    return {
        "crop": data["crop"].strip(), "season": data["season"].strip(),
        "unit_rates": rates, "variable_cost": sum(breakdown.values()),
        "cost_breakdown": breakdown,
    }


def uncertainty_model(settings, *, area, yield_rate, price, rejection, total_cost):
    """Exploratory, seeded independent triangular inputs; not market calibration."""
    import random
    if not isinstance(settings, dict):
        raise ValueError("uncertainty must be an object")
    y_min = number(settings.get("yield_min_kg_per_m2"), "yield_min_kg_per_m2", minimum=0, maximum="100000000")
    y_max = number(settings.get("yield_max_kg_per_m2"), "yield_max_kg_per_m2", minimum=0, maximum="100000000")
    p_min = number(settings.get("price_min_per_kg"), "price_min_per_kg", minimum=0, maximum="100000000")
    p_max = number(settings.get("price_max_per_kg"), "price_max_per_kg", minimum=0, maximum="100000000")
    if not y_min <= yield_rate <= y_max or not p_min <= price <= p_max:
        raise ValueError("triangular mode must be within its stated min/max")
    seed = settings.get("seed", 0)
    if type(seed) is not int or not 0 <= seed < 2**31:
        raise ValueError("seed must be a bounded non-negative integer")
    rng = random.Random(seed)
    iterations = 2000
    usable_factor = Decimal(1) - rejection / Decimal(100)
    margins = []
    for _ in range(iterations):
        sampled_yield = Decimal(str(rng.triangular(float(y_min), float(y_max), float(yield_rate))))
        sampled_price = Decimal(str(rng.triangular(float(p_min), float(p_max), float(price))))
        margins.append(area * sampled_yield * usable_factor * sampled_price - total_cost)
    margins.sort()
    negatives = sum(value < 0 for value in margins)
    return {
        "method": "seeded_independent_triangular_monte_carlo",
        "sample_count": iterations,
        "seed": seed,
        "p05_net_margin": money(margins[int((iterations - 1) * 0.05)]),
        "median_net_margin": money(margins[int((iterations - 1) * 0.50)]),
        "p95_net_margin": money(margins[int((iterations - 1) * 0.95)]),
        "negative_margin_percent_model_only": money(Decimal(negatives) * 100 / iterations),
        "uncertainty_inputs_market_calibrated": False,
        "assumption": "Yield and selling price are independent triangular inputs entered by the user; this is not a validated probability forecast.",
    }


def calculate(data):
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    area = number(data.get("area_m2"), "area_m2", minimum="0.000001")
    yield_rate = number(data.get("expected_yield_kg_per_m2"),
                        "expected_yield_kg_per_m2", minimum=0)
    price = number(data.get("price_per_kg"), "price_per_kg", minimum=0)
    fixed_cost = number(data.get("fixed_cost_total"), "fixed_cost_total", minimum=0)
    rejection = number(data.get("rejection_rate_percent", 0),
                       "rejection_rate_percent", minimum=0, maximum=100)
    currency = str(data.get("currency") or "").strip().upper()
    if not currency or len(currency) > 12 or not currency.isascii() or not currency.replace("_", "").isalnum():
        raise ValueError("currency must be an ISO code or clearly labeled unit")

    granular = granular_costs(data, area)
    if granular is None:
        variable_cost_rate = number(data.get("variable_cost_per_m2"),
                                    "variable_cost_per_m2", minimum=0)
        variable_cost = area * variable_cost_rate
    else:
        variable_cost = granular["variable_cost"]
        variable_cost_rate = variable_cost / area

    gross_yield = area * yield_rate
    saleable_yield = gross_yield * (Decimal(1) - rejection / Decimal(100))
    revenue = saleable_yield * price
    total_cost = variable_cost + fixed_cost
    margin = revenue - total_cost
    # A nearest-cent price can be below break-even; always round upward.
    break_even_price = (None if saleable_yield == 0 else
                        minimum_threshold(total_cost / saleable_yield, "0.01"))
    gross_yield_revenue_factor = area * (Decimal(1) - rejection / Decimal(100)) * price
    if total_cost == 0:
        break_even_gross_yield = "0.000"
    elif gross_yield_revenue_factor == 0:
        break_even_gross_yield = None
    else:
        break_even_gross_yield = minimum_threshold(
            total_cost / gross_yield_revenue_factor, "0.001")
    # Illustrative simultaneous downside, not a calibrated forecast. Resource
    # mode additionally exposes the cost of a higher water tariff.
    stress_revenue = saleable_yield * Decimal("0.90") * price * Decimal("0.90")
    water_tariff_increment = (
        granular["cost_breakdown"]["water"] * Decimal("0.20")
        if granular is not None else None
    )
    stress_total_cost = total_cost + (water_tariff_increment or Decimal(0))
    stress_margin = stress_revenue - stress_total_cost
    result = {
        "version": "2.1" if granular else "1.1",
        "model_scope": "resource_explicit_uncalibrated" if granular else "legacy_aggregate_cost",
        "input_values_independently_validated": False,
        "output_scope": "user_supplied_scenario_arithmetic_not_a_forecast",
        "market_data_independently_validated": False,
        "currency": currency,
        "assumptions": [
            "Area, yield, price, rejection and all costs are user-supplied; there are no live market feeds.",
            "Yield and price are treated as constant across the entered growing area in the base case.",
            "Taxes, financing, depreciation and any unentered expenses are excluded.",
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
            "minimum_gross_yield_kg_per_m2_to_break_even": break_even_gross_yield,
            "minimum_gross_yield_reachable": break_even_gross_yield is not None,
            "break_even_reachable": saleable_yield > 0,
            "downside_stress_test": {
                "yield_multiplier": "0.90",
                "price_multiplier": "0.90",
                "water_tariff_multiplier": "1.20" if granular is not None else None,
                "water_tariff_scenario_applicable": granular is not None,
                "modeled_revenue": money(stress_revenue),
                "modeled_total_cost": money(stress_total_cost),
                "modeled_net_margin": money(stress_margin),
                "modeled_loss": stress_margin < 0,
                "market_probability_calibrated": False,
            },
        },
    }
    if granular:
        result["inputs"]["crop"] = granular["crop"]
        result["inputs"]["season"] = granular["season"]
        result["inputs"]["resource_rates"] = {key: str(value) for key, value in granular["unit_rates"].items()}
        result["results"]["resource_cost_breakdown"] = {
            key: money(value) for key, value in granular["cost_breakdown"].items()
        }
    if "uncertainty" in data:
        if granular is None:
            raise ValueError("uncertainty analysis requires a complete explicit crop/season resource model")
        result["results"]["uncertainty"] = uncertainty_model(
            data["uncertainty"], area=area, yield_rate=yield_rate, price=price,
            rejection=rejection, total_cost=total_cost)
    return result


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
