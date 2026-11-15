"""Production-economics arithmetic for user-supplied irrigation scenarios.

A pure, dependency-free accounting model. Do not feed the synthetic R01
policy rows into farm revenue claims: they have no verified yield, cost or
farmgate-price observations. This model does not sell a product, price a crop
market, make payments or validate a farmer's measurements.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import re

IDENT = re.compile(r"[a-z][a-z0-9_-]{2,63}\Z")
DECIMAL_TEXT = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?\Z")
MAX_INPUT = Decimal("1000000000000")
UNIT = Decimal("0.000001")
ALLOWED_CURRENCIES = frozenset(("IRR", "TOMAN", "USD", "EUR"))
ALLOWED_PROVENANCE = frozenset(("planning_assumption", "synthetic", "unverified_user_record"))
NUMERIC_FIELDS = (
    "area_ha", "yield_kg_per_ha", "farmgate_price_per_kg",
    "irrigation_m3_per_ha", "water_cost_per_m3",
    "energy_kwh_per_ha", "energy_cost_per_kwh",
    "other_variable_cost_per_ha", "allocated_fixed_cost_per_ha",
)


class FarmBudgetError(ValueError):
    pass


def _amount(value, field_name, *, positive=False):
    if type(value) is str:
        if DECIMAL_TEXT.fullmatch(value) is None:
            raise FarmBudgetError(field_name + ": expected canonical decimal")
        number = Decimal(value)
    elif type(value) is Decimal:
        number = value
    elif type(value) is int:
        number = Decimal(value)
    else:
        raise FarmBudgetError(field_name + ": floats, bools and invalid types forbidden")
    if (not number.is_finite() or not 0 <= number <= MAX_INPUT
            or number.as_tuple().exponent < -6
            or (positive and number == 0)):
        raise FarmBudgetError(field_name + ": out of range or precision")
    return number


@dataclass(frozen=True)
class FarmScenario:
    scenario_id: str
    crop_id: str
    season_id: str
    currency: str
    provenance: str
    area_ha: Decimal
    yield_kg_per_ha: Decimal
    farmgate_price_per_kg: Decimal
    irrigation_m3_per_ha: Decimal
    water_cost_per_m3: Decimal
    energy_kwh_per_ha: Decimal
    energy_cost_per_kwh: Decimal
    other_variable_cost_per_ha: Decimal
    allocated_fixed_cost_per_ha: Decimal

    def __post_init__(self):
        if any(
            type(getattr(self, field)) is not str
            or IDENT.fullmatch(getattr(self, field)) is None
            for field in ("scenario_id", "crop_id", "season_id")
        ):
            raise FarmBudgetError("invalid scenario, crop or season identity")
        if type(self.currency) is not str or self.currency not in ALLOWED_CURRENCIES:
            raise FarmBudgetError("currency unit is unsupported")
        if type(self.provenance) is not str or self.provenance not in ALLOWED_PROVENANCE:
            raise FarmBudgetError("source class must be explicit")
        for field_name in NUMERIC_FIELDS:
            object.__setattr__(
                self, field_name,
                _amount(getattr(self, field_name), field_name,
                        positive=field_name == "area_ha"),
            )


def _exact(value):
    with localcontext() as ctx:
        ctx.prec = 58
        try:
            return format(value.quantize(UNIT), "f")
        except InvalidOperation as exc:
            raise FarmBudgetError("computed budget exceeds precision policy") from exc


def _ratio(numerator, denominator):
    if denominator == 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 58
        return _exact(numerator / denominator)


def _measures(scenario):
    with localcontext() as ctx:
        ctx.prec = 58
        gross = scenario.yield_kg_per_ha * scenario.farmgate_price_per_kg
        water_bill = scenario.irrigation_m3_per_ha * scenario.water_cost_per_m3
        energy_bill = scenario.energy_kwh_per_ha * scenario.energy_cost_per_kwh
        variable = water_bill + energy_bill + scenario.other_variable_cost_per_ha
        fixed = scenario.allocated_fixed_cost_per_ha
        total = variable + fixed
        margin = gross - variable
        net = margin - fixed
        return {
            "gross_return_per_ha": gross,
            "irrigation_cost_per_ha": water_bill,
            "energy_cost_per_ha": energy_bill,
            "other_variable_cost_per_ha": scenario.other_variable_cost_per_ha,
            "variable_cost_per_ha": variable,
            "allocated_fixed_cost_per_ha": fixed,
            "total_cost_per_ha": total,
            "gross_margin_per_ha": margin,
            "net_return_after_allocated_costs_per_ha": net,
            "gross_return_total": gross * scenario.area_ha,
            "gross_margin_total": margin * scenario.area_ha,
            "net_return_after_allocated_costs_total": net * scenario.area_ha,
            "water_volume_total_m3": scenario.irrigation_m3_per_ha * scenario.area_ha,
            "production_total_kg": scenario.yield_kg_per_ha * scenario.area_ha,
            "water_productivity_kg_per_m3": _ratio(
                scenario.yield_kg_per_ha, scenario.irrigation_m3_per_ha,
            ),
            "break_even_price_per_kg": _ratio(total, scenario.yield_kg_per_ha),
            "break_even_yield_kg_per_ha": _ratio(total, scenario.farmgate_price_per_kg),
        }


def budget(scenario: FarmScenario) -> dict:
    """Deterministic auditable budget; no income or field claim implied."""
    if type(scenario) is not FarmScenario:
        raise FarmBudgetError("validated enterprise scenario required")
    measures = _measures(scenario)
    inputs = {field.name: _exact(getattr(scenario, field.name))
              if field.name in NUMERIC_FIELDS else getattr(scenario, field.name)
              for field in fields(FarmScenario)}
    raw = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "schema": "zomorod.farm-enterprise-budget.v1",
        "input_digest_sha256": hashlib.sha256(raw.encode("ascii")).hexdigest(),
        "scenario_id": scenario.scenario_id,
        "crop_id": scenario.crop_id,
        "season_id": scenario.season_id,
        "currency": scenario.currency,
        "input_provenance": scenario.provenance,
        "input_values_verified": False,
        "field_efficacy_verified": False,
        "realized_income_verified": False,
        "all_fixed_costs_independently_verified": False,
        "accounting_scope": "single crop season with explicitly allocated fixed costs",
        "per_ha_and_total": {
            key: (value if type(value) is str or value is None else _exact(value))
            for key, value in measures.items()
        },
    }


def compare_scenarios(baseline: FarmScenario, alternative: FarmScenario) -> dict:
    """Within-crop partial comparison; never a causal irrigation treatment effect."""
    if type(baseline) is not FarmScenario or type(alternative) is not FarmScenario:
        raise FarmBudgetError("two validated scenarios required")
    if baseline.scenario_id == alternative.scenario_id:
        raise FarmBudgetError("comparison scenarios require distinct identifiers")
    for key in ("crop_id", "season_id", "currency", "area_ha"):
        if getattr(baseline, key) != getattr(alternative, key):
            raise FarmBudgetError("noncomparable farm budget dimension: " + key)
    with localcontext() as ctx:
        ctx.prec = 58
        b, a = _measures(baseline), _measures(alternative)
        changes = {
            "delta_water_m3_per_ha": (alternative.irrigation_m3_per_ha
                                      - baseline.irrigation_m3_per_ha),
            "delta_yield_kg_per_ha": (alternative.yield_kg_per_ha
                                      - baseline.yield_kg_per_ha),
            "delta_gross_return_per_ha": (a["gross_return_per_ha"]
                                           - b["gross_return_per_ha"]),
            "delta_variable_cost_per_ha": (a["variable_cost_per_ha"]
                                            - b["variable_cost_per_ha"]),
            "delta_gross_margin_per_ha": (a["gross_margin_per_ha"]
                                           - b["gross_margin_per_ha"]),
            "delta_net_return_per_ha": (
                a["net_return_after_allocated_costs_per_ha"]
                - b["net_return_after_allocated_costs_per_ha"]
            ),
        }
        return {
            "schema": "zomorod.farm-budget-comparison.v1",
            "baseline_digest_sha256": budget(baseline)["input_digest_sha256"],
            "alternative_digest_sha256": budget(alternative)["input_digest_sha256"],
            "currency": baseline.currency,
            "input_values_verified": False,
            "causal_effect_claimed": False,
            "field_water_savings_verified": False,
            "not_a_realized_profit_forecast": True,
            "differences_alternative_minus_baseline": {
                key: _exact(value) for key, value in changes.items()
            },
            "same_crop_season_area_required": True,
        }
