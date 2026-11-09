#!/usr/bin/env python3
"""C31: bounded paid-state aggregates, without per-order output or buyer data.

This source is for a proposed cPanel-local monitor, not a proof of revenue,
blockchain finality, entitlement, or a customer completing a download.
The deployment must provide an independently verified SELECT-only DB role.
"""

from __future__ import annotations

import json
import os
import re
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
from django.db import connection


def grant_is_select_only(grant, database_name=None):
    """Fail closed for broad grants, roles, DML, DDL, and GRANT OPTION."""
    if not isinstance(grant, str) or " WITH GRANT OPTION" in grant.upper():
        return False
    normalized = grant.strip()
    if not re.match(r"^GRANT (?:USAGE|SELECT(?:, SHOW VIEW)?) ON ",
                    normalized, flags=re.IGNORECASE):
        return False
    if normalized.upper().startswith("GRANT SELECT"):
        target = re.search(r"\sON\s+(`[^`]+`|[A-Za-z0-9_]+)\.",
                           normalized, flags=re.IGNORECASE)
        if not target or target.group(1).strip("`") == "*":
            return False
        if database_name is not None and target.group(1).strip("`") != database_name:
            return False
    return True


def assert_readonly_database_session():
    """Validate account privileges and additionally lock session transactions."""
    if connection.vendor != "mysql":
        raise RuntimeError("MONITOR_REQUIRES_MARIADB_SELECT_ONLY")
    database_name = connection.settings_dict.get("NAME")
    if not isinstance(database_name, str) or not database_name:
        raise RuntimeError("MONITOR_DATABASE_NAME_UNAVAILABLE")
    with connection.cursor() as cursor:
        cursor.execute("SHOW GRANTS FOR CURRENT_USER")
        grants = [str(row[0]) for row in cursor.fetchall()]
        if (not grants or not all(grant_is_select_only(g, database_name) for g in grants)
                or not any(g.strip().upper().startswith("GRANT SELECT") for g in grants)):
            raise RuntimeError("MONITOR_DATABASE_GRANTS_NOT_SELECT_ONLY")
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
        cursor.execute("SELECT @@session.transaction_read_only")
        state = cursor.fetchone()
        if not state or state[0] not in (1, True, "1"):
            raise RuntimeError("MONITOR_READONLY_SESSION_NOT_CONFIRMED")


def run():
    # Refuse privileged connections before any query of paid orders.
    assert_readonly_database_session()
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
