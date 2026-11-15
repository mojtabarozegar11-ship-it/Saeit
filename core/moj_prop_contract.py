"""Fail-closed Moj Prop challenge and funding contract.

This module defines commercial and risk invariants only. It does not connect
to a broker, accept a payment, move TRX, place a trade, or activate a funded
account. Live activation requires the explicit release gates represented by
the enrollment record.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import re
from typing import Optional


class PropContractError(ValueError):
    """Raised when a prop challenge contract cannot be proven safely."""


class ChallengeState(str, Enum):
    CREATED = "created"
    PAYMENT_PENDING = "payment_pending"
    KYC_PENDING = "kyc_pending"
    ELIGIBLE = "eligible"
    ACTIVE = "active"
    PASSED = "passed"
    FUNDED = "funded"
    FAILED = "failed"
    SUSPENDED = "suspended"


class ChallengeDecision(str, Enum):
    ACTIVE = "active"
    PASSED = "passed"
    FAILED = "failed"


TIER_LADDER_USD = (
    Decimal("100"),
    Decimal("200"),
    Decimal("400"),
    Decimal("800"),
    Decimal("1500"),
    Decimal("3000"),
    Decimal("5000"),
    Decimal("10000"),
    Decimal("20000"),
)
_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_TX = re.compile(r"^[A-Za-z0-9:_-]{8,256}$")


def _decimal(value: object, field: str, *, positive: bool = False, nonnegative: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise PropContractError(f"{field}_must_be_decimal_like")
    try:
        amount = Decimal(str(value))
    except Exception as exc:  # Decimal may raise several InvalidOperation variants.
        raise PropContractError(f"{field}_invalid") from exc
    if not amount.is_finite():
        raise PropContractError(f"{field}_must_be_finite")
    if positive and amount <= Decimal("0"):
        raise PropContractError(f"{field}_must_be_positive")
    if nonnegative and amount < Decimal("0"):
        raise PropContractError(f"{field}_must_be_nonnegative")
    return amount


def _slug(value: object, field: str) -> str:
    if not isinstance(value, str) or not _SLUG.fullmatch(value):
        raise PropContractError(f"{field}_invalid")
    return value


@dataclass(frozen=True)
class PropRules:
    """Owner-configurable challenge policy with the known 30 TRX / 100 USD base."""

    plan_id: str = "moj-prop-base"
    challenge_fee_trx: Decimal = Decimal("30")
    funded_account_usd: Decimal = Decimal("100")
    profit_target_pct: Decimal = Decimal("10")
    daily_loss_limit_pct: Decimal = Decimal("5")
    max_drawdown_pct: Decimal = Decimal("10")
    minimum_trading_days: int = 5
    maximum_trading_days: int = 30
    max_open_positions: int = 3
    max_risk_per_trade_pct: Decimal = Decimal("1")


def validate_rules(rules: PropRules) -> None:
    _slug(rules.plan_id, "plan_id")
    fee = _decimal(rules.challenge_fee_trx, "challenge_fee_trx", positive=True)
    if fee != Decimal("30"):
        raise PropContractError("challenge_fee_must_be_30_trx")
    account = _decimal(rules.funded_account_usd, "funded_account_usd", positive=True)
    if account not in TIER_LADDER_USD:
        raise PropContractError("funded_account_not_in_tier_ladder")
    target = _decimal(rules.profit_target_pct, "profit_target_pct", positive=True)
    daily = _decimal(rules.daily_loss_limit_pct, "daily_loss_limit_pct", positive=True)
    drawdown = _decimal(rules.max_drawdown_pct, "max_drawdown_pct", positive=True)
    if daily >= drawdown:
        raise PropContractError("daily_loss_must_be_below_max_drawdown")
    if target >= Decimal("100"):
        raise PropContractError("profit_target_unreasonable")
    if not isinstance(rules.minimum_trading_days, int) or isinstance(rules.minimum_trading_days, bool):
        raise PropContractError("minimum_trading_days_invalid")
    if not isinstance(rules.maximum_trading_days, int) or isinstance(rules.maximum_trading_days, bool):
        raise PropContractError("maximum_trading_days_invalid")
    if rules.minimum_trading_days < 1 or rules.maximum_trading_days < rules.minimum_trading_days:
        raise PropContractError("trading_day_window_invalid")
    if not isinstance(rules.max_open_positions, int) or isinstance(rules.max_open_positions, bool):
        raise PropContractError("max_open_positions_invalid")
    if rules.max_open_positions < 1:
        raise PropContractError("max_open_positions_invalid")
    risk = _decimal(rules.max_risk_per_trade_pct, "max_risk_per_trade_pct", positive=True)
    if risk > daily:
        raise PropContractError("risk_per_trade_exceeds_daily_loss")
    # Keep the named values consumed above explicit for reviewers and linters.
    _ = (account, target, daily, drawdown, risk)


def next_funded_tier(current_account_usd: object) -> Optional[Decimal]:
    current = _decimal(current_account_usd, "current_account_usd", positive=True)
    try:
        index = TIER_LADDER_USD.index(current)
    except ValueError as exc:
        raise PropContractError("current_account_not_in_tier_ladder") from exc
    if index + 1 >= len(TIER_LADDER_USD):
        return None
    return TIER_LADDER_USD[index + 1]


@dataclass(frozen=True)
class PropEnrollment:
    challenge_id: str
    customer_id: str
    rules: PropRules = PropRules()
    state: ChallengeState = ChallengeState.CREATED
    fee_payment_verified: bool = False
    kyc_approved: bool = False
    legal_reviewed: bool = False
    owner_approved: bool = False
    rights_cleared: bool = False
    public_wallet_published: bool = False
    automatic_payment_enabled: bool = False
    transaction_id: str = ""


def validate_enrollment(enrollment: PropEnrollment) -> None:
    _slug(enrollment.challenge_id, "challenge_id")
    _slug(enrollment.customer_id, "customer_id")
    validate_rules(enrollment.rules)
    for field in (
        "fee_payment_verified",
        "kyc_approved",
        "legal_reviewed",
        "owner_approved",
        "rights_cleared",
        "public_wallet_published",
        "automatic_payment_enabled",
    ):
        if type(getattr(enrollment, field)) is not bool:
            raise PropContractError(f"{field}_must_be_boolean")
    if enrollment.public_wallet_published:
        raise PropContractError("public_wallet_prohibited")
    if enrollment.automatic_payment_enabled:
        raise PropContractError("automatic_payment_disabled")
    if enrollment.fee_payment_verified:
        if not enrollment.transaction_id or not _TX.fullmatch(enrollment.transaction_id):
            raise PropContractError("verified_fee_requires_transaction_id")
    if enrollment.state in (ChallengeState.ELIGIBLE, ChallengeState.ACTIVE, ChallengeState.PASSED, ChallengeState.FUNDED):
        required = (
            enrollment.fee_payment_verified,
            enrollment.kyc_approved,
            enrollment.legal_reviewed,
            enrollment.owner_approved,
            enrollment.rights_cleared,
        )
        if not all(required):
            raise PropContractError("release_gates_incomplete")


def activate_enrollment(enrollment: PropEnrollment) -> PropEnrollment:
    validate_enrollment(enrollment)
    if enrollment.state is not ChallengeState.ELIGIBLE:
        raise PropContractError("enrollment_not_eligible")
    return PropEnrollment(
        challenge_id=enrollment.challenge_id,
        customer_id=enrollment.customer_id,
        rules=enrollment.rules,
        state=ChallengeState.ACTIVE,
        fee_payment_verified=enrollment.fee_payment_verified,
        kyc_approved=enrollment.kyc_approved,
        legal_reviewed=enrollment.legal_reviewed,
        owner_approved=enrollment.owner_approved,
        rights_cleared=enrollment.rights_cleared,
        transaction_id=enrollment.transaction_id,
    )


@dataclass(frozen=True)
class ChallengeSnapshot:
    initial_equity_usd: Decimal
    start_of_day_equity_usd: Decimal
    current_equity_usd: Decimal
    peak_equity_usd: Decimal
    trading_days: int


@dataclass(frozen=True)
class ChallengeResult:
    decision: ChallengeDecision
    reason: str
    profit_pct: Decimal
    daily_loss_pct: Decimal
    drawdown_pct: Decimal
    funded_account_usd: Decimal


def evaluate_challenge(rules: PropRules, snapshot: ChallengeSnapshot) -> ChallengeResult:
    validate_rules(rules)
    initial = _decimal(snapshot.initial_equity_usd, "initial_equity_usd", positive=True)
    start_day = _decimal(snapshot.start_of_day_equity_usd, "start_of_day_equity_usd", positive=True)
    current = _decimal(snapshot.current_equity_usd, "current_equity_usd", nonnegative=True)
    peak = _decimal(snapshot.peak_equity_usd, "peak_equity_usd", positive=True)
    if peak < current or peak < initial:
        raise PropContractError("peak_equity_inconsistent")
    if not isinstance(snapshot.trading_days, int) or isinstance(snapshot.trading_days, bool) or snapshot.trading_days < 0:
        raise PropContractError("trading_days_invalid")
    profit_pct = ((current - initial) / initial * Decimal("100")).quantize(Decimal("0.01"))
    daily_loss_pct = max(Decimal("0"), ((start_day - current) / start_day * Decimal("100"))).quantize(Decimal("0.01"))
    drawdown_pct = max(Decimal("0"), ((peak - current) / peak * Decimal("100"))).quantize(Decimal("0.01"))
    if current == Decimal("0"):
        return ChallengeResult(ChallengeDecision.FAILED, "equity_zero", profit_pct, daily_loss_pct, drawdown_pct, rules.funded_account_usd)
    if daily_loss_pct >= rules.daily_loss_limit_pct:
        return ChallengeResult(ChallengeDecision.FAILED, "daily_loss_limit_breached", profit_pct, daily_loss_pct, drawdown_pct, rules.funded_account_usd)
    if drawdown_pct >= rules.max_drawdown_pct:
        return ChallengeResult(ChallengeDecision.FAILED, "max_drawdown_breached", profit_pct, daily_loss_pct, drawdown_pct, rules.funded_account_usd)
    if snapshot.trading_days > rules.maximum_trading_days:
        return ChallengeResult(ChallengeDecision.FAILED, "maximum_trading_days_exceeded", profit_pct, daily_loss_pct, drawdown_pct, rules.funded_account_usd)
    if profit_pct >= rules.profit_target_pct and snapshot.trading_days >= rules.minimum_trading_days:
        return ChallengeResult(ChallengeDecision.PASSED, "profit_target_reached", profit_pct, daily_loss_pct, drawdown_pct, rules.funded_account_usd)
    return ChallengeResult(ChallengeDecision.ACTIVE, "challenge_in_progress", profit_pct, daily_loss_pct, drawdown_pct, rules.funded_account_usd)


def advance_state(current: ChallengeState, target: ChallengeState) -> ChallengeState:
    allowed = {
        ChallengeState.CREATED: {ChallengeState.PAYMENT_PENDING, ChallengeState.SUSPENDED},
        ChallengeState.PAYMENT_PENDING: {ChallengeState.KYC_PENDING, ChallengeState.SUSPENDED},
        ChallengeState.KYC_PENDING: {ChallengeState.ELIGIBLE, ChallengeState.SUSPENDED},
        ChallengeState.ELIGIBLE: {ChallengeState.ACTIVE, ChallengeState.SUSPENDED},
        ChallengeState.ACTIVE: {ChallengeState.PASSED, ChallengeState.FAILED, ChallengeState.SUSPENDED},
        ChallengeState.PASSED: {ChallengeState.FUNDED, ChallengeState.SUSPENDED},
        ChallengeState.FUNDED: {ChallengeState.SUSPENDED},
        ChallengeState.FAILED: set(),
        ChallengeState.SUSPENDED: set(),
    }
    if target not in allowed.get(current, set()):
        raise PropContractError("invalid_challenge_transition")
    return target
