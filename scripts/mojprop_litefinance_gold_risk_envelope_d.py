"""D-only source feasibility screen for MOJ-PROP-01 LiteFinance XAUUSD.

Official public LiteFinance contract pages quote a 100 troy-oz lot and 0.01
minimum lot, i.e. 1 oz minimum exposure. Those are NOT an authenticated
account-specific broker quote, signed commercial agreement, live prices or
permission to trade. Strictly no network, orders, payouts or side effects.

The conservative all-in adverse-price-distance model explicitly INCLUDES
spread, slippage allowance, and round-trip commissions/fees. No fee inferred.
It never enables a real trade or production checkout.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re

D = Decimal
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_QUOTE_AGE = timedelta(minutes=5)


class BrokerRiskUnproven(ValueError):
    """Preflight cannot establish account-specific minimum-lot feasibility."""


def _decimal(v, *, positive=True):
    if isinstance(v, (float, bool)):
        raise BrokerRiskUnproven("floats and booleans are inadmissible")
    if not isinstance(v, (str, int, Decimal)):
        raise BrokerRiskUnproven("exact decimal evidence required")
    try:
        x = D(str(v))
    except (ValueError, InvalidOperation):
        raise BrokerRiskUnproven("malformed decimal evidence") from None
    if not x.is_finite() or x < 0 or (positive and x == 0) or x > D("1000000000"):
        raise BrokerRiskUnproven("out of range decimal")
    return x


@dataclass(frozen=True)
class GoldLotRiskSnapshot:
    symbol: str
    quote_currency: str
    account_currency: str
    broker_account_type: str
    quote_timestamp_utc: str
    source_commit: str
    account_capital_usd: str
    account_available_margin_usd: str
    minimum_volume_lots: str
    lot_step_lots: str
    contract_oz_per_lot: str
    broker_min_stop_distance_usd_per_oz: str
    quoted_spread_usd_per_oz: str
    anticipated_slippage_usd_per_oz: str
    roundtrip_commission_usd: str
    extra_fee_reserve_usd: str
    margin_for_minimum_lot_usd: str
    authoritative_account_snapshot: bool
    broker_min_lot_for_account_verified: bool

    def assess(self, *, expected_source_commit: str,
               now: datetime, max_trade_risk_usd: str = "0.80") -> dict:
        if self.symbol != "XAUUSD" or self.quote_currency != "USD" or self.account_currency != "USD":
            raise BrokerRiskUnproven("unsupported instrument or currency")
        if self.broker_account_type not in ("ECN", "CLASSIC"):
            raise BrokerRiskUnproven("unverified account type")
        if not (type(expected_source_commit) is str and
                SHA40.fullmatch(expected_source_commit) and
                self.source_commit == expected_source_commit):
            raise BrokerRiskUnproven("source and quote commit mismatch")
        if self.authoritative_account_snapshot is not True or self.broker_min_lot_for_account_verified is not True:
            raise BrokerRiskUnproven("live account-specific broker evidence absent")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise BrokerRiskUnproven("trusted timezone-aware time required")
        try:
            quoted = datetime.fromisoformat(self.quote_timestamp_utc.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise BrokerRiskUnproven("invalid quote timestamp") from exc
        if quoted.tzinfo is None or quoted.utcoffset() is None:
            raise BrokerRiskUnproven("timezone-aware broker quote required")
        age = now.astimezone(timezone.utc) - quoted.astimezone(timezone.utc)
        if not timedelta(0) <= age <= MAX_QUOTE_AGE:
            raise BrokerRiskUnproven("broker quote stale or future")
        capital = _decimal(self.account_capital_usd)
        if capital != D("100"):
            raise BrokerRiskUnproven("MOJ-PROP-01 phase-3 real account capital must be $100")
        max_risk = _decimal(max_trade_risk_usd)
        if max_risk > D("0.80"):
            raise BrokerRiskUnproven("cannot exceed $0.80 risk at $100")
        available_margin = _decimal(self.account_available_margin_usd)
        lot = _decimal(self.minimum_volume_lots)
        step = _decimal(self.lot_step_lots)
        contract = _decimal(self.contract_oz_per_lot)
        if lot < step or lot % step != 0:
            raise BrokerRiskUnproven("minimum volume violates account lot increment")
        # This screen is explicitly about the public LiteFinance XAUUSD
        # minimum lot. Changed account specifications require new approval.
        if lot != D("0.01") or contract != D("100") or step != D("0.01"):
            raise BrokerRiskUnproven("LiteFinance gold source baseline mismatch")
        stop = _decimal(self.broker_min_stop_distance_usd_per_oz, positive=False)
        spread = _decimal(self.quoted_spread_usd_per_oz, positive=False)
        slippage = _decimal(self.anticipated_slippage_usd_per_oz, positive=False)
        commission = _decimal(self.roundtrip_commission_usd, positive=False)
        fee_reserve = _decimal(self.extra_fee_reserve_usd, positive=False)
        margin = _decimal(self.margin_for_minimum_lot_usd)
        if margin > available_margin:
            raise BrokerRiskUnproven("minimum lot margin exceeds available free margin")
        # Loss from a minimum adverse stop gap + whole spread + possible
        # execution slippage, with fees added explicitly. Conservative.
        minimum_loss = lot * contract * (stop + spread + slippage) + commission + fee_reserve
        if minimum_loss <= 0 or minimum_loss > max_risk:
            raise BrokerRiskUnproven("0.01-lot total stop cost exceeds $0.80 envelope")
        return {
            "product": "MOJ-PROP-01",
            "instrument": "XAUUSD",
            "minimum_volume_lots": str(lot),
            "minimum_exposure_ounces": str(lot * contract),
            "minimum_risk_at_stop_usd": str(minimum_loss),
            "risk_cap_usd": str(max_risk),
            "minimum_lot_math_possible": True,
            "broker_quote_authenticated_by_this_process": False,
            "legal_prop_authorization_verified": False,
            "signed_broker_prop_agreement_verified": False,
            "independent_capital_and_buffer_verified": False,
            "actual_funded_account_ready": False,
            "order_execution_authorized": False,
            "deployment_authorized": False,
            "payment_authorized": False,
        }
