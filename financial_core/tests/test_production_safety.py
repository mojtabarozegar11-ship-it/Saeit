from decimal import Decimal

from financial_core.assets import Asset, AssetRegistry
from financial_core.compliance import ComplianceEngine, ComplianceProfile
from financial_core.custody import DisabledCustodyConnector
from financial_core.limits import WithdrawalLimits
from financial_core.reconciliation import Reconciler, ReserveSnapshot
from financial_core.withdrawals import WithdrawalGate, WithdrawalRequest, WithdrawalState


def _request(amount='10'):
    return WithdrawalRequest('w1', 'u1', 'USDT', 'tron', Decimal(amount), 'destination')


def test_withdrawal_requires_owner_approval():
    registry = AssetRegistry([Asset('USDT', 'tron', 6, 20, True, True, Decimal('1'))])
    compliance = ComplianceEngine(lambda _: ComplianceProfile(True, True, True, True))
    gate = WithdrawalGate(registry, compliance, WithdrawalLimits(Decimal('100')))
    assert gate.review(_request()).state == WithdrawalState.REVIEW
    assert gate.review(_request(), owner_approved=True).state == WithdrawalState.APPROVED


def test_compliance_fails_closed():
    registry = AssetRegistry([Asset('USDT', 'tron', 6, 20, True, True, Decimal('1'))])
    gate = WithdrawalGate(registry, ComplianceEngine(lambda _: None), WithdrawalLimits(Decimal('100')))
    assert gate.review(_request(), owner_approved=True).state == WithdrawalState.REJECTED


def test_reserve_reconciliation_detects_shortfall():
    ok, failures = Reconciler().verify([ReserveSnapshot('USDT', Decimal('100'), Decimal('99'))])
    assert not ok and failures[0].surplus == Decimal('-1')


def test_custody_is_disabled_until_provider_configured():
    connector = DisabledCustodyConnector()
    try:
        connector.broadcast_approved_withdrawal(_request(), 'approval')
        assert False
    except RuntimeError as exc:
        assert str(exc) == 'custody-not-configured'
