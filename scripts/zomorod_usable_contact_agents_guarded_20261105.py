#!/usr/bin/env python3
"""Fix Zomorod contact and agent landing pages on the actual static site.

Surgical verified substitutions only. Exact-byte private backups, atomic
updates and automatic restore on independent live verification failure.
No submissions, payment, email, Django, or other website edits.
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
BACKUPS = HOME / ".private/usable-entry-backups"
ROUTES = ("agents", "contact")
PATCHES = {"agents":[["خدمات تخصصی هوش مصنوعی برای کشاورزان، باغداران، دامداران و فعالان زنجیره غذا؛ از تحلیل و آموزش تا تصمیم‌یارهای کاربردی.","آشنایی با کاربردهای هوش مصنوعی در کشاورزی و دامپروری و مسیر ثبت پرسش؛ موتور تحلیل اختصاصی داده و تصویر در این صفحه فعال نیست.",2],["این بخش برای ارائه خدمات تخصصی هوش مصنوعی طراحی شده است؛ خدمات پایه به‌صورت رایگان و محدود ارائه می‌شوند و خدمات حرفه‌ای و پرحجم از مسیر همکاری تجاری قابل ارائه‌اند.","برای پرسش عمومی و دریافت پاسخ اولیه از سامانه مسترایجنت استفاده کنید. بررسی تخصصی مزرعه، دام، تصویر یا داده تنها پس از ثبت شرح نیاز، پذیرش خدمت و تعیین دامنه انجام‌پذیر است؛ این صفحه ادعای اجرای خودکار این تحلیل‌ها ندارد.",1],["<h2>تحلیل هوشمند مزرعه و باغ</h2><p>تحلیل اطلاعات کشت، آبیاری، تغذیه، اقلیم و عملکرد برای کمک به تصمیم‌گیری بهتر.</p>","<h2>تحلیل مزرعه و باغ</h2><p>نوع کشت، آب، خاک و عملکرد را در شرح درخواست مشخص کنید؛ تحلیل اختصاصی فقط پس از پذیرش و احراز داده معتبر قابل ارائه است.</p>",1],["<h2>راهنمای هوشمند دامپروری</h2><p>تحلیل اطلاعات گله، تغذیه، مدیریت و شاخص‌های تولید؛ خروجی‌ها تصمیم‌یار هستند و جایگزین دامپزشک نیستند.</p>","<h2>راهنمای دامپروری</h2><p>پرسش عمومی درباره خوراک، مدیریت و شاخص‌های تولید قابل ثبت است؛ پاسخ اولیه جایگزین تشخیص دامپزشک نیست.</p>",1],["<h2>تحلیل تصویر و گزارش</h2><p>بررسی تصاویر و داده‌های ارسالی برای شناسایی الگوها، تهیه گزارش و پیشنهاد اقدامات بعدی.</p>","<h2>درخواست بررسی تصویر و داده</h2><p>موضوع و نوع داده را ابتدا در فرم توضیح دهید؛ بارگذاری و تشخیص خودکار تصویر در این صفحه فعال نیست.</p>",1],["<h2>پژوهش و امکان‌سنجی کشاورزی</h2><p>تحلیل منابع، فناوری‌ها، زنجیره‌های ارزش و تهیه گزارش‌های تخصصی برای پروژه‌های کشاورزی و دامپروری.</p>","<h2>مطالعه و امکان‌سنجی</h2><p>هدف، منابع و مقیاس طرح را شرح دهید تا امکان ارزیابی تخصصی و خروجی مورد انتظار مشخص شود.</p>",1],["<h2>آموزش هوشمند</h2><p>پاسخ‌های آموزشی و محتوای کاربردی برای یادگیری اصول تولید، مدیریت و فناوری‌های نوین.</p>","<h2>پرسش آموزشی عمومی</h2><p>از سامانه مسترایجنت برای ثبت پرسش و دریافت پاسخ اولیه عمومی استفاده کنید؛ پاسخ به معنی تأیید فنی نهایی نیست.</p>",1],["<h2>خدمات حرفه‌ای سازمانی</h2><p>گزارش‌های تخصصی، تحلیل‌های اختصاصی و خدمات متناسب با نیاز مزرعه، دامداری، مجموعه تولیدی یا پروژه.</p>","<h2>همکاری تخصصی سازمانی</h2><p>دامنه پروژه، داده‌های موجود و تحویل‌دادنی مطلوب را ثبت کنید؛ قیمت و زمان تنها پس از بررسی معتبر تعیین می‌شود.</p>",1],["<a href=\"/agriculture/\">کشاورزی ←</a><a href=\"/research/\">پژوهش ←</a><a href=\"/knowledge/\">دانشنامه ←</a><a href=\"/contact/\">همکاری ←</a>","<a href=\"/ask-master/index.php\">پرسش عمومی و ثبت درخواست ←</a><a href=\"/ask-master/status.php\">پیگیری درخواست ←</a><a href=\"/digital-lab/\">آزمایشگاه دیجیتال ←</a><a href=\"/agriculture/\">راهنماهای کشاورزی ←</a><a href=\"/research/\">پژوهش ←</a><a href=\"/contact/\">تماس رسمی ←</a>",1]],"contact":[["برای پژوهش، تولید، صنعت، فناوری، محصول و بازار با ما در ارتباط باشید.","برای همکاری پژوهشی، تولیدی، فناوری یا خرید، درخواست خود را در سامانه مشتریان ثبت و با شناسه پیگیری دنبال کنید.",2],["نوع همکاری و حوزه فعالیت موردنظر خود را مشخص کنید تا درخواست شما برای بررسی ارسال شود.","ثبت درخواست از پیوند «ثبت درخواست همکاری» انجام می‌شود. قیمت، زمان، امکان ارائه خدمت و پذیرش پروژه فقط پس از بررسی و پاسخ رسمی معتبر است.",1],["<a href=\"/research/\">پژوهش ←</a><a href=\"/market/\">بازار ←</a><a href=\"/api/health/\">وضعیت سامانه ←</a>","<a href=\"/ask-master/index.php\">ثبت درخواست همکاری ←</a><a href=\"/ask-master/status.php\">پیگیری درخواست ←</a><a href=\"/services/\">خدمات شرکت ←</a><a href=\"/market/\">بازار و ابزارها ←</a><a href=\"/research/\">پژوهش ←</a>",1]]}
MARKERS = {route: "<!-- zm-usable-" + route + "-20261105 -->" for route in ROUTES}
LINK_WRAP = '<div class="zm-v7-info-links">'

def target(route):
    if route not in ROUTES:
        raise RuntimeError("UNAUTHORIZED_ROUTE")
    return WEB / route / "index.html"

def validate():
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_CPANEL_USER")
    for p in (WEB, HTACCESS, *[target(route) for route in ROUTES]):
        if p.is_symlink() or not p.exists():
            raise RuntimeError("MISSING_OR_SYMLINK:" + p.name)
    for route in ROUTES:
        p=target(route)
        if p.parent.is_symlink() or not p.is_file() or p.stat().st_uid != os.geteuid():
            raise RuntimeError("UNSAFE_STATIC_TARGET:" + route)
    if not HTACCESS.is_file() or b'PassengerAppRoot "/home/zomorod2/Saeit"' not in HTACCESS.read_bytes():
        raise RuntimeError("PRIMARY_SITE_NOT_VERIFIED")

def patch(route, source):
    marker=MARKERS[route]
    if source.count(marker)==1:
        for old,new,count in PATCHES[route]:
            if new not in source or (old in source and old!=new):
                raise RuntimeError("INCONSISTENT_ALREADY_PATCHED:" + route)
        return "already-patched", source
    if marker in source:
        raise RuntimeError("DUPLICATE_PATCH_MARKER:" + route)
    result=source
    for old,new,count in PATCHES[route]:
        n=result.count(old)
        if n!=count:
            raise RuntimeError("SOURCE_DRIFT:" + route + ":" + str(count) + ":" + str(n))
        result=result.replace(old,new)
    if result.count(LINK_WRAP)!=1:
        raise RuntimeError("MISSING_LINK_GROUP:" + route)
    result=result.replace(LINK_WRAP,marker+LINK_WRAP,1)
    canonical='<link rel="canonical" href="https://zomorodmelal.ir/'+route+'/">'
    if source.count(canonical)!=1 or result.count(canonical)!=1:
        raise RuntimeError("CANONICAL_CHANGE:" + route)
    for token in ('<main','</main>','<h1','<footer','<style','<script'):
        if source.count(token)!=result.count(token):
            raise RuntimeError("HTML_STRUCTURE_CHANGE:" + route + ":" + token)
    if "zm-v7-information" not in source or "zm-v10-restored-content-and-unified-internal-pages" not in source:
        raise RuntimeError("EXPECTED_SITE_THEME_MISSING:" + route)
    if result.count(marker)!=1:
        raise RuntimeError("MARKER_NOT_SINGULAR:" + route)
    if route=="contact":
        for trust in ('#zm-trust-legal','#zm-trust-financial','#zm-trust-privacy','#zm-trust-terms'):
            if source.count(trust)!=result.count(trust):
                raise RuntimeError("TRUST_SECTION_LINK_CHANGED:" + trust)
    return "needs-patch", result

def atomic_write(p,data,mode):
    fd,tmp=tempfile.mkstemp(prefix=".zm-usable-",dir=str(p.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp,mode)
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def backup_path(route,run_id):
    if not re.fullmatch(r"[0-9]{5,20}",run_id):
        raise RuntimeError("INVALID_RUN_ID")
    if BACKUPS.parent.is_symlink():
        raise RuntimeError("UNSAFE_BACKUP_PARENT")
    BACKUPS.mkdir(mode=0o700,parents=True,exist_ok=True)
    if BACKUPS.is_symlink():
        raise RuntimeError("UNSAFE_BACKUP_ROOT")
    os.chmod(BACKUPS,0o700)
    return BACKUPS/("static-"+route+"-"+run_id+".bak")

def publish(run_id):
    files={}
    for route in ROUTES:
        p=target(route)
        source=p.read_text(encoding="utf-8")
        state,new=patch(route,source)
        files[route]=(p,source,new,state,stat.S_IMODE(p.stat().st_mode))
    backups={}
    for route,(p,source,new,state,mode) in files.items():
        if state=="already-patched":
            continue
        dest=backup_path(route,run_id)
        with dest.open("xb") as f:
            f.write(source.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        os.chmod(dest,0o600)
        backups[route]=dest
    published=[]
    try:
        for route,(p,source,new,state,mode) in files.items():
            if state=="needs-patch":
                atomic_write(p,new.encode("utf-8"),mode)
                published.append(route)
    except Exception:
        for route in reversed(published):
            p,source,new,state,mode=files[route]
            if p.read_bytes()==new.encode("utf-8"):
                atomic_write(p,source.encode("utf-8"),mode)
        raise
    print("CONTACT_AGENTS_STATIC_PUBLISHED="+str(len(published))+" BACKUPS="+str(len(backups)))

def public(url,includes,excludes=()):
    req=Request(url,headers={"User-Agent":"Zomorod-Usable-Entry-Guard/1.0"})
    with urlopen(req,timeout=25) as r:
        body=r.read(500000).decode("utf-8","replace")
        if r.status!=200 or "noindex" in r.headers.get("X-Robots-Tag","").lower():
            raise RuntimeError("PUBLIC_STATUS_OR_ROBOTS_REGRESSION:" + url)
    if any(t not in body for t in includes) or any(t in body for t in excludes):
        raise RuntimeError("PUBLIC_CONTENT_MISMATCH:" + url)
    return body

def verify():
    for route in ROUTES:
        if patch(route,target(route).read_text(encoding="utf-8"))[0]!="already-patched":
            raise RuntimeError("STATIC_TARGET_NOT_PATCHED:" + route)
    last=None
    for n in range(8):
        try:
            public("https://zomorodmelal.ir/agents/",
                   [MARKERS["agents"],'href="/ask-master/index.php"',
                    'href="/ask-master/status.php"','href="/digital-lab/"',
                    "موتور تحلیل اختصاصی داده و تصویر در این صفحه فعال نیست"])
            public("https://zomorodmelal.ir/contact/",
                   [MARKERS["contact"],'href="/ask-master/index.php"',
                    'href="/ask-master/status.php"','href="#zm-trust-legal"'],
                   ['href="/api/health/"'])
            public("https://zomorodmelal.ir/market/",['href="/store/"'])
            public("https://zomorodmelal.ir/",["زمرد ملل"])
            print("CONTACT_AGENTS_LIVE_PATHS=2 INQUIRY_LINKS=2 TRUST_PRESERVED=1")
            return
        except Exception as e:
            last=repr(e)
            if n!=7:
                time.sleep(6)
    raise RuntimeError("LIVE_VERIFICATION_FAILED:"+str(last))

def rollback(run_id):
    pairs=[]
    for route in ROUTES:
        dest=backup_path(route,run_id)
        if not dest.exists():
            continue
        if dest.is_symlink() or not dest.is_file():
            raise RuntimeError("INVALID_BACKUP:"+route)
        p=target(route)
        current=p.read_text(encoding="utf-8")
        if patch(route,current)[0]!="already-patched":
            raise RuntimeError("REFUSE_ROLLBACK_ON_DRIFT:"+route)
        original=dest.read_bytes()
        if patch(route,original.decode("utf-8"))[0]!="needs-patch":
            raise RuntimeError("INVALID_BACKUP_CONTENT:"+route)
        pairs.append((p,original,stat.S_IMODE(p.stat().st_mode)))
    for p,original,mode in pairs:
        atomic_write(p,original,mode)
    print("CONTACT_AGENTS_ROLLED_BACK="+str(len(pairs)))

if __name__ == "__main__":
    validate()
    if len(sys.argv)==2 and sys.argv[1]=="preview":
        for route in ROUTES:
            print("USABLE_ENTRY_PREVIEW_"+route.upper()+"="+patch(route,target(route).read_text(encoding="utf-8"))[0])
    elif len(sys.argv)==3 and sys.argv[1]=="publish":
        publish(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="verify-origin":
        verify()
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":
        rollback(sys.argv[2])
    else:
        raise RuntimeError("UNKNOWN_MODE")
