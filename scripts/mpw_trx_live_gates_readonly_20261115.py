#!/usr/bin/env python3
"""Read-only live diagnosis for the private MojPlayWin TRON gate.

Prints only booleans, safe database metadata, and bounded counts. It never
creates orders, invoices, receipts, ledger entries, files, or chain broadcasts.
"""
from __future__ import annotations

import hashlib
import inspect
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
import services.mpw_walletless_commercial_intent as intent_module
from services.mpw_trx_commercial_web import _configured_receiver

FLAGS = (
    "DEBUG",
    "MPW_COMMERCE_RELEASE_READY",
    "MPW_COMMERCE_DOWNLOADS_ENABLED",
    "MPW_WALLETLESS_TRX_PUBLIC_ENABLED",
    "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",
)

SAFE_BOOL_FLAGS = (
    "MPW_COMMERCE_AUTORECONCILE_ENABLED",
    "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED",
    "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
    "MPW_COMMERCE_DOWNLOADS_ENABLED",
    "MPW_COMMERCE_INVOICING_ENABLED",
    "MPW_COMMERCE_REAL_RPC_ENABLED",
    "MPW_COMMERCE_RELEASE_READY",
    "MPW_COMMERCE_SETTLEMENT_ENABLED",
    "MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED",
    "MPW_GUEST_EMAIL_SEND_APPROVED",
    "MPW_GUEST_RECOVERY_EMAIL_APPROVED",
    "MPW_GUEST_RECOVERY_ENABLED",
    "MPW_MERCHANT_WALLET_PROOF_ENABLED",
    "MPW_PRIVATE_FUNNEL_COUNTERS_ENABLED",
    "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",
    "MPW_WALLETLESS_TRX_PUBLIC_ENABLED",
    "MPW_WALLETLESS_TRX_PUBLIC_RELEASE_AUTHORIZED",
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
def safe_module_file(module):
    return str(getattr(module, "__file__", "")) if module is not None else ""
settings_module = sys.modules.get("config.settings")
settings_file_path = Path(safe_module_file(settings_module)) if settings_module is not None else None
settings_file_sha256 = None
if settings_file_path is not None and settings_file_path.is_file():
    settings_file_sha256 = hashlib.sha256(settings_file_path.read_bytes()).hexdigest()
flag_names = ("MPW_WALLETLESS_TRX_PUBLIC_ENABLED", "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED")
defined_by = []
for module_name, module in sorted(sys.modules.items()):
    if module is None:
        continue
    try:
        if any(name in getattr(module, "__dict__", {}) for name in flag_names):
            defined_by.append({"module": module_name, "file": safe_module_file(module)})
    except Exception:
        continue
def flag_meta(name: str):
    value = getattr(settings, name, None)
    text = value.lower() if isinstance(value, str) and value.lower() in ("true", "false") else None
    return {"type": type(value).__name__, "is_true": value is True, "is_false": value is False, "safe_text": text}
class _DummySettings:
    DEBUG = False
    MPW_COMMERCE_RELEASE_READY = True
    MPW_COMMERCE_DOWNLOADS_ENABLED = True
    MPW_WALLETLESS_TRX_PUBLIC_ENABLED = True
    MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED = False
class _DummyDB:
    vendor = "mysql"
    alias = "default"
dummy_contract = check(lambda: intent_module._commercial_db(_DummySettings, _DummyDB()))
commercial_source = inspect.getsource(intent_module._commercial_db)
report = {
    "status": "MPW_TRX_LIVE_GATES_READONLY_DIAGNOSTIC",
    "settings_defined": {name: hasattr(settings, name) for name in FLAGS},
    "settings_true": {name: is_true(name) for name in FLAGS},
    "settings_meta": {name: flag_meta(name) for name in FLAGS},
    "safe_boolean_settings": {
        name: flag_meta(name)
        for name in SAFE_BOOL_FLAGS
        if isinstance(getattr(settings, name, None), bool)
    },
    "environment_presence": {name: name in os.environ for name in ("MPW_WALLETLESS_TRX_PUBLIC_ENABLED", "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED")},
    "commercial_db_source": {
        "sha256": hashlib.sha256(commercial_source.encode()).hexdigest(),
        "requires_strict_true": "is not True" in commercial_source,
        "dummy_public_true_canary_false": dummy_contract,
    },
    "database": {"vendor": connection.vendor, "alias": connection.alias},
    "settings_source": {
        "module_file": safe_module_file(settings_module),
        "file_sha256": settings_file_sha256,
        "defined_names": sorted(
            name
            for name in getattr(settings_module, "__dict__", {})
            if name.startswith("MPW_") and "SECRET" not in name and "KEY" not in name
        ),
    },
    "flag_defined_by_modules": defined_by,
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
