"""Read-only TRON recipient registration status for the single merchant host.

No chain RPC, customer data, invoice creation, payment, wallet key or send.
Configuration presence and Base58Check validity do not prove actual settlement.
"""
from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand

from services.mpw_trx_merchant_binding import MerchantBindingRejected
from services.mojtaba_tron_owner_receiver import (
    APPROVED_NATIVE_TRX_RECIPIENT, MERCHANT_DOMAIN, MERCHANT_ID, MAINNET,
    approved_recipient, require_owner_trx_binding,
)


def receiver_status(config):
    """Pure read-only decision. Never infer money received from a source flag."""
    try:
        checksum_valid = approved_recipient() == APPROVED_NATIVE_TRX_RECIPIENT
    except MerchantBindingRejected:
        checksum_valid = False
    registry = getattr(config, "MPW_TRX_MERCHANT_BINDINGS", None)
    binding_configured = False
    if checksum_valid:
        try:
            bound = require_owner_trx_binding(config, MERCHANT_DOMAIN)
            binding_configured = (
                bound.network == MAINNET
                and bound.merchant_id == MERCHANT_ID
                and bound.recipient == APPROVED_NATIVE_TRX_RECIPIENT
            )
        except (MerchantBindingRejected, ValueError, TypeError):
            pass
    return {
        "schema": "mojtaba.tron.receiver_state.v1",
        "network": MAINNET,
        "asset": "TRX",
        "merchant_domain": MERCHANT_DOMAIN,
        "merchant_id": MERCHANT_ID,
        "receiver_suffix": APPROVED_NATIVE_TRX_RECIPIENT[-6:],
        "qr_base58check_valid": checksum_valid,
        "invoice_release_flag": getattr(config, "MPW_TRX_INVOICE_RELEASE_VERIFIED", False) is True,
        "finality_release_flag": getattr(config, "MPW_TRX_SOLIDITY_RELEASE_VERIFIED", False) is True,
        "merchant_binding_enabled": binding_configured,
        "live_invoice_issuance_verified": None,
        "chain_settlement_verified": None,
        "customer_delivery_verified": None,
        "revenue_received_trx": None,
        "warning": "Do not treat wallet registration or source checks as verified customer funds.",
    }


class Command(BaseCommand):
    help = "Read-only native TRON receiver registration; no balances, keys, transactions or invoicing."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(receiver_status(settings), sort_keys=True))
