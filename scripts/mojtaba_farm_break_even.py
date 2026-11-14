#!/usr/bin/env python3
"""Functional farm enterprise economics: actual arithmetic, never invented data.

An offline and deterministic economic capability of the ONLY Mojtaba.bot.ai.
User-provided aggregate figures may be real, but this module NEVER attests
their accuracy, issues a paid quotation, stores PII or submits a customer form.
All accounting is in IRR, with explicit periods and 27 sensitivity scenarios.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import re

BOT = "mojtaba.bot.ai"
NUM = re.compile(r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,4})?$")
MONEY = re.compile(r"^(?:0|[1-9][0-9]{0,13})$")
RATIO = re.compile(r"^(?:0|0\.[0-9]{1,4})$")
EXPECTED = frozenset({
    "canonical_bot", "period", "area_ha", "yield_kg_per_ha",
    "sale_price_irr_per_kg", "variable_cost_irr_per_kg",
    "fixed_cost_irr", "price_sensitivity_fraction",
    "yield_sensitivity_fraction", "cost_sensitivity_fraction",
    "synthetic_example",
})


def strict_decimal(value, pattern, field):
    if type(value) is not str or not pattern.fullmatch(value):
        raise ValueError("INVALID_" + field.upper())
    return Decimal(value)


def money_irr(value):
    return str(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def model(data: dict) -> dict:
    if type(data) is not dict or set(data) != EXPECTED:
        raise ValueError("FARM_MODEL_SCHEMA_REJECTED")
    if data["canonical_bot"] != BOT:
        raise ValueError("NON_CANONICAL_BOT_REJECTED")
    if data["period"] not in ("season", "annual"):
        raise ValueError("UNKNOWN_ACCOUNTING_PERIOD")
    if type(data["synthetic_example"]) is not bool:
        raise ValueError("SYNTHETIC_PROVENANCE_FLAG_INVALID")
    area = strict_decimal(data["area_ha"], NUM, "area")
    yield_kg = strict_decimal(data["yield_kg_per_ha"], NUM, "yield")
    price = strict_decimal(data["sale_price_irr_per_kg"], MONEY, "price")
    var = strict_decimal(data["variable_cost_irr_per_kg"], MONEY, "variable_cost")
    fixed = strict_decimal(data["fixed_cost_irr"], MONEY, "fixed")
    sensitivities = [
        strict_decimal(data[key], RATIO, key)
        for key in ("price_sensitivity_fraction", "yield_sensitivity_fraction",
                    "cost_sensitivity_fraction")
    ]
    if area <= 0 or yield_kg <= 0 or price <= 0:
        raise ValueError("AREA_YIELD_AND_PRICE_MUST_BE_POSITIVE")
    if any(x > Decimal("0.30") for x in sensitivities):
        raise ValueError("SENSITIVITY_EXCEEDS_30_PERCENT")
    quantity = area * yield_kg
    revenue = quantity * price
    variable_total = quantity * var
    total_cost = variable_total + fixed
    profit = revenue - total_cost
    unit_contribution = price - var
    if unit_contribution <= 0:
        breakeven_kg = None
        contribution_ratio = None
        breakeven_revenue = None
    else:
        breakeven_kg = (fixed / unit_contribution).quantize(
            Decimal("1"), rounding=ROUND_CEILING)
        contribution_ratio = unit_contribution / price
        breakeven_revenue = (fixed / contribution_ratio).quantize(
            Decimal("1"), rounding=ROUND_CEILING)
    breakeven_price = (var + fixed / quantity).quantize(
        Decimal("1"), rounding=ROUND_CEILING)
    margin_of_safety = None if breakeven_kg is None else quantity - breakeven_kg
    rows = []
    for dp in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dc in (-1, 0, 1):
                p2 = price * (1 + dp * sensitivities[0])
                q2 = quantity * (1 + dy * sensitivities[1])
                v2 = var * (1 + dc * sensitivities[2])
                profit2 = q2 * (p2 - v2) - fixed
                rows.append({
                    "price_direction": dp, "yield_direction": dy,
                    "variable_cost_direction": dc,
                    "profit_irr": money_irr(profit2),
                    "loss_scenario": profit2 < 0,
                })
    return {
        "schema": "mojtaba.bot.ai.farm-break-even.v1",
        "canonical_bot": BOT,
        "currency": "IRR",
        "period": data["period"],
        "synthetic_example": data["synthetic_example"],
        "input_figures_independently_verified": False,
        "volume_kg": str(quantity),
        "gross_revenue_irr": money_irr(revenue),
        "variable_cost_irr": money_irr(variable_total),
        "fixed_cost_irr": str(fixed),
        "total_cost_irr": money_irr(total_cost),
        "estimated_profit_irr": money_irr(profit),
        "unit_contribution_irr_per_kg": str(unit_contribution),
        "breakeven_quantity_kg_ceil": None if breakeven_kg is None else str(breakeven_kg),
        "breakeven_revenue_irr_ceil": None if breakeven_revenue is None else str(breakeven_revenue),
        "breakeven_sale_price_irr_per_kg_ceil": str(breakeven_price),
        "margin_of_safety_kg": None if margin_of_safety is None else str(margin_of_safety),
        "unit_contribution_nonpositive": unit_contribution <= 0,
        "scenario_count": len(rows),
        "sensitivity_scenarios": rows,
        "report_quality": "mathematical_output_subject_to_input_verification",
        "scope": "one_product_one_accounting_period_before_tax_financing_and_subsidies",
        "quote_approved": False,
        "invoice_created": False,
        "payment_collected": False,
        "production_deployed": False,
        "next_gate": "verify_farm_data_and_scope_before_commercial_client_delivery",
    }
