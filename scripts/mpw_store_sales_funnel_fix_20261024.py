#!/usr/bin/env python3
"""Install the store-only conversion cleanup and restore its Django route."""
from pathlib import Path
import hashlib, json, os, re, stat, sys, tempfile

APP = Path("/home/zomorod2/Saeit-staging")
STORE = APP / "core/templates/mojplaywin/store.html"
SITE = Path("/home/zomorod2/mojplaywin.com")
HTACCESS = SITE / ".htaccess"
WSGI = SITE / "passenger_wsgi.py"
HOME = Path("/home/zomorod2")
OLD_SHA = "8937201e5b0252cab846ab98145ee4d5570b70a11fd523804aa5815668f64c6b"
NEW_SHA = "5a8cf2c625853c3289846d0ad42099ff94675eb18afef9ed1311d161fe8e961c"
ROUTE_OLD = b"RewriteCond %{REQUEST_URI} ^/(store|games|ai|contact|support|privacy|terms|cookies|products|blockchain|commerce|crypto-payments|global-business|research-lab|canada-vision|agro-industry|agriculture|education|weather)/$"
ROUTE_NEW = ROUTE_OLD.replace(b"/(store|", b"/(")


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
        raise RuntimeError("Target path is no longer a regular file")
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
    for path in (STORE, HTACCESS, WSGI):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("Store or routing file path is unsafe")
    if STORE.parent.is_symlink():
        raise RuntimeError("Store template parent is unsafe")
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8", "replace"):
        raise RuntimeError("Passenger app no longer targets the verified MojPlayWin root")
    if not (APP / "config/settings.py").is_file():
        raise RuntimeError("Django app root does not match verified app")
    if sha(STORE.read_bytes()) != OLD_SHA:
        raise RuntimeError("Live store template changed since audit; refusing overwrite")
    ht=HTACCESS.read_bytes()
    if ht.count(ROUTE_OLD) != 1 or ROUTE_NEW in ht:
        raise RuntimeError("Expected one exact old store route in Apache config; refusing edit")


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
    if expect_fixed:
        required = ("Shop available books", "/store/product/72/", "/store/product/225/",
                    "View book & purchase", "order-specific TRX invoice")
        if any(token not in body for token in required):
            raise RuntimeError("Updated store render is missing purchase content")
        if "mpw-store-ten-guides" in body or "INITIAL COLLECTION" in body:
            raise RuntimeError("Low-conversion guide block or misleading heading remains")
    elif "mpw-store-ten-guides" not in body or "INITIAL COLLECTION" not in body:
        raise RuntimeError("Pre-change store baseline does not match audit")
    for route in ("/store/product/72/", "/store/product/225/"):
        response = client.get(route, secure=True, HTTP_HOST="mojplaywin.com")
        if response.status_code != 200:
            raise RuntimeError("Existing product detail route failed: " + route)
    for route in ("/store/product/72/checkout/", "/store/product/225/checkout/"):
        response = client.get(route, secure=True, HTTP_HOST="mojplaywin.com")
        if response.status_code != 302 or "login" not in response.get("Location", "").lower():
            raise RuntimeError("Checkout authentication/return route changed: " + route)
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
    if not incoming_dir.is_dir() or incoming_dir.is_symlink() or not incoming.is_file() or incoming.is_symlink():
        raise RuntimeError("Private stage is missing or unsafe")
    new = incoming.read_bytes()
    if sha(new) != NEW_SHA or b"mpw-store-ten-guides" in new or b"Explore this collection" in new:
        raise RuntimeError("Staged template failed pinned content checks")
    old = STORE.read_bytes()
    old_ht = HTACCESS.read_bytes()
    new_ht = old_ht.replace(ROUTE_OLD, ROUTE_NEW, 1)
    if new_ht.count(ROUTE_NEW) != 1 or ROUTE_OLD in new_ht:
        raise RuntimeError("Exact Apache route substitution failed")
    destination = backup(run)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("Backup collision; refusing overwrite")
    destination.mkdir(mode=0o700)
    save_private(destination / "store.original.html", old)
    save_private(destination / "htaccess.original", old_ht)
    info = {"run":run,"store_path":str(STORE),"htaccess_path":str(HTACCESS),
            "old_sha":OLD_SHA,"new_sha":NEW_SHA,
            "htaccess_old_sha":raw_sha(old_ht),"htaccess_new_sha":raw_sha(new_ht)}
    with open(destination / "manifest.json", "x", encoding="utf8") as stream:
        os.chmod(destination / "manifest.json", 0o600)
        json.dump(info, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    store_mode = stat.S_IMODE(STORE.stat().st_mode)
    ht_mode = stat.S_IMODE(HTACCESS.stat().st_mode)
    try:
        atomic_write(STORE, new, store_mode)
        atomic_write(HTACCESS, new_ht, ht_mode)
        if sha(STORE.read_bytes()) != NEW_SHA or raw_sha(HTACCESS.read_bytes()) != raw_sha(new_ht):
            raise RuntimeError("Post-write hashes mismatch")
        check_django_pages(expect_fixed=True)
    except BaseException:
        if STORE.is_file() and not STORE.is_symlink() and sha(STORE.read_bytes()) == NEW_SHA:
            atomic_write(STORE, old, store_mode)
        if HTACCESS.is_file() and not HTACCESS.is_symlink() and raw_sha(HTACCESS.read_bytes()) == raw_sha(new_ht):
            atomic_write(HTACCESS, old_ht, ht_mode)
        raise
    print(json.dumps({"status":"MPW_STORE_SALES_FIX_INSTALLED",
        "old_sha":OLD_SHA,"new_sha":NEW_SHA,
        "htaccess_old_sha":raw_sha(old_ht),"htaccess_new_sha":raw_sha(new_ht),
        "scope":"MojPlayWin /store route and store template only",
        "other_apache_routes_changed":0,"order_payment_product_database_changes":0,
        "backup":str(destination)}, sort_keys=True))


def rollback(run):
    run=run_id(run)
    destination=backup(run)
    if not destination.is_dir() or destination.is_symlink():
        raise RuntimeError("Store-only backup missing or unsafe")
    info=json.loads((destination/"manifest.json").read_text("utf8"))
    old=(destination/"store.original.html").read_bytes()
    old_ht=(destination/"htaccess.original").read_bytes()
    if (info.get("run")!=run or info.get("old_sha")!=OLD_SHA or sha(old)!=OLD_SHA
        or raw_sha(old_ht)!=info.get("htaccess_old_sha")):
        raise RuntimeError("Store-only backup integrity failure")
    current_store=sha(STORE.read_bytes())
    if current_store==NEW_SHA:
        atomic_write(STORE,old,stat.S_IMODE(STORE.stat().st_mode))
    elif current_store!=OLD_SHA:
        raise RuntimeError("Concurrent store template edit detected; refusing rollback")
    current_ht=HTACCESS.read_bytes()
    if raw_sha(current_ht)==info.get("htaccess_new_sha"):
        atomic_write(HTACCESS,old_ht,stat.S_IMODE(HTACCESS.stat().st_mode))
    elif raw_sha(current_ht)!=info.get("htaccess_old_sha"):
        raise RuntimeError("Concurrent Apache config edit detected; refusing rollback")
    check_django_pages(expect_fixed=False)
    print(json.dumps({"status":"MPW_STORE_SALES_FIX_ROLLED_BACK",
        "restored_store_sha":OLD_SHA,"restored_htaccess_sha":raw_sha(old_ht),
        "scope":"MojPlayWin /store route and store template only"},sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("install","rollback"):
        raise SystemExit("Usage: mpw_store_sales_funnel_fix_20261024.py install|rollback RUN_ID")
    {"install":install,"rollback":rollback}[sys.argv[1]](sys.argv[2])
