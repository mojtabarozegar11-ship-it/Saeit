#!/usr/bin/env python3
"""Guarded, reversible correction of a misleading production checkout label.

Changes exactly two strings in one cPanel template. No database, checkout,
email, payment, product, invoice or customer state is accessed or modified.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tempfile


ACCOUNT = "zomorod2"
ROOT = Path("/home/zomorod2/Saeit-staging")
PUBLIC = Path("/home/zomorod2/mojplaywin.com")
TARGET = ROOT / "mpw_commerce/templates/mpw_commerce/product_checkout.html"
RESTART = PUBLIC / "tmp/restart.txt"
BACKUPS = Path("/home/zomorod2/.local/share/mpw-checkout-truth-copy-20261106")

OLD_LABEL = b"Email for invoice, payment receipt and download"
NEW_LABEL = b"Email address for your order (no account required)"
OLD_BUTTON = b"Email my invoice and pay with TRX"
NEW_BUTTON = b"Create my TRX payment invoice"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fail(code):
    raise RuntimeError("MPW_CHECKOUT_TRUTH_ABORT:" + code)


def validate_target():
    if pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT:
        fail("WRONG_ACCOUNT")
    for path in (ROOT, ROOT / "mpw_commerce", ROOT / "mpw_commerce/templates",
                 TARGET.parent, PUBLIC, RESTART.parent):
        if path.is_symlink() or not path.is_dir() or path.resolve() != path:
            fail("INVALID_APP_ROOT")
    if TARGET.is_symlink() or not TARGET.is_file():
        fail("INVALID_CHECKOUT_TEMPLATE")
    info = TARGET.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_nlink != 1 or not 0 < info.st_size <= 180_000):
        fail("INVALID_TEMPLATE_OWNER_OR_SIZE")
    wsgi = PUBLIC / "passenger_wsgi.py"
    if wsgi.is_symlink() or not wsgi.is_file():
        fail("INVALID_PASSENGER_ENTRY")
    if b"APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_bytes():
        fail("WRONG_PASSENGER_APP")
    if RESTART.is_symlink():
        fail("UNSAFE_PASSENGER_RESTART")
    return info


def rewritten(before):
    labels = (OLD_LABEL, OLD_BUTTON, NEW_LABEL, NEW_BUTTON)
    counts = tuple(before.count(item) for item in labels)
    if counts == (0, 0, 1, 1):
        return before, False
    if counts != (1, 1, 0, 0):
        fail("COPY_NOT_EXACT_OR_PARTIALLY_CHANGED")
    i = before.index(OLD_LABEL)
    j = before.index(OLD_BUTTON)
    if not 0 < j - i < 1600:
        fail("COPY_OUTSIDE_CHECKOUT_FORM")
    if (b"<form" not in before[:j] or b"</form>" not in before[j:]
            or b"name=\"email\"" not in before[i:j]):
        fail("CHECKOUT_FORM_CONTEXT_CHANGED")
    after = before.replace(OLD_LABEL, NEW_LABEL, 1).replace(OLD_BUTTON, NEW_BUTTON, 1)
    if after == before or after.count(OLD_LABEL) or after.count(OLD_BUTTON):
        fail("UNEXPECTED_DIFF")
    return after, True


def write_atomically(path, data, expected):
    if sha(path.read_bytes()) != expected:
        fail("CONCURRENT_CHECKOUT_EDIT")
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, temp = tempfile.mkstemp(prefix=".mpw-truth-copy-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def restart():
    if RESTART.is_symlink():
        fail("UNSAFE_RESTART")
    RESTART.touch()


def save_backup(run_id, original):
    if BACKUPS.is_symlink():
        fail("UNSAFE_BACKUP_ROOT")
    BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (BACKUPS.stat().st_uid != os.geteuid()
            or stat.S_IMODE(BACKUPS.stat().st_mode) != 0o700):
        fail("UNSAFE_BACKUP_PERMISSIONS")
    folder = BACKUPS / run_id
    folder.mkdir(mode=0o700)
    path = folder / "product_checkout.before.html"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())
    return folder


def check_template_syntax(source):
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.template import engines
    engines["django"].from_string(source.decode("utf-8"))


def command(operation, run_id=None):
    validate_target()
    before = TARGET.read_bytes()
    after, should_change = rewritten(before)
    if operation == "preflight":
        if should_change:
            check_template_syntax(after)
        print("MPW_CHECKOUT_TRUTH_PREFLIGHT=" + ("READY" if should_change else "ALREADY_CORRECT")
              + ";SHA256=" + sha(before) + ";NO_CHANGE=TRUE", flush=True)
        return
    if operation == "verify":
        if should_change or after.count(NEW_LABEL) != 1 or after.count(NEW_BUTTON) != 1:
            fail("COPY_NOT_PUBLISHED")
        print("MPW_CHECKOUT_TRUTH_VERIFY=PASS;NO_EMAIL=TRUE;NO_PAYMENT=TRUE", flush=True)
        return
    if operation != "publish" or not run_id or not re.fullmatch(r"[0-9]{7,20}", run_id):
        fail("INVALID_OPERATION")
    if not should_change:
        print("MPW_CHECKOUT_TRUTH_PUBLISH=ALREADY_CORRECT;NO_CHANGE=TRUE", flush=True)
        return
    check_template_syntax(after)
    folder = save_backup(run_id, before)
    changed = False
    try:
        write_atomically(TARGET, after, sha(before))
        changed = True
        if TARGET.read_bytes() != after:
            fail("POST_WRITE_MISMATCH")
        restart()
    except BaseException:
        if changed and TARGET.read_bytes() == after:
            write_atomically(TARGET, before, sha(after))
            restart()
        raise
    print(json.dumps({"result": "MPW_CHECKOUT_TRUTH_PUBLISHED",
                      "backup_run": folder.name, "old_sha256": sha(before),
                      "new_sha256": sha(after), "email_change": False,
                      "payment_change": False, "database_change": False}, sort_keys=True), flush=True)


def selftest():
    fixture = (b'<form method="post"><label>' + OLD_LABEL + b'</label>'
               b'<input name="email" type="email"><button>' + OLD_BUTTON
               + b'</button></form><div>other text</div>')
    after, changed = rewritten(fixture)
    assert changed and after.endswith(b'<div>other text</div>')
    assert NEW_LABEL in after and NEW_BUTTON in after
    assert rewritten(after) == (after, False)
    for invalid in (fixture.replace(OLD_BUTTON, b"Wrong"),
                    fixture.replace(b'name="email"', b'name="wallet"'),
                    fixture + OLD_LABEL):
        try:
            rewritten(invalid)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Rejected checkout fixture was accepted")
    print("MPW_CHECKOUT_TRUTH_SELFTEST=PASS", flush=True)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 2 and sys.argv[1] in ("preflight", "verify"):
        command(sys.argv[1])
    elif len(sys.argv) == 3 and sys.argv[1] == "publish":
        command("publish", sys.argv[2])
    else:
        fail("OPERATION_REQUIRED")
