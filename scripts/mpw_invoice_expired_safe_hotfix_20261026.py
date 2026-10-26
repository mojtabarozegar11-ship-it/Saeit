#!/usr/bin/env python3
"""Single-function MojPlayWin invoice expiry hotfix. No order/payment/rights writes."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

APP = Path("/home/zomorod2/Saeit-staging")
PUBLIC = Path("/home/zomorod2/mojplaywin.com")
TARGET = APP / "services/mpw_trx_commercial_web.py"
BACKUP = Path("/home/zomorod2/.local/share/mpw-invoice-expiry-20261026")
PYTHON = Path("/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python")
OLD = '''    if intent.status!=WAITING or invoice.expires_at<=timezone.now():
        raise Http404("This invoice is no longer payable")'''
NEW = '''    if intent.status!=WAITING or invoice.expires_at<=timezone.now():
        # Expired quotes remain unpayable, but old invoice URLs explain recovery.
        # Do not display a stale TRX amount or receiving address.
        from services.mpw_trx_public_pages import _page
        return _page("Invoice no longer payable",
            '<p>This payment quote has expired or is no longer awaiting payment. '
            'Do not send TRX to an expired quote.</p>'
            '<p>If you already paid, do not pay again. Check payment status in '
            '<a href="/commerce/trx-easy/purchases/">My TRX purchases</a> '
            'or contact support with your order number.</p>'
            '<p>For a fresh quote, open the product again from the '
            '<a href="/store/">store</a>.</p>')'''


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def transform(text):
    if text.count(NEW) == 1 and OLD not in text:
        return text, False
    if text.count(OLD) != 1 or NEW in text or "def _show_invoice(" not in text:
        raise RuntimeError("UNEXPECTED_LIVE_INVOICE_HANDLER")
    if "render_one_tap_invoice(invoice," not in text:
        raise RuntimeError("LIVE_INVOICE_RENDERER_MISSING")
    changed = text.replace(OLD, NEW, 1)
    compile(changed, str(TARGET), "exec")
    return changed, True


def selftest():
    fake = "def _show_invoice(request, invoice_id):\n" + OLD + "\n    render_one_tap_invoice(invoice,\n        status_path=\"x\")\n"
    new, changed = transform(fake)
    assert changed and "raise Http404(\"This invoice is no longer payable\")" not in new
    assert "Do not send TRX to an expired quote" in new
    assert transform(new) == (new, False)
    for invalid in ("", fake.replace("render_one_tap_invoice(invoice,", "missing("), fake + OLD):
        try:
            transform(invalid)
        except RuntimeError:
            pass
        else:
            raise AssertionError("FAIL_OPEN_TRANSFORM")
    print("MPW_INVOICE_PATCH_SELFTEST=PASS")


def preflight():
    if os.geteuid() == 0 or not APP.is_dir() or APP.is_symlink():
        raise RuntimeError("WRONG_HOST_CONTEXT")
    if not PUBLIC.is_dir() or PUBLIC.is_symlink() or not PYTHON.is_file():
        raise RuntimeError("MISSING_MOJPLAYWIN_APP")
    passenger = PUBLIC / "passenger_wsgi.py"
    if passenger.is_symlink() or "Saeit-staging" not in passenger.read_text("utf-8", "replace"):
        raise RuntimeError("WRONG_PASSENGER_BINDING")
    if TARGET.is_symlink() or not TARGET.is_file() or TARGET.parent.is_symlink():
        raise RuntimeError("WRONG_TARGET")
    BACKUP.mkdir(mode=0o700, parents=True, exist_ok=True)
    if BACKUP.is_symlink() or not BACKUP.is_dir():
        raise RuntimeError("UNSAFE_BACKUP_DIR")
    os.chmod(BACKUP, 0o700)


def atomic_replace(target, raw, mode):
    fd, temp = tempfile.mkstemp(prefix=".invoice-expiry-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        if target.is_symlink():
            raise RuntimeError("TARGET_BECAME_SYMLINK")
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def create_private(path, raw):
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, 0o600)


def restart():
    folder = APP / "tmp"
    if not folder.is_dir() or folder.is_symlink():
        raise RuntimeError("PASSENGER_RESTART_DIR_UNSAFE")
    target = folder / "restart.txt"
    if target.is_symlink():
        raise RuntimeError("PASSENGER_RESTART_SYMLINK")
    target.touch(exist_ok=True)


def probe_new_source():
    script = '''
import os,sys
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
os.chdir("/home/zomorod2/Saeit-staging")
sys.path.insert(0,os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.test import RequestFactory
from django.utils import timezone
from services import mpw_trx_commercial_web as m
req=RequestFactory().get("/commerce/trx-easy/invoice/9/",secure=True,HTTP_HOST="mojplaywin.com")
expired=SimpleNamespace(expires_at=timezone.now()-timedelta(minutes=2))
intent=SimpleNamespace(status=m.WAITING)
with patch.object(m,"_ensure_live"),patch.object(m,"_get_owner_invoice",return_value=intent),patch.object(m,"_decode",return_value=expired):
    resp=m._show_invoice(req,9)
assert resp.status_code==200
assert b"Do not send TRX" in resp.content
assert b"/commerce/trx-easy/purchases/" in resp.content
assert b"recipient" not in resp.content.lower()
'''
    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    run=subprocess.run([str(PYTHON), "-B", "-c", script], cwd=str(APP), env=env,
                       capture_output=True, text=True, timeout=35)
    if run.returncode != 0:
        raise RuntimeError("ISOLATED_EXPIRED_INVOICE_RENDER_FAILED")


def perform(action, run_id):
    if not re.fullmatch(r"[0-9]{5,20}", run_id):
        raise RuntimeError("RUN_ID_INVALID")
    preflight()
    with (BACKUP / "lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        original_path = BACKUP / (run_id + ".original.py")
        receipt_path = BACKUP / (run_id + ".receipt.json")
        raw = TARGET.read_bytes()
        mode = stat.S_IMODE(TARGET.stat().st_mode)
        if action == "apply":
            original = raw.decode("utf-8")
            result, changed = transform(original)
            if not changed:
                print("MPW_INVOICE_PATCH_ALREADY_PRESENT=TRUE")
                return
            changed_bytes = result.encode("utf-8")
            receipt = dict(run_id=run_id, original_sha256=digest(raw),
                           patched_sha256=digest(changed_bytes), target="mpw_trx_commercial_web.py")
            create_private(original_path, raw)
            create_private(receipt_path, (json.dumps(receipt, sort_keys=True)+"\n").encode("utf-8"))
            atomic_replace(TARGET, changed_bytes, mode)
            try:
                if digest(TARGET.read_bytes()) != receipt["patched_sha256"]:
                    raise RuntimeError("WRITE_VERIFY_FAILED")
                probe_new_source()
                restart()
            except BaseException:
                if digest(TARGET.read_bytes()) == receipt["patched_sha256"]:
                    atomic_replace(TARGET, raw, mode)
                raise
            print("MPW_INVOICE_PATCH_APPLIED=PASS; ORDERS_WRITTEN=0; RIGHTS_FLAGS_WRITTEN=0")
        elif action == "rollback":
            if not receipt_path.is_file() or not original_path.is_file():
                print("MPW_INVOICE_PATCH_ROLLBACK_NO_RECEIPT=TRUE")
                return
            receipt = json.loads(receipt_path.read_text())
            saved = original_path.read_bytes()
            if receipt.get("run_id") != run_id or digest(saved) != receipt.get("original_sha256"):
                raise RuntimeError("ROLLBACK_RECEIPT_INVALID")
            if digest(raw) != receipt.get("patched_sha256"):
                raise RuntimeError("REFUSE_ROLLBACK_OVER_NEWER_VERSION")
            atomic_replace(TARGET, saved, mode)
            restart()
            print("MPW_INVOICE_PATCH_ROLLED_BACK=PASS")
        else:
            raise RuntimeError("ACTION_UNKNOWN")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        selftest()
    elif len(sys.argv) == 3 and sys.argv[1] in ("apply", "rollback"):
        perform(sys.argv[1], sys.argv[2])
    else:
        raise SystemExit("usage: script.py --selftest | apply RUN_ID | rollback RUN_ID")
