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
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit

PRIVATE_ROOT = Path("/home/zomorod2/.private_mojplaywin_main_agents")
MONITOR_CREDENTIAL_FILE = PRIVATE_ROOT / "mpw_readonly_db_url.secret"


def load_monitor_database_identity(path=MONITOR_CREDENTIAL_FILE):
    """Require owner-only, explicit monitor credentials before Django setup.

    Never fall back to the storefront DATABASE_URL from the application's .env.
    The configured monitor account is separately checked for SELECT-only grants.
    """
    parent = path.parent
    parent_info = parent.lstat()
    if (not stat.S_ISDIR(parent_info.st_mode)
            or parent_info.st_uid != os.getuid()
            or stat.S_IMODE(parent_info.st_mode) != 0o700):
        raise RuntimeError("MONITOR_PRIVATE_DIRECTORY_UNSAFE")
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise RuntimeError("MONITOR_CREDENTIAL_FILE_UNSAFE")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            raw = handle.read(2049)
    finally:
        if fd >= 0:
            os.close(fd)
    if len(raw) > 2048:
        raise RuntimeError("MONITOR_CREDENTIAL_FILE_TOO_LARGE")
    try:
        database_url = raw.decode("utf-8").rstrip("\n")
        parsed = urlsplit(database_url)
        hostname = parsed.hostname
    except (UnicodeError, ValueError):
        raise RuntimeError("MONITOR_CREDENTIAL_URL_INVALID") from None
    if (parsed.scheme != "mysql" or hostname not in ("localhost", "127.0.0.1", "::1")
            or not parsed.username or not parsed.password
            or not re.fullmatch(r"/[A-Za-z0-9_]{1,64}", parsed.path)
            or parsed.query or parsed.fragment or "\n" in database_url):
        raise RuntimeError("MONITOR_CREDENTIAL_URL_INVALID")
    # Django-environ's read_env does not override an already exported value.
    os.environ["DATABASE_URL"] = database_url
    return parsed.path[1:]

ROOT = Path("/home/zomorod2/Saeit-staging")
if not ROOT.is_dir() or ROOT.is_symlink():
    raise RuntimeError("UNEXPECTED_LIVE_RUNTIME_ROOT")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
MONITOR_DATABASE_NAME = load_monitor_database_identity()
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

import django
django.setup()

from core.models import PaymentIntent
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


def assert_readonly_database_session(expected_database_name=None):
    """Validate account privileges and additionally lock session transactions."""
    if connection.vendor != "mysql":
        raise RuntimeError("MONITOR_REQUIRES_MARIADB_SELECT_ONLY")
    database_name = connection.settings_dict.get("NAME")
    if (not isinstance(database_name, str) or not database_name
            or (expected_database_name is not None and database_name != expected_database_name)):
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
    # Refuse privileged connections before any query of payment state.
    assert_readonly_database_session(MONITOR_DATABASE_NAME)
    # The sole commerce query returns one integer. No PaymentIntent or Order
    # record, including their identifiers, references, and customer fields,
    # is materialized in this process. Verification needs a separate gate.
    total = PaymentIntent.objects.filter(status="paid").count()

    # Zero verified credits means NOT MEASURED, not zero actual credited sales.
    # The explicit false flags prevent this conservative count from being
    # mistaken for payment correctness, receipts or customer delivery.
    print("MPW_PAID_AGGREGATE_READONLY=" + json.dumps({
        "paid_intent_count": total,
        "rows_examined": 0,
        "truncated": total > 0,
        "walletless_persisted_credit_verified": 0,
        "payment_intent_detail_read_performed": False,
        "walletless_credit_verification_performed": False,
        "independent_mainnet_recheck_performed": False,
        "customer_download_e2e_performed": False,
        "production_db_writes": False,
    }, sort_keys=True))


if __name__ == "__main__":
    run()
