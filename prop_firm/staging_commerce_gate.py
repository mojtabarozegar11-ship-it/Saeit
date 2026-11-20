"""Fail-closed contract/refund/KYC gate for a non-payable staging preview.

This module is pure policy evaluation. It never creates an invoice, writes a
database row, sends email, accepts payment, or authorizes a live account.
"""

from dataclasses import dataclass


PRODUCT_CODE = "MOJ-PROP-01"
TERMS_VERSION = "2026-11-20/simulation-v1"
REFUND_POLICY_VERSION = "2026-11-20/refund-v1"

REQUIRED_GATES = (
    "country_allowed",
    "age_verified",
    "kyc_verified",
    "terms_accepted",
    "simulation_disclosure_accepted",
    "refund_policy_accepted",
    "privacy_accepted",
    "support_ready",
)


class CommerceGateClosed(ValueError):
    """Raised when a staging preview request is malformed or unsafe."""


@dataclass(frozen=True)
class NonPayablePreview:
    product_code: str
    country: str
    terms_version: str
    refund_policy_version: str
    missing_gates: tuple[str, ...]
    eligible_for_preview: bool
    payable: bool = False
    settlement_allowed: bool = False
    public_route_allowed: bool = False


def evaluate_nonpayable_preview(*, product_code, country, gates):
    if product_code != PRODUCT_CODE:
        raise CommerceGateClosed("canonical product is required")
    if not isinstance(country, str) or len(country) != 2 or not country.isascii():
        raise CommerceGateClosed("two-letter country code is required")
    country = country.upper()
    if not isinstance(gates, dict):
        raise CommerceGateClosed("trusted gate mapping is required")
    if any(type(gates.get(name)) is not bool for name in REQUIRED_GATES):
        raise CommerceGateClosed("all gate values must be trusted booleans")
    missing = tuple(name for name in REQUIRED_GATES if gates[name] is not True)
    return NonPayablePreview(
        product_code=PRODUCT_CODE,
        country=country,
        terms_version=TERMS_VERSION,
        refund_policy_version=REFUND_POLICY_VERSION,
        missing_gates=missing,
        eligible_for_preview=not missing,
    )
