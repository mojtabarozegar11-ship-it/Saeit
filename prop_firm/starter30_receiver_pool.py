"""Single owner-authorized receive-only TRON wallet for new Starter30 invoices.

No second deposit address, legacy pool, signing key, private key, or sweep
capability may be used to collect new customer fees. The sending-wallet binding
and unique settled transaction proof identify each invoice. Previously issued
invoices must be reconciled independently without deleting their history.
"""
from __future__ import annotations

import json
import re

from django.conf import settings

from services.mojtaba_tron_owner_receiver import approved_recipient
from services.mpw_trx_merchant_binding import validate_tron_recipient


class InvoiceAttributionUnavailable(ValueError):
    """Fail closed rather than let a public txid credit another buyer."""


_ATTESTATION = re.compile(r"[A-Za-z0-9._:/-]{16,128}\Z")
_MAX_POOL_SIZE = 256


def attested_receivers() -> tuple[str, ...]:
    """Return only owner-attested public addresses, never wallet secrets."""
    # Owner explicitly selected one shared receive-only wallet. In this mode
    # payer-wallet binding is mandatory and the wallet is never used as reserve.
    if getattr(settings, "MPW_MOJPROP_SINGLE_RECEIVER_MODE", False) is not True:
        raise InvoiceAttributionUnavailable(
            "only the sole owner-approved receive-only wallet is permitted"
        )
    ref = getattr(settings, "MPW_MOJPROP_SINGLE_RECEIVER_CONTROL_REF", "")
    if type(ref) is not str or _ATTESTATION.fullmatch(ref) is None:
        raise InvoiceAttributionUnavailable("single receiver control evidence is missing")
    try:
        return (approved_recipient(),)
    except Exception as exc:
        raise InvoiceAttributionUnavailable("merchant wallet configuration is unavailable") from exc

def select_unused_receiver(pool: tuple[str, ...], used: set[str]) -> str:
    """Deterministic public-address selection, with DB uniqueness as final gate."""
    if type(pool) is not tuple or type(used) is not set:
        raise InvoiceAttributionUnavailable("untrusted receiver allocation data")
    # The approved merchant wallet is reused; sender binding and independent
    # finalized-chain proof must identify the invoice. Never accept a pool.
    if len(pool) != 1:
        raise InvoiceAttributionUnavailable("multiple invoice receivers prohibited")
    try:
        only_owner_receiver = approved_recipient()
    except Exception as exc:
        raise InvoiceAttributionUnavailable("owner receiving wallet unavailable") from exc
    if pool[0] != only_owner_receiver:
        raise InvoiceAttributionUnavailable("non-owner invoice recipient prohibited")
    return only_owner_receiver


def require_payment_binding(*, recorded_recipient: str, onchain_recipient: str) -> None:
    """Match the on-chain recipient to the single owner-approved receive wallet.

    In single-receiver mode that wallet is reused by multiple invoices, and
    the database does NOT enforce UNIQUE(recipient). This condition verifies
    the merchant wallet only, never buyer wallet ownership or a unique invoice
    attribution. Independent finalized-chain proof and unique TXID are also
    insufficient to authenticate a text-supplied payer address.
    """
    allowed = attested_receivers()
    if recorded_recipient not in allowed or onchain_recipient != recorded_recipient:
        raise InvoiceAttributionUnavailable(
            "payment cannot be attributed to this unique invoice; seek support"
        )