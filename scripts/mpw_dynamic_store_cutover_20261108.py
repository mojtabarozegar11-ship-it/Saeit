#!/usr/bin/env python3
"""Owner-gated, reversible cutover from the owned static /store/ fallback.

Touches only the exact fallback rule, its one-file directory, and the already
present Passenger restart marker. Never changes invoices, payments or mail.
"""
from __future__ import annotations

import ast
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
    b"/store/product/72/checkout/",
    b"/store/product/225/checkout/",
    b"/store/product/879/",
)


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


def verify_guarded_store_source(source: bytes) -> None:
    """Accept source drift only when the actual fail-open storefront contract holds.

    Optional funnel instrumentation may exist, yet have no installed model/table.
    A fixed file length or an absent funnel module is not evidence of safety.
    Instead require that the recorder call is inside a broad, non-raising handler;
    the live Django render and public HTTPS check remain mandatory afterward.
    """
    if len(source) < 200 or len(source) > 64_000:
        raise RuntimeError("STAGING_VIEW_SOURCE_SIZE_REFUSED")
    try:
        tree = ast.parse(source.decode("utf-8"), filename="core/mojplaywin_views.py")
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise RuntimeError("STAGING_VIEW_SOURCE_INVALID") from exc
    views = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name == "store" and len(node.args.args) == 1
             and node.args.args[0].arg == "request"]
    if len(views) != 1:
        raise RuntimeError("STAGING_GUARDED_VIEW_NOT_PROVEN")
    view = views[0]
    guarded = [node for node in view.body if isinstance(node, ast.Try)
               and any(isinstance(handler.type, ast.Name)
                       and handler.type.id == "Exception" and handler.body
                       and not any(isinstance(item, ast.Raise)
                                   for item in ast.walk(handler))
                       for handler in node.handlers)]
    safe_recorder = any(
        any(isinstance(node, ast.ImportFrom) and node.level == 1
            and node.module == "commerce_funnel"
            and any(alias.name == "record_funnel_event" for alias in node.names)
            for child in guarded_try.body for node in ast.walk(child))
        and any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "record_funnel_event"
                for child in guarded_try.body for node in ast.walk(child))
        for guarded_try in guarded
    )
    store_render = any(
        isinstance(node, ast.Return) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name) and node.value.func.id == "render"
        and len(node.value.args) >= 2
        and isinstance(node.value.args[1], ast.Constant)
        and node.value.args[1].value == "mojplaywin/store.html"
        for node in view.body
    )
    if not safe_recorder or not store_render:
        raise RuntimeError("STAGING_GUARDED_VIEW_NOT_PROVEN")


def check_actual_staging_store() -> None:
    """Import and render the real store view; never supply a metrics stub."""
    target = APP / "core/mojplaywin_views.py"
    funnel = APP / "core/commerce_funnel.py"
    if (APP.is_symlink() or not APP.is_dir() or target.is_symlink() or
            not target.is_file() or funnel.is_symlink() or
            (funnel.exists() and not funnel.is_file())):
        raise RuntimeError("STAGING_SOURCE_DRIFT")
    verify_guarded_store_source(target.read_bytes())
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    import django
    django.setup()
    from django.test import RequestFactory
    from core import mojplaywin_views
    if Path(mojplaywin_views.__file__).resolve() != target.resolve():
        raise RuntimeError("STAGING_VIEW_IMPORT_ORIGIN_MISMATCH")
    store = mojplaywin_views.store
    page = store(RequestFactory().get("/store/", secure=True, HTTP_HOST="mojplaywin.com"))
    if page.status_code != 200 or len(page.content) < 2000 or any(
            route not in page.content for route in PRODUCT_ROUTES):
        raise RuntimeError("REAL_STAGING_STORE_RENDER_FAILED")
    print("MPW_DYNAMIC_STAGING_GUARDED_RENDER=PASS;PRODUCTS=3")


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
                    all(route in data for route in PRODUCT_ROUTES)):
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

