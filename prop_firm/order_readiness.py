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

    The historical 20-gate 'buyer_kyc_verified' means lawful BUYER PURCHASE
    screening for the simulated evaluation (as independently determined for
    the relevant jurisdiction), NOT mandatory opening or KYC of a REAL broker
    account before the two demo stages. Broker KYC has its own independent
    proof gate only in the post-two-pass funded-account transition. This
    function cannot decide whether a country's purchase laws require KYC;
    no marketing form, email OTP, self-reported country or 'not applicable'
    browser claim may flip this gate to True.
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
    "Only AFTER passing BOTH independently verified DEMO stages may a trader "
    "be considered for broker-authorized order execution on the EXISTING "
    "LiteFinance real account under its lawful holder's control. NO buyer-owned "
    "real brokerage account is promised or needed.",
    "The nominal initial USD 100 is an independently funded, auditable "
    "trading/risk allocation in that owner-controlled real account, NOT "
    "money deposited to the buyer's own account or wallet.",
    "Access requires explicit broker approval for individual order authority "
    "and attribution; the buyer receives NO account passwords, 2FA, "
    "broker withdrawal rights or trading principal.",
    "After the contractually defined period, only independently reconciled "
    "attributable REALIZED net profit after valid prior losses is split "
    "70% trader and 30% organizer. Actual disclosed cryptocurrency transfer "
    "fees are deducted once from the trader share.",
    "Broker withdrawal must go through the broker-authorized holder's "
    "original funding/withdrawal channel. A possible customer crypto profit "
    "payment is a SEPARATE lawful business-treasury transfer to the verified "
    "beneficiary wallet, subject to KYC, sanctions, local rules and actual funds.",
    "Email verification, age declaration and country selection are simple "
    "interest onboarding, NOT complete legal buyer screening; any legally "
    "required pre-purchase checks still apply.",
    "The fee is 30 native TRX, not USD, IRR or a training-report purchase.",
    "The evaluation runs for 28 days from independently confirmed settlement.",
    "At least 50 verified closed positions are required across the challenge.",
    "Each phase requires at least six verified trading days.",
    "No new REAL account is opened for the buyer; funding and risk limits "
    "for the existing broker account must be independently verified.",
    "The funded profit split is 70% trader and 30% company; 14 levels are conditional.",
    "No Instagram or Facebook post, upload, link, publication or promotional "
    "submission is required from a buyer, regardless of phase or outcome. "
    "The 2026-11-17 no-social-post waiver supersedes the buyer-post clause of "
    "the historical 2026-11-15/v1.2 information packet. Optional promotions "
    "need separately obtained advertising consent; owner accounts are excluded.",
    "Eligibility, KYC, geographic restrictions and fair refund terms apply.",
    "No payable invoice or challenge activation is offered until all gates pass.",
)
