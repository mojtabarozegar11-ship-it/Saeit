#!/usr/bin/env python3
"""Single-file bounded MojPlayWin live source repair. No customer/order/payment changes."""
from __future__ import annotations
import hashlib, os, pwd, re, stat, sys, tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
PUBLIC = HOME / "mojplaywin.com"
TARGET = APP / "core/mojplaywin_views.py"
EXPECTED_LENGTH = 15919
EXPECTED_PREFIX = "337bd51a2390578d"
OLD = "def store(request):\n from .commerce_funnel import record_funnel_event\n record_funnel_event(request, \"view_store\")\n return render(request,\"mojplaywin/store.html\",{\"products\":PRODUCTS})\n"
NEW = "def store(request):\n # Analytics must never make the public storefront unavailable. The cPanel\n # main-site deploy may publish this view before the optional funnel module\n # and migration have been installed in the independent runtime.\n try:\n  from .commerce_funnel import record_funnel_event\n  record_funnel_event(request, \"view_store\")\n except Exception as exc:\n  # No visitor identity, query string or other buyer data enters the log.\n  import logging\n  logging.getLogger(__name__).warning(\n   \"MojPlayWin store telemetry unavailable: %s\", type(exc).__name__\n  )\n return render(request,\"mojplaywin/store.html\",{\"products\":PRODUCTS})\n"

def transformed(raw: bytes, *, expected_size=EXPECTED_LENGTH, expected_prefix=EXPECTED_PREFIX) -> bytes:
    if len(raw) != expected_size or not hashlib.sha256(raw).hexdigest().startswith(expected_prefix):
        raise RuntimeError("LIVE_STORE_SOURCE_DRIFT_REFUSED")
    source = raw.decode("utf-8")
    if source.count(OLD) != 1 or "except Exception as exc:" in source[source.index(OLD):source.index(OLD)+len(OLD)]:
        raise RuntimeError("STORE_ANCHOR_AMBIGUOUS_REFUSED")
    updated = source.replace(OLD, NEW, 1)
    compile(updated, str(TARGET), "exec")
    return updated.encode("utf-8")

def atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix=".mpw-store-p0-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def verify_runtime() -> None:
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    import django
    django.setup()
    from django.test import RequestFactory
    from core.mojplaywin_views import store
    request = RequestFactory().get("/store/", secure=True, HTTP_HOST="mojplaywin.com")
    response = store(request)
    html = response.content
    if response.status_code != 200 or len(html) < 2000:
        raise RuntimeError("LIVE_STORE_DJANGO_RENDER_FAILED")
    for needle in (b"/store/product/72/checkout/", b"/store/product/225/checkout/", b"/store/product/879/"):
        if needle not in html:
            raise RuntimeError("LIVE_STORE_MISSING_PRODUCT_LINK")
    print("MPW_STORE_INTERNAL_DJANGO_RENDER=PASS;PRODUCT_LINKS=3")

def main(run_id: str) -> None:
    if not re.fullmatch(r"[0-9]{8,12}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("UNEXPECTED_CPANEL_USER")
    for p in (APP, PUBLIC, TARGET.parent):
        if p.is_symlink() or not p.is_dir():
            raise RuntimeError("UNSAFE_APPLICATION_ROOT")
    ht = PUBLIC / ".htaccess"
    marker = PUBLIC / "tmp/restart.txt"
    if ht.is_symlink() or marker.is_symlink() or not ht.is_file() or not marker.is_file():
        raise RuntimeError("UNSAFE_PASSENGER_RESTART_OR_HTACCESS")
    if "MPW_STATIC_STORE_FALLBACK_V1" not in ht.read_text("utf-8", "replace"):
        raise RuntimeError("PUBLIC_STORE_FALLBACK_NOT_PROVEN")
    if (APP / "core/commerce_funnel.py").exists():
        raise RuntimeError("METRICS_MODULE_CHANGED_ABORT")
    if not TARGET.is_file() or TARGET.is_symlink():
        raise RuntimeError("UNSAFE_STORE_VIEW_TARGET")
    original = TARGET.read_bytes()
    changed = transformed(original)
    mode = stat.S_IMODE(TARGET.stat().st_mode)
    backup_dir = HOME / ".backups" / "mpw-store-source-p0" / run_id
    if backup_dir.exists() or backup_dir.is_symlink():
        raise RuntimeError("NON_UNIQUE_BACKUP_DIR")
    backup_dir.mkdir(mode=0o700, parents=True)
    backup = backup_dir / "mojplaywin_views.py"
    old_umask = os.umask(0o077)
    try:
        with backup.open("xb") as out:
            out.write(original)
            out.flush()
            os.fsync(out.fileno())
    finally:
        os.umask(old_umask)
    if backup.read_bytes() != original:
        raise RuntimeError("BACKUP_READBACK_FAILED")
    installed = False
    try:
        if TARGET.read_bytes() != original:
            raise RuntimeError("CONCURRENT_EDIT_REFUSED")
        atomic_write(TARGET, changed, mode)
        installed = True
        if TARGET.read_bytes() != changed:
            raise RuntimeError("WRITE_READBACK_FAILED")
        verify_runtime()
        marker.touch()
        print("MPW_STORE_ONE_FILE_REPAIR=PASS;BACKUP_VERIFIED=YES;FALLBACK_PRESERVED=YES")
    except BaseException:
        if installed:
            if TARGET.read_bytes() != changed:
                raise RuntimeError("ROLLBACK_REFUSED_CONCURRENT_EDIT")
            atomic_write(TARGET, original, mode)
            marker.touch()
            print("MPW_STORE_ONE_FILE_ROLLBACK=COMPLETE")
        raise

if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("INVALID_ARGUMENT_COUNT")
        main(sys.argv[1])
    except BaseException as exc:
        print("MPW_STORE_SOURCE_REPAIR=BLOCKED_OR_ROLLED_BACK;ERROR_CLASS="+type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
