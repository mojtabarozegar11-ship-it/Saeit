"""Explicit TRX commerce scope for the five owner-requested surfaces.

This is a scope and safety registry, not a live payment gateway. It makes the
five commercial destinations auditable without inheriting a wallet, invoice
ledger, or permission from another host or brand.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import islice

CANONICAL_BOT = "mojtaba.bot.ai"
CANONICAL_NETWORK = "TRON"
CANONICAL_ASSET = "TRX"

COMMON_BLOCKERS = (
    "merchant_entity_verified",
    "site_dns_tls_host_attestation",
    "tron_mainnet_receipt_proven",
    "unique_invoice_ledger_verified",
    "refund_and_dispute_process_approved",
    "delivery_entitlement_reconciled",
)

# The order is the owner's commercial priority. Each row is a separate
# tenant/scope, even when two rows use the same host.
SURFACE_SPECS = (
    {
        "surface_id": "moj_prop",
        "tenant_id": "moj_prop",
        "host": "mojplaywin.com",
        "path": "/moj-prop/",
        "surface_kind": "prop_challenge_fee",
        "priority": 1,
    },
    {
        "surface_id": "signal_sales",
        "tenant_id": "mojtaba_bot_signal_sales",
        "host": "mojtaba.bot.ai",
        "path": "/signals/",
        "surface_kind": "signal_subscription",
        "priority": 2,
    },
    {
        "surface_id": "zomorod_melal_store",
        "tenant_id": "zomorod_melal_store",
        "host": "zomorodmelal.ir",
        "path": "/store/",
        "surface_kind": "physical_and_digital_products",
        "priority": 3,
    },
    {
        "surface_id": "mojplaywin_store",
        "tenant_id": "mojplaywin_store",
        "host": "mojplaywin.com",
        "path": "/store/",
        "surface_kind": "digital_products_and_games",
        "priority": 4,
    },
    {
        "surface_id": "robot_products",
        "tenant_id": "mojtaba_bot_robot_products",
        "host": "mojtaba.bot.ai",
        "path": "/products/robots/",
        "surface_kind": "robot_products_and_services",
        "priority": 5,
    },
)

EXPECTED_SURFACE_IDS = tuple(item["surface_id"] for item in SURFACE_SPECS)


def surface_ids() -> tuple[str, ...]:
    """Return the stable five-surface order used by reports and manifests."""
    return EXPECTED_SURFACE_IDS


def build_surface_registry() -> tuple[dict, ...]:
    """Build a disabled, JSON-friendly registry with no external side effect."""
    return tuple(
        {
            **item,
            "canonical_bot": CANONICAL_BOT,
            "network": CANONICAL_NETWORK,
            "asset": CANONICAL_ASSET,
            "source_of_scope": "owner_requested_commercial_priority",
            "status": "requested_not_verified",
            "payment_enabled": False,
            "checkout_enabled": False,
            "invoice_created": False,
            "live_gateway_connected": False,
            "blockers": list(COMMON_BLOCKERS),
        }
        for item in SURFACE_SPECS
    )


def assert_safe_surface_registry(
    registry: Iterable[Mapping[str, object]] | None = None,
) -> bool:
    """Reject drift that could silently turn scope documentation into billing."""
    if registry is None:
        rows = build_surface_registry()
    else:
        # Read at most one element beyond the fixed five-surface limit:
        # an infinite iterator must not exhaust the release-gate worker.
        if isinstance(registry, (str, bytes, bytearray, Mapping)):
            raise ValueError("A bounded iterable of commerce surfaces is required")
        try:
            rows = tuple(islice(iter(registry), len(SURFACE_SPECS) + 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("A bounded iterable of commerce surfaces is required") from exc
    if len(rows) != len(SURFACE_SPECS):
        raise ValueError("Exactly five explicit commerce surfaces are required")
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("Each commerce surface must be a mapping")
    ids = tuple(row.get("surface_id") for row in rows)
    if ids != EXPECTED_SURFACE_IDS:
        raise ValueError("Surface IDs must match the canonical priority order")
    for row, spec in zip(rows, SURFACE_SPECS):
        for key in ("tenant_id", "host", "path", "surface_kind", "priority"):
            if key == "priority" and type(row.get(key)) is not int:
                raise ValueError("Surface registry priority must be an integer")
            if row.get(key) != spec[key]:
                raise ValueError(f"Surface registry drift: {key}")
        if row.get("source_of_scope") != "owner_requested_commercial_priority":
            raise ValueError("Source of commerce scope cannot be changed")
        if row.get("canonical_bot") != CANONICAL_BOT:
            raise ValueError("Every route must use the single canonical bot")
        if row.get("network") != CANONICAL_NETWORK or row.get("asset") != CANONICAL_ASSET:
            raise ValueError("Only native TRX on TRON is allowed in this registry")
        if row.get("payment_enabled") is not False:
            raise ValueError("Payment activation is not permitted by this registry")
        if row.get("checkout_enabled") is not False:
            raise ValueError("Checkout activation is not permitted by this registry")
        if row.get("invoice_created") is not False:
            raise ValueError("Invoice creation is not permitted by this registry")
        if row.get("live_gateway_connected") is not False:
            raise ValueError("Live gateway connection is not proven")
        if row.get("status") != "requested_not_verified":
            raise ValueError("Unverified scope cannot be marked live")
        blockers = row.get("blockers")
        if type(blockers) not in (list, tuple) or tuple(blockers) != COMMON_BLOCKERS:
            raise ValueError("Every surface must retain all independent release blockers")
    return True


def commercial_surface_summary() -> dict:
    """Return an auditable summary for control-tower and release reports."""
    registry = build_surface_registry()
    assert_safe_surface_registry(registry)
    return {
        "requested_surface_count": len(registry),
        "live_surface_count": sum(row["payment_enabled"] for row in registry),
        "invoice_created_count": sum(row["invoice_created"] for row in registry),
        "surface_ids": list(surface_ids()),
        "hosts": sorted({row["host"] for row in registry}),
        "canonical_bot": CANONICAL_BOT,
        "network": CANONICAL_NETWORK,
        "asset": CANONICAL_ASSET,
        "one_gateway_architecture": True,
        "independent_tenant_registration_required": True,
        "live_gateway_connected": False,
        "status": "scope_registered_not_live",
    }
