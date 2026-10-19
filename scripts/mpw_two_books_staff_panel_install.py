#!/usr/bin/env python3
"""Install isolated MojPlayWin book-sales observability on cPanel.

Never migrates database, changes payment flags, restarts Passenger or touches
sibling site code. Atomic backup/rollback if any preflight or Django check fails.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path("/home/zomorod2")
APP = ROOT / "Saeit-staging"
STAGING = ROOT / ".saeit-factory-inbox/private/mpw-books-status"
APP_PYTHON = Path("/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python")
IMPORT = "from .mpw_two_books_panel import dashboard as mpw_two_books_dashboard"
ROUTE = '    path("mpw-two-books/", mpw_two_books_dashboard, name="mpw_two_books_dashboard"),'
MARK_IMPORT = "from .mpw_operations import desk as mpw_operations"
MARK_ROUTE = '    path("mpw-operations/", mpw_operations, name="mpw_operations"),'


def _atom(path, data):
    fd, temp = tempfile.mkstemp(prefix=".mpw-book-status-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def install():
    source = APP / "command_center"
    urlfile = source / "urls.py"
    new_view = source / "mpw_two_books_panel.py"
    new_template = source / "templates/command_center/mpw_two_books_panel.html"
    assert ROOT.is_dir() and APP.is_dir() and source.is_dir()
    assert not APP.is_symlink() and not source.is_symlink()
    assert APP_PYTHON.is_file() and (APP / "manage.py").is_file()
    assert (ROOT / "mojplaywin.com/passenger_wsgi.py").is_file()
    assert urlfile.is_file() and not urlfile.is_symlink()
    assert STAGING.is_dir() and not STAGING.is_symlink()
    incoming = [
        (STAGING / "mpw_two_books_panel.py", new_view),
        (STAGING / "mpw_two_books_panel.html", new_template),
    ]
    for src, dest in incoming:
        assert src.is_file() and not src.is_symlink() and src.stat().st_size < 55000
        assert dest.parent.is_dir() and not dest.parent.is_symlink() and not dest.is_symlink()
        if dest.exists() and dest.read_bytes() != src.read_bytes():
            raise RuntimeError("REFUSE_REPLACE_EXISTING_UNRELATED_SOURCE:" + dest.name)
    old = urlfile.read_text(encoding="utf-8")
    if old.count(IMPORT) or old.count(ROUTE):
        if old.count(IMPORT) != 1 or old.count(ROUTE) != 1:
            raise RuntimeError("PARTIALLY_INSTALLED_URLCONF")
        new = old
    else:
        if old.count(MARK_IMPORT) != 1 or old.count(MARK_ROUTE) != 1:
            raise RuntimeError("UNKNOWN_COMMAND_CENTER_ROUTING")
        new = old.replace(MARK_IMPORT, MARK_IMPORT + "\n" + IMPORT).replace(
            MARK_ROUTE, MARK_ROUTE + "\n" + ROUTE,
        )
    backup = STAGING / ("backup-" + uuid.uuid4().hex)
    backup.mkdir(mode=0o700)
    shutil.copy2(urlfile, backup / "urls.py")
    created = []
    try:
        for src, dest in incoming:
            if not dest.exists():
                _atom(dest, src.read_bytes())
                created.append(dest)
        if new != old:
            _atom(urlfile, new.encode("utf-8"))
        check = subprocess.run(
            [str(APP_PYTHON), "manage.py", "check"], cwd=APP,
            capture_output=True, text=True, timeout=70,
        )
        if check.returncode != 0:
            raise RuntimeError("DJANGO_CHECK_FAILED:" + check.stderr[-500:])
        probe = (
            "import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');"
            "django.setup();from command_center.mpw_two_books_panel import _status_dict;"
            "r=_status_dict();assert len(r['books'])==2;"
            "assert r['can_enable_payments'] is False;"
            "assert r['real_settlement_test_verified'] is False;"
            "print('MPW_BOOK_PANEL_TWO_PRODUCTS='+str(len(r['books'])));"
            "print('MPW_BOOK_PANEL_REAL_ORDERS='+str(r['orders_total']));"
            "print('MPW_BOOK_PANEL_GATEWAY_FLAGS_ENABLED='+str(r['all_gateway_flags_enabled']))"
        )
        result = subprocess.run(
            [str(APP_PYTHON), "-c", probe], cwd=APP,
            capture_output=True, text=True, timeout=35,
        )
        if result.returncode != 0:
            raise RuntimeError("READ_ONLY_LIVE_DASHBOARD_PROBE_FAILED:" + result.stderr[-550:])
        print(result.stdout.strip())
        print("MPW_BOOK_PANEL_SOURCE_INSTALLED=true")
        print("MPW_BOOK_PANEL_SHARED_PASSENGER_RESTARTED=false")
        print("MPW_BOOK_PANEL_PAYMENTS_CHANGED=false")
        print("MPW_BOOK_PANEL_DB_WRITES=0")
    except Exception:
        _atom(urlfile, (backup / "urls.py").read_bytes())
        for dest in created:
            if dest.is_file() and not dest.is_symlink():
                dest.unlink()
        print("MPW_BOOK_PANEL_SAFE_ROLLBACK=true", file=sys.stderr)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit("EXPLICIT_APPLY_REQUIRED")
    install()
