"""MOJ commercial release board: evidence-gated decisions, not a sales engine.

A published URL, successful test, marketing copy or database payment status
alone does not prove a commercial service is ready to accept customer funds.
All attestations must come from independently reconciled operational evidence.
"""
from __future__ import annotations

from dataclasses import dataclass

# Explicit release obligations across the owner's product/service lines.
# No account/payment/deploy operation is performed by this module.
SECTORS = {
    "mojplaywin_store": (
        "rights_verified_for_every_listed_sku", "guest_email_checkout_verified",
        "native_trx_invoice_from_private_gateway_verified",
        "independent_mainnet_payment_reconciled",
        "private_download_and_receipt_delivery_verified",
        "buyer_recovery_and_refund_path_verified",
        "live_cpanel_release_evidence_approved",
    ),
    "digital_books": (
        "content_final", "rights_cleared", "catalog_approved",
        "payment_reconciled", "delivery_verified", "recovery_verified",
    ),
    "website_kits": (
        "artifact_complete", "license_reviewed", "support_ready",
        "payment_reconciled", "delivery_verified",
    ),
    "moj_coin": (
        "client_build_and_server_gameplay_verified",
        "server_authoritative_economy_and_anti_cheat_audited",
        "game_assets_and_player_rights_verified",
        "tron_purchase_and_entitlement_reconciled",
        "player_account_recovery_and_refunds_verified",
        "token_mechanics_and_local_law_reviewed",
    ),
    "games": (
        "build_approved", "rights_cleared", "payment_reconciled",
        "entitlement_verified", "support_ready",
    ),
    "agriculture_services": (
        "service_scope_approved", "provider_capacity_verified",
        "price_approved", "billing_approved", "customer_delivery_ready",
    ),
    "ai_services": (
        "service_scope_approved", "privacy_reviewed",
        "capacity_verified", "billing_approved", "customer_support_ready",
    ),
    "education_courses": (
        "course_content_approved", "access_verified", "rights_cleared",
        "billing_approved", "refund_policy_approved",
    ),
    "research_publications": (
        "editorial_approved", "citation_and_rights_verified",
        "file_delivery_verified", "price_approved", "billing_approved",
    ),
    "moj_prop": (
        "jurisdiction_legal_approval", "broker_contract_verified",
        "funding_and_reserves_attested", "trader_kyc_aml_ready",
        "signed_broker_evidence_reconciled", "payout_and_trx_controls_live",
    ),
    "signal_subscriptions": (
        "signal_source_independently_verified", "timestamped_history_audited",
        "drawdown_and_fees_disclosed", "seller_jurisdiction_approved",
        "subscription_entitlement_verified", "terms_and_refunds_approved",
        "trx_payment_reconciled",
    ),
    "tron_gateway": (
        "merchant_entity_verified", "site_and_subsite_registry_approved",
        "tron_mainnet_receipt_proven", "independent_confirmations_verified",
        "tenant_invoice_isolation_verified", "replay_and_double_settlement_blocked",
        "refund_and_dispute_process_approved", "delivery_entitlement_reconciled",
    ),
}

# Strict owner-set priority: preserve first FIVE lines in every report.
# MOJ COIN has a dedicated release gate, distinct from all other games.
# A shared gateway is not permission to charge or imply token returns.
PRIORITY = (
    "moj_prop", "signal_subscriptions", "tron_gateway", "mojplaywin_store",
    "moj_coin", "digital_books", "website_kits", "agriculture_services",
    "ai_services", "education_courses", "research_publications", "games",
)


@dataclass(frozen=True)
class SectorAssessment:
    code: str
    outcome: str
    completed: int
    required: int
    percent_evidenced: int
    missing: tuple[str, ...]


def assess_sector(code, attestations=None):
    """Only literal True counts; a flag does not replace independent proof."""
    if code not in SECTORS:
        raise ValueError("Unknown business line")
    attestations = {} if attestations is None else attestations
    if not isinstance(attestations, dict):
        raise ValueError("Attestations must be a dict")
    required = SECTORS[code]
    missing = tuple(key for key in required if attestations.get(key) is not True)
    completed = len(required) - len(missing)
    return SectorAssessment(
        code=code,
        outcome="eligible_for_commercial_review" if not missing else "not_released",
        completed=completed,
        required=len(required),
        percent_evidenced=100 * completed // len(required),
        missing=missing,
    )


def build_board(attestations_by_sector=None):
    attestations_by_sector = {} if attestations_by_sector is None else attestations_by_sector
    if not isinstance(attestations_by_sector, dict):
        raise ValueError("Malformed sector attestations")
    decisions = tuple(
        assess_sector(code, attestations_by_sector.get(code, {}))
        for code in PRIORITY
    )
    return {
        "ready_for_live_payment": False,  # an independent operator must authorize launch
        "eligible_for_commercial_review": sum(
            x.outcome == "eligible_for_commercial_review" for x in decisions
        ),
        "sectors": [
            {
                "code": x.code,
                "outcome": x.outcome,
                "complete": x.completed,
                "required": x.required,
                "percent_evidenced": x.percent_evidenced,
                "missing": list(x.missing),
            }
            for x in decisions
        ],
        "method": "evidence_attestation_not_revenue",
        "verified_income_usd": None,  # no audited settlement source connected
        "never_auto_post_social": True,
        "excluded_instagram_profile": "Dr.mojtaba.rozegar",
    }
