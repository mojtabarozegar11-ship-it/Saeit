"""AGR-01: original farm enterprise cost, break-even and scenario work product.

Deterministic advisory computation from a buyer's verified input figures;
there is NO invented regional yield, market price, irrigation benchmark or
profit guarantee. This standalone kernel is not a public paid service.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

TWO = Decimal("0.01")
THREE = Decimal("0.001")
HUNDRED = Decimal("100")


class FarmEconomicsInputError(ValueError):
    pass


@dataclass(frozen=True)
class FarmEnterpriseInputs:
    area_hectares: str
    production_tonnes_per_hectare: str
    farmgate_price_per_tonne: str
    variable_cost_per_hectare: str
    fixed_cost_total: str
    irrigation_m3_per_hectare: str
    currency_code: str = "IRR"


@dataclass(frozen=True)
class FarmEnterpriseReport:
    currency_code: str
    gross_revenue: str
    variable_cost_total: str
    total_cost: str
    operating_surplus: str
    contribution_per_tonne: str
    break_even_yield_tonnes_per_hectare: str | None
    water_productivity_kg_per_m3: str
    price_down_10pct_surplus: str
    yield_down_10pct_surplus: str
    combined_price_and_yield_down_10pct_surplus: str
    operating_margin_pct: str | None
    inputs_provenance: str = "customer_supplied_not_independently_verified"
    buyer_payment_collected: bool = False
    forecast_or_profit_guaranteed: bool = False


def _number(value, name, *, positive=False):
    if type(value) not in (str, int, Decimal):
        raise FarmEconomicsInputError(name + "_type")
    try:
        n = Decimal(str(value))
    except (ValueError, InvalidOperation, ArithmeticError):
        raise FarmEconomicsInputError(name + "_invalid") from None
    if (not n.is_finite() or len(n.as_tuple().digits) > 25
            or n < 0 or (positive and n <= 0)):
        raise FarmEconomicsInputError(name + "_range")
    return n


def _money(value):
    return format(value.quantize(TWO, rounding=ROUND_HALF_UP), ".2f")


def assess_farm_enterprise(v: FarmEnterpriseInputs) -> FarmEnterpriseReport:
    """Fixed/variable economics with loss and risk scenarios in same currency."""
    if not isinstance(v, FarmEnterpriseInputs):
        raise FarmEconomicsInputError("farm_inputs_missing")
    if type(v.currency_code) is not str or v.currency_code not in ("IRR", "TOMAN", "USD"):
        raise FarmEconomicsInputError("farm_currency_not_recognized")
    area = _number(v.area_hectares, "area", positive=True)
    yield_rate = _number(v.production_tonnes_per_hectare, "yield")
    price = _number(v.farmgate_price_per_tonne, "farmgate_price")
    unit_cost = _number(v.variable_cost_per_hectare, "variable_cost")
    fixed = _number(v.fixed_cost_total, "fixed_cost")
    water_rate = _number(v.irrigation_m3_per_hectare, "irrigation", positive=True)
    if area > Decimal("100000000") or yield_rate > Decimal("10000000"):
        raise FarmEconomicsInputError("farm_physical_scale_invalid")
    if any(v > Decimal("1000000000000") for v in (price, unit_cost, fixed)):
        raise FarmEconomicsInputError("farm_currency_scale_invalid")
    # Keep IRR-scale financial coefficients exactly representable, including
    # cents, without rounding-overflow at the default 28-digit precision.
    with localcontext() as ctx:
        ctx.prec = 60
        revenue = area * yield_rate * price
        variable = area * unit_cost
        total = variable + fixed
        surplus = revenue - total
        tonnage = area * yield_rate
        water = area * water_rate
        # Per-tonne variable unit cost is undefined at zero production. In the
        # zero-output case both contribution and break-even price require a hold.
        contribution = (price - unit_cost / yield_rate) if yield_rate > 0 else None
        break_even_yield = ((variable + fixed) / (area * price)
                            if price > 0 else None)
        water_productivity = tonnage * Decimal("1000") / water
        price_down = revenue * Decimal("0.9") - total
        # The variable costs and fixed costs are conservatively held constant
        # for a one-period 10% yield shock; change requires a new buyer scenario.
        yield_down = revenue * Decimal("0.9") - total
        both_down = revenue * Decimal("0.81") - total
        ratio = surplus / revenue * HUNDRED if revenue > 0 else None
        return FarmEnterpriseReport(
            currency_code=v.currency_code,
            gross_revenue=_money(revenue),
            variable_cost_total=_money(variable),
            total_cost=_money(total),
            operating_surplus=_money(surplus),
            contribution_per_tonne=(_money(contribution) if contribution is not None else "undefined_no_production"),
            break_even_yield_tonnes_per_hectare=(
                format(break_even_yield.quantize(THREE, rounding=ROUND_HALF_UP), ".3f")
                if break_even_yield is not None else None
            ),
            water_productivity_kg_per_m3=format(
                water_productivity.quantize(THREE, rounding=ROUND_HALF_UP), ".3f"
            ),
            price_down_10pct_surplus=_money(price_down),
            yield_down_10pct_surplus=_money(yield_down),
            combined_price_and_yield_down_10pct_surplus=_money(both_down),
            operating_margin_pct=(_money(ratio) if ratio is not None else None),
        )
