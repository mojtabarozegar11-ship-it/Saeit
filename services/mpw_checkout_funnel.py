"""Minimal private MojPlayWin checkout funnel counters, with no visitor records.

Events can count a checkout attempt, an exception, or a completed stage. No IP,
cookie, session, referrer, email, URL, transaction or invoice identifier is
stored.  Counts are *events*, never unique buyers or confirmed payments.

Production is opt-in through MPW_PRIVATE_FUNNEL_COUNTERS_ENABLED=True.  The
SQLite file lives outside the public web root and uses no external service.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import pwd
import re
import sqlite3
import stat


ACCOUNT = "zomorod2"
DATA_DIR = Path("/home/zomorod2/.local/share/mpw-private-funnel")
DATA_FILE = DATA_DIR / "daily-counts.sqlite3"
STAGES = frozenset({
    "checkout_view", "order_start_attempt", "order_start_accepted",
    "order_start_not_invoiced", "order_start_exception",
    "invoice_view", "paid_download",
})
BOT_UA = re.compile(r"bot|crawl|spider|curl/|wget/|python-|headless|lighthouse|pagespeed|monitor", re.I)
MAX_COUNT = 1_000_000
SCHEMA = """CREATE TABLE IF NOT EXISTS daily (
  day_utc TEXT NOT NULL,
  stage TEXT NOT NULL,
  product_id INTEGER NOT NULL,
  count INTEGER NOT NULL CHECK(count >= 0 AND count <= 1000000),
  PRIMARY KEY(day_utc, stage, product_id)
) WITHOUT ROWID"""


def _private_path():
    """Reject wrong-account, symlinked or publicly accessible storage."""
    if pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT:
        raise RuntimeError("wrong hosting account")
    for ancestor in (DATA_DIR.parent, DATA_DIR.parent.parent):
        if ancestor.is_symlink():
            raise RuntimeError("unsafe metric ancestor")
    if DATA_DIR.is_symlink():
        raise RuntimeError("unsafe metric directory")
    DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = DATA_DIR.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise RuntimeError("metric directory permissions")
    if DATA_FILE.is_symlink():
        raise RuntimeError("unsafe metric file")
    try:
        fd = os.open(DATA_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(fd)
    info = DATA_FILE.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
        raise RuntimeError("metric file permissions")
    return DATA_FILE


def _readable_path():
    if pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT:
        raise RuntimeError("wrong hosting account")
    for node in (DATA_DIR.parent.parent, DATA_DIR.parent, DATA_DIR, DATA_FILE):
        if node.is_symlink():
            raise RuntimeError("unsafe metric path")
    if not DATA_FILE.is_file():
        return None
    directory = DATA_DIR.stat()
    file = DATA_FILE.stat()
    if (directory.st_uid != os.geteuid() or
            stat.S_IMODE(directory.st_mode) != 0o700 or
            file.st_uid != os.geteuid() or
            file.st_nlink != 1 or
            stat.S_IMODE(file.st_mode) != 0o600):
        raise RuntimeError("unsafe metric permissions")
    return DATA_FILE


def _enabled(request):
    from django.conf import settings
    if getattr(settings, "MPW_PRIVATE_FUNNEL_COUNTERS_ENABLED", False) is not True:
        return False
    if not request.is_secure() or request.get_host().split(":")[0].lower() not in (
            "mojplaywin.com", "www.mojplaywin.com"):
        return False
    # Heuristic exclusion, without storing the User-Agent.
    return not BOT_UA.search(str(request.META.get("HTTP_USER_AGENT", ""))[:256])


def record(request, stage, product_id=0):
    """Best-effort anonymous event aggregate; errors never block checkout."""
    try:
        if stage not in STAGES or not _enabled(request):
            return False
        if type(product_id) is not int or not 0 <= product_id <= 999_999:
            return False
        if stage in ("checkout_view", "order_start_attempt", "order_start_accepted",
                     "order_start_not_invoiced", "order_start_exception"):
            from django.conf import settings
            if product_id not in getattr(settings, "MPW_TRX_PUBLIC_PRODUCT_IDS", ()):
                return False
        else:
            product_id = 0  # Never treat order/invoice IDs as product identifiers.
        day = datetime.now(timezone.utc).date().isoformat()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=45)).date().isoformat()
        with sqlite3.connect(f"file:{_private_path()}?mode=rw", uri=True, timeout=0.35) as db:
            db.execute("PRAGMA busy_timeout = 350")
            db.execute(SCHEMA)
            db.execute("""INSERT INTO daily(day_utc, stage, product_id, count)
                          VALUES (?, ?, ?, 1)
                          ON CONFLICT(day_utc, stage, product_id) DO UPDATE SET
                          count=MIN(count + 1, ?)""", (day, stage, product_id, MAX_COUNT))
            db.execute("DELETE FROM daily WHERE day_utc < ?", (cutoff,))
        return True
    except Exception:
        # The store must never depend on analytics availability.
        return False


def report(days=7):
    """Read only daily aggregate results, never events or buyer identities."""
    if type(days) is not int or not 1 <= days <= 45:
        raise ValueError("days must be 1-45")
    file = _readable_path()
    if file is None:
        return {"days": days, "status": "not_installed", "daily": [],
                "uniques_available": False, "payments_verified": False,
                "contains_customer_data": False}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date().isoformat()
    with sqlite3.connect(f"file:{file}?mode=ro", uri=True, timeout=2) as db:
        result = db.execute("""SELECT day_utc, stage, product_id, count
                               FROM daily WHERE day_utc >= ?
                               ORDER BY day_utc, stage, product_id""", (cutoff,))
        rows = [dict(zip(("day_utc", "stage", "product_id", "events"), row))
                for row in result.fetchall()]
    return {"days": days, "status": "aggregated", "daily": rows,
            "uniques_available": False, "payments_verified": False,
            "contains_customer_data": False}
