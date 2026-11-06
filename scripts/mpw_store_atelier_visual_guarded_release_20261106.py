#!/usr/bin/env python3
"""Safely show the already-public Atelier artwork on the MojPlayWin store card.

Single exact-span HTML edit, backed up and rolled back if restart/verification
fails. No checkout, payment, customer, email, static asset, or price mutation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat

from mpw_store_demo_guarded_release_20261106 import (
    BACKUPS as DEMO_BACKUPS,
    TARGET,
    atomic_replace,
    checked_file,
    fail,
    guard_host,
    restart,
    sha,
)

BACKUPS = DEMO_BACKUPS.parent / "mpw-store-atelier-visual-releases"
OLD = (
    '<div class="mpw-product-visual" aria-hidden="true"><div class="mpw-site-preview">'
    '<div class="mpw-site-preview-bar"></div><div class="mpw-site-preview-content">'
    '<span></span><span></span></div></div></div>'
).encode("utf-8")
NEW = (
    '<div class="mpw-product-visual"><img class="mpw-product-image" '
    'src="/static/site/mojplaywin-products/atelier-interior-kit.webp" '
    'alt="Atelier Interior promotional interior-design artwork (not a kit screenshot)" '
    'width="720" height="900" loading="lazy" decoding="async"></div>'
).encode("utf-8")
CONTEXT = (b'mpw-product--atelier', b'mpw-product-879-title')


def reviewed(data: bytes) -> bytes:
    if data.count(OLD) != 1 or data.count(NEW) != 0:
        fail("VISUAL_SOURCE_NOT_UNIQUE_OR_CHANGED")
    i = data.index(OLD)
    start = data.rfind(b'<article', 0, i)
    end = data.find(b'</article>', i)
    if start < 0 or end < 0 or not all(token in data[start:end] for token in CONTEXT):
        fail("VISUAL_OUTSIDE_ATELIER_PRODUCT")
    if b'atelier-interior-kit.webp' in data[start:end]:
        fail("ARTWORK_ALREADY_PRESENT_IN_PRODUCT")
    after = data.replace(OLD, NEW, 1)
    if after.replace(NEW, OLD, 1) != data:
        fail("UNEXPECTED_VISUAL_DIFF")
    return after


def inspect_current() -> tuple[str, bytes]:
    guard_host()
    data = checked_file(TARGET)
    if data.count(NEW) == 1 and data.count(OLD) == 0:
        return "ALREADY_UPDATED", data
    reviewed(data)
    return "READY", data


def preflight() -> None:
    result, current = inspect_current()
    print("MPW_ATELIER_VISUAL_PREFLIGHT=" + result + ";NO_CHANGE=TRUE;SHA256=" + sha(current), flush=True)


def publish(run_id: str) -> None:
    if not re.fullmatch(r"[0-9]{7,20}", run_id):
        fail("BAD_RUN_ID")
    state, before = inspect_current()
    if state == "ALREADY_UPDATED":
        print("MPW_ATELIER_VISUAL_PUBLISH=ALREADY_UPDATED;NO_CHANGE=TRUE", flush=True)
        return
    after = reviewed(before)
    if BACKUPS.is_symlink():
        fail("BACKUP_ROOT_SYMLINK")
    BACKUPS.mkdir(parents=True, mode=0o700, exist_ok=True)
    st = BACKUPS.stat()
    if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        fail("BAD_BACKUP_ROOT_PERMISSIONS")
    folder = BACKUPS / run_id
    folder.mkdir(mode=0o700)
    backup = folder / "store.before.html"
    fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(before)
        stream.flush()
        os.fsync(stream.fileno())
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
    print(json.dumps({
        "result": "MPW_ATELIER_VISUAL_PUBLISHED",
        "source_sha256": sha(before),
        "published_sha256": sha(after),
        "backup_run": run_id,
        "price_change": False,
        "payment_change": False,
        "email_change": False,
        "customer_change": False,
    }, sort_keys=True), flush=True)


def verify(run_id: str) -> None:
    if not re.fullmatch(r"[0-9]{7,20}", run_id):
        fail("BAD_RUN_ID")
    guard_host()
    current = checked_file(TARGET)
    if current.count(NEW) != 1 or current.count(OLD) != 0:
        fail("PUBLISHED_VISUAL_MISSING")
    backup = BACKUPS / run_id / "store.before.html"
    if backup.is_file() and current != reviewed(checked_file(backup)):
        fail("PUBLISHED_DIFF_FROM_BACKUP")
    print("MPW_ATELIER_VISUAL_VERIFY=PASS;NO_PAYMENT=TRUE;NO_EMAIL=TRUE", flush=True)


def selftest() -> None:
    valid = (b'<article class="mpw-product--atelier"><h3 id="mpw-product-879-title">'
             b'Atelier</h3>' + OLD + b'</article><article>untouched</article>')
    changed = reviewed(valid)
    assert changed == valid.replace(OLD, NEW, 1)
    assert changed.count(NEW) == 1 and changed.count(OLD) == 0
    for broken in (
        valid.replace(CONTEXT[0], b'other-product'),
        valid.replace(CONTEXT[1], b'other-title'),
        valid + OLD,
        changed,
    ):
        try:
            reviewed(broken)
        except RuntimeError:
            pass
        else:
            raise AssertionError("unsafe source accepted")
    print("MPW_ATELIER_VISUAL_SELFTEST=PASS")


if __name__ == "__main__":
    import sys
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
