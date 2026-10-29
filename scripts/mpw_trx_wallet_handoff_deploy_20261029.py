#!/usr/bin/env python3
"""Single-module, exact-SHA cPanel install for MojPlayWin mobile TRX wallet handoff.

Run only by the pinned GitHub Actions > VPS > cPanel relay. No financial or
customer data is read or written; no code outside the one verified module changes.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

ROOT = Path("/home/zomorod2")
APP = ROOT / "Saeit-staging"
SITE = ROOT / "mojplaywin.com"
TARGET = APP / "services/mpw_trx_walletless_one_tap_ui.py"
WSGI = SITE / "passenger_wsgi.py"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def assert_regular(path):
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("EXPECTED_REGULAR_FILE_MISSING:" + str(path))


def context(run):
    if not re.fullmatch(r"[0-9]{6,20}", run):
        raise RuntimeError("INVALID_RUN_ID")
    stage = ROOT / (".mpw-trx-handoff-20261029-" + run)
    for folder in (ROOT, APP, APP / "services", SITE, stage):
        if not folder.is_dir() or folder.is_symlink():
            raise RuntimeError("UNSAFE_DIRECTORY:" + str(folder))
    if stat.S_IMODE(stage.stat().st_mode) & 0o077:
        raise RuntimeError("STAGING_MUST_BE_PRIVATE")
    for path in (WSGI, SITE / ".htaccess", TARGET, stage / "reviewed.py"):
        assert_regular(path)
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8", "replace"):
        raise RuntimeError("UNEXPECTED_PASSENGER_APP_BINDING")
    return stage


def baseline(run, original_sha, updated_sha):
    if not all(re.fullmatch(r"[0-9a-f]{64}", h) for h in (original_sha, updated_sha)):
        raise RuntimeError("INVALID_REVIEWED_SHA")
    if original_sha == updated_sha:
        raise RuntimeError("IDENTICAL_SOURCE_REVISIONS")
    stage = context(run)
    reviewed = (stage / "reviewed.py").read_bytes()
    if sha(reviewed) != updated_sha:
        raise RuntimeError("STAGED_SOURCE_HASH_MISMATCH")
    source = reviewed.decode("utf8")
    compile(source, str(TARGET), "exec")
    if ('"trust://send?"' not in source or
            'id="mpw-easy-pay" type="button" hidden' not in source or
            'Never pay an expired invoice.' not in source or
            "https://link.trustwallet.com/send?" in source):
        raise RuntimeError("REVIEWED_WALLET_GUARD_MARKERS_MISSING")
    return stage, reviewed


def atomic_write(path, data):
    fd, name = tempfile.mkstemp(prefix=".mpw-trx-wallet-", dir=str(path.parent))
    try:
        os.fchmod(fd, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, str(path))
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def audit(run, original_sha, updated_sha):
    baseline(run, original_sha, updated_sha)
    current = sha(TARGET.read_bytes())
    print("MPW_TRX_HANDOFF_LIVE_AUDIT=" + json.dumps({
        "sha256": current,
        "expected_original": original_sha,
        "expected_new": updated_sha,
        "publishable": current == original_sha,
        "already_applied": current == updated_sha,
    }, sort_keys=True))
    if current not in (original_sha, updated_sha):
        raise RuntimeError("LIVE_MODULE_DRIFT_ABORT_NO_CHANGE")


def publish(run, original_sha, updated_sha):
    stage, reviewed = baseline(run, original_sha, updated_sha)
    current = TARGET.read_bytes()
    if sha(current) == updated_sha:
        print("MPW_TRX_HANDOFF_ALREADY_APPLIED")
        return
    if sha(current) != original_sha:
        raise RuntimeError("LIVE_MODULE_DRIFT_ABORT_NO_CHANGE")
    saved = stage / "original.py"
    manifest = stage / "manifest.json"
    if saved.exists() or saved.is_symlink() or manifest.exists() or manifest.is_symlink():
        raise RuntimeError("REFUSE_REPLACE_EXISTING_BACKUP")
    with saved.open("xb") as output:
        os.chmod(saved, 0o600)
        output.write(current)
        output.flush()
        os.fsync(output.fileno())
    with manifest.open("x", encoding="utf8") as output:
        os.chmod(manifest, 0o600)
        json.dump({"run": run, "before": original_sha, "after": updated_sha}, output)
        output.flush()
        os.fsync(output.fileno())
    if sha(TARGET.read_bytes()) != original_sha:
        raise RuntimeError("CONCURRENT_MODULE_EDIT_ABORT")
    try:
        atomic_write(TARGET, reviewed)
        if sha(TARGET.read_bytes()) != updated_sha:
            raise RuntimeError("POST_INSTALL_SHA_MISMATCH")
    except BaseException:
        if sha(TARGET.read_bytes()) == updated_sha:
            atomic_write(TARGET, current)
        raise
    print("MPW_TRX_HANDOFF_ATOMIC_PUBLISH_OK:" + updated_sha)


def rollback(run, original_sha, updated_sha):
    stage = context(run)
    saved = stage / "original.py"
    manifest = stage / "manifest.json"
    if not saved.exists() and not manifest.exists():
        print("MPW_TRX_HANDOFF_NOT_INSTALLED_BY_THIS_RUN")
        return
    assert_regular(saved)
    assert_regular(manifest)
    record = json.loads(manifest.read_text("utf8"))
    if record != {"run": run, "before": original_sha, "after": updated_sha}:
        raise RuntimeError("ROLLBACK_MANIFEST_MISMATCH")
    previous = saved.read_bytes()
    if sha(previous) != original_sha:
        raise RuntimeError("BACKUP_INTEGRITY_FAILURE")
    if sha(TARGET.read_bytes()) != updated_sha:
        raise RuntimeError("REFUSE_ROLLBACK_CONCURRENT_EDIT")
    atomic_write(TARGET, previous)
    if sha(TARGET.read_bytes()) != original_sha:
        raise RuntimeError("ROLLBACK_SHA_MISMATCH")
    print("MPW_TRX_HANDOFF_ROLLBACK_OK")


def refresh(run, original_sha, updated_sha):
    context(run)
    for root in (APP, SITE):
        folder = root / "tmp"
        if folder.is_symlink():
            raise RuntimeError("UNSAFE_RESTART_DIRECTORY")
        folder.mkdir(exist_ok=True)
        marker = folder / "restart.txt"
        if marker.is_symlink() or (marker.exists() and not marker.is_file()):
            raise RuntimeError("UNSAFE_RESTART_MARKER")
        marker.touch()
    print("MPW_TRX_HANDOFF_PASSENGER_REFRESH_REQUESTED")


def check_render(run, original_sha, updated_sha):
    baseline(run, original_sha, updated_sha)
    if sha(TARGET.read_bytes()) != updated_sha:
        raise RuntimeError("ACTIVE_MODULE_NOT_REVIEWED_VERSION")
    # No database writes, real orders, wallet transactions or blockchain lookups.
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    from unittest.mock import patch
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    from services.mpw_trx_walletless_core import InvoiceIntent
    from services.mpw_trx_walletless_one_tap_ui import render_one_tap_invoice
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    intent = InvoiceIntent(
        order_id=14, customer_id=22, network="tron-mainnet",
        recipient="T" + "A" * 33, amount_sun=1234567,
        usd_total=Decimal("0.37"), issued_at=now,
        expires_at=now + timedelta(minutes=10),
        quote_usd_per_trx=Decimal("0.30"),
    )
    with patch("services.mpw_trx_walletless_checkout_ui.build_recipient_qr",
               return_value='<svg xmlns="http://www.w3.org/2000/svg"></svg>'):
        html, csp = render_one_tap_invoice(
            intent, status_path="/commerce/trx-easy/status/14/"
        )
    page = html.decode("utf8")
    for marker in ("trust://send?asset=c195", 'id="mpw-easy-pay" type="button" hidden',
                   "Never pay an expired invoice.", "Copy exact TRX amount"):
        if marker not in page:
            raise RuntimeError("RENDERED_TRX_INVOICE_MARKER_MISSING:" + marker)
    if "https://link.trustwallet.com/send" in page or "'unsafe-inline'" in csp:
        raise RuntimeError("UNSAFE_INVOICE_FALLBACK_OR_CSP")
    print("MPW_TRX_HANDOFF_SYNTHETIC_RENDER_OK")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("usage: {audit|publish|rollback|refresh|check_render} RUN OLD_SHA NEW_SHA")
    command, run_id, before, after = sys.argv[1:]
    actions = {"audit": audit, "publish": publish, "rollback": rollback,
               "refresh": refresh, "check_render": check_render}
    if command not in actions:
        raise SystemExit("UNKNOWN_COMMAND")
    actions[command](run_id, before, after)
