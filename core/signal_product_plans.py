"""Proposed, unpublished 3-tier subscription packages for 17 signal mirrors.

Prices are planning assumptions, NOT active catalog prices or recurring charges.
An entitlement belongs to one canonical SKU, never billed again by mirrors.
No order placement, recurring billing, live alerts, or trade execution here.
"""
from dataclasses import dataclass
from decimal import Decimal

from .signal_commercial_catalog import CANONICAL_AGENT, SIGNAL_BRANDS
from .tron_tenant_policy import (TenantDecision, canonical_host,
                                 DEFAULT_ALLOWED_ANCHORS)


@dataclass(frozen=True)
class SignalPlan:
    sku: str
    monthly_usd_proposed: Decimal
    market_limit: int
    includes_risk_notes: bool
    outcome_guaranteed: bool = False
    auto_billing_enabled: bool = False
    paid_access_enabled: bool = False


SIGNAL_PLANS = (
    SignalPlan("moj-signals-standard", Decimal("12.00"), 1, True),
    SignalPlan("moj-signals-plus", Decimal("29.00"), 3, True),
    SignalPlan("moj-signals-professional", Decimal("59.00"), 5, True),
)
PROOF_REQUIRED = (
    "independent_history_audit",
    "complete_losing_trade_and_fee_history",
    "jurisdiction_clearance",
    "subscriber_delivery_verified",
    "cancellation_and_refund_terms_approved",
    "site_identity_and_privacy_approved",
    "trx_finality_and_merchant_reconciled",
)


def canonical_signal_product(sku, brand):
    if brand not in SIGNAL_BRANDS:
        raise ValueError("Not a mapped financial brand")
    match = next((p for p in SIGNAL_PLANS if p.sku == sku), None)
    if match is None:
        raise ValueError("Unknown signal subscription")
    # Stable across all 17 mirrors, to avoid separate duplicate licenses.
    return {
        "entitlement_sku": match.sku,
        "plan_price_usd_proposed": str(match.monthly_usd_proposed),
        "host_brand": brand,
        "only_organizational_bot": CANONICAL_AGENT,
        "one_global_entitlement": True,
        "checkout_enabled": False,
        "renewal_enabled": False,
    }


def subscription_review(*, tenant, proofs):
    if not isinstance(tenant, TenantDecision) or tenant.brand not in SIGNAL_BRANDS:
        raise ValueError("A separately verified signal-brand merchant is required")
    if not isinstance(proofs, dict):
        raise ValueError("A trusted proof set is required")
    blockers = [k for k in PROOF_REQUIRED if proofs.get(k) is not True]
    # Reject forged truthy values; a merchant is reviewable only after an
    # explicit verified registry decision, never an HTTP-supplied "yes"/1.
    if tenant.eligible_for_checkout_review is not True:
        blockers.append("merchant_approval_missing")
    # A forged or stale affirmative tenant DTO must not green-light a
    # checkout review on an unrelated domain or an unresolved tenant ID.
    try:
        host = canonical_host(tenant.host)
    except ValueError:
        host = None
    if (host is None or host != tenant.host
            or not any(host == anchor or host.endswith("." + anchor)
                       for anchor in DEFAULT_ALLOWED_ANCHORS)):
        blockers.append("merchant_host_not_within_owned_domain")
    if (type(tenant.tenant_id) is not str or not tenant.tenant_id
            or type(tenant.missing) is not tuple or tenant.missing):
        blockers.append("merchant_identity_or_attestations_inconsistent")
    if tenant.payment_enabled is not False or tenant.invoice_created is not False:
        blockers.append("unexpected_active_payment_or_invoice_claim")
    return {
        "eligible_for_external_review": not blockers,
        "missing": blockers,
        "plans_proposed": len(SIGNAL_PLANS),
        "prices_are_live": False,
        "checkout_enabled": False,
        "auto_renewal_enabled": False,
        "signal_execution_enabled": False,
    }
