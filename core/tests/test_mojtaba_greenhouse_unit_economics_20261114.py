"""Business-grade offline unit economics for the ONE Mojtaba bot.

Only deterministic customer-supplied fixtures. No commerce, mail, network,
user data, autonomous worker, payment, deployment or live server access.
"""
import pytest

from core.economic_tool_pack import (
    greenhouse_unit_economics, build_economic_gateway,
)


def sample(**changes):
    data = {
        "currency": "USD", "area_m2": "100",
        "harvested_kg": "200", "saleable_kg": "180",
        "sale_price_per_kg": "10.50",
        "production_cost_per_harvested_kg": "4.00",
        "fixed_cost": "200.00", "energy_cost": "100.00",
        "water_cost": "10.00", "labor_cost": "300.00",
        "other_cost": "50.00",
    }
    data.update(changes)
    return data


def test_real_unit_economics_report_uses_harvested_cost_and_saleable_revenue():
    result = greenhouse_unit_economics(sample())
    assert result["gross_revenue_estimate"] == "1890.00"
    assert result["harvest_production_cost"] == "800.00"
    assert result["period_overheads"] == "660.00"
    assert result["period_total_cost"] == "1460.00"
    assert result["operating_surplus_estimate"] == "430.00"
    assert result["marketable_rate_percent"] == "90.00"
    assert result["harvested_kg_per_m2"] == "2.0000"
    assert result["break_even_saleable_kg_at_same_period_cost"] == "139.05"
    assert result["break_even_within_observed_harvest"] is True
    assert result["bot_id"] == "mojtaba.bot.ai"
    assert result["external_actions"] == 0


def test_loss_report_can_be_negative_without_false_profit_claim():
    result = greenhouse_unit_economics(sample(sale_price_per_kg="1.00"))
    assert result["operating_surplus_estimate"] == "-1280.00"
    assert result["break_even_within_observed_harvest"] is False
    assert result["independent_cash_settlement_verified"] is False


def test_zero_saleable_crop_is_not_division_by_zero():
    result = greenhouse_unit_economics(sample(saleable_kg="0"))
    assert result["gross_revenue_estimate"] == "0.00"
    assert result["operating_margin_percent"] is None


def test_empty_harvest_and_saleable_share_unknown_not_zero_percent():
    result = greenhouse_unit_economics(sample(harvested_kg="0", saleable_kg="0"))
    assert result["marketable_rate_percent"] is None


@pytest.mark.parametrize("field,value", [
    ("area_m2", "0"), ("sale_price_per_kg", "0"),
    ("area_m2", "-1"), ("labor_cost", "-50"),
    ("harvested_kg", "NaN"), ("harvested_kg", "Infinity"),
    ("water_cost", 5.0), ("fixed_cost", True),
    ("sale_price_per_kg", "1e10"), ("other_cost", "1000000001"),
    ("fixed_cost", "0.00001"), ("energy_cost", " 10"),
])
def test_invalid_and_unsafe_input_fails_closed(field, value):
    with pytest.raises(ValueError):
        greenhouse_unit_economics(sample(**{field: value}))


def test_saleable_volume_cannot_exceed_harvested_volume():
    with pytest.raises(ValueError, match="SALEABLE_EXCEEDS_HARVEST"):
        greenhouse_unit_economics(sample(saleable_kg="201"))


def test_unknown_field_rejected_to_prevent_sensitive_data_echos():
    with pytest.raises(ValueError, match="EXACT_INPUTS_REQUIRED"):
        greenhouse_unit_economics(sample(customer_email="private@example.test"))


def test_currency_is_constrained_and_not_a_payment_quote():
    with pytest.raises(ValueError, match="CURRENCY_INVALID"):
        greenhouse_unit_economics(sample(currency="trx"))
    result = greenhouse_unit_economics(sample(currency="IRR"))
    assert result["commercial_release"] == "blocked_pending_owner_and_payment_review"


def test_source_digest_deterministic_when_same_observations_are_ordered_differently():
    a = greenhouse_unit_economics(sample())
    b = greenhouse_unit_economics(dict(reversed(list(sample().items()))))
    assert a["input_sha256"] == b["input_sha256"]
    assert len(a["input_sha256"]) == 64


def test_gateway_contains_single_b2b_capability_disabled_by_default():
    specs = build_economic_gateway().describe()
    assert specs["income_greenhouse_economics"] == {
        "risk": "medium", "enabled": False,
    }
    assert "income_greenhouse_economics" not in (
        "income_market_research", "income_offer_design",
    )
