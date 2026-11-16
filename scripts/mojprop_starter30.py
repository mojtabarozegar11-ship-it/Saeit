"""Moj Prop Starter 30: deterministic EDUCATIONAL journal scoring.

The 30 TRX label is an indicative, one-time future invoice amount. This module
does not invoice, debit wallets, enrol users, place trades or issue funded accounts.
A 100 USD reference balance here is simulated bookkeeping only.
"""
from __future__ import annotations

import re
from decimal import Decimal

PRODUCT_ID = "MOJPROP-STARTER30"
PRICE_TRX = 30
PRICE_SUN = 30_000_000
REFERENCE_BALANCE_USD = Decimal("100.00")
SESSIONS_REQUIRED = 10
MAX_DAILY_LOSS_PERCENT = Decimal("3.00")
MAX_PEAK_DRAWDOWN_PERCENT = Decimal("6.00")
_AMOUNT = re.compile(r"(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,2})?\Z")


class InvalidJournal(ValueError):
    """Invalid log; do not produce an apparent student completion certificate."""


def public_product() -> dict:
    """Informational offer only. Intentionally no public wallet or checkout."""
    return {
        "code": PRODUCT_ID,
        "title": "Moj Prop Starter 30 — educational simulator assessment",
        "indicative_price_trx": PRICE_TRX,
        "price_sun": PRICE_SUN,
        "simulation_reference_usd": "100.00",
        "sessions_required": SESSIONS_REQUIRED,
        "daily_loss_limit_percent": str(MAX_DAILY_LOSS_PERCENT),
        "overall_drawdown_limit_percent": str(MAX_PEAK_DRAWDOWN_PERCENT),
        "deliverables": [
            "Ten-session trading journal review",
            "Risk-rule adherence scorecard",
            "Individual written learning recommendations",
        ],
        "funded_account": False,
        "withdrawals": False,
        "profit_sharing": False,
        "broker_account": False,
        "investment_service": False,
        "automatic_checkout": False,
        "charge_approved": False,
        "operator": "mojtaba.bot.ai",
        "availability": "request_only_until_legal_payment_and_delivery_proof",
    }


def _money(value: object) -> Decimal:
    # Reject floats (rounding ambiguity), negatives, exponential notation,
    # NaN, Infinity and extraneous controls.
    if type(value) is not str or _AMOUNT.fullmatch(value) is None:
        raise InvalidJournal("closing_equity_usd must be a decimal string (0..999999.99)")
    amount = Decimal(value)
    if not amount.is_finite():
        raise InvalidJournal("nonfinite closing equity")
    return amount


def assess_journal(sessions: object) -> dict:
    """Score up to ten consecutive, self-reported simulation journal entries.

    This is educational feedback, NEVER proof of a real trade, eligibility for
    funding, brokerage performance or a paid settlement. Do not upload private
    broker credentials or personal financial records.
    """
    if type(sessions) is not list or not 1 <= len(sessions) <= SESSIONS_REQUIRED:
        raise InvalidJournal("require 1 through 10 consecutive sessions")
    previous = REFERENCE_BALANCE_USD
    peak = REFERENCE_BALANCE_USD
    breaches: list[dict] = []
    documented = 0
    for index, row in enumerate(sessions, 1):
        if type(row) is not dict or set(row) != {
            "session", "closing_equity_usd", "risk_plan_recorded", "reflection_recorded"
        }:
            raise InvalidJournal("invalid or ambiguous journal fields")
        if type(row["session"]) is not int or row["session"] != index:
            raise InvalidJournal("session identifiers must be consecutive integers")
        if type(row["risk_plan_recorded"]) is not bool or type(row["reflection_recorded"]) is not bool:
            raise InvalidJournal("recorded flags must be explicit booleans")
        equity = _money(row["closing_equity_usd"])
        if row["risk_plan_recorded"] and row["reflection_recorded"]:
            documented += 1
        # When a prior simulated session closed at zero, there is no
        # positive opening denominator for a percentage daily-loss rate.
        # Zero-to-zero or zero-to-positive is NOT a new 100% daily loss.
        # The original catastrophic loss remains correctly recorded in
        # that earlier session and the running peak drawdown remains breached.
        daily_loss = (
            max(Decimal("0"), (previous - equity) * Decimal("100") / previous)
            if previous > 0 else Decimal("0")
        )
        overall_dd = max(Decimal("0"), (peak - equity) * Decimal("100") / peak)
        if daily_loss > MAX_DAILY_LOSS_PERCENT:
            breaches.append({"session": index, "rule": "daily_loss"})
        if overall_dd > MAX_PEAK_DRAWDOWN_PERCENT:
            breaches.append({"session": index, "rule": "overall_peak_drawdown"})
        if not row["risk_plan_recorded"]:
            breaches.append({"session": index, "rule": "risk_plan_missing"})
        if not row["reflection_recorded"]:
            breaches.append({"session": index, "rule": "reflection_missing"})
        peak = max(peak, equity)
        previous = equity
    if len(sessions) < SESSIONS_REQUIRED:
        status = "incomplete_training"
    elif breaches:
        status = "completed_needs_coaching"
    else:
        status = "completed_educational_review"
    return {
        "schema": "mojprop.starter30.education.v1",
        "product_id": PRODUCT_ID,
        "status": status,
        "sessions_recorded": len(sessions),
        "sessions_required": SESSIONS_REQUIRED,
        "documented_sessions": documented,
        "closing_simulated_equity_usd": str(previous.quantize(Decimal("0.01"))),
        "rule_breaches": breaches,
        "funded_account_earned": False,
        "payment_recorded": False,
        "trades_executed": False,
        "not_financial_advice": True,
    }
