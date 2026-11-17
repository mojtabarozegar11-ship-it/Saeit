"""Owner-identified native-TRX receiving wallet for MojPlayWin.

On 2026-11-15 the owner presented a Trust Wallet receive QR and explicitly
attested that taking TRON payments to this wallet is legally authorized.
The address below is from the QR *payload*, not a visual transcription.

A public payment address is not a secret. This file is NOT a payment gateway:
it never creates a buyer invoice, claims a confirmed on-chain payment, assigns
a customer balance, issues paid research entitlements or contacts a wallet.
Merchant activation remains gated by independently configured production
billing/settlement checks, with no implicit www, external domains or aliases.
"""
from __future__ import annotations

from types import MappingProxyType

from services.mpw_trx_merchant_binding import (
    MerchantBindingRejected,
    binding_for_request,
    validate_tron_recipient,
)

APPROVED_NATIVE_TRX_RECIPIENT = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
MAINNET = "tron-mainnet"
ASSET = "TRX"
DECIMALS = 6
MERCHANT_DOMAIN = "mojplaywin.com"
MERCHANT_ID = "mojplaywin-store"


def approved_recipient():
    """Reject incorrect QR transcription, unknown address, or invalid checksum."""
    return validate_tron_recipient(APPROVED_NATIVE_TRX_RECIPIENT)


def owner_merchant_registry(*, invoice_enabled: bool = False,
                            finality_enabled: bool = False,
                            recipient: str = APPROVED_NATIVE_TRX_RECIPIENT):
    """Exact-host merchant registry. Never derive a beneficiary from a request.

    Both explicit production permissions are necessary; a source merge and
    wallet attestation alone must not begin issuing payable invoices. The
    validated recipient cannot be swapped by a request or deployment typo.
    """
    if type(invoice_enabled) is not bool or type(finality_enabled) is not bool:
        raise MerchantBindingRejected("TRON collection gates must be explicit booleans")
    if type(recipient) is not str or recipient != approved_recipient():
        raise MerchantBindingRejected("Receiver differs from owner-verified QR")
    record = MappingProxyType({
        "domain": MERCHANT_DOMAIN,
        "merchant_id": MERCHANT_ID,
        "network": MAINNET,
        "recipient": recipient,
        "enabled": invoice_enabled and finality_enabled,
    })
    return MappingProxyType({MERCHANT_DOMAIN: record})


def require_owner_trx_binding(settings, host: str):
    """Guard new merchant invoices with the existing host-bound checksum policy."""
    return binding_for_request(settings, host, approved_recipient())


def public_receiving_terms():
    """Information for a customer-visible invoice only AFTER merchant release.

    Terms do not specify an amount: only an authenticated server-issued
    order/invoice may define exact sun units, expiry and supported product.
    """
    return MappingProxyType({
        "merchant_domain": MERCHANT_DOMAIN,
        "merchant_id": MERCHANT_ID,
        "network": MAINNET,
        "asset": ASSET,
        "decimals": DECIMALS,
        "recipient": approved_recipient(),
        "amount_sun": None,
        "invoice_id": None,
        "payment_verified": False,
        "paid_entitlement": False,
        "checkout_live": False,
    })
