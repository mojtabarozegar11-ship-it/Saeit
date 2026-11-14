"""Deterministic, side-effect-free quote/unit-economics calculation.

The result is a scenario, never a provider-confirmed settlement or actual profit.
No IO, private customer data, currency conversion, external model or payment.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP

_PRECISION = {"IRR": 0, "IRT": 0, "USD": 2, "TRX": 6}
_FIELDS = frozenset({
    "currency", "base_unit_price", "discount_percent", "direct_unit_cost",
    "delivery_unit_cost", "payment_unit_fee", "refund_unit_reserve",
    "tax_unit_reserve", "period_fixed_cost", "expected_units",
})
_NONNEGATIVE = (
    "discount_percent", "direct_unit_cost", "delivery_unit_cost",
    "payment_unit_fee", "refund_unit_reserve", "tax_unit_reserve",
    "period_fixed_cost",
)
_NUMERIC = re.compile(r"^(?:0|[1-9][0-9]{0,14})(?:\.[0-9]{1,6})?$")


def _amount(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(
        value, (str, int, Decimal)
    ):
        raise ValueError(f"{field}: use a decimal string, int or Decimal; never float/bool")
    text = str(value)
    if not _NUMERIC.fullmatch(text):
        raise ValueError(f"{field}: expected a bounded, non-negative decimal")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{field}: invalid decimal") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{field}: non-negative finite decimal required")
    return result


def compute_quote_scenario(data: dict) -> dict:
    """Compute conservative unit economics with strict, explicit units.

    Input prices and costs are in exactly one specified currency, not mixed
    rials/tomans, fiat and TRX. No accepted value may imply cash has settled.
    """
    if not isinstance(data, dict):
        raise ValueError("quote data must be a dictionary")
    missing = _FIELDS - set(data)
    extra = set(data) - _FIELDS
    if missing or extra:
        raise ValueError("quote fields mismatch: missing=%s extra=%s" % (
            sorted(missing), sorted(extra)
        ))
    currency = data["currency"]
    if not isinstance(currency, str) or currency not in _PRECISION:
        raise ValueError("currency must be exactly IRR, IRT, USD or TRX")
    units = data["expected_units"]
    if isinstance(units, bool) or not isinstance(units, int) or not 0 <= units <= 1_000_000:
        raise ValueError("expected_units must be integer between 0 and 1000000")

    amounts = {field: _amount(data[field], field) for field in _NONNEGATIVE}
    base = _amount(data["base_unit_price"], "base_unit_price")
    if not base:
        raise ValueError("base_unit_price must be positive")
    discount = amounts["discount_percent"]
    if discount > 100:
        raise ValueError("discount_percent cannot exceed 100")
    quantum = Decimal("1").scaleb(-_PRECISION[currency])
    unit_sale_price = (base * (Decimal("100") - discount) / Decimal("100")).quantize(
        quantum, rounding=ROUND_HALF_UP
    )
    variable_unit = sum((
        amounts["direct_unit_cost"],
        amounts["delivery_unit_cost"],
        amounts["payment_unit_fee"],
        amounts["refund_unit_reserve"],
        amounts["tax_unit_reserve"],
    ), Decimal("0")).quantize(quantum, rounding=ROUND_HALF_UP)
    fixed = amounts["period_fixed_cost"].quantize(quantum, rounding=ROUND_HALF_UP)
    contribution = unit_sale_price - variable_unit
    break_even = None
    if contribution > 0:
        break_even = int((fixed / contribution).to_integral_value(rounding=ROUND_CEILING))
    gross = unit_sale_price * units
    variable_total = variable_unit * units
    expected_contribution = contribution * units
    operating_result = expected_contribution - fixed

    def show(value: Decimal) -> str:
        return format(value.quantize(quantum, rounding=ROUND_HALF_UP), "f")

    return {
        "schema_version": 1,
        "source": "hypothetical_quote_scenario",
        "currency": currency,
        "expected_units": units,
        "discount_percent": show(discount),
        "unit_price": show(unit_sale_price),
        "variable_unit_cost": show(variable_unit),
        "unit_contribution": show(contribution),
        "estimated_gross_sales": show(gross),
        "estimated_variable_cost": show(variable_total),
        "estimated_contribution": show(expected_contribution),
        "period_fixed_cost": show(fixed),
        "estimated_operating_result": show(operating_result),
        "break_even_units": break_even,
        "unit_economics_viable": contribution > 0,
        "scenario_reaches_break_even": bool(
            break_even is not None and units >= break_even
        ),
        "external_cash_settlement": None,
        "verified_net_profit": None,
        "financial_claim": "SCENARIO_ONLY_NOT_RECEIPT",
        "requires_owner_approval_for_price_and_spend": True,
    }
