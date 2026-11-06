#!/usr/bin/env python3
"""Replace four nonfunctional public academy cards with working, verified links.

Fail closed on an unexpected public HTML version. No Django, database, mail,
customer, payment, or unrelated hosting files are modified.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

HOME = Path("/home/zomorod2")
TARGET = HOME / "public_html/amozeshgah/index.html"
BACKUPS = HOME / ".backups/zomorod-amozeshgah-static-catalog-20261106"
BASELINE_SHA256 = "95117d54a2ef9c79df34dd6ab80c50029a2cb8250f0428f304797d01d0ab8ba6"
MARKER = 'data-zm-functional-catalog="20261106"'
PUBLIC_URL = "https://zomorodmelal.ir/amozeshgah/"
LINKS = (
    "/agriculture/free-tools/20261025/farm-break-even/",
    "/agriculture/free-tools/20261025/import-landed-cost/",
    "/resources/20261025/farm-risk/",
    "/ask-master/index.php?service=1",
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run_key(value: str) -> str:
    if not re.fullmatch(r"[0-9]{6,20}", value):
        raise RuntimeError("STATIC_CATALOG_INVALID_RUN_ID")
    return value


def patch(raw: bytes, *, enforce_sha: bool = True) -> bytes:
    if enforce_sha and digest(raw) != BASELINE_SHA256:
        raise RuntimeError("STATIC_CATALOG_BASELINE_CHANGED_ABORT")
    text = raw.decode("utf-8")
    if MARKER in text:
        raise RuntimeError("STATIC_CATALOG_ALREADY_PRESENT")
    start = '    <section class="section" id="catalog"><div class="wrap">'
    end = '    <section class="section alt"><div class="wrap access">'
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError("STATIC_CATALOG_SECTION_AMBIGUOUS")
    begin = text.index(start)
    finish = text.index(end, begin)
    old = text[begin:finish]
    if (old.count('<article class="offer">') != 4 or
        'CONTENT CATALOG' not in old or
        'جزوه، دوره، آزمون و پروژه' not in old):
        raise RuntimeError("STATIC_CATALOG_CONTENT_CHANGED_ABORT")

    catalog = '''    <section class="section" id="catalog" data-zm-functional-catalog="20261106"><div class="wrap">
      <div class="section-heading"><div><span class="eyebrow">AVAILABLE NOW · VERIFIED LINKS</span><h2>ابزارهای کاربردی و راه ارتباط با خدمات</h2></div><p>این چهار مسیر اکنون در سایت فعال‌اند. محتوای آموزشی و دورهٔ فاقد صفحهٔ قابل‌استفاده در این فهرست تبلیغ نمی‌شود.</p></div>
      <div class="offer-grid" aria-label="ابزارها و خدمات فعال زمرد ملل">
        <a class="offer zm-active-offer" href="/agriculture/free-tools/20261025/farm-break-even/"><small>FREE · FARM ECONOMICS</small><h3>محاسبهٔ نقطهٔ سربه‌سر مزرعه</h3><p>هزینه و درآمد تولید را وارد کنید و نتیجهٔ محاسبه را در ابزار تخصصی ببینید.</p><b>ورود به محاسبه‌گر ←</b></a>
        <a class="offer zm-active-offer" href="/agriculture/free-tools/20261025/import-landed-cost/"><small>FREE · IMPORT ECONOMICS</small><h3>محاسبهٔ بهای تمام‌شدهٔ واردات</h3><p>ارزیابی اولیهٔ هزینه‌های واردات با ابزار موجود در سایت زمرد ملل.</p><b>باز کردن ابزار ←</b></a>
        <a class="offer zm-active-offer" href="/resources/20261025/farm-risk/"><small>FREE · RISK ASSESSMENT</small><h3>بررسی ریسک فعالیت کشاورزی</h3><p>برای تحلیل اولیهٔ ریسک‌های تولید و تصمیم‌گیری از این ابزار استفاده کنید.</p><b>مشاهدهٔ ابزار ریسک ←</b></a>
        <a class="offer zm-active-offer" href="/ask-master/index.php?service=1"><small>BUSINESS · SERVICE REQUEST</small><h3>درخواست خدمات تخصصی</h3><p>برای طرح نیاز واقعی شرکت یا مزرعه، فرم ثبت درخواست خدمات را باز کنید.</p><b>ورود به فرم درخواست ←</b></a>
      </div>
      <p style="font-size:12px;margin-top:19px">استفاده از این ابزارهای عمومی به معنی ثبت‌نام در دوره یا خرید محصول نیست. برای آشنایی با سایر خدمات <a href="/services/" style="color:var(--gold);text-decoration:underline">فهرست خدمات فعال</a> را ببینید.</p>
    </div></section>
'''
    text = text[:begin] + catalog + text[finish:]
    # Put the verified functional entry points in the first screen, too.
    original_cta = '<a class="nav-cta" href="#tracks">شروع یادگیری <span aria-hidden="true">←</span></a>'
    if text.count(original_cta) != 1:
        raise RuntimeError("STATIC_CATALOG_NAV_CHANGED_ABORT")
    text = text.replace(original_cta, '<a class="nav-cta" href="#catalog">ابزارهای فعال <span aria-hidden="true">←</span></a>', 1)
    text = text.replace('<a href="#catalog">جزوه و دوره</a>', '<a href="#catalog">ابزارها و خدمات</a>', 1)
    original_hero = '<a class="button secondary" href="#catalog">آشنایی با محتوای آموزشی</a>'
    if text.count(original_hero) != 1:
        raise RuntimeError("STATIC_CATALOG_HERO_CHANGED_ABORT")
    text = text.replace(original_hero, '<a class="button secondary" href="#catalog">ابزارهای آمادهٔ استفاده</a>', 1)
    text = text.replace('</style>', '.zm-active-offer{display:flex;flex-direction:column;transition:transform .2s,border-color .2s}.zm-active-offer:hover{transform:translateY(-3px);border-color:var(--gold)}.zm-active-offer b{margin-top:auto;padding-top:14px}</style>', 1)
    if text.count(MARKER) != 1 or any(text.count('href="' + link + '"') != 1 for link in LINKS):
        raise RuntimeError("STATIC_CATALOG_PATCH_VALIDATION_FAILED")
    return text.encode("utf-8")


def host_guard() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError("STATIC_CATALOG_USER_INVALID")
    for p in (HOME / "public_html", TARGET.parent, TARGET):
        if p.is_symlink():
            raise RuntimeError("STATIC_CATALOG_SYMLINK_FORBIDDEN")
    if not TARGET.is_file() or TARGET.stat().st_size > 300_000:
        raise RuntimeError("STATIC_CATALOG_TARGET_NOT_REGULAR")
    if BACKUPS.is_symlink() or (BACKUPS.exists() and not BACKUPS.is_dir()):
        raise RuntimeError("STATIC_CATALOG_BACKUP_UNSAFE")


def atomic(path: Path, data: bytes, mode: int) -> None:
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".zm-catalog-", delete=False) as f:
            name = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
        name = None
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def public_fetch() -> bytes:
    query = "?zm_catalog_release=" + str(time.time_ns())
    req = Request(PUBLIC_URL + query, headers={"Cache-Control": "no-cache", "User-Agent": "ZM-Guarded-Catalog/1.0"})
    with urlopen(req, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError("STATIC_CATALOG_PUBLIC_STATUS_UNEXPECTED")
        return response.read(300_001)


def main(mode: str, run_id: str) -> None:
    rid = run_key(run_id)
    if mode == "selftest":
        # Production HTML is not embedded in source control; catch parser and
        # encoding regressions using a minimal exact-structure fixture.
        fixture = ('<style></style><a class="nav-cta" href="#tracks">شروع یادگیری <span aria-hidden="true">←</span></a>'
                   '<a href="#catalog">جزوه و دوره</a><a class="button secondary" href="#catalog">آشنایی با محتوای آموزشی</a>'
                   '    <section class="section" id="catalog"><div class="wrap">CONTENT CATALOG جزوه، دوره، آزمون و پروژه'
                   + '<article class="offer">' * 4 + '    <section class="section alt"><div class="wrap access">')
        out = patch(fixture.encode(), enforce_sha=False)
        if MARKER.encode() not in out or any(link.encode() not in out for link in LINKS):
            raise RuntimeError("STATIC_CATALOG_SELFTEST_FAILED")
        print("STATIC_CATALOG_SELFTEST_PASS=yes")
        return
    host_guard()
    backup = BACKUPS / rid
    if mode in ("preview", "publish"):
        old = TARGET.read_bytes()
        modified = patch(old)
        if backup.exists():
            raise RuntimeError("STATIC_CATALOG_REUSED_RELEASE_ID")
        if mode == "preview":
            print("STATIC_CATALOG_LIVE_SHA_MATCH=yes")
            return
        backup.mkdir(mode=0o700, parents=True, exist_ok=False)
        with (backup / "index.original.html").open("xb") as file:
            file.write(old)
            file.flush()
            os.fsync(file.fileno())
        (backup / "index.original.html").chmod(0o600)
        atomic(TARGET, modified, TARGET.stat().st_mode & 0o777)
        print("STATIC_CATALOG_WRITTEN=yes")
        return
    if mode == "verify":
        if not backup.is_dir():
            raise RuntimeError("STATIC_CATALOG_RELEASE_BACKUP_MISSING")
        old = (backup / "index.original.html").read_bytes()
        expected = patch(old)
        if digest(TARGET.read_bytes()) != digest(expected):
            raise RuntimeError("STATIC_CATALOG_CONCURRENT_MODIFICATION")
        for _ in range(6):
            try:
                received = public_fetch()
                if (MARKER.encode() in received and
                    all(('href="' + link + '"').encode() in received for link in LINKS)):
                    print("STATIC_CATALOG_PUBLIC_VERIFIED=yes")
                    return
            except Exception:
                pass
            time.sleep(3)
        raise RuntimeError("STATIC_CATALOG_NOT_PUBLIC_ABORT")
    if mode == "rollback":
        if not backup.is_dir():
            print("STATIC_CATALOG_NO_WRITE_TO_ROLLBACK=yes")
            return
        old = (backup / "index.original.html").read_bytes()
        modified = patch(old)
        current = TARGET.read_bytes()
        if digest(current) != digest(modified):
            raise RuntimeError("STATIC_CATALOG_CONCURRENT_MODIFICATION_REFUSE_ROLLBACK")
        atomic(TARGET, old, TARGET.stat().st_mode & 0o777)
        print("STATIC_CATALOG_ROLLBACK_COMPLETE=yes")
        return
    raise RuntimeError("STATIC_CATALOG_INVALID_MODE")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: SCRIPT [selftest|preview|publish|verify|rollback] RUN_ID")
    main(sys.argv[1], sys.argv[2])
