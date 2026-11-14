"""Auditable TRX rollout inventory across *known* sites and financial paths.

This enumerates logical payment scopes, not 37 production hosts or live
checkout installations. Additional independently owned subdomains need an
explicit verified registration before anyone can issue an invoice.
"""
from .signal_commercial_catalog import SIGNAL_BRANDS
from .tron_tenant_policy import registered_scope, canonical_host

DISCOVERED_DOMAIN_ANCHORS = ("mojplaywin.com", "zomorodmelal.ir")
EXTRA_PRIORITY = ("moj_prop",)


def _candidate_subsites(extra_owned_domains):
    """List literal known-parent subsite candidates, NOT independent ownership proof.

    Only separately approved tenant registry rows can ever be eligible for
    payment adapter review; arbitrary external TLDs are not silently trusted.
    """
    if extra_owned_domains is None:
        return ()
    if not isinstance(extra_owned_domains, (tuple, list)):
        raise ValueError("Additional domains must be a trusted collection")
    if len(extra_owned_domains) > 64:
        raise ValueError("Too many domain candidates")
    selected = []
    for raw in extra_owned_domains:
        host = canonical_host(raw)
        if host in DISCOVERED_DOMAIN_ANCHORS:
            continue
        if (host not in selected and
                any(host.endswith("." + anchor) for anchor in DISCOVERED_DOMAIN_ANCHORS)):
            selected.append(host)
    return tuple(sorted(selected))


def rollout_targets(extra_owned_domains=None):
    subsites = _candidate_subsites(extra_owned_domains)
    targets = []
    for host in (*DISCOVERED_DOMAIN_ANCHORS, *subsites):
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
    subsites = _candidate_subsites(extra_owned_domains)
    # A client-provided hostname may never extend the financial trust anchors.
    # Exact registered tenant id and all payment prerequisites remain required.
    anchors = DISCOVERED_DOMAIN_ANCHORS
    entries = []
    for item in rollout_targets(subsites):
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
        "candidate_subsites_not_verified_live": list(subsites),
        "candidate_subsite_count": len(subsites),
        "unverified_external_hosts_never_trusted": True,
        "logical_payment_scopes_not_hosts": len(entries),
        "brand_routes_per_site": len(SIGNAL_BRANDS),
        "trading_bot": "mojtaba.bot.ai",
        "one_gateway_architecture": True,
        "live_gateway_connected": False,
        "excluded_instagram_profile": "Dr.mojtaba.rozegar",
        "entries": entries,
    }
