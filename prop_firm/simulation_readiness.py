"""Zero-cost readiness separation for MOJ PROP.

Internal deterministic replay can exercise the engine without a paid provider.
It is never authoritative market data and can never enable checkout or customer
admission. External sale remains fail-closed until real gates are evidenced.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterator

from .simulation_engine import MarketQuote


@dataclass(frozen=True)
class ReadinessInputs:
    mode: str = "external_sale"
    provider_verified: bool = False
    license_verified: bool = False
    reward_reserve_verified: bool = False
    legal_review_verified: bool = False
    anti_tamper_operational: bool = False


@dataclass(frozen=True)
class ReadinessDecision:
    mode: str
    internal_replay_allowed: bool
    customer_admission_allowed: bool
    checkout_enabled: bool
    blockers: tuple[str, ...]


def evaluate_readiness(inputs: ReadinessInputs) -> ReadinessDecision:
    if inputs.mode not in {"internal_replay", "external_sale"}:
        raise ValueError("mode must be internal_replay or external_sale")
    if inputs.mode == "internal_replay":
        return ReadinessDecision(
            mode=inputs.mode,
            internal_replay_allowed=True,
            customer_admission_allowed=False,
            checkout_enabled=False,
            blockers=("synthetic_replay_not_authoritative",),
        )
    checks = {
        "market_data_provider_missing": inputs.provider_verified,
        "market_data_license_missing": inputs.license_verified,
        "reward_reserve_missing": inputs.reward_reserve_verified,
        "legal_review_missing": inputs.legal_review_verified,
        "anti_tamper_operations_missing": inputs.anti_tamper_operational,
    }
    blockers = tuple(name for name, passed in checks.items() if passed is not True)
    return ReadinessDecision(
        mode=inputs.mode,
        internal_replay_allowed=False,
        customer_admission_allowed=not blockers,
        checkout_enabled=not blockers,
        blockers=blockers,
    )


class SyntheticReplayFeed:
    """Deterministic fixtures for internal QA only; never a market-data source."""

    production_authoritative = False

    def __init__(self, *, symbol="EURUSD", start_price="100",
                 spread="1", step="0.25", count=10):
        if type(count) is not int or not 1 <= count <= 86400:
            raise ValueError("count must be an integer between 1 and 86400")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required")
        self.symbol = symbol
        try:
            self.start_price = Decimal(str(start_price))
            self.spread = Decimal(str(spread))
            self.step = Decimal(str(step))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("prices must be finite decimals") from exc
        self.count = count
        if not all(value.is_finite() for value in
                   (self.start_price, self.spread, self.step)):
            raise ValueError("prices must be finite decimals")
        if self.spread <= 0:
            raise ValueError("spread must be positive")
        last_price = self.start_price + self.step * Decimal(count - 1)
        if min(self.start_price, last_price) <= self.spread / Decimal("2"):
            raise ValueError("all replay bid prices must be positive")

    def __iter__(self) -> Iterator[MarketQuote]:
        for sequence in range(1, self.count + 1):
            mid = self.start_price + self.step * Decimal(sequence - 1)
            half = self.spread / Decimal("2")
            yield MarketQuote(
                symbol=self.symbol,
                bid=mid - half,
                ask=mid + half,
                timestamp=(datetime(2026, 11, 19, tzinfo=timezone.utc)
                           + timedelta(seconds=sequence)).isoformat().replace("+00:00", "Z"),
                sequence=sequence,
            )
