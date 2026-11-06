#!/usr/bin/env python3
"""Add the existing 879 detail-page link to its live MojPlayWin store card.

One exact, reversible template insertion. Never touches checkout, price,
payments, buyer records or email. Requires a precise known live template hash.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat

from mpw_store_demo_guarded_release_20261106 import (
    TARGET, BACKUPS as ROOT_BACKUPS, atomic_replace, checked_file,
    fail, guard_host, restart, sha,
)

SOURCE_SHA = "6732ed6199e871fedeb686705e2234a48e59166ef9af874398a73747e7866070"
BACKUPS = ROOT_BACKUPS.parent / "mpw-store-product879-details-releases"
BUY = (b'<a class="mpw-shop-secondary" href="/commerce/book/879/" '
       b'aria-label="Buy Atelier Interior website kit with TRX">'
       b'Buy securely with TRX <span aria-hidden="true">&nbsp;\xe2\x86\x97</span></a>')
DETAIL = (b'<a class="mpw-product-demo" href="/store/product/879/">'
          b'Read full website kit details</a>')
CONTEXT = (b'mpw-product--atelier', b'mpw-product-879-title',
           b'atelier-interior-kit.webp')


def reviewed(data: bytes) -> bytes:
    if data.count(BUY) != 1 or DETAIL in data:
        fail("PRODUCT879_ANCHOR_CHANGED")
    index = data.index(BUY)
    start = data.rfind(b'<article', 0, index)
    end = data.find(b'</article>', index)
    if start < 0 or end < 0 or not all(x in data[start:end] for x in CONTEXT):
        fail("PRODUCT879_CONTEXT_MISMATCH")
    if b'href="/store/product/879/"' in data[start:end]:
        fail("PRODUCT879_DETAILS_ALREADY_LINKED")
    result = data.replace(BUY, BUY + DETAIL, 1)
    if result.replace(BUY + DETAIL, BUY, 1) != data:
        fail("UNEXPECTED_SOURCE_CHANGE")
    return result


def current():
    guard_host()
    data = checked_file(TARGET)
    if DETAIL in data:
        if data.count(DETAIL) != 1 or data.count(BUY) != 1:
            fail("PARTIALLY_UPDATED")
        return "ALREADY_UPDATED", data
    if sha(data) != SOURCE_SHA:
        fail("LIVE_TEMPLATE_HASH_CHANGED")
    reviewed(data)
    return "READY", data


def preflight():
    state, data = current()
    print("MPW_PRODUCT879_DETAILS_PREFLIGHT=" + state + ";SHA256=" + sha(data)
          + ";NO_CHANGE=TRUE", flush=True)


def publish(run_id: str):
    if not re.fullmatch(r"[0-9]{7,20}", run_id):
        fail("INVALID_RUN_ID")
    state, before = current()
    if state == "ALREADY_UPDATED":
        print("MPW_PRODUCT879_DETAILS_PUBLISH=ALREADY_UPDATED", flush=True)
        return
    after = reviewed(before)
    if BACKUPS.is_symlink():
        fail("BACKUP_SYMLINK")
    BACKUPS.mkdir(parents=True, mode=0o700, exist_ok=True)
    mode = stat.S_IMODE(BACKUPS.stat().st_mode)
    if BACKUPS.stat().st_uid != os.geteuid() or mode != 0o700:
        fail("UNSAFE_BACKUP_ROOT")
    folder = BACKUPS / run_id
    folder.mkdir(mode=0o700)
    backup = folder / "store.before.html"
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as fp:
        fp.write(before)
        fp.flush()
        os.fsync(fp.fileno())
    changed = False
    try:
        atomic_replace(TARGET, after, sha(before))
        changed = True
        if checked_file(TARGET) != after:
            fail("POST_WRITE_INCONSISTENT")
        restart()
    except BaseException:
        if changed and checked_file(TARGET) == after:
            atomic_replace(TARGET, before, sha(after))
            restart()
        raise
    print(json.dumps({"result": "MPW_PRODUCT879_DETAILS_PUBLISHED",
                      "backup_run": run_id, "old_sha256": sha(before),
                      "new_sha256": sha(after), "checkout_change": False,
                      "price_change": False, "payment_change": False,
                      "email_change": False, "buyer_data_change": False},
                     sort_keys=True), flush=True)


def verify(run_id: str):
    if not re.fullmatch(r"[0-9]{7,20}", run_id):
        fail("INVALID_RUN_ID")
    guard_host()
    data = checked_file(TARGET)
    if data.count(DETAIL) != 1 or data.count(BUY) != 1:
        fail("DETAIL_LINK_MISSING")
    backup = BACKUPS / run_id / "store.before.html"
    if backup.is_file() and reviewed(checked_file(backup)) != data:
        fail("LIVE_DIFF_UNEXPECTED")
    print("MPW_PRODUCT879_DETAILS_VERIFY=PASS;NO_EMAIL=TRUE;NO_PAYMENT=TRUE", flush=True)


def selftest():
    valid = (b'<article class="mpw-product--atelier">'
             b'<h3 id="mpw-product-879-title">Atelier</h3>'
             b'<img src="atelier-interior-kit.webp">' + BUY +
             b'</article><article>Other product</article>')
    assert reviewed(valid) == valid.replace(BUY, BUY + DETAIL, 1)
    for invalid in (valid + BUY, valid + DETAIL,
                    valid.replace(CONTEXT[0], b'not-atelier'),
                    valid.replace(CONTEXT[2], b'not-an-image')):
        try:
            reviewed(invalid)
        except RuntimeError:
            continue
        raise AssertionError("unsafe source was accepted")
    print("MPW_PRODUCT879_DETAILS_SELFTEST=PASS")


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
