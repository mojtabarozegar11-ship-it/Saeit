"""Explicit site-specific TRON merchant and receiver assignments.

Trust is configured by the verified infrastructure owner in private settings,
never by browser, product metadata, URL parameter or payment candidate.
A merchant may not borrow another site's receiver or tenant ID.
This module does not activate checkout or provision wallets.
"""
from dataclasses import dataclass
import re

from .tron_gateway_verify import PaymentNotFinal, address_hex

ROOTS = frozenset(("mojplaywin.com", "zomorodmelal.ir"))
TENANT_ID = re.compile(r"[a-z][a-z0-9_]{2,63}\Z")
MAX_MERCHANTS = 64

class MerchantConfigurationError(ValueError):
    pass

@dataclass(frozen=True)
class SiteMerchant:
    host: str
    tenant_id: str
    receiver: str
    chain: str = "tron-mainnet"
    asset: str = "TRX"


def _canonical_site(host):
    if type(host) is not str or not 1 <= len(host) <= 150 or host != host.lower():
        raise MerchantConfigurationError("Host is not canonical")
    if host.startswith("www.") or host.endswith(".") or ":" in host or "/" in host or "*" in host:
        raise MerchantConfigurationError("Host is not canonical")
    if not (host in ROOTS or any(host.endswith("." + root) for root in ROOTS)):
        raise MerchantConfigurationError("Unknown owned merchant site")
    if any(not label or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z",label) for label in host.split(".")):
        raise MerchantConfigurationError("Invalid site label")
    return host


def configured_site_merchant(host, registry):
    """Fail closed for every malformed or ambiguously shared merchant mapping.

    Each site must have its own explicitly configured receiver and tenant.
    A single-wallet arrangement across multiple sites is not silently described
    as independent merchant settlement.
    """
    name = _canonical_site(host)
    if type(registry) is not dict or not 1 <= len(registry) <= MAX_MERCHANTS:
        raise MerchantConfigurationError("Private merchant registry missing or oversized")
    seen_tenants, seen_receivers = set(), set()
    found = None
    for raw_host, entry in registry.items():
        candidate = _canonical_site(raw_host)
        if (type(entry) is not dict
                or set(entry) != {"tenant_id", "receiver", "network", "asset", "approved"}):
            raise MerchantConfigurationError("Unapproved merchant registry entry")
        tenant = entry["tenant_id"]
        receiver = entry["receiver"]
        if (type(tenant) is not str or TENANT_ID.fullmatch(tenant) is None
                or type(receiver) is not str or
                entry["network"] != "tron-mainnet" or entry["asset"] != "TRX"
                or entry["approved"] is not True):
            raise MerchantConfigurationError("Merchant identity or asset not authorized")
        try:
            receiver_hex = address_hex(receiver)
        except PaymentNotFinal as exc:
            raise MerchantConfigurationError("Malformed mainnet merchant receiver") from exc
        if tenant in seen_tenants or receiver_hex in seen_receivers:
            raise MerchantConfigurationError("Merchant tenant or receiver reused by another site")
        seen_tenants.add(tenant)
        seen_receivers.add(receiver_hex)
        if candidate == name:
            found = SiteMerchant(candidate, tenant, receiver)
    if found is None:
        raise MerchantConfigurationError("This host lacks a dedicated approved merchant")
    return found
