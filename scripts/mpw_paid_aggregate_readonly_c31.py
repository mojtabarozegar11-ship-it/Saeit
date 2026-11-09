#!/usr/bin/env python3
"""C31: bounded paid-state aggregates, without per-order output or buyer data.

This source is for a proposed cPanel-local monitor, not a proof of revenue,
blockchain finality, entitlement, or a customer completing a download.
The deployment must provide an independently verified SELECT-only DB role.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
if not ROOT.is_dir() or ROOT.is_symlink():
    raise RuntimeError("UNEXPECTED_LIVE_RUNTIME_ROOT")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from core.models import PaymentIntent
from core.crown_tron_receipts import PROVIDER, verified_walletless_credit


def run():
    qs = PaymentIntent.objects.filter(status="paid").select_related("order")
    total = qs.count()
    examined = 0
    verified_credits = 0
    for intent in qs.order_by("pk")[:100]:
        examined += 1
        if (intent.provider == PROVIDER
                and verified_walletless_credit(intent.order, intent)):
            verified_credits += 1

    # Emit strictly aggregate scalars; never serialize order/intent records,
    # addresses, emails, customer IDs, product item lists, or transaction hashes.
    print("MPW_PAID_AGGREGATE_READONLY=" + json.dumps({
        "paid_intent_count": total,
        "rows_examined": examined,
        "truncated": total > examined,
        "walletless_persisted_credit_verified": verified_credits,
        "independent_mainnet_recheck_performed": False,
        "customer_download_e2e_performed": False,
        "production_db_writes": False,
    }, sort_keys=True))


if __name__ == "__main__":
    run()
