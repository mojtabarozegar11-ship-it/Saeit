"""Auditable TRX rollout inventory across *known* sites and financial paths.

This enumerates logical payment scopes, not 37 production hosts or live
checkout installations. Additional independently owned subdomains need an
explicit verified registration before anyone can issue an invoice.
"""
from .signal_commercial_catalog import SIGNAL_BRANDS
from .tron_tenant_policy import registered_scope

DISCOVERED_DOMAIN_ANCHORS = ("mojplaywin.com", "zomorodmelal.ir")
EXTRA_PRIORITY = ("moj_prop",)


def rollout_targets():
    targets = []
    for host in DISCOVERED_DOMAIN_ANCHORS:
        targets.append({
            "host": host, "brand": "",
            "section": "main_digital_store", "path": "/store/",
            "priority": 4 if host == "mojplaywin.com" else 3,
        })
        for brand in SIGNAL_BRANDS:
            targets.append({
                "host": host, "brand": brand,
                "section": "market_signal_subscription",
                "path": f"/{brand}/market-signals/",
                "priority": 2,
            })
    targets.append({
        "host": "mojplaywin.com", "brand": "moj_prop",
        "section": "prop_trader_challenge", "path": "/moj-prop/",
        "priority": 1,
    })
    targets.sort(key=lambda x: (x["priority"], x["host"], x["brand"]))
    return tuple(targets)


def inspect_rollout(registry=None, extra_owned_domains=None):
    """Return evidence-gated inventory; never materialize a payment route."""
    anchors = DISCOVERED_DOMAIN_ANCHORS
    if extra_owned_domains is not None:
        if not isinstance(extra_owned_domains, (tuple, list)):
            raise ValueError("Additional verified domains must be a trusted list")
        anchors = (*anchors, *extra_owned_domains)
    entries = []
    for item in rollout_targets():
        decision = registered_scope(
            host=item["host"], brand=item["brand"], registry=registry,
            allowed_anchors=anchors,
        )
        entries.append({
            **item,
            "tenant_id": decision.tenant_id,
            "eligible_for_adapter_review": decision.eligible_for_checkout_review,
            "missing": list(decision.missing),
            "checkout_enabled": False,
            "invoice_created": False,
        })
    return {
        "known_canonical_site_domains": len(DISCOVERED_DOMAIN_ANCHORS),
        "logical_payment_scopes_not_hosts": len(entries),
        "brand_routes_per_site": len(SIGNAL_BRANDS),
        "trading_bot": "mojtaba.bot.ai",
        "one_gateway_architecture": True,
        "live_gateway_connected": False,
        "excluded_instagram_profile": "Dr.mojtaba.rozegar",
        "entries": entries,
    }
