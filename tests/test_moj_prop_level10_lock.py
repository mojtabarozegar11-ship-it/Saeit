"""Regression: owner-decision hold protects the 20k -> 35k Moj Prop step."""
from decimal import Decimal

from prop_firm.rules import (
    LEVELS, LEVEL_10_CAPACITY_USD, LEVEL_10_INDEX, LEVEL_10_LOCKED,
    assess_promotion, assess_risk,
)


def decision(level_index, *, verified=True, funded=True):
    capital = LEVELS[level_index]
    risk = assess_risk(
        account_capital=capital, equity=capital, day_open_equity=capital,
    )
    return assess_promotion(
        level_index=level_index,
        realized_monthly_profit=capital * Decimal("0.04"),
        trading_days=12,
        max_profitable_day=capital * Decimal("0.005"),
        risk=risk,
        evidence_verified=verified,
        funding_for_next_level=funded,
    )


def test_owner_decision_gate_is_explicit_and_exact():
    assert LEVEL_10_LOCKED is True
    assert LEVEL_10_INDEX == 9
    assert LEVEL_10_CAPACITY_USD == Decimal("35000")


def test_promotion_into_level_10_stays_blocked_even_when_all_evidence_passes():
    d = decision(8)
    assert d.current_level == Decimal("20000")
    assert d.next_level == Decimal("35000")
    assert not d.eligible
    assert "level10_owner_decision_required" in d.reasons


def test_prior_tier_progression_is_not_accidentally_disabled():
    d = decision(7)
    assert d.current_level == Decimal("10000")
    assert d.next_level == Decimal("20000")
    assert d.eligible
    assert "level10_owner_decision_required" not in d.reasons


def test_subsequent_tier_progression_is_not_accidentally_disabled():
    d = decision(9)
    assert d.current_level == Decimal("35000")
    assert d.next_level == Decimal("50000")
    assert d.eligible
    assert "level10_owner_decision_required" not in d.reasons


def test_mismatched_broker_evidence_cannot_unlock_level_10():
    d = decision(8, verified=False, funded=False)
    assert not d.eligible
    assert "level10_owner_decision_required" in d.reasons
    assert "reconciled_evidence_required" in d.reasons
    assert "next_level_funding_not_confirmed" in d.reasons
