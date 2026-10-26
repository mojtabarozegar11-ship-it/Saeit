#!/usr/bin/env python3
"""Atomically install the corrected three-product MojPlayWin store template."""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys
import tempfile

APP = Path("/home/zomorod2/Saeit-staging")
STORE = APP / "core/templates/mojplaywin/store.html"
SITE_BASE = APP / "core/templates/mojplaywin/site_base.html"
SITE = Path("/home/zomorod2/mojplaywin.com")
HTACCESS = SITE / ".htaccess"
WSGI = SITE / "passenger_wsgi.py"
HOME = Path("/home/zomorod2")
OLD_SHA = "c5b8d28149b9c0cd07c4c8efef3b0f4c82b6659f76e93eecc5a3b581d80ea113"
NEW_SHA = "704d7d338caa51d89addaf14934886005b359a9016b37ebb443c396c4f315cc0"
ROUTE_NEW = b"RewriteCond %{REQUEST_URI} ^/(games|ai|contact|support|privacy|terms|cookies|products|blockchain|commerce|crypto-payments|global-business|research-lab|canada-vision|agro-industry|agriculture|education|weather)/$"


def sha(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def raw_sha(data):
    return hashlib.sha256(data).hexdigest()


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
        raise RuntimeError("Store template is no longer a regular file")
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
    for path in (STORE, SITE_BASE, HTACCESS, WSGI):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("Store runtime or routing file path is unsafe")
    if STORE.parent.is_symlink() or SITE_BASE.parent.is_symlink():
        raise RuntimeError("Template directory is unsafe")
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8", "replace"):
        raise RuntimeError("Passenger app no longer targets the verified MojPlayWin root")
    if not (APP / "config/settings.py").is_file():
        raise RuntimeError("Django app root does not match verified app")
    if sha(STORE.read_bytes()) != OLD_SHA:
        raise RuntimeError("Live store template changed since audit; refusing overwrite")
    if HTACCESS.read_bytes().count(ROUTE_NEW) != 1:
        raise RuntimeError("MojPlayWin Apache route no longer matches audited route")


def reset_template_loaders(engine):
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
    products = ("/store/product/72/", "/store/product/225/", "/store/product/879/")
    if expect_fixed:
        required = (
            "Digital products with a clear purpose.", "id=\"mpw-products\"",
            "The Science and Practice of Chess Improvement", "Taniya and the Little Baker Worms",
            "Atelier Interior — Client-Ready Website Kit", "US $7.50", "US $4.00", "US $6.80",
            "84-day training plan", "English illustrated PDF · 40 pages", "five original SVG illustrations",
            "order-specific TRX invoice", "Open the live demo", *products,
        )
        if any(token not in body for token in required):
            raise RuntimeError("Corrected three-product store content is missing")
        for token in ("Farm Enterprise Economics Toolkit", "Applied AI Learning Path",
                      "Original Browser Games", "Research & Digital Project Services",
                      "Explore our books, learning, games & tools", "mpw-original-books",
                      "INITIAL COLLECTION", "FEATURED PICKS", "mpw-store-ten-guides"):
            if token in body:
                raise RuntimeError("Misleading, duplicate, or legacy store content remains: " + token)
        if body.count('class="mpw-product ') != 3:
            raise RuntimeError("Store must render exactly three purchasable product cards")
        if "Sign-in is required" not in body or "Never send funds" not in body:
            raise RuntimeError("Checkout and payment guidance is missing")
    elif ("Shop available books" not in body or "FEATURED PICKS" not in body
          or "mpw-store-ten-guides" in body):
        raise RuntimeError("Current store baseline does not match the audited version")
    for route in ("/store/product/72/", "/store/product/225/", "/store/product/879/"):
        response = client.get(route, secure=True, HTTP_HOST="mojplaywin.com")
        if response.status_code != 200:
            raise RuntimeError("Existing product detail route failed: " + route)
    for route in ("/store/product/72/checkout/", "/store/product/225/checkout/",
                  "/store/product/879/checkout/"):
        response = client.get(route, secure=True, HTTP_HOST="mojplaywin.com")
        if response.status_code != 302 or "login" not in response.get("Location", "").lower():
            raise RuntimeError("Checkout sign-in/return route changed: " + route)
    register = client.get("/accounts/register/?next=/store/product/72/checkout/",
                          secure=True, HTTP_HOST="mojplaywin.com")
    if register.status_code != 200 or "/store/product/72/checkout/" not in register.content.decode("utf8", "replace"):
        raise RuntimeError("Registration no longer retains the product checkout return path")


def save_private(path, data):
    with open(path, "xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def install(run):
    run = run_id(run)
    guard()
    check_django_pages(expect_fixed=False)
    incoming_dir = stage(run)
    incoming = incoming_dir / "store.html"
    if (not incoming_dir.is_dir() or incoming_dir.is_symlink()
        or not incoming.is_file() or incoming.is_symlink()):
        raise RuntimeError("Private store-template stage is missing or unsafe")
    new = incoming.read_bytes()
    if (sha(new) != NEW_SHA or b"mpw-store-ten-guides" in new
        or b"Explore this collection" in new or b"INITIAL COLLECTION" in new):
        raise RuntimeError("Staged store template failed its pinned content checks")
    old = STORE.read_bytes()
    old_ht = HTACCESS.read_bytes()
    destination = backup(run)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("Backup collision; refusing overwrite")
    destination.mkdir(mode=0o700)
    save_private(destination / "store.original.html", old)
    save_private(destination / "htaccess.original", old_ht)
    info = {"run": run, "store_path": str(STORE), "old_sha": OLD_SHA,
            "new_sha": NEW_SHA, "htaccess_sha": raw_sha(old_ht),
            "scope": "MojPlayWin store template only"}
    with open(destination / "manifest.json", "x", encoding="utf8") as stream:
        os.chmod(stream.fileno(), 0o600)
        json.dump(info, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    mode = stat.S_IMODE(STORE.stat().st_mode)
    try:
        if sha(STORE.read_bytes()) != OLD_SHA or raw_sha(HTACCESS.read_bytes()) != raw_sha(old_ht):
            raise RuntimeError("Store or route changed during install")
        atomic_write(STORE, new, mode)
        if sha(STORE.read_bytes()) != NEW_SHA or SITE_BASE.is_symlink() or not SITE_BASE.is_file():
            raise RuntimeError("Post-write template hashes mismatch")
        if raw_sha(HTACCESS.read_bytes()) != raw_sha(old_ht):
            raise RuntimeError("Apache route changed during isolated store install")
        check_django_pages(expect_fixed=True)
    except BaseException:
        if STORE.is_file() and not STORE.is_symlink() and sha(STORE.read_bytes()) == NEW_SHA:
            atomic_write(STORE, old, mode)
        raise
    print(json.dumps({"status": "MPW_THREE_PRODUCT_STORE_INSTALLED", "old_sha": OLD_SHA,
                      "new_sha": NEW_SHA,
                      "htaccess_sha": raw_sha(old_ht), "scope": "MojPlayWin store template only",
                      "database_payment_checkout_and_other_site_changes": 0,
                      "backup": str(destination)}, sort_keys=True))


def rollback(run):
    run = run_id(run)
    destination = backup(run)
    if not destination.is_dir() or destination.is_symlink():
        raise RuntimeError("Store-only backup missing or unsafe")
    info = json.loads((destination / "manifest.json").read_text("utf8"))
    old = (destination / "store.original.html").read_bytes()
    old_ht = (destination / "htaccess.original").read_bytes()
    if (info.get("run") != run or info.get("old_sha") != OLD_SHA or sha(old) != OLD_SHA
        or info.get("new_sha") != NEW_SHA
        or raw_sha(old_ht) != info.get("htaccess_sha")):
        raise RuntimeError("Store-only backup integrity failure")
    current = sha(STORE.read_bytes())
    if current == NEW_SHA:
        atomic_write(STORE, old, stat.S_IMODE(STORE.stat().st_mode))
    elif current != OLD_SHA:
        raise RuntimeError("Concurrent store template edit detected; refusing rollback")
    if (raw_sha(HTACCESS.read_bytes()) != info.get("htaccess_sha")
        or SITE_BASE.is_symlink() or not SITE_BASE.is_file()):
        raise RuntimeError("Protected routing or page shell changed; refusing rollback")
    if sha(STORE.read_bytes()) != OLD_SHA:
        raise RuntimeError("Store rollback hash mismatch")
    print("MPW_STORE_TEMPLATE_ROLLBACK_VERIFIED")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in {"install", "rollback"}:
        raise SystemExit("usage: script.py install|rollback RUN_ID")
    globals()[sys.argv[1]](sys.argv[2])
