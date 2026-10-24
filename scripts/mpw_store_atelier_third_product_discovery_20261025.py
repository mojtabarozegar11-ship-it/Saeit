#!/usr/bin/env python3
"""Add a discoverable, verified third product to MojPlayWin's active store.

Single isolated Django template edit in Saeit-staging. No database, payments,
views, shared site, Passenger, subsite, social account, or customer data writes.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys
import tempfile

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
STORE = APP / "core/templates/mojplaywin/store.html"
BACKUPS = HOME / ".mpw-store-atelier-discovery-20261025"
ANCHOR = "<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_START -->"
MARKER = 'id="mpw-atelier-discovery-20261025"'
BLOCK = """<section class="mpw-store-section" id="mpw-atelier-discovery-20261025" aria-labelledby="mpw-atelier-title" style="border:1px solid rgba(212,175,55,.65);border-radius:18px;padding:clamp(18px,3vw,34px);background:linear-gradient(125deg,#111a24,#10100f);margin-top:32px">
<span class="mpw-store-label">NEW · DIGITAL WEBSITE KIT</span>
<h2 id="mpw-atelier-title">Atelier Interior — Client-Ready Website Kit</h2>
<p style="max-width:760px;color:#d7d0c2;line-height:1.8">An editable responsive HTML, CSS and JavaScript website kit for an interior-design studio, with five original SVG illustrations, setup instructions and a non-exclusive one-site/client license. Demo photographs are not included.</p>
<p style="font-weight:800;font-size:1.45rem;color:#f0d98f">US $6.80 <span style="font-size:.82rem;font-weight:500;color:#c5bdab">· digital ZIP · order-specific TRX invoice after sign-in</span></p>
<a class="mpw-store-button" href="/store/product/879/?utm_source=mojplaywin&amp;utm_medium=storefront&amp;utm_campaign=atelier_discovery_20261025" aria-label="View Atelier Interior website kit and secure checkout">View website kit &amp; checkout →</a>
<p class="mpw-store-note" style="font-size:.84rem">Private ZIP access follows independently confirmed payment. No payment is requested on this listing card.</p>
</section>
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def guard():
    if APP.is_symlink() or not APP.is_dir() or STORE.is_symlink() or not STORE.is_file():
        raise RuntimeError("ACTIVE_ISOLATED_STORE_PATH_INVALID")
    p = HOME / "mojplaywin.com/passenger_wsgi.py"
    if p.is_symlink() or not p.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in p.read_text("utf-8", "replace"):
        raise RuntimeError("ACTIVE_MOJPLAYWIN_RUNTIME_NOT_VERIFIED")
    if not (APP / "config/settings.py").is_file():
        raise RuntimeError("MISSING_APP_IDENTITY")


def patch(old):
    s = old.decode("utf-8")
    if len(old) < 4000 or len(old) > 150000:
        raise RuntimeError("UNEXPECTED_TEMPLATE_SIZE")
    if s.count(ANCHOR) != 1 or MARKER in s:
        raise RuntimeError("STORE_ANCHOR_DRIFT_OR_DUPLICATE")
    for required in ('id="catalog"', 'id="mpw-original-books"', '/store/product/72/', '/store/product/225/'):
        if required not in s:
            raise RuntimeError("STORE_PROTECTED_SECTION_MISSING")
    new = s.replace(ANCHOR, BLOCK + ANCHOR, 1)
    if new.replace(BLOCK, "", 1) != s or new.count(MARKER) != 1:
        raise RuntimeError("PATCH_NOT_EXACT")
    return new.encode("utf-8")


def atomic(data):
    mode = stat.S_IMODE(STORE.stat().st_mode)
    fd, tmp = tempfile.mkstemp(prefix=".mpw-atelier-", dir=str(STORE.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STORE)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run(action, run_id):
    if not re.fullmatch(r"[0-9]{6,20}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    guard()
    backup = BACKUPS / run_id
    if action == "apply":
        old = STORE.read_bytes()
        new = patch(old)
        if backup.exists() or backup.is_symlink():
            raise RuntimeError("BACKUP_ALREADY_EXISTS")
        backup.mkdir(parents=True, mode=0o700)
        (backup / "store.html.bak").write_bytes(old)
        manifest = {"before": sha(old), "after": sha(new), "state": "prepared"}
        (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        if STORE.read_bytes() != old:
            raise RuntimeError("CONCURRENT_STORE_EDIT")
        atomic(new)
        if sha(STORE.read_bytes()) != manifest["after"]:
            raise RuntimeError("STORE_WRITE_MISMATCH")
        manifest["state"] = "installed"
        (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        print("ATELIER_THIRD_PRODUCT_LINK_INSTALLED_ISOLATED_STORE")
    elif action == "rollback":
        manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
        old = (backup / "store.html.bak").read_bytes()
        if sha(old) != manifest["before"] or sha(STORE.read_bytes()) != manifest["after"]:
            raise RuntimeError("ROLLBACK_REFUSED_CONCURRENT_CHANGE")
        atomic(old)
        if sha(STORE.read_bytes()) != manifest["before"]:
            raise RuntimeError("ROLLBACK_VERIFY_FAILED")
        print("ATELIER_THIRD_PRODUCT_ROLLBACK_VERIFIED")
    else:
        raise RuntimeError("UNKNOWN_ACTION")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: script.py apply|rollback RUN_ID")
    run(sys.argv[1], sys.argv[2])
