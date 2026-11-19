"""Public-offer contract for the zero-cost synthetic MOJ PROP product.

This is a commercial offer definition, not a payment side effect. Admission is
fail-closed until the reward reserve, disclosures, recipient configuration and
explicit activation approval are evidenced.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


D = Decimal


def _money(value, name):
    try:
        result = D(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite amount") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result.quantize(D("0.01"))


@dataclass(frozen=True)
class SyntheticSaleOffer:
    sku: str = "MOJ-PROP-SIM-01"
    entry_fee_trx: int = 30
    retry_fee_trx: int = 18
    retry_discount_pct: int = 40
    simulated_balance_usd: int = 1000
    challenge_days: int = 60
    data_mode: str = "synthetic_replay"
    virtual_principal_withdrawable: bool = False
    customer_deposit_required: bool = False
    performance_rewards_real: bool = True

    def __post_init__(self):
        if self.entry_fee_trx <= 0 or self.retry_fee_trx <= 0:
            raise ValueError("TRX prices must be positive")
        if self.retry_fee_trx >= self.entry_fee_trx:
            raise ValueError("retry price must be lower than entry price")
        if self.data_mode != "synthetic_replay":
            raise ValueError("synthetic offer requires synthetic_replay mode")


@dataclass(frozen=True)
class SyntheticSaleDecision:
    offer: SyntheticSaleOffer
    eligible_for_activation: bool
    checkout_enabled: bool
    reward_reserve_available_usd: Decimal
    maximum_reward_commitment_usd: Decimal
    blockers: tuple[str, ...]


def assess_synthetic_sale(
    *,
    reward_reserve_available_usd,
    maximum_reward_commitment_usd,
    terms_disclosed,
    reserve_policy_accepted,
    recipient_configured,
    activation_approved,
    offer=None,
):
    offer = offer or SyntheticSaleOffer()
    reserve = _money(reward_reserve_available_usd, "reward_reserve_available_usd")
    maximum = _money(maximum_reward_commitment_usd,
                     "maximum_reward_commitment_usd")
    checks = {
        "synthetic_mode_disclosure_missing": terms_disclosed is True,
        "reward_reserve_policy_missing": reserve_policy_accepted is True,
        "recipient_not_configured": recipient_configured is True,
        "public_activation_not_approved": activation_approved is True,
        "reward_reserve_shortfall": reserve >= maximum,
    }
    blockers = tuple(name for name, passed in checks.items() if not passed)
    eligible = not blockers
    return SyntheticSaleDecision(
        offer=offer,
        eligible_for_activation=eligible,
        checkout_enabled=eligible,
        reward_reserve_available_usd=reserve,
        maximum_reward_commitment_usd=maximum,
        blockers=blockers,
    )
