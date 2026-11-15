"""Owner gate regression for the canonical Moj Prop ladder."""
from decimal import Decimal

from prop_firm.rules import (
    LEVEL_10_CAPACITY_USD,
    LEVEL_10_LOCKED,
    assess_promotion,
    assess_risk,
)


def test_level_10_is_explicitly_locked_until_owner_decision():
    assert LEVEL_10_LOCKED is True
    assert LEVEL_10_CAPACITY_USD == Decimal("35000")
    risk = assess_risk(
        account_capital=Decimal("20000"),
        equity=Decimal("20000"),
        day_open_equity=Decimal("20000"),
    )
    decision = assess_promotion(
        level_index=8,
        realized_monthly_profit=Decimal("800"),
        trading_days=12,
        max_profitable_day=Decimal("100"),
        risk=risk,
        evidence_verified=True,
        funding_for_next_level=True,
    )
    assert decision.eligible is False
    assert "level10_owner_decision_required" in decision.reasons
