"""Unified native-TRX multi-tenant integration contract, NOT a live gateway.

Known domains, subdomains and 17 branded paths require explicit per-tenant
registration. Exact host matching prevents cross-site wallet and invoice
confusion. A signed scope is an internal routing assertion, never an invoice
or evidence of a TRON payment. No wallet is generated or money moved here.
"""
from dataclasses import dataclass
from hashlib import sha256
import hmac
import re

from .signal_commercial_catalog import SIGNAL_BRANDS

CANONICAL_CHAIN = "tron-mainnet"
CANONICAL_ASSET = "TRX"
ACCEPTED_BRANDS = frozenset((*SIGNAL_BRANDS, "moj_prop"))
HOST_PATTERN = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z"
)
VALID_TENANT_ID = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,79}\Z")
REQUIRED_ATTESTATIONS = (
    "merchant_identity_approved",
    "jurisdiction_approved",
    "custody_control_verified",
    "network_settlement_verified",
    "unique_invoice_ledger_verified",
    "refund_and_delivery_verified",
)
DEFAULT_ALLOWED_ANCHORS = ("mojplaywin.com", "zomorodmelal.ir")


@dataclass(frozen=True)
class TenantDecision:
    tenant_id: str | None
    host: str
    brand: str
    eligible_for_checkout_review: bool
    missing: tuple[str, ...]
    payment_enabled: bool = False
    invoice_created: bool = False


def canonical_host(value):
    if not isinstance(value, str):
        raise ValueError("Host must be string")
    host = value.strip().lower()
    if not host.isascii() or len(host) > 253 or not HOST_PATTERN.fullmatch(host):
        raise ValueError("Invalid canonical hostname")
    return host


def registered_scope(*, host, brand="", registry=None, allowed_anchors=None):
    """Caller registry must be separately protected configuration, not HTTP JSON."""
    actual = canonical_host(host)
    # Validate type BEFORE set membership: an HTTP-supplied array/dict
    # must cause a clean refusal, not an unhashable 500 response.
    if type(brand) is not str:
        raise ValueError("Brand must be text")
    if brand and brand not in ACCEPTED_BRANDS:
        raise ValueError("Unknown branded route")
    anchors = DEFAULT_ALLOWED_ANCHORS if allowed_anchors is None else allowed_anchors
    if not isinstance(anchors, (tuple, list, set)) or not anchors:
        raise ValueError("Trusted anchor domains missing")
    anchors = tuple(canonical_host(a) for a in anchors)
    if not any(actual == domain or actual.endswith("." + domain) for domain in anchors):
        return TenantDecision(None, actual, brand, False, ("host_not_owned_or_approved",))
    if registry is None:
        return TenantDecision(None, actual, brand, False, ("tenant_registry_missing",))
    if not isinstance(registry, dict):
        raise ValueError("Malformed site registry")
    # Register exact host + logical brand; site root is the empty brand.
    key = (actual, brand)
    item = registry.get(key)
    if not isinstance(item, dict):
        return TenantDecision(None, actual, brand, False, ("tenant_not_registered",))
    tenant_id = item.get("tenant_id")
    if not isinstance(tenant_id, str) or not VALID_TENANT_ID.fullmatch(tenant_id):
        return TenantDecision(None, actual, brand, False, ("invalid_tenant_id",))
    # Every brand/site must have a unique accounting identity. A copied ID on
    # a second host could collapse separate customer invoices into one ledger.
    if len(registry) > 4096:
        return TenantDecision(tenant_id, actual, brand, False, ("tenant_registry_too_large",))
    for other_key, other in registry.items():
        if (
            not isinstance(other_key, tuple) or len(other_key) != 2
            or not all(isinstance(v, str) for v in other_key)
            or not isinstance(other, dict)
        ):
            return TenantDecision(tenant_id, actual, brand, False, ("malformed_tenant_registry",))
        if other_key != key and other.get("tenant_id") == tenant_id:
            return TenantDecision(tenant_id, actual, brand, False, ("duplicate_tenant_id",))
    if item.get("asset") != CANONICAL_ASSET or item.get("network") != CANONICAL_CHAIN:
        return TenantDecision(tenant_id, actual, brand, False, ("wrong_network_or_asset",))
    missing = tuple(k for k in REQUIRED_ATTESTATIONS if item.get(k) is not True)
    # Eligibility is not checkout activation; a separate actual payment adapter,
    # regulator/merchant onboarding, production keys and reconciler are required.
    return TenantDecision(
        tenant_id, actual, brand, not missing, missing,
        payment_enabled=False, invoice_created=False,
    )


def signed_routing_context(*, decision, product_sku, key):
    """Produce an internal routing token; it cannot settle or create invoices."""
    if (
        not isinstance(decision, TenantDecision)
        or decision.eligible_for_checkout_review is not True
        or decision.payment_enabled is not False
        or decision.invoice_created is not False
    ):
        raise ValueError("Tenant requires verified review gates")
    if not isinstance(key, str) or len(key) < 32:
        raise ValueError("Missing trusted signing key")
    if not isinstance(product_sku, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,119}", product_sku):
        raise ValueError("Invalid immutable product SKU")
    message = "|".join((
        "MOJ-TRX-TENANT-v1", decision.host, decision.brand,
        decision.tenant_id, CANONICAL_CHAIN, CANONICAL_ASSET, product_sku,
    ))
    digest = hmac.new(key.encode(), message.encode(), sha256).hexdigest()
    return {
        "domain": decision.host,
        "brand": decision.brand,
        "tenant_id": decision.tenant_id,
        "product_sku": product_sku,
        "network": CANONICAL_CHAIN,
        "asset": CANONICAL_ASSET,
        "routing_digest": digest,
        "is_invoice": False,
        "is_paid": False,
        "checkout_enabled": False,
    }


def verify_signed_routing_context(*, context, key, registry, allowed_anchors=None):
    """Validate a routing assertion against CURRENT protected merchant registry.

    This verifier is for internal routing only. It does not authorize checkout,
    create an invoice, prove an on-chain transfer, or provide replay prevention.
    Never use an HTTP-supplied registry or HMAC key.
    """
    if not isinstance(context, dict) or set(context) != {
        "domain", "brand", "tenant_id", "product_sku", "network", "asset",
        "routing_digest", "is_invoice", "is_paid", "checkout_enabled",
    }:
        return False
    # Reject edited or forged paid flags, including 0 and other false-like data.
    if (context["is_invoice"] is not False or context["is_paid"] is not False
            or context["checkout_enabled"] is not False):
        return False
    if (context["network"] != CANONICAL_CHAIN
            or context["asset"] != CANONICAL_ASSET
            or not isinstance(context["routing_digest"], str)
            or len(context["routing_digest"]) != 64):
        return False
    try:
        decision = registered_scope(
            host=context["domain"], brand=context["brand"],
            registry=registry, allowed_anchors=allowed_anchors,
        )
        if (decision.eligible_for_checkout_review is not True
                or decision.tenant_id != context["tenant_id"]
                or decision.host != context["domain"]):
            return False
        expected = signed_routing_context(
            decision=decision, product_sku=context["product_sku"], key=key,
        )
    except (TypeError, ValueError, AttributeError):
        return False
    return hmac.compare_digest(context["routing_digest"], expected["routing_digest"])
