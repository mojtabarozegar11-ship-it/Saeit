from decimal import Decimal

from core.revenue_lifecycle import RevenueState, SettlementEvidence, may_mark_verified, next_state


def test_revenue_states_are_strictly_sequential():
    assert next_state(RevenueState.OPPORTUNITY) == RevenueState.QUALIFIED
    assert next_state(RevenueState.PAID) == RevenueState.SETTLED
    assert next_state(RevenueState.SETTLED) == RevenueState.VERIFIED
    assert next_state(RevenueState.VERIFIED) is None


def test_paid_or_unreconciled_is_not_verified_revenue():
    assert not may_mark_verified(RevenueState.PAID, None)
    assert not may_mark_verified(RevenueState.SETTLED, None)


def test_reconciled_settlement_can_be_verified():
    evidence = SettlementEvidence(
        provider="test-provider",
        external_reference="txn-1",
        amount=Decimal("100.00"),
        currency="USD",
        settled_at="2026-09-30T00:00:00Z",
        reconciliation_reference="rec-1",
    )
    assert may_mark_verified(RevenueState.SETTLED, evidence)
