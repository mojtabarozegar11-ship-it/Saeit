"""Fail-closed merchant identity binding for persisted TRON invoices.

The binding is deliberately independent of Django and of blockchain RPC.  A
payable invoice must carry the exact HTTPS host, merchant identifier, network,
and receiver selected by a server-side registry.  Browser input never creates
or changes this registry.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import hmac
import re

_DOMAIN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)
_MERCHANT = re.compile(r"^[a-z0-9][a-z0-9_-]{2,47}$")
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class MerchantBindingRejected(ValueError):
    """The invoice cannot be safely attributed to one configured merchant."""


@dataclass(frozen=True)
class MerchantBinding:
    domain: str
    merchant_id: str
    network: str
    recipient: str



def validate_tron_recipient(value: str) -> str:
    """Require a checksummed, canonical TRON mainnet Base58Check address.

    The leading T alone is not proof of address integrity. Decode exactly
    21 payload bytes (0x41 + 20 account bytes) and the four-byte double-SHA256
    checksum. This performs no wallet lookup, RPC or network operation.
    """
    if (type(value) is not str or len(value) != 34
            or not value.startswith("T")
            or any(ch not in _BASE58 for ch in value)):
        raise MerchantBindingRejected("Invalid TRON mainnet receiver address")
    number = 0
    for ch in value:
        number = number * 58 + _BASE58.index(ch)
    try:
        raw = number.to_bytes(25, "big")
    except OverflowError as exc:
        raise MerchantBindingRejected("TRON receiver address overflow") from exc
    if raw[0] != 0x41:
        raise MerchantBindingRejected("TRON receiver network prefix mismatch")
    digest = hashlib.sha256(hashlib.sha256(raw[:21]).digest()).digest()[:4]
    if not hmac.compare_digest(raw[21:], digest):
        raise MerchantBindingRejected("TRON receiver checksum mismatch")
    return value

def normalize_domain(value: str) -> str:
    if type(value) is not str:
        raise MerchantBindingRejected("Merchant domain must be text")
    value = value.strip().casefold()
    if value.endswith("."):
        value = value[:-1]
    if (not value or len(value) > 253 or not value.isascii()
            or _DOMAIN.fullmatch(value) is None):
        raise MerchantBindingRejected("Merchant domain is not a canonical host")
    return value


def normalize_merchant_id(value: str) -> str:
    if type(value) is not str:
        raise MerchantBindingRejected("Merchant identifier must be text")
    value = value.strip().casefold()
    if _MERCHANT.fullmatch(value) is None:
        raise MerchantBindingRejected("Merchant identifier is invalid")
    return value


def validate_persisted_binding(domain: str, merchant_id: str) -> tuple[str, str]:
    """Validate only immutable envelope identity fields."""
    return normalize_domain(domain), normalize_merchant_id(merchant_id)


def binding_for_request(settings, request_domain: str, recipient: str) -> MerchantBinding:
    """Resolve a request host through an explicit owner-managed registry.

    Required setting shape (default-deny):
    MPW_TRX_MERCHANT_BINDINGS = {
        "mojplaywin.com": {
            "domain": "mojplaywin.com",
            "merchant_id": "mojplaywin-store",
            "network": "tron-mainnet",
            "recipient": "<server-side TRON address>",
            "enabled": True,
        },
    }
    Both apex and www are separate keys when both are intentionally served.
    """
    domain = normalize_domain(request_domain)
    bindings = getattr(settings, "MPW_TRX_MERCHANT_BINDINGS", None)
    if not isinstance(bindings, Mapping):
        raise MerchantBindingRejected("TRON merchant registry is not configured")
    record = bindings.get(domain)
    if not isinstance(record, Mapping):
        raise MerchantBindingRejected("Request host is not registered for TRON")
    if record.get("enabled") is not True:
        raise MerchantBindingRejected("Merchant binding is disabled")
    configured_domain = normalize_domain(record.get("domain"))
    merchant_id = normalize_merchant_id(record.get("merchant_id"))
    network = record.get("network")
    configured_recipient = record.get("recipient")
    if configured_domain != domain or network != "tron-mainnet":
        raise MerchantBindingRejected("Merchant binding network/domain mismatch")
    if type(recipient) is not str or configured_recipient != recipient:
        raise MerchantBindingRejected("Receiver does not belong to request merchant")
    recipient = validate_tron_recipient(recipient)
    return MerchantBinding(
        domain=domain,
        merchant_id=merchant_id,
        network=network,
        recipient=recipient,
    )


def require_same_invoice_host(invoice, request_domain: str) -> str:
    """Protect buyer invoice lookup from cross-domain/alias reuse.

    A settled invoice must remain recoverable even after the merchant registry
    has been disabled, so this guard checks only the *persisted* immutable
    attribution. A new payable invoice additionally needs an active registry.
    """
    domain = normalize_domain(request_domain)
    validate_tron_recipient(getattr(invoice, "recipient", None))
    saved, merchant_id = validate_persisted_binding(
        getattr(invoice, "merchant_domain", None),
        getattr(invoice, "merchant_id", None),
    )
    if (saved != domain or getattr(invoice, "network", None) != "tron-mainnet"
            or type(getattr(invoice, "recipient", None)) is not str
            or not merchant_id):
        raise MerchantBindingRejected("Invoice is owned by a different merchant host")
    return domain


def require_current_merchant_for_invoice(settings, request_domain, invoice) -> MerchantBinding:
    """Prevent a prior merchant's pending invoice from being reused after drift."""
    domain = require_same_invoice_host(invoice, request_domain)
    binding = binding_for_request(settings, domain, invoice.recipient)
    if binding.merchant_id != invoice.merchant_id:
        raise MerchantBindingRejected("Merchant identifier drifted since invoice issue")
    return binding
