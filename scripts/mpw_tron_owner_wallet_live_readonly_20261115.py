#!/usr/bin/env python3
"""Safe live cPanel merchant-recipient compatibility check.

Read-only: executed through the existing authorized GitHub -> VPS -> cPanel
SSH relay. This program never prints addresses, credentials, wallet history,
buyer records or balances; no transaction creation, RPC, SQL or funds movement.
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

OWNER_QR = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
ROOT = Path("/home/zomorod2/Saeit-staging")


def safe_report(settings, receiver_entry=None):
    # Compare only; do not print the unknown production receiver on mismatch.
    shape = (isinstance(receiver_entry, (tuple, list))
             and len(receiver_entry) == 3)
    network, wallet, decimals = receiver_entry if shape else (None, None, None)
    registration = getattr(settings, "MPW_TRX_MERCHANT_BINDINGS", {})
    merchant_record = (registration.get("mojplaywin.com")
                       if isinstance(registration, Mapping) else None)
    if not isinstance(merchant_record, Mapping):
        merchant_record = {}
    return {
        "schema": "mpw.tron.receiver.live.readonly.v1",
        "host": "mojplaywin.com",
        "asset": "TRX",
        "network": "tron-mainnet",
        "owner_qr_receiver_match": type(wallet) is str and wallet == OWNER_QR,
        "effective_receiver_native_mainnet": (
            network == "tron-mainnet" and decimals == 6
        ),
        "receiver_tuple_present": shape,
        "host_registry_matches_qr": (
            merchant_record.get("domain") == "mojplaywin.com"
            and merchant_record.get("network") == "tron-mainnet"
            and merchant_record.get("merchant_id") == "mojplaywin-store"
            and merchant_record.get("recipient") == OWNER_QR
        ),
        "host_registry_enabled": merchant_record.get("enabled") is True,
        "commercial_invoicing_enabled": (
            getattr(settings, "MPW_COMMERCE_INVOICING_ENABLED", False) is True
        ),
        "real_rpc_enabled": (
            getattr(settings, "MPW_COMMERCE_REAL_RPC_ENABLED", False) is True
        ),
        "settlement_enabled": (
            getattr(settings, "MPW_COMMERCE_SETTLEMENT_ENABLED", False) is True
        ),
        "owned_wallet": "user_attested_not_independently_signed",
        "live_sale_verified": False,
        "payment_finality_checked": False,
        "customer_delivery_checked": False,
        "read_only": True,
    }


def main():
    if (not ROOT.is_dir() or ROOT.is_symlink()
            or ROOT.resolve() != ROOT):
        raise SystemExit("LIVE_ROOT_NOT_AUTHENTICATED")
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        import django
        django.setup()
        from django.conf import settings
    except (Exception,) as exc:
        print("MPW_TRON_READONLY_SETUP_ERROR=" + type(exc).__name__)
        raise SystemExit(3) from None

    receiver = None
    try:
        from mpw_commerce.invoicing import RECEIVERS
        receiver = RECEIVERS.get("TRX") if isinstance(RECEIVERS, Mapping) else None
    except (Exception,) as exc:
        # Do not output exception message, source path, or sensitive values.
        print("MPW_TRON_READONLY_RECEIVER_MODULE=" + type(exc).__name__)
    print("MPW_TRON_OWNER_WALLET_LIVE_READONLY="
          + json.dumps(safe_report(settings, receiver), sort_keys=True))


if __name__ == "__main__":
    main()
