#!/usr/bin/env python3
"""Patch only the actual public_html/market/index.html page, preserving HTML theme.

Requires exact old visible content and old links. Supports backup, rollback,
origin checks; no payment, order, email or Django application mutation.
"""
from __future__ import annotations
import os
import pwd
import re
import stat
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

HOME = Path("/home/zomorod2")
WEB = HOME / "public_html"
HTACCESS = WEB / ".htaccess"
TARGET = WEB / "market/index.html"
BACKUPS = HOME / ".private/market-landing-backups"
MARKER = "<!-- zm-market-actionable-20261105 -->"
REPLACEMENTS = [["محصول و خدمت، سفارش و پرداخت کنترل‌شده؛ آماده برای توسعه به یک Super Platform تجاری.","دسترسی به ابزار دیجیتال رایگان و ثبت درخواست واقعی؛ خرید آنلاین تا زمان فعال‌سازی درگاه بانکی غیرفعال است.",2],["محصولات و خدمات شرکت، معرفی و دسترسی به مسیرهای تجاری و اطلاعات موردنیاز برای مشتریان و همکاران.","محصول فعلی قابل استفاده در فروشگاه، محاسبه‌گر رایگان بذر گندم است. می‌توانید ابزار را اجرا کنید یا برای محصول، خدمت و همکاری استعلام ثبت کنید. ثبت استعلام به معنی سفارش قطعی یا پرداخت نیست.",1],["<h2>محصولات</h2><p>معرفی محصولات و خدمات شرکت.</p>","<h2>محصول رایگان فعال</h2><p>محاسبه‌گر علمی بذر گندم برای برآورد مقدار بذر بر پایه داده‌های مزرعه؛ قابل اجرا بدون پرداخت.</p>",1],["<h2>سفارش</h2><p>اطلاعات و مسیر درخواست سفارش.</p>","<h2>ثبت استعلام و پیگیری</h2><p>سامانه مشتریان، فرم ثبت پرسش یا درخواست و مسیر پیگیری با شناسه درخواست دارد.</p>",1],["<h2>همکاری تجاری</h2><p>ارتباط برای خرید، فروش و همکاری‌های مجاز.</p>","<h2>وضعیت خرید آنلاین</h2><p>پرداخت بانک شهر هنوز فعال نشده و خرید و برداشت آنلاین این فروشگاه غیرفعال است؛ قیمت و امکان ارائه خدمات صرفاً با استعلام معتبر تعیین می‌شود.</p>",1],["<a href=\"/api/products/\">محصولات API ←</a><a href=\"/api/orders/\">سفارش‌ها ←</a><a href=\"/knowledge/\">دانش ←</a>","<a href=\"/store/\">فروشگاه و وضعیت محصولات ←</a><a href=\"/store/free-products/wheat-seed-rate-planner-v1/index.html\">اجرای محاسبه‌گر رایگان بذر گندم ←</a><a href=\"/ask-master/index.php\">ثبت استعلام و پیگیری سفارش ←</a><a href=\"/digital-lab/\">آزمایشگاه دیجیتال ←</a>",1]]
SOURCE_CANONICAL = '<link rel="canonical" href="https://zomorodmelal.ir/market/">'

def validate_account():
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_CPANEL_USER")
    for p in (WEB, HTACCESS, TARGET.parent, TARGET):
        if p.is_symlink() or not p.exists():
            raise RuntimeError("MISSING_OR_SYMLINK:" + p.name)
    if not TARGET.is_file() or not HTACCESS.is_file():
        raise RuntimeError("UNSAFE_STATIC_TARGET")
    if b'PassengerAppRoot "/home/zomorod2/Saeit"' not in HTACCESS.read_bytes():
        raise RuntimeError("PRIMARY_SITE_ANCHOR_MISSING")
    if TARGET.stat().st_uid != os.geteuid():
        raise RuntimeError("STATIC_OWNERSHIP_CHANGED")

def assert_static_invariants(old, new):
    if SOURCE_CANONICAL not in old or new.count(SOURCE_CANONICAL) != 1:
        raise RuntimeError("CANONICAL_NOT_PRESERVED")
    for token in ('<main', '</main>', '<h1', '<footer', '<style', '<script'):
        if old.count(token) != new.count(token):
            raise RuntimeError("STATIC_STRUCTURE_CHANGED:" + token)
    for token in ('zm-v7-information', 'zm-v10-restored-content-and-unified-internal-pages'):
        if token not in old or token not in new:
            raise RuntimeError("SITE_THEME_MARKER_MISSING:" + token)
    if new.count(MARKER) != 1:
        raise RuntimeError("PATCH_MARKER_MISSING")

def patched(source):
    if source.count(MARKER) == 1:
        for old, new, count in REPLACEMENTS:
            if new not in source or old in source and new != old:
                raise RuntimeError("MARKET_PARTIALLY_PATCHED")
        return "already-patched", source
    if MARKER in source:
        raise RuntimeError("DUPLICATE_MARKET_PATCH_MARKER")
    candidate = source
    for old, new, count in REPLACEMENTS:
        if candidate.count(old) != count:
            raise RuntimeError("MARKET_STATIC_SOURCE_DRIFT_EXPECTED_" + str(count) + "_GOT_" + str(candidate.count(old)))
        candidate = candidate.replace(old, new)
    old_div = '<div class="zm-v7-info-links">'
    if candidate.count(old_div) != 1:
        raise RuntimeError("LINK_WRAPPER_MISSING")
    candidate = candidate.replace(old_div, MARKER + old_div, 1)
    assert_static_invariants(source, candidate)
    return "needs-patch", candidate

def atomic_write(data, mode):
    fd, temp_path = tempfile.mkstemp(prefix=".market-public-", dir=str(TARGET.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, TARGET)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def backup_file(run_id):
    if not re.fullmatch(r"[0-9]{5,20}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    if BACKUPS.parent.is_symlink():
        raise RuntimeError("UNSAFE_BACKUP_PARENT")
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    if BACKUPS.is_symlink():
        raise RuntimeError("UNSAFE_BACKUP_DIR")
    os.chmod(BACKUPS, 0o700)
    return BACKUPS / ("public-market-" + run_id + ".bak")

def publish(run_id):
    source = TARGET.read_text(encoding="utf-8")
    state, new = patched(source)
    if state == "already-patched":
        print("STATIC_MARKET_ALREADY_APPLIED")
        return
    dest = backup_file(run_id)
    data = source.encode("utf-8")
    mode = stat.S_IMODE(TARGET.stat().st_mode)
    with dest.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(dest, 0o600)
    try:
        atomic_write(new.encode("utf-8"), mode)
    except Exception:
        if TARGET.read_bytes() == new.encode("utf-8"):
            atomic_write(data, mode)
        raise
    print("STATIC_MARKET_PUBLISHED_BACKED_UP=1")

def check_public(url, contains, excludes=()):
    with urlopen(Request(url, headers={"User-Agent": "Zomorod-Market-Guard/1.0"}), timeout=25) as r:
        body = r.read(450000).decode("utf-8", "replace")
        if r.status != 200 or "noindex" in r.headers.get("X-Robots-Tag", "").lower():
            raise RuntimeError("LIVE_HTTP_OR_ROBOTS_REGRESSION")
    if any(x not in body for x in contains) or any(x in body for x in excludes):
        raise RuntimeError("LIVE_CONTENT_MISMATCH:" + url)
    return body

def verify_origin():
    if patched(TARGET.read_text(encoding="utf-8"))[0] != "already-patched":
        raise RuntimeError("STATIC_FILE_NOT_PATCHED")
    last = None
    for attempt in range(8):
        try:
            check_public(
                "https://zomorodmelal.ir/market/",
                ["بازار و محصولات", "محاسبه‌گر رایگان بذر گندم",
                 'href="/store/"', 'href="/ask-master/index.php"',
                 'href="/digital-lab/"', MARKER],
                ['href="/api/products/"', 'href="/api/orders/"'],
            )
            check_public("https://zomorodmelal.ir/store/", ["محاسبه‌گر علمی بذر گندم"])
            check_public("https://zomorodmelal.ir/", ["زمرد ملل"])
            print("STATIC_MARKET_LIVE_TOOL_LINKS=4 INQUIRY_LINK=1 HOMEPAGE_OK=1")
            return
        except Exception as exc:
            last = repr(exc)
            if attempt != 7:
                time.sleep(6)
    raise RuntimeError("LIVE_VERIFICATION_FAILED:" + str(last))

def rollback(run_id):
    dest = backup_file(run_id)
    if not dest.is_file() or dest.is_symlink():
        print("NO_STATIC_MARKET_BACKUP_FOR_THIS_RUN")
        return
    current = TARGET.read_text(encoding="utf-8")
    if patched(current)[0] != "already-patched":
        raise RuntimeError("REFUSE_ROLLBACK_ON_SOURCE_DRIFT")
    old = dest.read_bytes()
    if patched(old.decode("utf-8"))[0] != "needs-patch":
        raise RuntimeError("BACKUP_IS_NOT_EXPECTED_SOURCE")
    atomic_write(old, stat.S_IMODE(TARGET.stat().st_mode))
    print("STATIC_MARKET_ROLLBACK_COMPLETE")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: market_guard.py preview|publish|verify-origin|rollback [run_id]")
    validate_account()
    cmd = sys.argv[1]
    if cmd == "preview" and len(sys.argv) == 2:
        print("STATIC_MARKET_GUARD_STATE=" + patched(TARGET.read_text(encoding="utf-8"))[0])
    elif cmd == "publish" and len(sys.argv) == 3:
        publish(sys.argv[2])
    elif cmd == "verify-origin" and len(sys.argv) == 3:
        verify_origin()
    elif cmd == "rollback" and len(sys.argv) == 3:
        rollback(sys.argv[2])
    else:
        raise RuntimeError("UNRECOGNIZED_MODE")
