#!/usr/bin/env python3
"""One-file, rollback-capable removal of a misdirected MojPlayWin store demo link.

Never touches checkout handlers, products, price, orders, invoices, database,
payment configuration or mail. Keeps every live byte except the exact bad anchor.
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
APP = Path("/home/zomorod2/Saeit-staging")
PUBLIC = Path("/home/zomorod2/mojplaywin.com")
TARGET = APP / "core/templates/mojplaywin/store.html"
RESTART = PUBLIC / "tmp/restart.txt"
BACKUPS = Path("/home/zomorod2/.local/share/mpw-store-demo-releases")
AFTER_SHA = "a848bd267fb0751931d121c82c84db8f79577e1f912f608109105cb51ac97b09"
DEMO = ('<a class="mpw-product-demo" '
        'href="https://atelier-interior-kit-demo.mojtaba-rozegar11.chatgpt.site/" '
        'target="_blank" rel="noopener noreferrer">Open the live demo '
        '<span aria-hidden="true">↗</span></a>').encode("utf-8")
PRODUCT_CONTEXT = (b'mpw-product--atelier', b'mpw-product-879-title')


def sha(content):
    return hashlib.sha256(content).hexdigest()


def fail(code):
    raise RuntimeError("MPW_STORE_DEMO_ABORT:" + code)


def checked_file(path):
    if path.is_symlink() or path.parent.is_symlink():
        fail("SYMLINK:" + path.name)
    if not path.is_file():
        fail("MISSING:" + path.name)
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_nlink != 1:
        fail("WRONG_OWNER_OR_LINKS:" + path.name)
    return path.read_bytes()


def guard_host():
    if pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT:
        fail("WRONG_ACCOUNT")
    for path in (APP, APP / "core", APP / "core/templates",
                 TARGET.parent, PUBLIC, RESTART.parent):
        if path.is_symlink() or not path.is_dir() or path.resolve() != path:
            fail("WRONG_ROOT:" + path.name)
    wsgi = checked_file(PUBLIC / "passenger_wsgi.py").decode("utf-8", "replace")
    if "APP='/home/zomorod2/Saeit-staging'" not in wsgi:
        fail("WRONG_PASSENGER_SOURCE")
    if RESTART.is_symlink():
        fail("UNSAFE_RESTART")


def reviewed(data):
    if (data.count(DEMO) != 1 or
            data.count(b'atelier-interior-kit-demo.mojtaba-rozegar11.chatgpt.site/') != 1 or
            data.count(b'Open the live demo') != 1):
        fail("DEMO_LINK_NOT_UNIQUE_OR_CHANGED")
    # The cPanel template can contain independently edited prices and products.
    # Require the mistaken link inside the Atelier product card, but leave all
    # other live content byte-for-byte intact regardless of its source revision.
    start = data.rfind(b'<article', 0, data.index(DEMO))
    end = data.find(b'</article>', data.index(DEMO))
    if (start < 0 or end < 0 or
            not all(token in data[start:end] for token in PRODUCT_CONTEXT)):
        fail("DEMO_OUTSIDE_ATELIER_CARD")
    after = data.replace(DEMO, b"", 1)
    if len(data) - len(after) != len(DEMO) or after.count(b'Open the live demo'):
        fail("UNEXPECTED_DIFF")
    return after


def preflight():
    guard_host()
    current = checked_file(TARGET)
    if DEMO not in current and b'Open the live demo' not in current:
        print("MPW_STORE_DEMO_PREFLIGHT=ALREADY_FIXED;NO_CHANGE=TRUE")
        return
    reviewed(current)
    print("MPW_STORE_DEMO_PREFLIGHT=PASS;NO_CHANGE=TRUE;SOURCE_SHA256=" + sha(current))


def atomic_replace(path, data, expected):
    if sha(checked_file(path)) != expected:
        fail("CONCURRENT_TEMPLATE_EDIT")
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, temp = tempfile.mkstemp(prefix=".mpw-demo-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def restart():
    if RESTART.is_symlink():
        fail("UNSAFE_RESTART")
    RESTART.touch()


def publish(run_id):
    if not re.fullmatch(r"[0-9]{7,20}", run_id):
        fail("BAD_RUN_ID")
    guard_host()
    before = checked_file(TARGET)
    if DEMO not in before and b'Open the live demo' not in before:
        print("MPW_STORE_DEMO_PUBLISH=ALREADY_FIXED;NO_CHANGE=TRUE")
        return
    after = reviewed(before)
    if BACKUPS.is_symlink():
        fail("UNSAFE_BACKUP_ROOT")
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = BACKUPS.stat()
    if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        fail("UNSAFE_BACKUP_PERMISSIONS")
    folder = BACKUPS / run_id
    folder.mkdir(mode=0o700)
    backup = folder / "store.before.html"
    fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(before)
        out.flush()
        os.fsync(out.fileno())
    changed = False
    try:
        atomic_replace(TARGET, after, sha(before))
        changed = True
        if checked_file(TARGET) != after:
            fail("POST_WRITE_MISMATCH")
        restart()
    except BaseException:
        if changed and checked_file(TARGET) == after:
            atomic_replace(TARGET, before, sha(after))
            restart()
        raise
    print(json.dumps({"result": "MPW_STORE_DEMO_PUBLISHED", "backup": folder.name,
                      "source_sha256": sha(before), "published_sha256": sha(after),
                      "removed_bytes": len(DEMO), "payment_change": False,
                      "email_change": False, "customer_data_change": False},
                     sort_keys=True), flush=True)


def verify(run_id):
    if not re.fullmatch(r"[0-9]{7,20}", run_id):
        fail("BAD_RUN_ID")
    guard_host()
    current = checked_file(TARGET)
    backup = BACKUPS / run_id / "store.before.html"
    if backup.is_file():
        expected = reviewed(checked_file(backup))
        if current != expected:
            fail("VERIFY_DIFF_FROM_BACKUP")
    elif DEMO in current or b'Open the live demo' in current:
        fail("VERIFY_NOT_PUBLISHED")
    if DEMO in current or b'Open the live demo' in current:
        fail("VERIFY_NOT_PUBLISHED")
    print("MPW_STORE_DEMO_VERIFY=PASS;NO_PAYMENT=TRUE;NO_EMAIL=TRUE", flush=True)


def selftest():
    sample = b"prefix" + DEMO + b"suffix"
    assert sample.count(DEMO) == 1
    assert sample.replace(DEMO, b"", 1) == b"prefixsuffix"
    assert sha(sample) != sha(sample.replace(DEMO, b"", 1))
    live = (b'<article class="mpw-product--atelier"><h3 id="mpw-product-879-title">'
            b'Atelier</h3><p>Independent price and listing edits</p>' + DEMO +
            b'</article><article>Other product unchanged</article>')
    assert reviewed(live) == live.replace(DEMO, b"", 1)
    try:
        reviewed(b'<article>Unrelated product</article>' + live.replace(
            b'<article class="mpw-product--atelier">', b'<div>'))
    except RuntimeError as exc:
        assert "DEMO_OUTSIDE_ATELIER_CARD" in str(exc)
    else:
        raise AssertionError("foreign demo link was accepted")
    fixed_source = Path(__file__).resolve().parents[1] / "core/templates/mojplaywin/store.html"
    if fixed_source.is_file():
        fixed = fixed_source.read_bytes()
        assert sha(fixed) == AFTER_SHA
        assert DEMO not in fixed
        assert all(token in fixed for token in PRODUCT_CONTEXT)
    print("MPW_STORE_DEMO_SELFTEST=PASS")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 2 and sys.argv[1] == "preflight":
        preflight()
    elif len(sys.argv) == 3 and sys.argv[1] == "publish":
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "verify":
        verify(sys.argv[2])
    else:
        fail("OPERATION_REQUIRED")
