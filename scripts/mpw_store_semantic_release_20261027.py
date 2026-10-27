#!/usr/bin/env python3
"""MojPlayWin STORE TEMPLATE ONLY: guarded one-landmark repair and rollback.

Never modifies Django code, payment, .htaccess, sub-sites or customer data.
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
STORE = APP / "core/templates/mojplaywin/store.html"
BASE = APP / "core/templates/mojplaywin/site_base.html"
WSGI = SITE / "passenger_wsgi.py"
OLD_SHA = "9e8fadc16025571383188aad305d76281b41c059ce9ffd1e0fa043a9b1d5690d"
OLD_START = b'<main class="mpw-shop">'
NEW_START = b'<div class="mpw-shop">'
OLD_END = b'</div></main>\n{% endblock %}'
NEW_END = b'</div></div>\n{% endblock %}'


def digest(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def validate():
    for p in (STORE, BASE, WSGI, SITE / ".htaccess"):
        if not p.is_file() or p.is_symlink():
            raise RuntimeError("EXPECTED_REGULAR_FILE_MISSING:" + str(p))
    for p in (SITE, APP, STORE.parent):
        if not p.is_dir() or p.is_symlink():
            raise RuntimeError("UNSAFE_DIRECTORY:" + str(p))
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8", "replace"):
        raise RuntimeError("UNEXPECTED_WSGI_BINDING")
    shell = BASE.read_text("utf8", "replace")
    if shell.count('<main id="main-content"') != 1 or shell.count("</main>") != 1:
        raise RuntimeError("UNEXPECTED_SHARED_BASE_MAIN")


def patch(data):
    if NEW_START in data and NEW_END in data and OLD_START not in data and OLD_END not in data:
        return data
    if (data.count(OLD_START) != 1 or data.count(OLD_END) != 1
        or data.count(b"{% endblock %}") < 1):
        raise RuntimeError("STORE_TEMPLATE_SEMANTIC_DRIFT")
    if digest(data) != OLD_SHA:
        raise RuntimeError("STORE_TEMPLATE_BASELINE_HASH_DRIFT:" + digest(data))
    fixed = data.replace(OLD_START, NEW_START, 1).replace(OLD_END, NEW_END, 1)
    if fixed.count(NEW_START) != 1 or fixed.count(NEW_END) != 1 or OLD_START in fixed:
        raise RuntimeError("STORE_PATCH_FAILED")
    for marker in (b"/store/product/72/", b"/store/product/225/", b"/store/product/879/"):
        if data.count(marker) != fixed.count(marker):
            raise RuntimeError("PRODUCT_LINK_CHANGED")
    return fixed


def backup(run):
    if not re.fullmatch(r"[0-9]{6,20}", run):
        raise RuntimeError("INVALID_RUN_ID")
    return ROOT / (".mpw-store-semantics-20261027-" + run)


def atomic_write(path, data):
    fd, name = tempfile.mkstemp(dir=str(path.parent), prefix=".mpw-store-semantic-")
    try:
        os.fchmod(fd, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def audit():
    validate()
    raw = STORE.read_bytes()
    print("MPW_STORE_SEMANTIC_AUDIT=" + json.dumps({
        "live_sha256": digest(raw),
        "expected_old_sha256": OLD_SHA,
        "old_main": raw.count(OLD_START),
        "new_div": raw.count(NEW_START),
        "old_tail": raw.count(OLD_END),
        "new_tail": raw.count(NEW_END),
        "bytes": len(raw),
    }, sort_keys=True))


def publish(run):
    validate()
    raw = STORE.read_bytes()
    fixed = patch(raw)
    if fixed == raw:
        print("MPW_STORE_SEMANTIC_ALREADY_APPLIED")
        return
    state = backup(run)
    if state.exists() or state.is_symlink():
        raise RuntimeError("BACKUP_ALREADY_EXISTS")
    state.mkdir(mode=0o700)
    (state / "store.before").write_bytes(raw)
    (state / "manifest.json").write_text(json.dumps({
        "run": run, "original": digest(raw), "updated": digest(fixed)
    }, sort_keys=True))
    if digest(STORE.read_bytes()) != digest(raw):
        raise RuntimeError("CONCURRENT_STORE_CHANGE")
    try:
        atomic_write(STORE, fixed)
        if digest(STORE.read_bytes()) != digest(fixed):
            raise RuntimeError("STORE_ATOMIC_POSTWRITE_FAILED")
    except BaseException:
        if digest(STORE.read_bytes()) == digest(fixed):
            atomic_write(STORE, raw)
        raise
    print("MPW_STORE_SEMANTIC_PUBLISHED=" + digest(fixed))


def rollback(run):
    validate()
    state = backup(run)
    if not state.is_dir() or state.is_symlink():
        print("MPW_STORE_NO_MATCHING_BACKUP")
        return
    manifest = json.loads((state / "manifest.json").read_text())
    raw = (state / "store.before").read_bytes()
    if manifest.get("run") != run or digest(raw) != manifest.get("original"):
        raise RuntimeError("BACKUP_INTEGRITY_FAILURE")
    if digest(STORE.read_bytes()) != manifest.get("updated"):
        raise RuntimeError("REFUSE_ROLLBACK_CONCURRENT_EDIT")
    atomic_write(STORE, raw)
    print("MPW_STORE_SEMANTIC_ROLLBACK_VERIFIED")


def refresh():
    validate()
    # Passenger's pre-existing application marker only: no app/source edits.
    for root in (APP, SITE):
        directory = root / "tmp"
        if directory.is_symlink():
            raise RuntimeError("UNSAFE_RESTART_DIRECTORY")
        directory.mkdir(exist_ok=True)
        marker = directory / "restart.txt"
        if marker.is_symlink() or (marker.exists() and not marker.is_file()):
            raise RuntimeError("UNSAFE_RESTART_MARKER")
        marker.touch()
    print("MPW_STORE_TEMPLATE_CACHE_REFRESH_REQUESTED")


def selftest():
    original = (b'{% block content %}\n<main class="mpw-shop"><div>'
        + b'<a href="/store/product/72/">a</a><a href="/store/product/225/">b</a>'
        + b'<a href="/store/product/879/">c</a></div></main>\n{% endblock %}')
    assert original.count(OLD_START) == 1
    assert original.replace(OLD_START, NEW_START).replace(OLD_END, NEW_END).count(NEW_START) == 1
    assert OLD_SHA and len(OLD_SHA) == 64
    print("MPW_STORE_SEMANTIC_SELFTEST=PASS")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in ("audit", "refresh", "selftest"):
        {"audit": audit, "refresh": refresh, "selftest": selftest}[sys.argv[1]]()
    elif len(sys.argv) == 3 and sys.argv[1] in ("publish", "rollback"):
        (publish if sys.argv[1] == "publish" else rollback)(sys.argv[2])
    else:
        raise SystemExit("usage: audit | refresh | selftest | publish RUN_ID | rollback RUN_ID")
