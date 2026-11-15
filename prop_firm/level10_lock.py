"""Owner-decision lock at Moj Prop level 10.

Level 10 is a governance boundary in the fourteen-level ladder. Reaching it
does not authorize checkout, funding, brokerage, trading, or payout. It only
becomes reviewable when the owner decision and every independent release
attestation are literally true.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from collections.abc import Mapping

from .rules import LEVELS

OWNER_DECISION_LEVEL_NUMBER = 10
OWNER_DECISION_LEVEL_INDEX = OWNER_DECISION_LEVEL_NUMBER - 1
OWNER_DECISION_LEVEL_CAPITAL_USD = Decimal("35000")

REQUIRED_LEVEL_10_ATTESTATIONS = (
    "owner_decision_recorded",
    "jurisdiction_legal_approval",
    "broker_contract_verified",
    "independent_capital_proof",
    "kyc_aml_ready",
    "payout_ledger_ready",
)

if len(LEVELS) != 14:
    raise RuntimeError("Moj Prop level ladder must remain fourteen levels")
if LEVELS[OWNER_DECISION_LEVEL_INDEX] != OWNER_DECISION_LEVEL_CAPITAL_USD:
    raise RuntimeError("Moj Prop level 10 capital anchor drifted")


@dataclass(frozen=True)
class LevelDecision:
    level_number: int
    capital_usd: Decimal
    owner_decision_required: bool
    locked: bool
    missing: tuple[str, ...]
    checkout_enabled: bool
    trading_enabled: bool
    payout_enabled: bool


def evaluate_level_lock(
    *,
    level_number: int,
    attestations: Mapping[str, object] | None = None,
) -> LevelDecision:
    """Fail closed at level 10+; never performs a financial side effect."""
    if isinstance(level_number, bool) or not isinstance(level_number, int):
        raise ValueError("level_number must be an integer")
    if not 1 <= level_number <= len(LEVELS):
        raise ValueError("level_number outside the canonical ladder")
    if attestations is None:
        attestations = {}
    if not isinstance(attestations, Mapping):
        raise ValueError("attestations must be a mapping")
    required = (
        REQUIRED_LEVEL_10_ATTESTATIONS
        if level_number >= OWNER_DECISION_LEVEL_NUMBER
        else ()
    )
    missing = tuple(
        key for key in required if attestations.get(key) is not True
    )
    return LevelDecision(
        level_number=level_number,
        capital_usd=LEVELS[level_number - 1],
        owner_decision_required=level_number >= OWNER_DECISION_LEVEL_NUMBER,
        locked=bool(missing),
        missing=missing,
        checkout_enabled=False,
        trading_enabled=False,
        payout_enabled=False,
    )


def level10_lock_summary() -> dict:
    """Safe control-tower output; all money-moving flags remain false."""
    decision = evaluate_level_lock(level_number=OWNER_DECISION_LEVEL_NUMBER)
    return {
        "decision_level_number": OWNER_DECISION_LEVEL_NUMBER,
        "decision_level_capital_usd": str(OWNER_DECISION_LEVEL_CAPITAL_USD),
        "required_attestations": list(REQUIRED_LEVEL_10_ATTESTATIONS),
        "locked_by_default": decision.locked,
        "missing_by_default": list(decision.missing),
        "checkout_enabled": decision.checkout_enabled,
        "trading_enabled": decision.trading_enabled,
        "payout_enabled": decision.payout_enabled,
    }
