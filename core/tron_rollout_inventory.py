"""Auditable TRX rollout inventory across *known* sites and financial paths.

This enumerates logical payment scopes, not 37 production hosts or live
checkout installations. Additional independently owned subdomains need an
explicit verified registration before anyone can issue an invoice.
"""
from .signal_commercial_catalog import SIGNAL_BRANDS
from .tron_tenant_policy import canonical_host, registered_scope

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


def inspect_explicit_site_expansion(*, merchant_registry, approved_site_hosts):
    """Inventory additional sites WITHOUT activating or auto-inheriting payments.

    approved_site_hosts must originate from an independently maintained owner
    domain/SSL verification registry. A host on the list is a proposed scope,
    not DNS proof: every brand still needs its own exact merchant registration.
    This includes subdomains explicitly, instead of silently inheriting a
    parent site's wallet or invoice ledger.
    """
    if type(merchant_registry) is not dict:
        raise ValueError("Protected merchant registry required")
    if type(approved_site_hosts) not in (tuple, list) or len(approved_site_hosts) > 100:
        raise ValueError("Explicit owned hosts must be a bounded trusted list")
    hosts = tuple(canonical_host(host) for host in approved_site_hosts)
    if (len(set(hosts)) != len(hosts)
            or any(host in DISCOVERED_DOMAIN_ANCHORS for host in hosts)):
        raise ValueError("Duplicate or previously inventoried site hostname")
    anchors = (*DISCOVERED_DOMAIN_ANCHORS, *hosts)
    existing = inspect_rollout(registry=merchant_registry)
    additions = []
    for host in sorted(hosts):
        # The root and each brand are different payment tenants, even on the
        # exact same host. Neither an owned DNS name nor 200 OK enables billing.
        candidates = [("", "main_digital_store", "/store/", 4)]
        candidates.extend(
            (brand, "market_signal_subscription",
             f"/{brand}/market-signals/", 2)
            for brand in SIGNAL_BRANDS
        )
        for brand, section, path, priority in candidates:
            decision = registered_scope(
                host=host, brand=brand, registry=merchant_registry,
                allowed_anchors=anchors,
            )
            additions.append({
                "host": host, "brand": brand, "section": section,
                "path": path, "priority": priority,
                "tenant_id": decision.tenant_id,
                "eligible_for_adapter_review": decision.eligible_for_checkout_review,
                "missing": list(decision.missing),
                "checkout_enabled": False, "invoice_created": False,
                "domain_live_independently_verified": False,
            })
    all_entries = tuple(sorted(
        (*existing["entries"], *additions),
        key=lambda item: (item["priority"], item["host"], item["brand"]),
    ))
    return {
        **existing,
        "additional_operator_listed_hosts": len(hosts),
        "logical_payment_scopes_not_hosts": len(all_entries),
        "entries": list(all_entries),
        "live_gateway_connected": False,
        "unverified_dns_and_legal_host_state": True,
    }
