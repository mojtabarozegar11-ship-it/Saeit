#!/usr/bin/env python3
"""Single-bot economic unit-pricing math for synthetic manual-quote previews.

This is NOT an accepted price, invoice, offer to sell, settlement or checkout.
No real customer, inventory or confidential accounting values are accepted.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
import re
from mojtaba_revenue_portfolio import CANONICAL_BOT, OFFERS

COST = re.compile(r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?$")
RATE = re.compile(r"^(?:0|0\.[0-9]{1,4})$")


def _decimal_string(value, regex, label):
    if type(value) is not str or not regex.fullmatch(value):
        raise ValueError("INVALID_" + label)
    return Decimal(value)


def estimate(request: dict) -> dict:
    expected = {"canonical_bot", "offer_id", "currency", "direct_cost",
                "overhead_cost", "processor_fee_fraction", "target_margin_fraction",
                "synthetic_example"}
    if type(request) is not dict or set(request) != expected:
        raise ValueError("INVALID_COST_MODEL_SCHEMA")
    if request["canonical_bot"] != CANONICAL_BOT:
        raise ValueError("NON_CANONICAL_BOT")
    code = request["offer_id"]
    if type(code) is not str or code not in OFFERS:
        raise ValueError("UNKNOWN_OFFER")
    domain = OFFERS[code].domain
    currency = "IRR" if domain == "zomorodmelal.ir" else "USD"
    if request["currency"] != currency:
        raise ValueError("CURRENCY_MISMATCH_NO_FX_CONVERSION")
    if request["synthetic_example"] is not True:
        raise ValueError("REAL_COST_QUOTES_REQUIRE_PRIVATE_OWNER_REVIEW")
    direct = _decimal_string(request["direct_cost"], COST, "DIRECT_COST")
    overhead = _decimal_string(request["overhead_cost"], COST, "OVERHEAD_COST")
    fee = _decimal_string(request["processor_fee_fraction"], RATE, "FEE_RATE")
    margin = _decimal_string(request["target_margin_fraction"], RATE, "MARGIN")
    if currency == "IRR" and (direct % 1 or overhead % 1):
        raise ValueError("IRR_MUST_BE_WHOLE_UNITS")
    if not (0 <= fee <= Decimal("0.25") and 0 <= margin <= Decimal("0.70")):
        raise ValueError("RATE_OUTSIDE_REVIEW_POLICY")
    if fee + margin >= 1:
        raise ValueError("INVALID_MARGIN_FEE_COMBINATION")
    cost = direct + overhead
    if cost <= 0:
        raise ValueError("NONZERO_COST_EVIDENCE_REQUIRED")
    unit = Decimal("1") if currency == "IRR" else Decimal("0.01")
    # P - fee*P - direct - overhead >= margin*P
    floor = (cost / (Decimal(1) - fee - margin)).quantize(unit, rounding=ROUND_CEILING)
    contribution = floor * (Decimal(1) - fee) - cost
    return {
        "schema": "mojtaba.bot.ai.synthetic-quote-math.v1",
        "canonical_bot": CANONICAL_BOT,
        "offer_id": code,
        "currency": currency,
        "synthetic_example": True,
        "cost_total_synthetic": str(cost),
        "gross_price_floor_synthetic": str(floor),
        "contribution_before_tax_synthetic": str(contribution),
        "assumptions": "direct+overhead only; before any taxes, refund and fixed collection fees",
        "quote_approved": False,
        "invoice_created": False,
        "payment_authorized": False,
        "revenue_verified": False,
        "production_deployed": False,
        "next_gate": "verify_actual_costs_rights_tax_contract_and_owner_quote_approval",
    }
