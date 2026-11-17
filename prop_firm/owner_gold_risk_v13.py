"""Owner-authorized *prospective* MOJ PROP Plan 1 XAUUSD risk terms.

3% per prospective order, 8% aggregate open stop-at-risk. These ceilings
NEVER override the stricter 4% intraday or 8% absolute capital drawdown
floors. Not a trading order or broker authorization. Historical v1.2
contracts retain their original 0.8% and 1.6% per-order/open-risk limits.

Immutable v1.3 terms may only apply after a separately signed and verified
buyer contract. A source-code change is NOT existing-buyer consent.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

OWNER_GOLD_CONTRACT_VERSION = "2026-11-17/v1.3"


@dataclass(frozen=True)
class ProspectiveGoldRiskTerms:
    contract_version: str = OWNER_GOLD_CONTRACT_VERSION
    exact_broker_symbol: str = "XAUUSD"
    max_per_order_risk_pct: Decimal = Decimal("3")
    max_aggregate_open_risk_pct: Decimal = Decimal("8")
    max_daily_loss_pct: Decimal = Decimal("4")
    max_total_loss_pct: Decimal = Decimal("8")
    required_broker_symbol_proof: bool = True
    requires_new_buyer_consent: bool = True
    checkout_enabled: bool = False
    real_execution_enabled: bool = False
    historically_applicable_to_v12: bool = False


OWNER_GOLD_V13 = ProspectiveGoldRiskTerms()


def risk_terms_summary() -> dict:
    """Source-only buyer-review record; never a brokerage signal or entitlement."""
    r = OWNER_GOLD_V13
    return {
        "contract_version": r.contract_version,
        "symbol": r.exact_broker_symbol,
        "risk_per_trade_percent": str(r.max_per_order_risk_pct),
        "aggregate_open_risk_percent": str(r.max_aggregate_open_risk_pct),
        "daily_loss_limit_percent": str(r.max_daily_loss_pct),
        "total_loss_limit_percent": str(r.max_total_loss_pct),
        "broker_verified_symbol_required": True,
        "explicit_signed_new_buyer_terms_required": True,
        "historical_v12_unchanged": True,
        "checkout_enabled": False,
        "real_execution_enabled": False,
        "independent_capital_broker_legal_approval_verified": False,
    }


assert (
    OWNER_GOLD_V13.exact_broker_symbol == "XAUUSD"
    and OWNER_GOLD_V13.max_per_order_risk_pct == Decimal("3")
    and OWNER_GOLD_V13.max_aggregate_open_risk_pct == Decimal("8")
    and OWNER_GOLD_V13.max_daily_loss_pct == Decimal("4")
    and OWNER_GOLD_V13.max_total_loss_pct == Decimal("8")
    and OWNER_GOLD_V13.max_per_order_risk_pct <= OWNER_GOLD_V13.max_aggregate_open_risk_pct
    and not OWNER_GOLD_V13.checkout_enabled
    and not OWNER_GOLD_V13.real_execution_enabled
)
