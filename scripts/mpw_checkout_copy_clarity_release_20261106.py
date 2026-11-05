#!/usr/bin/env python3
"""Guarded, reversible production checkout truth-in-copy correction.

No checkout, payment, invoice, delivery, recovery route, email, or database row
is created or modified. Only one literal text fragment in a pinned live
checkout template is changed, with an outside-webroot backup and rollback.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tempfile

ROOT = Path("/home/zomorod2/Saeit-staging")
RELATIVE = "mpw_commerce/templates/mpw_commerce/product_checkout.html"
EXPECTED_OLD_SHA256 = "28e8f7475f17acd49b021037deb05393aa949f0ecdcb1d50dbabbc4955dc2630"
BACKUPS = Path("/home/zomorod2/.local/share/mpw-checkout-copy-clarity-20261106")
OLD = "to recover your download"
NEW = ("to reopen your download from this original browser session. "
       "Email recovery on another device is not yet available")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validated_live_target():
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_USER")
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("INVALID_APP_ROOT")
    path = ROOT / RELATIVE
    if (path.is_symlink() or not path.is_file() or
            not path.resolve().is_relative_to(ROOT.resolve())):
        raise RuntimeError("INVALID_TEMPLATE_PATH")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size > 180000:
        raise RuntimeError("INVALID_TEMPLATE_TYPE")
    return path, st


def restart():
    marker = ROOT / "tmp/restart.txt"
    if marker.is_symlink() or not marker.parent.is_dir():
        raise RuntimeError("INVALID_RESTART_MARKER")
    marker.touch()


def replace_atomically(path, data, mode):
    fd, temporary = tempfile.mkstemp(prefix=".mpw-copy-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "publish":
        raise RuntimeError("INVALID_OPERATION")
    run_id = sys.argv[2]
    if not re.fullmatch(r"[0-9]{8,15}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    path, st = validated_live_target()
    old_data = path.read_bytes()
    if digest(old_data) != EXPECTED_OLD_SHA256:
        raise RuntimeError("PINNED_TEMPLATE_SHA_MISMATCH")
    source = old_data.decode("utf-8")
    if source.count(OLD) != 1 or NEW in source:
        raise RuntimeError("EXACT_CHECKOUT_COPY_NOT_FOUND")
    replaced = source.replace(OLD, NEW, 1)
    new_data = replaced.encode("utf-8")
    if len(new_data) > 180000 or digest(new_data) == digest(old_data):
        raise RuntimeError("INVALID_TEMPLATE_MODIFICATION")

    # Require the current Django engine to parse the new template before write.
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.template import engines
    engines["django"].from_string(replaced)

    if BACKUPS.is_symlink():
        raise RuntimeError("INVALID_BACKUP_ROOT")
    BACKUPS.mkdir(parents=True, mode=0o700, exist_ok=True)
    if stat.S_IMODE(BACKUPS.stat().st_mode) & 0o077:
        raise RuntimeError("BACKUP_PERMISSIONS_NOT_PRIVATE")
    backup = BACKUPS / ("checkout-before-" + run_id + ".html")
    with backup.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(old_data)
        handle.flush()
        os.fsync(handle.fileno())

    updated = False
    try:
        # Fail closed on unrelated edits between preflight and file replacement.
        path, fresh = validated_live_target()
        if digest(path.read_bytes()) != EXPECTED_OLD_SHA256:
            raise RuntimeError("TEMPLATE_CHANGED_DURING_PREFLIGHT")
        replace_atomically(path, new_data, stat.S_IMODE(fresh.st_mode))
        updated = True
        restart()
        if digest(path.read_bytes()) != digest(new_data):
            raise RuntimeError("POST_WRITE_HASH_MISMATCH")
        print("MPW_CHECKOUT_COPY_CLARIFIED=PASS;BACKUP=PRIVATE;PUBLIC_RECOVERY=UNCHANGED;"
              "EMAILS_SENT=0;DB_WRITES=0;PAYMENTS=0", flush=True)
    except Exception:
        if updated:
            replace_atomically(path, old_data, stat.S_IMODE(st.st_mode))
            restart()
            print("MPW_CHECKOUT_COPY_ROLLBACK=PERFORMED", flush=True)
        raise


if __name__ == "__main__":
    main()
