from dataclasses import replace
from decimal import Decimal

from .mojprop_starter30_product_profile import (
    DEFAULT_STARTER30_PROFILE,
    validate_starter30_profile,
)


def test_default_profile_encodes_owner_operational_constraints():
    profile = DEFAULT_STARTER30_PROFILE
    assert profile.virtual_capital_usd == Decimal("1000")
    assert profile.challenge_duration_days == 60
    assert profile.daily_drawdown_pct == Decimal("6")
    assert profile.per_trade_risk_pct == Decimal("3")
    assert profile.open_positions_risk_pct == Decimal("4")
    assert profile.entry_fee_trx == 30
    assert profile.retry_discount_pct == Decimal("40")
    assert profile.retry_fee_trx == 18
    assert profile.best_day_profit_share_cap_pct == Decimal("50")
    assert profile.simulation_only is True
    assert profile.customer_funds_custodied is False
    assert profile.profit_guarantee is False
    assert validate_starter30_profile(profile) == ()


def test_profile_rejects_another_consistency_cap():
    profile = replace(
        DEFAULT_STARTER30_PROFILE,
        best_day_profit_share_cap_pct=Decimal("75"),
    )
    assert validate_starter30_profile(profile) == (
        "best_day_profit_cap_must_equal_50_percent",
    )


def test_profile_is_fail_closed_for_customer_funds_and_profit_promises():
    profile = replace(
        DEFAULT_STARTER30_PROFILE,
        customer_funds_custodied=True,
        profit_guarantee=True,
    )
    errors = validate_starter30_profile(profile)
    assert "customer_funds_must_not_be_custodied" in errors
    assert "profit_guarantee_forbidden" in errors


def test_profile_module_does_not_contain_payment_side_effects():
    source = open(
        __file__.replace(
            "test_mojprop_starter30_product_profile.py",
            "mojprop_starter30_product_profile.py",
        ),
        encoding="utf-8",
    ).read()
    for forbidden in (
        "create_invoice",
        "broadcast",
        "settle",
        "send_mail",
        "place_order",
        "enable_payment",
    ):
        assert forbidden not in source
