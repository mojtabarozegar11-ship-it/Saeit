#!/usr/bin/env python3
"""Safely correct the public storefront checkout explanation on cPanel.

Only one paragraph in core/templates/mojplaywin/store.html may change.
No orders, database, payments, recovery routes or emails are touched.
Publish requires the exact SHA-256 observed during a read-only audit.
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
SITE = Path("/home/zomorod2/mojplaywin.com")
STORE = ROOT / "core/templates/mojplaywin/store.html"
BACKUPS = Path("/home/zomorod2/.local/share/mpw-store-payment-copy-20261106")
RESTART = SITE / "tmp/restart.txt"

OLD = (
    b'No account is required. Checkout accepts native TRX on the TRON network only; '
    b'bank cards, USDT and other networks are not accepted. Your order invoice shows '
    b'the exact TRX amount and receiving address; network fees may apply. The private '
    b'digital file unlocks after on-chain confirmation. Send funds only to the address '
    b'shown in your live order invoice. Never send funds to an address found outside '
    b'your verified order invoice. <a href="/commerce/trx-easy/purchases/">'
    b'View your purchases and invoices</a>.'
)
NEW = (
    b'No account or wallet connection is required, but a valid purchase email must be '
    b'entered. Checkout accepts native TRX on the TRON network only; bank cards, '
    b'USDT and other networks are not accepted. Your browser displays the invoice '
    b'with the exact TRX amount and receiving address; network fees may apply. After '
    b'confirmed payment, use <a href="/commerce/trx-easy/purchases/">My TRX '
    b'purchases</a> in the original browser to access your private download. Email '
    b'receipts and recovery on another device are not yet available. Send funds only '
    b'to the address shown on your live order invoice. Never send funds to an address '
    b'found outside your verified order invoice.'
)
LANDMARK = b'<aside class="mpw-shop-payment"'
RUN_ID = re.compile(r"[0-9]{8,20}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def fail(reason):
    raise RuntimeError("MPW_STORE_COPY_ABORT:" + reason)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def rewrite(source):
    """Fail closed on drift; preserve every byte outside the payment paragraph."""
    if not 2000 <= len(source) <= 250_000 or source.count(LANDMARK) != 1:
        fail("INVALID_STORE_STRUCTURE")
    start = source.index(LANDMARK)
    end = source.find(b"</aside>", start)
    if end < start or end - start > 5000:
        fail("INVALID_PAYMENT_SECTION")
    original = source[start:end]
    old_count, new_count = source.count(OLD), source.count(NEW)
    if (old_count, new_count) == (0, 1) and NEW in original:
        return source, False
    if (old_count, new_count) != (1, 0) or OLD not in original:
        fail("UNEXPECTED_COPY_OR_DUPLICATE")
    updated = source.replace(OLD, NEW, 1)
    if source[:start] != updated[:start] or source.count(b"/commerce/book/") != updated.count(b"/commerce/book/"):
        fail("UNEXPECTED_PRODUCT_CHANGE")
    if updated.count(NEW) != 1 or updated.count(OLD):
        fail("REWRITE_CHECK_FAILED")
    return updated, True


def trusted_dir(path):
    if (path.is_symlink() or not path.is_dir() or path.resolve() != path
            or path.stat().st_uid != os.geteuid()):
        fail("UNTRUSTED_DIRECTORY:" + path.name)


def preflight():
    if pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT:
        fail("WRONG_ACCOUNT")
    for path in (ROOT, ROOT / "core", ROOT / "core/templates", STORE.parent,
                 SITE, RESTART.parent):
        trusted_dir(path)
    if (STORE.is_symlink() or not STORE.is_file() or STORE.resolve() != STORE
            or STORE.stat().st_uid != os.geteuid() or STORE.stat().st_nlink != 1
            or not 2000 <= STORE.stat().st_size <= 250_000):
        fail("UNTRUSTED_STORE_FILE")
    entry = SITE / "passenger_wsgi.py"
    if entry.is_symlink() or not entry.is_file() or entry.stat().st_uid != os.geteuid():
        fail("UNTRUSTED_PASSENGER")
    if b"APP='/home/zomorod2/Saeit-staging'" not in entry.read_bytes():
        fail("WRONG_PASSENGER_APP")
    if RESTART.is_symlink():
        fail("UNSAFE_RESTART")
    return STORE.read_bytes()


def syntax_check(source):
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.template import engines
    engines["django"].from_string(source.decode("utf-8"))


def replace_atomically(payload, expected_sha):
    if sha(preflight()) != expected_sha:
        fail("CONCURRENT_EDIT")
    fd, name = tempfile.mkstemp(dir=STORE.parent, prefix=".mpw-store-copy-")
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), stat.S_IMODE(STORE.stat().st_mode))
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, STORE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def backup(run_id, before):
    if BACKUPS.is_symlink():
        fail("UNSAFE_BACKUP_ROOT")
    BACKUPS.mkdir(parents=True, mode=0o700, exist_ok=True)
    trusted_dir(BACKUPS)
    if stat.S_IMODE(BACKUPS.stat().st_mode) != 0o700:
        fail("BACKUP_PERMISSIONS")
    folder = BACKUPS / run_id
    folder.mkdir(mode=0o700)
    with (folder / "store.before.html").open("xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(before)
        stream.flush()
        os.fsync(stream.fileno())
    return folder


def command(operation, run_id=None, expected=None):
    if operation not in ("audit", "verify", "publish", "rollback"):
        fail("UNKNOWN_OPERATION")
    current = preflight()
    changed, necessary = rewrite(current)
    if operation == "audit":
        if necessary:
            syntax_check(changed)
        print(json.dumps({"state": "READY" if necessary else "ALREADY_CORRECT",
                          "sha256": sha(current), "changed": False,
                          "payments": 0, "mail": 0}, sort_keys=True))
        return
    if operation == "verify":
        if necessary:
            fail("OLD_COPY_STILL_LIVE")
        syntax_check(current)
        print("MPW_STORE_COPY_VERIFY=PASS;PAYMENTS=0;MAIL=0")
        return
    if not run_id or not RUN_ID.fullmatch(run_id) or not expected or not SHA256.fullmatch(expected):
        fail("MISSING_EXACT_RUN_AND_SHA")
    if sha(current) != expected:
        fail("UNEXPECTED_LIVE_PREIMAGE")
    if operation == "publish":
        if not necessary:
            print("MPW_STORE_COPY_ALREADY_CORRECT")
            return
        syntax_check(changed)
        folder = backup(run_id, current)
        try:
            replace_atomically(changed, expected)
            if sha(preflight()) != sha(changed):
                fail("POSTWRITE_MISMATCH")
            RESTART.touch()
        except BaseException:
            if sha(preflight()) == sha(changed):
                replace_atomically(current, sha(changed))
                RESTART.touch()
            raise
        print("MPW_STORE_COPY_PUBLISHED=" + sha(changed) + ";BACKUP=" + folder.name)
        return
    folder = BACKUPS / run_id
    if folder.is_symlink() or not folder.is_dir():
        fail("MISSING_BACKUP")
    saved = (folder / "store.before.html")
    if (saved.is_symlink() or not saved.is_file() or saved.stat().st_uid != os.geteuid()
            or stat.S_IMODE(saved.stat().st_mode) != 0o600):
        fail("INVALID_BACKUP")
    original = saved.read_bytes()
    candidate, needed = rewrite(original)
    if not needed or sha(candidate) != expected:
        fail("BACKUP_DOES_NOT_MATCH_PUBLISHED_SHA")
    replace_atomically(original, expected)
    RESTART.touch()
    print("MPW_STORE_COPY_ROLLBACK=PASS;ORIGINAL=" + sha(original))


def selftest():
    sample = (b"X" * 2100 + LANDMARK + b"><h3>How checkout and delivery work</h3><p>"
              + OLD + b"</p></aside>" + b"Y" * 300)
    fixed, needed = rewrite(sample)
    assert needed and fixed.count(NEW) == 1 and fixed.count(OLD) == 0
    assert rewrite(fixed) == (fixed, False)
    for invalid in (sample.replace(OLD, b"Something else"), sample + OLD,
                    sample.replace(LANDMARK, b'<aside class="other"')):
        try:
            rewrite(invalid)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Unsafe source accepted")
    print("MPW_STORE_COPY_SELFTEST=PASS")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 2:
        command(sys.argv[1])
    elif len(sys.argv) == 4:
        command(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        fail("USAGE_audit_verify_publish_RUN_SHA_rollback_RUN_SHA")
