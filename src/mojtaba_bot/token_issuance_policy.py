"""Deterministic, no-network token issuance policy validation for mojtaba.bot.ai.

This module does not mint, sign, transfer, deploy, or select an unapproved chain.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

MIN_SUPPLY = 100_000_000_000
MAX_SUPPLY = 10_000_000_000_000
MOJONER_SUPPLY = 24_567_856


@dataclass(frozen=True)
class TokenPlan:
    symbol: str
    chain: Optional[str]
    supply: Optional[int]
    approved: bool = False

    def validate(self) -> None:
        if self.symbol == "Mojoner":
            if self.supply != MOJONER_SUPPLY:
                raise ValueError("Mojoner supply must be exactly 24567856")
            if self.chain not in (None, "bitcoin"):
                raise ValueError("Mojoner is Bitcoin-only")
        elif self.symbol in {f"Moj{i}" for i in range(1, 51)}:
            if self.supply is not None and (
                type(self.supply) is not int
                or not MIN_SUPPLY <= self.supply <= MAX_SUPPLY
            ):
                raise ValueError("Moj1..Moj50 supply outside approved range")
            if self.chain == "bitcoin":
                raise ValueError("Moj1..Moj50 require other chains")
        else:
            raise ValueError("Unknown token symbol")
        if self.approved and (not self.chain or self.supply is None):
            raise ValueError("Approval requires a specified chain and supply")


def planned_tokens() -> tuple[TokenPlan, ...]:
    """Return all 51 planned tokens without inventing chain/supply decisions."""
    return (TokenPlan("Mojoner", "bitcoin", MOJONER_SUPPLY),) + tuple(
        TokenPlan(f"Moj{i}", None, None) for i in range(1, 51)
    )


def issuance_units(plan: TokenPlan, decimals: int) -> int:
    """Calculate exact smallest-unit issuance without floating-point rounding."""
    plan.validate()
    if plan.supply is None:
        raise ValueError("Supply awaits owner decision")
    if type(decimals) is not int or not 0 <= decimals <= 18:
        raise ValueError("Invalid precision")
    return int(Decimal(plan.supply) * (Decimal(10) ** decimals))


def can_deploy(plan: TokenPlan) -> bool:
    """An explicit approval flag is necessary but not sufficient for deployment."""
    plan.validate()
    return False  # Legal, security, funding, and case-specific release gates remain external.
