#!/usr/bin/env python3
"""Owner-gated, reversible cutover from the owned static /store/ fallback.

Touches only the exact fallback rule, its one-file directory, and the already
present Passenger restart marker. Never changes invoices, payments or mail.
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


HOME = Path("/home/zomorod2")
PUBLIC = HOME / "mojplaywin.com"
APP = HOME / "Saeit-staging"
BACKUP_BASE = HOME / ".backups/mpw-store-dynamic-cutover"
FALLBACK_BLOCK = (
    b"# MPW_STATIC_STORE_FALLBACK_V1\n"
    b"RewriteEngine On\n"
    b"RewriteCond %{REQUEST_METHOD} ^GET$\n"
    b"RewriteCond %{REQUEST_URI} ^/store/?$\n"
    b"RewriteRule ^store/?$ store/index.html [END]\n\n"
)
MARKER = b"MPW_STATIC_STORE_FALLBACK_V1"
PRODUCT_ROUTES = (
    b'href="/store/product/72/"',
    b'href="/store/product/225/"',
    b'href="/store/product/879/"',
)
# These were false purchase CTAs in a previous public source revision.
# A catalog cutover may not reinstate them; real TRX checkout requires its
# separate merchant/rights/settlement/delivery release decision.
DEAD_CHECKOUT_ROUTES = (
    b'href="/store/product/72/checkout/"',
    b'href="/store/product/225/checkout/"',
    b"Buy securely with TRX",
)

# The live cPanel audit (2026-11-15) proved an older staging view and store
# template were still installed, and commerce_funnel.py was missing. Pin the
# exact independently reviewed public source files before removing the public
# fallback. These are git blob SHA-1 IDs, not hashes of buyer/private data.
REVIEWED_STAGING_BLOBS = {
    "core/mojplaywin_views.py": "eb97b2b7a38c6a99842a1d49c15bf657acf3abf5",
    "core/templates/mojplaywin/store.html": "0a41d31299da2b0884412d2adc1700d57c588341",
    "core/mojplaywin_product_detail.py": "9350c172591fbe9d49ee1c08b24beeb1bdd70cb2",
    "core/templates/mojplaywin/product_detail.html": "21678160b12bb2f73727c624ab5237e6b0272fd9",
    "core/commerce_funnel.py": "b2b0b0ccfc632652e32ce40cc4bd879b2cd4b9b9",
}


def git_blob_sha(payload: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
    ).hexdigest()


def assert_reviewed_staging_sources(app: Path) -> None:
    """No remote file writes/DB calls. Reject missing/old checkout source."""
    if app.is_symlink() or not app.is_dir():
        raise RuntimeError("STAGING_DIRECTORY_NOT_SAFE")
    for name, expected in REVIEWED_STAGING_BLOBS.items():
        path = app / name
        parent = path.parent
        while parent != app:
            if parent.is_symlink():
                raise RuntimeError("STAGING_PARENT_SYMLINK_REFUSED")
            parent = parent.parent
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 800_000:
            raise RuntimeError("STAGING_REQUIRED_SOURCE_MISSING_OR_UNSAFE")
        if git_blob_sha(path.read_bytes()) != expected:
            raise RuntimeError("STAGING_SOURCE_VERSION_MISMATCH")
    model = app / "core/models.py"
    if model.is_symlink() or not model.is_file() or model.stat().st_size > 800_000:
        raise RuntimeError("STAGING_FUNNEL_MODEL_MISSING")
    if b"class CommerceFunnelEvent(" not in model.read_bytes():
        raise RuntimeError("STAGING_FUNNEL_MODEL_MISSING")


def atomic_replace(target: Path, content: bytes, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".mpw-store-cutover-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def inspect_owned_fallback(public: Path) -> tuple[bytes, bytes, int]:
    """Require one exact owned rule and only one marker-bearing index file."""
    ht = public / ".htaccess"
    store = public / "store"
    index = store / "index.html"
    marker = public / "tmp/restart.txt"
    if (public.is_symlink() or not public.is_dir() or ht.is_symlink() or
            not ht.is_file() or store.is_symlink() or not store.is_dir() or
            index.is_symlink() or not index.is_file() or marker.is_symlink() or
            not marker.is_file()):
        raise RuntimeError("UNSAFE_PUBLIC_STORE_FILES")
    if any(p.stat().st_uid != os.geteuid() for p in (public, ht, store, index, marker)):
        raise RuntimeError("UNEXPECTED_FILE_OWNER")
    files = list(store.iterdir())
    if len(files) != 1 or files[0].name != "index.html":
        raise RuntimeError("UNOWNED_STORE_DIRECTORY_CONTENTS")
    if index.stat().st_size > 200_000 or ht.stat().st_size > 128_000:
        raise RuntimeError("FALLBACK_FILE_SIZE_REFUSED")
    data = index.read_bytes()
    conf = ht.read_bytes()
    if (MARKER not in data or conf.count(FALLBACK_BLOCK) != 1 or
            conf.count(MARKER) != 1):
        raise RuntimeError("FALLBACK_ANCHOR_DRIFT_REFUSED")
    changed = conf.replace(FALLBACK_BLOCK, b"", 1)
    if not changed or MARKER in changed:
        raise RuntimeError("FALLBACK_REPLACEMENT_INVALID")
    return conf, changed, stat.S_IMODE(ht.stat().st_mode)


def check_actual_staging_store() -> None:
    """Require reviewed, coherent Django source before any public rewrite."""
    assert_reviewed_staging_sources(APP)
    # URL resolution imports the live Django app without rendering a view.
    # Rendering the store would emit a funnel database event on current main,
    # so the cutover preflight deliberately avoids the old write-prone GET.
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    import django
    django.setup()
    from django.urls import resolve
    from django.template.loader import get_template
    from core.mojplaywin_views import store
    from core.mojplaywin_product_detail import brand_product_detail

    main_route = resolve("/store/")
    if main_route.url_name != "store" or main_route.func is not store:
        raise RuntimeError("STAGING_STORE_ROUTE_DRIFT")
    for product_id in (72, 225, 879):
        route = resolve(f"/store/product/{product_id}/")
        if (route.url_name != "store_product_detail" or
                route.func is not brand_product_detail):
            raise RuntimeError("STAGING_DETAIL_ROUTE_DRIFT")
    get_template("mojplaywin/store.html")
    get_template("mojplaywin/product_detail.html")
    print("MPW_DYNAMIC_STAGING_SOURCE_AND_ROUTES=PASS;PRODUCTS=3;DB_WRITES=NO")


def public_response(run_id: str) -> bytes:
    """Public HTTPS GET, cache-busted; no credentials, payment or mail."""
    url = "https://mojplaywin.com/store/?mpw_cutover_probe=" + run_id
    request = urllib.request.Request(url, headers={
        "User-Agent": "MojPlayWin-owner-cutover-smoke/1.0",
        "Cache-Control": "no-cache, no-store",
        "Pragma": "no-cache",
    })
    with urllib.request.urlopen(request, timeout=7) as reply:
        if reply.status != 200 or reply.geturl() != url:
            raise RuntimeError("PUBLIC_STORE_UNEXPECTED_HTTP_STATUS_OR_REDIRECT")
        data = reply.read(700_000)
    if len(data) < 2000:
        raise RuntimeError("PUBLIC_STORE_BODY_TOO_SMALL")
    return data


def verify_dynamic_public(run_id: str) -> bool:
    # Allow Passenger time to switch while bounding public requests and the
    # total observation window. A fixed six probes only waited ~15 seconds.
    end = time.monotonic() + 55
    observations = {}
    attempts = 0
    while attempts < 18 and (attempts == 0 or time.monotonic() < end - 4):
        attempt = attempts
        attempts += 1
        try:
            data = public_response(run_id + "-" + str(attempt))
            if (MARKER not in data and b"mpw-shop-kicker" in data and
                    b"mpw-store-catalog-20261026" in data and
                    all(route in data for route in PRODUCT_ROUTES) and
                    not any(route in data for route in DEAD_CHECKOUT_ROUTES)):
                print("MPW_PUBLIC_SWITCH_PROBE=" + json.dumps({
                    "dynamic_confirmed": True,
                    "observations": observations,
                    "attempts": attempts,
                }, sort_keys=True))
                return True
            category = "still_owned_static_fallback" if MARKER in data else "unexpected_non_django_html"
        except urllib.error.HTTPError as err:
            category = "http_" + str(err.code) if err.code in (403, 404, 429, 500, 502, 503, 504) else "http_other"
        except TimeoutError:
            category = "network_timeout"
        except (OSError, RuntimeError, urllib.error.URLError):
            category = "network_or_response_validation_error"
        observations[category] = observations.get(category, 0) + 1
        remaining = end - time.monotonic() - 4
        if attempts < 18 and remaining > 0:
            time.sleep(min(3, remaining))
    print("MPW_PUBLIC_SWITCH_PROBE=" + json.dumps({
        "dynamic_confirmed": False,
        "observations": observations,
        "attempts": attempts,
    }, sort_keys=True))
    return False


def perform_cutover(public: Path, backup_base: Path, run_id: str, probe) -> None:
    """Guaranteed rollback of owned files for any failed verification."""
    if not re.fullmatch(r"[0-9]{8,12}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    old_conf, new_conf, mode = inspect_owned_fallback(public)
    ht = public / ".htaccess"
    store = public / "store"
    marker = public / "tmp/restart.txt"
    backup = backup_base / run_id
    if backup.exists() or backup.is_symlink() or backup_base.is_symlink():
        raise RuntimeError("NON_UNIQUE_OR_UNSAFE_BACKUP")
    backup.mkdir(parents=True, mode=0o700)
    original = backup / "htaccess.original"
    with original.open("xb") as out:
        out.write(old_conf)
        out.flush()
        os.fsync(out.fileno())
    if original.read_bytes() != old_conf:
        raise RuntimeError("BACKUP_READBACK_FAILED")
    conf_changed = False
    dir_moved = False
    try:
        if ht.read_bytes() != old_conf:
            raise RuntimeError("CONCURRENT_HTACCESS_CHANGE")
        atomic_replace(ht, new_conf, mode)
        conf_changed = True
        if ht.read_bytes() != new_conf:
            raise RuntimeError("HTACCESS_REPLACEMENT_NOT_VERIFIED")
        if sorted(p.name for p in store.iterdir()) != ["index.html"]:
            raise RuntimeError("CONCURRENT_STORE_DIRECTORY_CHANGE")
        store.rename(backup / "store")
        dir_moved = True
        marker.touch()
        if not probe():
            raise RuntimeError("LIVE_DYNAMIC_PUBLIC_SMOKE_FAILED")
        print("MPW_DYNAMIC_STORE_CUTOVER=PASS;PUBLIC_DJANGO_CONFIRMED=YES;BACKUP=VERIFIED")
    except BaseException:
        rollback_safe = True
        if dir_moved:
            if store.exists() or not (backup / "store").is_dir():
                rollback_safe = False
            else:
                (backup / "store").rename(store)
        if conf_changed:
            if ht.read_bytes() != new_conf:
                rollback_safe = False
            else:
                atomic_replace(ht, old_conf, mode)
        marker.touch()
        if not rollback_safe:
            raise RuntimeError("ROLLBACK_CONFLICT_REQUIRES_MANUAL_RECOVERY")
        print("MPW_DYNAMIC_STORE_CUTOVER=ROLLED_BACK;FALLBACK_RESTORED=YES")
        raise


def main(run_id: str) -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("UNEXPECTED_CPANEL_ACCOUNT")
    if not re.fullmatch(r"[0-9]{8,12}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    check_actual_staging_store()
    baseline = public_response(run_id + "-before")
    if MARKER not in baseline:
        raise RuntimeError("PUBLIC_FALLBACK_BASELINE_NOT_PROVEN")
    print("MPW_STATIC_FALLBACK_BASELINE=CONFIRMED")
    perform_cutover(PUBLIC, BACKUP_BASE, run_id, lambda: verify_dynamic_public(run_id))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("INVALID_ARGUMENTS")
        main(sys.argv[1])
    except BaseException as err:
        print("MPW_DYNAMIC_STORE_CUTOVER=BLOCKED_OR_REVERTED;ERROR_CLASS=" + type(err).__name__, file=sys.stderr)
        raise SystemExit(1)
