#!/usr/bin/env python3
"""Guarded one-section improvement for Zomorod's live market page.

Only changes core/views.py MARKET mapping on cPanel after an exact source
match and a private backup. No orders, payments, email, or other pages.
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
APP = HOME / "Saeit"
TARGET = APP / "core/views.py"
HTACCESS = HOME / "public_html/.htaccess"
RESTART = APP / "tmp/restart.txt"
BACKUPS = HOME / ".private/market-landing-backups"
OLD = "        \"market\": {\n            \"kicker\":\"MARKET · PRODUCTS\",\"title\":\"بازار و محصولات\",\"lead\":\"محصول و خدمت، سفارش و پرداخت کنترل‌شده؛ آماده برای توسعه به یک Super Platform تجاری.\",\n            \"badge\":\"MARKET\",\"heading\":\"بازار و محصولات\",\"body\":\"محصولات و خدمات شرکت، معرفی و دسترسی به مسیرهای تجاری و اطلاعات موردنیاز برای مشتریان و همکاران.\",\n            \"items\":[{\"title\":\"محصولات\",\"text\":\"معرفی محصولات و خدمات شرکت.\"},{\"title\":\"سفارش\",\"text\":\"اطلاعات و مسیر درخواست سفارش.\"},{\"title\":\"همکاری تجاری\",\"text\":\"ارتباط برای خرید، فروش و همکاری‌های مجاز.\"}],\n            \"links\":[{\"title\":\"محصولات API\",\"text\":\"کاتالوگ عملیاتی\",\"url\":\"/api/products/\"},{\"title\":\"سفارش‌ها\",\"text\":\"چرخه سفارش\",\"url\":\"/api/orders/\"},{\"title\":\"دانش\",\"text\":\"منشأ محصولات\",\"url\":\"/knowledge/\"}],\n            \"cta_title\":\"با بازار شرکت آشنا شوید\",\"cta_text\":\"برای دریافت اطلاعات محصولات، خدمات و فرصت‌های همکاری تجاری با ما در ارتباط باشید.\",\"cta_label\":\"تماس تجاری\",\"cta_url\":\"/contact/\"\n        },\n"
NEW = "        \"market\": {\n            \"kicker\":\"MARKET · AVAILABLE PRODUCTS & INQUIRIES\",\"title\":\"بازار و محصولات\",\n            \"lead\":\"دسترسی به ابزار دیجیتال رایگان و ثبت درخواست واقعی؛ خرید آنلاین تا زمان فعال‌سازی درگاه بانکی غیرفعال است.\",\n            \"badge\":\"MARKET\",\"heading\":\"محصولات و مسیر درخواست\",\"body\":\"محصول فعلی قابل استفاده در فروشگاه، محاسبه‌گر رایگان بذر گندم است. می‌توانید ابزار را اجرا کنید یا برای محصول، خدمت و همکاری استعلام ثبت کنید. ثبت استعلام به معنی سفارش قطعی یا پرداخت نیست.\",\n            \"items\":[{\"title\":\"محصول رایگان فعال\",\"text\":\"محاسبه‌گر علمی بذر گندم برای برآورد مقدار بذر بر پایه داده‌های مزرعه؛ قابل اجرا بدون پرداخت.\"},{\"title\":\"ثبت استعلام و پیگیری\",\"text\":\"سامانه مشتریان، فرم ثبت پرسش یا درخواست و مسیر پیگیری با شناسه درخواست دارد.\"},{\"title\":\"وضعیت خرید آنلاین\",\"text\":\"پرداخت بانک شهر هنوز فعال نشده و خرید و برداشت آنلاین این فروشگاه غیرفعال است؛ قیمت و امکان ارائه خدمات صرفاً با استعلام معتبر تعیین می‌شود.\"}],\n            \"links\":[{\"title\":\"فروشگاه و وضعیت محصولات\",\"text\":\"مشاهده محصول فعال و وضعیت خرید\",\"url\":\"/store/\"},{\"title\":\"اجرای محاسبه‌گر رایگان بذر گندم\",\"text\":\"استفاده مستقیم از ابزار\",\"url\":\"/store/free-products/wheat-seed-rate-planner-v1/index.html\"},{\"title\":\"ثبت استعلام و پیگیری سفارش\",\"text\":\"ورود به فرم واقعی درخواست\",\"url\":\"/ask-master/index.php\"},{\"title\":\"آزمایشگاه دیجیتال\",\"text\":\"محاسبه و دریافت فایل خروجی\",\"url\":\"/digital-lab/\"}],\n            \"cta_title\":\"درخواست محصول یا همکاری\",\"cta_text\":\"برای پیگیری و استعلام، درخواست خود را در سامانه مشتریان ثبت کنید.\",\"cta_label\":\"ثبت درخواست\",\"cta_url\":\"/ask-master/index.php\"\n        },\n"

def validate_account():
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_CPANEL_USER")
    for p in (APP, TARGET.parent, TARGET, HTACCESS, RESTART.parent):
        if p.is_symlink() or not p.exists():
            raise RuntimeError("MISSING_OR_SYMLINK:" + p.name)
    if not TARGET.is_file() or not HTACCESS.is_file():
        raise RuntimeError("UNSAFE_SOURCE_FILE")
    if b'PassengerAppRoot "/home/zomorod2/Saeit"' not in HTACCESS.read_bytes():
        raise RuntimeError("PRODUCTION_PASSENGER_ANCHOR_MISSING")
    if TARGET.stat().st_uid != os.geteuid():
        raise RuntimeError("SOURCE_OWNERSHIP_CHANGED")

def digest_state(source):
    old = source.count(OLD)
    new = source.count(NEW)
    if (old, new) == (1, 0):
        changed = source.replace(OLD, NEW, 1)
        compile(changed, str(TARGET), "exec")
        if changed.count(NEW) != 1:
            raise RuntimeError("PATCH_POSTCONDITION_FAILED")
        return "needs-patch", changed
    if (old, new) == (0, 1):
        compile(source, str(TARGET), "exec")
        return "already-patched", source
    raise RuntimeError("MARKET_SOURCE_DRIFT_OR_AMBIGUITY")

def atomic_write(data, mode):
    fd, temp_path = tempfile.mkstemp(prefix=".market-section-", dir=str(TARGET.parent))
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

def restart():
    if RESTART.is_symlink() or RESTART.parent.is_symlink():
        raise RuntimeError("PASSENGER_RESTART_SYMLINK")
    RESTART.touch()

def backup_file(run_id):
    if not re.fullmatch(r"[0-9]{5,20}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    if BACKUPS.is_symlink():
        raise RuntimeError("UNSAFE_BACKUP_DIR")
    os.chmod(BACKUPS, 0o700)
    return BACKUPS / ("core-views-market-" + run_id + ".bak")

def publish(run_id):
    source = TARGET.read_text(encoding="utf-8")
    state, changed = digest_state(source)
    if state == "already-patched":
        print("MARKET_SECTION_ALREADY_APPLIED")
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
        atomic_write(changed.encode("utf-8"), mode)
        restart()
    except Exception:
        if TARGET.read_bytes() == changed.encode("utf-8"):
            atomic_write(data, mode)
            restart()
        raise
    print("MARKET_SECTION_PUBLISHED_BACKED_UP=1")

def check_public(url, contains, excludes=()):
    with urlopen(Request(url, headers={"User-Agent": "Zomorod-Market-Guard/1.0"}), timeout=25) as r:
        body = r.read(400000).decode("utf-8", "replace")
        if r.status != 200 or "noindex" in r.headers.get("X-Robots-Tag", "").lower():
            raise RuntimeError("LIVE_HTTP_OR_ROBOTS_REGRESSION")
    if any(x not in body for x in contains) or any(x in body for x in excludes):
        raise RuntimeError("LIVE_CONTENT_MISMATCH:" + url)
    return body

def verify_origin():
    if digest_state(TARGET.read_text(encoding="utf-8"))[0] != "already-patched":
        raise RuntimeError("LIVE_FILE_NOT_PATCHED")
    last = None
    for attempt in range(8):
        try:
            page = check_public(
                "https://zomorodmelal.ir/market/",
                ["بازار و محصولات", "محاسبه‌گر رایگان بذر گندم",
                 'href="/store/"', 'href="/ask-master/index.php"',
                 'href="/digital-lab/"'],
                ['href="/api/products/"', 'href="/api/orders/"'],
            )
            check_public("https://zomorodmelal.ir/store/", ["محاسبه‌گر علمی بذر گندم"])
            check_public("https://zomorodmelal.ir/", ["زمرد ملل"])
            print("MARKET_LIVE_TOOL_LINKS=4 INQUIRY_LINK=1 HOMEPAGE_OK=1")
            return
        except Exception as exc:
            last = repr(exc)
            if attempt != 7:
                time.sleep(6)
    raise RuntimeError("LIVE_VERIFICATION_FAILED:" + str(last))

def rollback(run_id):
    dest = backup_file(run_id)
    if not dest.is_file() or dest.is_symlink():
        print("NO_MARKET_BACKUP_FOR_THIS_RUN")
        return
    current = TARGET.read_text(encoding="utf-8")
    state, _ = digest_state(current)
    if state != "already-patched":
        raise RuntimeError("REFUSE_ROLLBACK_ON_SOURCE_DRIFT")
    original = dest.read_bytes()
    if original.decode("utf-8").count(OLD) != 1:
        raise RuntimeError("BACKUP_IS_NOT_EXPECTED_SOURCE")
    atomic_write(original, stat.S_IMODE(TARGET.stat().st_mode))
    restart()
    print("MARKET_SECTION_ROLLBACK_COMPLETE")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: market_guard.py preview|publish|verify-origin|rollback [run_id]")
    validate_account()
    cmd = sys.argv[1]
    if cmd == "preview" and len(sys.argv) == 2:
        print("MARKET_GUARD_STATE=" + digest_state(TARGET.read_text(encoding="utf-8"))[0])
    elif cmd == "publish" and len(sys.argv) == 3:
        publish(sys.argv[2])
    elif cmd == "verify-origin" and len(sys.argv) == 3:
        verify_origin()
    elif cmd == "rollback" and len(sys.argv) == 3:
        rollback(sys.argv[2])
    else:
        raise RuntimeError("UNRECOGNIZED_MODE")
