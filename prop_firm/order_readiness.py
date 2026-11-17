"""MOJ PROP Plan 1 pre-order legal/contract readiness; pure, fail-closed gates.

No payment, invoice, account activation or external side effects. Evidence is
supplied by independently trusted adapters, never by unchecked buyer form data.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

SKU = "MOJ-PROP-01"
FEE_TRX = Decimal("30")
TERMS_VERSION = "2026-11-15/v1.2"
REQUIRED = (
    "entity_legal_clearance",
    "buyer_country_permitted",
    "buyer_age_verified",
    "buyer_kyc_verified",
    "buyer_consent_recorded",
    "terms_version_accepted",
    "simulated_phases_disclosed",
    "real_funding_conditional_disclosed",
    "refund_policy_disclosed",
    "social_policy_lawful",
    "advertising_disclosure_accepted",
    "privacy_notice_accepted",
    "independent_funding_proof",
    "broker_agreement_verified",
    "treasury_authorization_verified",
    "invoice_provider_authorized",
    "native_trx_settlement_adapter_verified",
    "immutable_contract_storage_ready",
    "two_phase_evidence_source_ready",
    "customer_support_ready",
)

@dataclass(frozen=True)
class OrderReadiness:
    sku: str
    fee_trx: Decimal
    contract_version: str
    eligible: bool
    missing: tuple[str, ...]
    checked_at: datetime

def assess_plan_one(evidence: dict, *, sku: str = SKU, fee_trx: Decimal = FEE_TRX,
                    contract_version: str = TERMS_VERSION) -> OrderReadiness:
    """No invoice may be issued merely because a customer claims eligibility.

    Values must be trusted booleans from verified internal services. Unknown
    evidence, invalid SKU, price or contract revision always blocks.
    """
    if type(evidence) is not dict:
        raise TypeError("Evidence must be a trusted named mapping")
    missing = tuple(key for key in REQUIRED if evidence.get(key) is not True)
    if type(sku) is not str or sku != SKU:
        missing += ("canonical_sku",)
    if type(fee_trx) is not Decimal or fee_trx != FEE_TRX:
        missing += ("native_trx_price",)
    if type(contract_version) is not str or contract_version != TERMS_VERSION:
        missing += ("versioned_contract",)
    return OrderReadiness(SKU, FEE_TRX, TERMS_VERSION, not missing, missing,
                          datetime.now(timezone.utc))

PREPURCHASE_DISCLOSURES = (
    "Both evaluation phases use DEMO/simulated accounts, not real brokerage "
    "accounts; a live LiteFinance or other broker account is NOT required to "
    "enter or complete either evaluation stage.",
    "Only AFTER passing BOTH independently verified demo stages may a buyer "
    "begin separately reviewed real broker KYC, real-account agreement and "
    "genuinely evidenced USD 100 capital-allocation procedures.",
    "Email verification, age declaration and country selection are simple "
    "interest onboarding, NOT complete legal buyer screening; any legally "
    "required pre-purchase checks still apply.",
    "The fee is 30 native TRX, not USD, IRR or a training-report purchase.",
    "The evaluation runs for 28 days from independently confirmed settlement.",
    "At least 50 verified closed positions are required across the challenge.",
    "Each phase requires at least six verified trading days.",
    "A real USD 100 account is conditional on passing and independently proven funding.",
    "The funded profit split is 70% trader and 30% company; 14 levels are conditional.",
    "No Instagram or Facebook post, upload, link, publication or promotional "
    "submission is required from a buyer, regardless of phase or outcome. "
    "The 2026-11-17 no-social-post waiver supersedes the buyer-post clause of "
    "the historical 2026-11-15/v1.2 information packet. Optional promotions "
    "need separately obtained advertising consent; owner accounts are excluded.",
    "Eligibility, KYC, geographic restrictions and fair refund terms apply.",
    "No payable invoice or challenge activation is offered until all gates pass.",
)
