#!/usr/bin/env python3
"""Read-only live diagnosis for the private MojPlayWin TRON gate.

Prints only booleans, safe database metadata, and bounded counts. It never
creates orders, invoices, receipts, ledger entries, files, or chain broadcasts.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP = Path("/home/zomorod2/Saeit-staging")
EXPECTED_RECEIVER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
sys.path.insert(0, str(APP))
os.chdir(APP)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.conf import settings
from django.db import connection
from services.mpw_trx_walletless_core import ADDRESS, PaymentHold
from services.mpw_walletless_commercial_intent import _commercial_db, _paid_read_db
from services.mpw_trx_commercial_web import _configured_receiver

FLAGS = (
    "DEBUG",
    "MPW_COMMERCE_RELEASE_READY",
    "MPW_COMMERCE_DOWNLOADS_ENABLED",
    "MPW_WALLETLESS_TRX_PUBLIC_ENABLED",
    "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",
)

def is_true(name: str) -> bool:
    return getattr(settings, name, False) is True

def check(fn):
    try:
        fn()
        return {"ok": True, "error_type": None}
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__}

receiver = _configured_receiver()
backend = check(lambda: _paid_read_db(settings, connection))
commercial = check(lambda: _commercial_db(settings, connection))
report = {
    "status": "MPW_TRX_LIVE_GATES_READONLY_DIAGNOSTIC",
    "settings_defined": {name: hasattr(settings, name) for name in FLAGS},
    "settings_true": {name: is_true(name) for name in FLAGS},
    "database": {"vendor": connection.vendor, "alias": connection.alias},
    "paid_read_backend": backend,
    "commercial_gate": commercial,
    "permanent_public_gates_closed": (
        is_true("MPW_WALLETLESS_TRX_PUBLIC_ENABLED") is False
        and is_true("MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED") is False
    ),
    "receiver": {
        "shape_valid": ADDRESS.fullmatch(receiver) is not None,
        "base58_owned_binding_matches": receiver == EXPECTED_RECEIVER,
    },
    "financial_writes": 0,
    "chain_broadcasts": 0,
}
print("MPW_TRX_LIVE_GATES=" + json.dumps(report, sort_keys=True))
