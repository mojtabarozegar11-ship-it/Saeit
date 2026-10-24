#!/usr/bin/env python3
"""Atomic, MojPlayWin-store-only conversion cleanup.

Verifies exact live file, app root and WSGI route before replacing one template.
No database, order, payment, product, sibling-site, WSGI or Passenger changes.
"""
from pathlib import Path
import hashlib, json, os, re, stat, sys, tempfile

APP = Path("/home/zomorod2/Saeit-staging")
STORE = APP / "core/templates/mojplaywin/store.html"
SITE = Path("/home/zomorod2/mojplaywin.com")
WSGI = SITE / "passenger_wsgi.py"
HOME = Path("/home/zomorod2")
OLD_SHA = "8937201e5b0252cab846ab98145ee4d5570b70a11fd523804aa5815668f64c6b"
NEW_SHA = "784cb9d754e72b910c7ab6ccb301b5954a0bdc91dbcc4a9499ea9cdf6fdbd4b2"


def sha(data):
    # Git checkout may normalize line endings; compare template content canonically.
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def run_id(value):
    if not re.fullmatch(r"[0-9]{9,20}", value):
        raise RuntimeError("Invalid GitHub run ID")
    return value


def stage(run):
    return HOME / (".mpw-store-sales-stage-" + run_id(run))


def backup(run):
    return HOME / (".mpw-store-sales-backup-" + run_id(run))


def atomic_write(path, data, mode):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Store template path is no longer a regular file")
    fd, name = tempfile.mkstemp(prefix=".mpw-store-sales-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def guard():
    if APP.is_symlink() or not APP.is_dir() or SITE.is_symlink() or not SITE.is_dir():
        raise RuntimeError("Verified MojPlayWin app/site root changed")
    if STORE.is_symlink() or not STORE.is_file() or STORE.parent.is_symlink():
        raise RuntimeError("Store template path is unsafe")
    if not WSGI.is_file() or WSGI.is_symlink():
        raise RuntimeError("Passenger entry point is unsafe")
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8", "replace"):
        raise RuntimeError("Passenger app no longer targets the verified MojPlayWin root")
    if not (APP / "config/settings.py").is_file():
        raise RuntimeError("Django app root does not match verified app")
    if sha(STORE.read_bytes()) != OLD_SHA:
        raise RuntimeError("Live store template changed since audit; refusing overwrite")


def reset_template_loaders(engine):
    # The pre/post probes run in one process; clear Django's cache so the
    # post-install render checks the new bytes instead of the preflight result.
    def reset(loader):
        if hasattr(loader, "reset"):
            loader.reset()
        for child in getattr(loader, "loaders", ()):
            reset(child)
    for loader in engine.template_loaders:
        reset(loader)


def check_django_pages(expect_fixed):
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.test import Client
    from django.template import engines
    reset_template_loaders(engines["django"].engine)
    client = Client(raise_request_exception=True)
    page = client.get("/store/", secure=True, HTTP_HOST="mojplaywin.com")
    if page.status_code != 200:
        raise RuntimeError("Store Django route is not HTTP 200")
    body = page.content.decode("utf8", "replace")
    if expect_fixed:
        required = (
            "Shop available books", "/store/product/72/", "/store/product/225/",
            "View book & purchase", "order-specific TRX invoice",
        )
        if any(token not in body for token in required):
            raise RuntimeError("Updated store render is missing purchase content")
        if "mpw-store-ten-guides" in body or "INITIAL COLLECTION" in body:
            raise RuntimeError("Low-conversion guide block or misleading heading remains")
    else:
        if "mpw-store-ten-guides" not in body or "INITIAL COLLECTION" not in body:
            raise RuntimeError("Pre-change store baseline does not match audit")
    for route in ("/store/product/72/", "/store/product/225/"):
        response = client.get(route, secure=True, HTTP_HOST="mojplaywin.com")
        if response.status_code != 200:
            raise RuntimeError("Existing product detail route failed: " + route)
    for route in (
        "/store/product/72/checkout/",
        "/store/product/225/checkout/",
    ):
        response = client.get(route, secure=True, HTTP_HOST="mojplaywin.com")
        if response.status_code != 302 or "login" not in response.get("Location", "").lower():
            raise RuntimeError("Checkout authentication/return route changed: " + route)
    register = client.get(
        "/accounts/register/?next=/store/product/72/checkout/",
        secure=True, HTTP_HOST="mojplaywin.com",
    )
    if register.status_code != 200 or "/store/product/72/checkout/" not in register.content.decode("utf8", "replace"):
        raise RuntimeError("Registration no longer retains the product checkout return path")


def install(run):
    run = run_id(run)
    guard()
    check_django_pages(expect_fixed=False)
    incoming_dir = stage(run)
    incoming = incoming_dir / "store.html"
    if not incoming_dir.is_dir() or incoming_dir.is_symlink() or not incoming.is_file() or incoming.is_symlink():
        raise RuntimeError("Private stage is missing or unsafe")
    new = incoming.read_bytes()
    if sha(new) != NEW_SHA:
        raise RuntimeError("Staged template failed pinned SHA check")
    if b"mpw-store-ten-guides" in new or b"Explore this collection" in new:
        raise RuntimeError("Staged template still contains audited conversion defects")
    destination = backup(run)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("Backup collision; refusing overwrite")
    old = STORE.read_bytes()
    destination.mkdir(mode=0o700)
    with open(destination / "store.original.html", "xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(old)
        stream.flush()
        os.fsync(stream.fileno())
    info = {
        "run": run, "store_path": str(STORE),
        "old_sha": OLD_SHA, "new_sha": NEW_SHA,
    }
    with open(destination / "manifest.json", "x", encoding="utf8") as stream:
        os.chmod(destination / "manifest.json", 0o600)
        json.dump(info, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    mode = stat.S_IMODE(STORE.stat().st_mode)
    try:
        atomic_write(STORE, new, mode)
        if sha(STORE.read_bytes()) != NEW_SHA:
            raise RuntimeError("Live store template hash mismatch")
        check_django_pages(expect_fixed=True)
    except BaseException:
        if STORE.is_file() and not STORE.is_symlink() and sha(STORE.read_bytes()) == NEW_SHA:
            atomic_write(STORE, old, mode)
        raise
    print(json.dumps({
        "status": "MPW_STORE_SALES_FIX_INSTALLED",
        "old_sha": OLD_SHA, "new_sha": NEW_SHA,
        "scope": "one MojPlayWin store template only",
        "store_guides_removed_from_store_render": True,
        "book_cards_link_to_real_product_pages": True,
        "order_payment_product_database_changes": 0,
        "passenger_restart": False,
        "backup": str(destination),
    }, sort_keys=True))


def rollback(run):
    run = run_id(run)
    guard = None
    destination = backup(run)
    if not destination.is_dir() or destination.is_symlink():
        raise RuntimeError("Store-only backup missing or unsafe")
    info = json.loads((destination / "manifest.json").read_text("utf8"))
    old = (destination / "store.original.html").read_bytes()
    if info.get("run") != run or info.get("old_sha") != OLD_SHA or sha(old) != OLD_SHA:
        raise RuntimeError("Store-only backup integrity failure")
    actual = sha(STORE.read_bytes())
    if actual == NEW_SHA:
        atomic_write(STORE, old, stat.S_IMODE(STORE.stat().st_mode))
    elif actual != OLD_SHA:
        raise RuntimeError("Concurrent store template edit detected; refusing rollback")
    check_django_pages(expect_fixed=False)
    print(json.dumps({
        "status": "MPW_STORE_SALES_FIX_ROLLED_BACK",
        "restored_sha": OLD_SHA, "scope": "one MojPlayWin store template only",
    }, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("install", "rollback"):
        raise SystemExit("Usage: mpw_store_sales_funnel_fix_20261024.py install|rollback RUN_ID")
    {"install": install, "rollback": rollback}[sys.argv[1]](sys.argv[2])
