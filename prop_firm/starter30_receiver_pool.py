"""Owner-attested, exclusive public receiving-address pool for native Starter30 TRX.

Every invoice uses an address that can NEVER be assigned to a second invoice.
Public addresses only. No xprv, seed, key, private key or sweep capability on
the Django server. Actual spend/refund custody is separately attested off-host.

No configured and independently attested owner-controlled deposit pool => no
invoice may be issued or automatically settled. A shared old store receiver is
NEVER an eligible per-invoice address.
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
    if getattr(settings, "MPW_MOJPROP_SINGLE_RECEIVER_MODE", False) is True:
        ref = getattr(settings, "MPW_MOJPROP_SINGLE_RECEIVER_CONTROL_REF", "")
        if type(ref) is not str or _ATTESTATION.fullmatch(ref) is None:
            raise InvoiceAttributionUnavailable("single receiver control evidence is missing")
        try:
            return (approved_recipient(),)
        except Exception as exc:
            raise InvoiceAttributionUnavailable("merchant wallet configuration is unavailable") from exc
    if getattr(settings, "MPW_MOJPROP_INVOICE_ADDRESS_POOL_VERIFIED", False) is not True:
        raise InvoiceAttributionUnavailable("invoice-specific receiving addresses are not approved")
    ref = getattr(settings, "MPW_MOJPROP_INVOICE_ADDRESS_CONTROL_REF", "")
    if type(ref) is not str or _ATTESTATION.fullmatch(ref) is None:
        raise InvoiceAttributionUnavailable("independent private wallet-control evidence is missing")
    raw = getattr(settings, "MPW_MOJPROP_INVOICE_ADDRESS_POOL_JSON", "")
    if type(raw) is not str or not 2 <= len(raw) <= 20000:
        raise InvoiceAttributionUnavailable("owner-controlled invoice address pool is unavailable")
    try:
        values = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise InvoiceAttributionUnavailable("malformed invoice address pool") from exc
    if type(values) is not list or not 1 <= len(values) <= _MAX_POOL_SIZE:
        raise InvoiceAttributionUnavailable("expected a bounded list of public receiving addresses")
    try:
        shared = approved_recipient()
    except Exception as exc:
        raise InvoiceAttributionUnavailable("merchant wallet configuration is unavailable") from exc
    unique: set[str] = set()
    for address in values:
        if type(address) is not str or len(address) != 34 or not address.startswith("T"):
            raise InvoiceAttributionUnavailable("invalid invoice receiving address")
        try:
            validate_tron_recipient(address)
        except Exception as exc:
            raise InvoiceAttributionUnavailable("invoice receiver checksum invalid") from exc
        if address == shared:
            raise InvoiceAttributionUnavailable("a shared merchant receiver is not invoice-specific")
        if address in unique:
            raise InvoiceAttributionUnavailable("receiving address repeated in private pool")
        unique.add(address)
    return tuple(values)


def select_unused_receiver(pool: tuple[str, ...], used: set[str]) -> str:
    """Deterministic public-address selection, with DB uniqueness as final gate."""
    if type(pool) is not tuple or type(used) is not set:
        raise InvoiceAttributionUnavailable("untrusted receiver allocation data")
    # In single-receiver mode the same owner wallet is deliberately reused;
    # mandatory payer binding and the unique txid provide attribution.
    if len(pool) == 1:
        return pool[0]
    for address in pool:
        if address not in used:
            return address
    raise InvoiceAttributionUnavailable("owner-attested invoice receiver pool exhausted")


def require_payment_binding(*, recorded_recipient: str, onchain_recipient: str) -> None:
    """Trust only a current, unique, owner-attested invoice receiver.

    Actual uniqueness is enforced by a database UNIQUE constraint on the
    PropSimulationPayment.recipient column. Transaction dual-RPC proofs alone
    are NOT evidence of invoice ownership.
    """
    allowed = attested_receivers()
    if recorded_recipient not in allowed or onchain_recipient != recorded_recipient:
        raise InvoiceAttributionUnavailable(
            "payment cannot be attributed to this unique invoice; seek support"
        )