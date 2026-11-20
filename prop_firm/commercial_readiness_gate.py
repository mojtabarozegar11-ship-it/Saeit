"""Pure fail-closed commercial release readiness evaluator.

This module reports whether separately evidenced commercial gates are complete.
It never enables a route, creates an invoice, accepts payment, sends email,
creates a customer account, settles funds, or authorizes a broker action.
"""
from __future__ import annotations

from dataclasses import dataclass


REQUIRED_GATES = (
    "product_contract_finalized",
    "risk_rules_published",
    "simulation_disclosure_published",
    "jurisdiction_and_eligibility_defined",
    "kyc_and_age_provider_ready",
    "refund_and_support_ready",
    "invoice_and_amount_controls_ready",
    "payment_reconciliation_verified",
    "delivery_and_receipt_verified",
    "owner_release_approval_recorded",
)


class CommercialReleaseClosed(ValueError):
    """Raised when an untrusted or incomplete gate mapping is supplied."""


@dataclass(frozen=True)
class CommercialReadiness:
    missing_gates: tuple[str, ...]
    disabled_controls: tuple[str, ...]
    eligible_for_release: bool
    public_route_enabled: bool = False
    payment_enabled: bool = False
    invoice_created: bool = False
    settlement_allowed: bool = False


def evaluate_commercial_readiness(
    *, gates, public_route_enabled=False, payment_enabled=False
):
    """Return evidence status only; never mutate runtime configuration."""
    if not isinstance(gates, dict):
        raise CommercialReleaseClosed("trusted gate mapping is required")
    if any(type(gates.get(name)) is not bool for name in REQUIRED_GATES):
        raise CommercialReleaseClosed("all gate values must be trusted booleans")
    if type(public_route_enabled) is not bool or type(payment_enabled) is not bool:
        raise CommercialReleaseClosed("release controls must be trusted booleans")

    missing = tuple(name for name in REQUIRED_GATES if gates[name] is not True)
    disabled = tuple(
        name
        for name, enabled in (
            ("public_route_enabled", public_route_enabled),
            ("payment_enabled", payment_enabled),
        )
        if enabled is not True
    )
    return CommercialReadiness(
        missing_gates=missing,
        disabled_controls=disabled,
        eligible_for_release=not missing and not disabled,
        public_route_enabled=public_route_enabled,
        payment_enabled=payment_enabled,
    )
