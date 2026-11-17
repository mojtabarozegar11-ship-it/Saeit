"""MOJ-PROP-01 legal commerce lane pre-invoice router.

Never creates a payable invoice, transfers money, enrolls a challenge, or trades.
All evidence fields MUST originate from independently verified server-side
records; browser location and caller flags are not regulatory authorization.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import re

PRODUCT = "MOJ-PROP-01"
NATIVE_TRX_SUN = 30_000_000
COUNTRY = re.compile(r"[A-Z]{2}\Z")


class Lane(str, Enum):
    RECRUITMENT = "free_trader_recruitment"
    EVALUATION = "independent_skill_evaluation"


class PaymentMethod(str, Enum):
    NONE = "none"
    IRR = "licensed_domestic_irr_gateway"
    NATIVE_TRX = "tron_native_trx"


@dataclass(frozen=True)
class LegalEvidence:
    """Independently reviewed legal BASIS, not necessarily a new permit.

    If applicable law actually requires a governmental authorization, that
    authorization must be in the back-office evidence file. Do not invent a
    universal pre-authorization requirement absent a specific law. Neither a
    merchant self-assertion nor this dataclass constitutes a legal opinion.
    """
    merchant_owner_verified: bool
    merchant_residence_country: str
    buyer_residence_verified: bool
    buyer_residence_country: str
    customer_country_permitted: bool
    seller_cross_border_lawful_basis_reviewed: bool
    fee_based_independent_evaluation_approved: bool
    full_terms_accepted_and_verified: bool
    refunds_and_consumer_rights_cleared: bool
    authorized_receiving_account_verified: bool
    payment_method_legally_cleared: bool
    compliance_reference: str
    # Independently sourced, immutable back-office legal/identity decisions.
    # These flags cannot be attested by a visitor/browser, IP or wallet alone.
    seller_role: str = "unknown"  # natural_person_independent_service, licensed_crypto_broker, other
    seller_role_verified: bool = False
    iran_foreign_trx_settlement_lawfulness_reviewed: bool = False
    us_person_and_us_nexus_excluded: bool = False
    relevant_sanctions_screen_verified: bool = False


@dataclass(frozen=True)
class PreinvoiceDecision:
    lane: Lane
    eligible_for_next_step: bool
    proposed_method: PaymentMethod
    proposed_native_sun: int | None
    reason: str
    payable_invoice_issued: bool = False
    challenge_access_granted: bool = False
    revenue_recognized: bool = False


def decide_preinvoice(lane: Lane, method: PaymentMethod,
                      evidence: LegalEvidence | None) -> PreinvoiceDecision:
    """Route a future purchase with independent trusted evidence, never charge."""
    if type(lane) is not Lane or type(method) is not PaymentMethod:
        raise ValueError("unrecognized product lane or payment method")
    if lane is Lane.RECRUITMENT:
        if method is not PaymentMethod.NONE:
            return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                      "Recruitment applications must never collect fees")
        return PreinvoiceDecision(lane, True, PaymentMethod.NONE, None,
                                  "Unpaid recruitment application only; no hiring guarantee")

    if evidence is None or type(evidence) is not LegalEvidence:
        return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                  "Missing independently reviewed merchant/buyer legal evidence")
    countries = (evidence.merchant_residence_country, evidence.buyer_residence_country)
    if any(type(c) is not str or not COUNTRY.fullmatch(c) for c in countries):
        return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                  "Verified two-letter country of residence required")
    verified = (
        "merchant_owner_verified", "buyer_residence_verified",
        "customer_country_permitted", "fee_based_independent_evaluation_approved",
        "full_terms_accepted_and_verified", "refunds_and_consumer_rights_cleared",
        "authorized_receiving_account_verified", "payment_method_legally_cleared",
    )
    if any(type(getattr(evidence, name)) is not bool or
           getattr(evidence, name) is not True for name in verified):
        return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                  "Independent seller, buyer, service, payment or consumer proof missing")
    if (type(evidence.compliance_reference) is not str or
            len(evidence.compliance_reference.strip()) < 12):
        return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                  "Documented external compliance decision missing")
    if method is PaymentMethod.NONE:
        return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                  "No merchant collection method")
    if evidence.buyer_residence_country == "IR":
        if method is not PaymentMethod.IRR or evidence.merchant_residence_country != "IR":
            return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                      "Domestic Iranian cryptocurrency settlement prohibited")
        return PreinvoiceDecision(lane, True, PaymentMethod.IRR, None,
                                  "IRR price, merchant registration and licensed PSP still required")
    if (evidence.merchant_residence_country == "IR" and
            evidence.seller_cross_border_lawful_basis_reviewed is not True):
        return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                  "No independently documented legal basis for foreign-service merchant receipt")
    if method is not PaymentMethod.NATIVE_TRX:
        return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                  "Payment method not cleared by this foreign-buyer route")
    # Art. 38 of Iran's crypto-broker regulation prohibits licensees using
    # crypto assets as payment. Type-2 does not by itself authorize this sale.
    if (evidence.seller_role == "licensed_crypto_broker"):
        return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                  "Iran-licensed crypto broker cannot use crypto as merchant payment (art.38)")
    if (evidence.seller_role_verified is not True or
            evidence.seller_role != "natural_person_independent_service"):
        return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                  "Independent seller's actual contracting capacity not verified")
    if evidence.merchant_residence_country == "IR" and (
            evidence.iran_foreign_trx_settlement_lawfulness_reviewed is not True):
        return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                  "No reviewed foreign TRX export-service tax and FX settlement basis")
    if (evidence.us_person_and_us_nexus_excluded is not True or
            evidence.relevant_sanctions_screen_verified is not True):
        return PreinvoiceDecision(lane, False, PaymentMethod.NONE, None,
                                  "US-origin service import/nexus or counterparty sanctions screening incomplete")
    return PreinvoiceDecision(lane, True, PaymentMethod.NATIVE_TRX, NATIVE_TRX_SUN,
                              "Provisional quote only: server invoice, TRON solidified settlement and atomic ledger are separate")
