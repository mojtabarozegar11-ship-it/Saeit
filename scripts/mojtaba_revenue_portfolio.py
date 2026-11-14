#!/usr/bin/env python3
"""Source-backed, offline portfolio for ONE canonical Mojtaba.bot.ai.

This is a pure capability/quote-intake planner, NOT a second bot, scheduler,
checkout, buyer database, autonomous trading system or live revenue tracker.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType

SCHEMA = "mojtaba.bot.ai.revenue-portfolio.v1"
CANONICAL_BOT = "mojtaba.bot.ai"
INQUIRY_ONLY = "inquiry_only"
UNKNOWN = "UNKNOWN"
MAX_SYNTHETIC_COUNT = 1_000_000_000
MAX_SOURCE_CHECKS = 1_000_000

@dataclass(frozen=True)
class Offer:
    code: str
    domain: str
    path: str
    source: str
    kind: str
    proof: str
    buyer_value: str
    lawful_channel: str
    commercial_mode: str = INQUIRY_ONLY

# Hypotheses are NOT invented product listings or claims of available stock.
_OFFERS = (
    Offer("farm_economics", "zomorodmelal.ir", "/services/",
          "core/templates/core/services.html", "service", "draft_source",
          "Farm break-even and scenario analysis", "/contact/"),
    Offer("website_diagnosis", "mojplaywin.com", "/services/",
          "core/templates/mojplaywin/section.html", "service", "draft_source",
          "Website checkout incident diagnosis", "mailto:mojplaywin@gmail.com"),
    Offer("website_bounded_repair", "mojplaywin.com", "/services/",
          "core/templates/brands/mojplaywin/page.html", "service", "draft_source",
          "Bounded checkout defect remediation", "mailto:mojplaywin@gmail.com"),
    Offer("cafe_b2b", "zomorodmelal.ir", "/ghanadi/cafe-shiraz/",
          "public/ghanadi/cafe-shiraz/index.html", "supply_inquiry", "source_existing",
          "Café food supply feasibility and quotation", "/ask-master/index.php?service=1"),
    Offer("company_catalog", "zomorodmelal.ir", "/store/",
          "content/zomorod-v11/store_index.php", "catalog_inquiry", "source_existing",
          "Request a quote for an enabled company product", "/ask-master/index.php?service=1"),
    Offer("industrial_feasibility", "zomorodmelal.ir", "/industry/",
          "core/templates/core/platform_page.html", "service", "source_existing",
          "Industrial project feasibility scoping", "/contact/"),
    Offer("research_contract", "zomorodmelal.ir", "/research/",
          "core/templates/core/platform_page.html", "service", "source_existing",
          "Applied research collaboration scoping", "/contact/"),
    Offer("digital_publication", "mojplaywin.com", "/store/",
          "core/templates/mojplaywin/store.html", "digital_rights", "proposed_not_listed",
          "Rights-cleared digital book or toolkit", "manual_review_only"),
    Offer("game_license", "mojplaywin.com", "/games/",
          "core/templates/mojplaywin/section.html", "game_license", "proposed_not_listed",
          "Rights-cleared game license and delivery", "manual_review_only"),
    Offer("trading_education", "mojplaywin.com", "/services/",
          "core/templates/mojplaywin/section.html", "education_only", "proposed_not_listed",
          "Financial risk education, never an execution service", "manual_review_only"),
)
OFFERS = MappingProxyType({x.code: x for x in _OFFERS})
if len(OFFERS) != len(_OFFERS):
    raise RuntimeError("duplicate revenue offer IDs")
if any(x.domain not in {"zomorodmelal.ir", "mojplaywin.com"} for x in _OFFERS):
    raise RuntimeError("unapproved sales domain")

_ALLOWED = frozenset({"canonical_bot", "offer_id", "scope_items", "evidence_items",
                       "consent", "rights_documents", "inventory_documents",
                       "delivery_documents", "synthetic_example"})
_PII = frozenset({"name", "email", "phone", "wallet", "address", "customer",
                   "password", "api_key", "private_key", "payment_id", "card"})


def evaluate(request: dict) -> dict:
    """Accept only aggregate metadata; emit an anonymized triage disposition."""
    if type(request) is not dict:
        raise ValueError("INTAKE_MUST_BE_OBJECT")
    if set(request) & _PII or set(request) - _ALLOWED:
        raise ValueError("PERSONAL_OR_UNKNOWN_FIELDS_REJECTED")
    if request.get("canonical_bot") != CANONICAL_BOT:
        raise ValueError("NON_CANONICAL_BOT_REJECTED")
    code = request.get("offer_id")
    if type(code) is not str or code not in OFFERS:
        raise ValueError("UNKNOWN_OFFER_REJECTED")
    for field in ("scope_items", "evidence_items", "rights_documents",
                  "inventory_documents", "delivery_documents"):
        value = request.get(field)
        if type(value) is not int or not 0 <= value <= 20:
            raise ValueError("INVALID_BOUNDED_COUNT_" + field.upper())
    for field in ("consent", "synthetic_example"):
        if type(request.get(field)) is not bool:
            raise ValueError("INVALID_BOOL_" + field.upper())
    offer = OFFERS[code]
    blockers = []
    if not request["consent"]:
        blockers.append("NO_CONTACT_CONSENT")
    if request["scope_items"] == 0 or request["scope_items"] > 3:
        blockers.append("SCOPE_REQUIRES_REVIEW")
    if request["evidence_items"] == 0:
        blockers.append("EVIDENCE_MISSING")
    if offer.proof == "proposed_not_listed":
        blockers.append("PRODUCT_NOT_LIVE_OR_PROVEN")
    if offer.kind in {"digital_rights", "game_license"}:
        if request["rights_documents"] == 0:
            blockers.append("RIGHTS_NOT_DOCUMENTED")
        if request["delivery_documents"] == 0:
            blockers.append("DELIVERABLE_NOT_DOCUMENTED")
    if offer.kind in {"supply_inquiry", "catalog_inquiry"} and request["inventory_documents"] == 0:
        blockers.append("STOCK_OR_CAPACITY_NOT_DOCUMENTED")
    if offer.kind == "education_only":
        blockers.append("NO_TRADING_EXECUTION_ALLOWED")
    # Counts alone cannot authenticate the documents, prove site deployment,
    # authorize price/payment, create an order or prove delivered value.
    return {
        "schema": SCHEMA,
        "canonical_bot": CANONICAL_BOT,
        "offer_id": offer.code,
        "domain": offer.domain,
        "source_evidence": offer.proof,
        "category": offer.kind,
        "next_channel": offer.lawful_channel,
        "decision": "manual_scope_review" if not blockers else "blocked_pending_evidence",
        "blockers": sorted(set(blockers)),
        "all_document_counts_unverified": True,
        "price_approved": False,
        "invoice_authorized": False,
        "payment_verified": False,
        "order_state": INQUIRY_ONLY,
        "delivery_verified": False,
        "production_deployed": False,
        "trade_execution_authorized": False,
        "auto_send": False,
        "synthetic_example": request["synthetic_example"],
        "collected_revenue": None,
    }


_KPI_KEYS = ("views", "inquiries", "qualified", "approved_quotes",
             "paid_orders", "delivered_orders")


def synthetic_kpis(counts: dict) -> dict:
    """Compute example denominators, never convert mock counts to real receipts."""
    if type(counts) is not dict or set(counts) != set(_KPI_KEYS) | {"synthetic_example"}:
        raise ValueError("KPI_SCHEMA_INVALID")
    if counts["synthetic_example"] is not True:
        raise ValueError("REAL_METRICS_REQUIRE_INDEPENDENT_RECEIPT_LEDGER")
    if any(type(counts[x]) is not int or not 0 <= counts[x] <= MAX_SYNTHETIC_COUNT for x in _KPI_KEYS):
        raise ValueError("KPI_COUNTS_INVALID")
    if not (counts["delivered_orders"] <= counts["paid_orders"] <= counts["approved_quotes"]
            <= counts["qualified"] <= counts["inquiries"] <= counts["views"]):
        raise ValueError("KPI_FUNNEL_ORDER_INVALID")
    def ratio(a, b):
        return str((Decimal(a) / Decimal(b)).quantize(Decimal("0.0001"))) if b else None
    return {
        "schema": "mojtaba.bot.ai.synthetic-kpi.v1",
        "canonical_bot": CANONICAL_BOT,
        "synthetic_example": True,
        "inquiry_rate": ratio(counts["inquiries"], counts["views"]),
        "qualification_rate": ratio(counts["qualified"], counts["inquiries"]),
        "quote_to_paid_rate": ratio(counts["paid_orders"], counts["approved_quotes"]),
        "paid_to_delivery_rate": ratio(counts["delivered_orders"], counts["paid_orders"]),
        "actual_revenue": None,
        "source_of_truth": "synthetic_only_no_settlement_evidence",
    }


def no_revenue_claims_from_source(source_check_passes: int, *, receipts_verified: bool = False) -> dict:
    """A passing CI is not a deposit, payment confirmation or entitlement."""
    if (type(source_check_passes) is not int
            or not 0 <= source_check_passes <= MAX_SOURCE_CHECKS):
        raise ValueError("INVALID_SOURCE_CHECK_COUNT")
    if type(receipts_verified) is not bool:
        raise ValueError("INVALID_RECEIPT_FLAG")
    return {"canonical_bot": CANONICAL_BOT, "source_checks_passed": source_check_passes,
            "receipt_attestation_from_source_only": False,
            "requested_receipt_flag_untrusted": receipts_verified,
            "verified_collected_revenue": None,
            "verified_paid_orders": None, "deployed": False}


def validate_manual_money_range(value: str) -> Decimal:
    """Parsing helper only; never a quote, accepted pricing or payment."""
    if type(value) is not str or not value or len(value) > 18:
        raise ValueError("MONEY_INPUT_INVALID")
    if not value.replace(".", "", 1).isdigit() or value.count(".") > 1:
        raise ValueError("MONEY_INPUT_INVALID")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("MONEY_INPUT_INVALID") from exc
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        raise ValueError("MONEY_INPUT_INVALID")
    return amount
