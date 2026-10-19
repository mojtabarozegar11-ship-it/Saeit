#!/usr/bin/env python3
"""Safely link the two live MojPlayWin book cards to existing product/checkout routes.

Changes only a bounded section of the original main-domain store template;
no database writes, payment activation, wallet operations or Passenger restart.
"""
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path("/home/zomorod2")
APP = ROOT / "Saeit-staging"
TEMPLATE = APP / "core/templates/mojplaywin/store.html"
WSGI = ROOT / "mojplaywin.com/passenger_wsgi.py"
START = "<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_START -->"
END = "<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_END -->"
OPEN = "<!-- MPW_BOOK_LINKS_20261019_START -->"
CLOSE = "<!-- MPW_BOOK_LINKS_20261019_END -->"
NOTICE_OLD = "Payment is not open for these books yet."
NOTICE_NEW = ("Check the individual product pages for current checkout options. "
              "Sign-in may be required. Send funds only for a verified order-specific invoice. "
              "Private downloads follow confirmed payment; a listed book is not proof of an accepted transaction.")
LINKS = {
    72: ('<p class="mpw-book-price">US $7.50</p></div>',
         '<p class="mpw-book-price">US $7.50</p>\n'
         '<!-- MPW_BOOK_LINKS_20261019_START -->\n'
         '<p class="mpw-book-cta"><a href="/store/product/72/">View book details ↗</a> '
         '<a href="/store/product/72/checkout/">Go to secure checkout ↗</a></p>\n'
         '<!-- MPW_BOOK_LINKS_20261019_END -->\n</div>'),
    225: ('<p class="mpw-book-price">US $4.00</p></div>',
          '<p class="mpw-book-price">US $4.00</p>\n'
          '<!-- MPW_BOOK_LINKS_20261019_START -->\n'
          '<p class="mpw-book-cta"><a href="/store/product/225/">View book details ↗</a> '
          '<a href="/store/product/225/checkout/">Go to secure checkout ↗</a></p>\n'
          '<!-- MPW_BOOK_LINKS_20261019_END -->\n</div>'),
}
CSS = """<style id="mpw-book-links-style-20261019">
.mpw-two-books .mpw-book-cta{display:flex;gap:10px;flex-wrap:wrap;margin-top:15px}
.mpw-two-books .mpw-book-cta a{display:inline-flex;min-height:42px;align-items:center;padding:9px 13px;border-radius:10px;border:1px solid #dbb971;background:rgba(224,180,86,.13);color:#f4d99b;text-decoration:none;font-size:.84rem;font-weight:700}
.mpw-two-books .mpw-book-cta a:hover{background:rgba(224,180,86,.24)}
.mpw-two-books .mpw-book-cta a:focus-visible{outline:3px solid #f4d99b;outline-offset:3px}
</style>"""

def ready_environment():
    if APP.is_symlink() or TEMPLATE.is_symlink() or WSGI.is_symlink():
        raise RuntimeError("Protected symlink detected")
    if not TEMPLATE.is_file() or not WSGI.is_file() or not (APP/"manage.py").is_file():
        raise RuntimeError("Exact audited live main-store path is missing")
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8","replace"):
        raise RuntimeError("Unexpected Passenger app pin")

def check_routes_and_book_flags():
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.urls import resolve
    from django.conf import settings
    from core.models import Product
    gates=("MPW_COMMERCE_RELEASE_READY", "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
           "MPW_COMMERCE_INVOICING_ENABLED", "MPW_COMMERCE_SETTLEMENT_ENABLED",
           "MPW_COMMERCE_REAL_RPC_ENABLED", "MPW_COMMERCE_AUTORECONCILE_ENABLED",
           "MPW_COMMERCE_DOWNLOADS_ENABLED")
    if not all(getattr(settings,g,False) is True for g in gates):
        raise RuntimeError("Commerce runtime gates not configured; no checkout links published")
    from core.cryptopay_checkout import product_delivery_ready
    for pk,price in ((72,"7.50"),(225,"4.00")):
        p=Product.objects.filter(pk=pk).first()
        if p is None or not p.active or p.currency!="USD" or str(p.price)!=price:
            raise RuntimeError("Book is unavailable or price differs from audited catalog")
        m=p.metadata if isinstance(p.metadata,dict) else {}
        if m.get("checkout_enabled") is not True or m.get("payment_live") is not True:
            raise RuntimeError("Book checkout flags are not active")
        if not product_delivery_ready(p):
            raise RuntimeError("Verified private delivery file is not ready")
        for route in (f"/store/product/{pk}/",f"/store/product/{pk}/checkout/"):
            match=resolve(route)
            if match is None:
                raise RuntimeError("No checkout route found")
    print("MPW_BOOK_LINKS_ROUTE_PREFLIGHT="+json.dumps({"ids":[72,225],
        "routes_resolve":True,"product_delivery_ready":True,"payment_settlement_test_executed":False}))

def transform(original):
    text=original.decode("utf8")
    if text.count(START)!=1 or text.count(END)!=1:
        raise RuntimeError("Original book section boundaries missing")
    before, remainder=text.split(START,1)
    segment, after=remainder.split(END,1)
    if OPEN in segment or CLOSE in segment or "mpw-book-links-style-20261019" in segment:
        raise RuntimeError("Checkout links already applied")
    if segment.count(NOTICE_OLD)!=1:
        raise RuntimeError("Expected stale public payment notice changed")
    for pk,(a,b) in LINKS.items():
        if segment.count(a)!=1 or segment.count(f'id="mpw-sale-book{pk}"')!=1:
            raise RuntimeError("Book card or price mismatch: "+str(pk))
        segment=segment.replace(a,b,1)
    segment=segment.replace(NOTICE_OLD,NOTICE_NEW,1)
    if segment.count("Catalog listing · checkout pending")==2:
        segment=segment.replace("Catalog listing · checkout pending","Digital PDF · checkout sign-in may be required")
    segment=CSS+"\n"+segment
    result=(before+START+segment+END+after).encode("utf8")
    if result.count(OPEN.encode())!=2 or result.count(CLOSE.encode())!=2:
        raise RuntimeError("Link card marker count mismatch")
    if NOTICE_OLD.encode() in result[result.index(START.encode()):result.index(END.encode())]:
        raise RuntimeError("Stale notice remains in changed scope")
    if any(token in CSS.lower() for token in ("<form", "<script", "wallet", "<iframe")):
        raise RuntimeError("Unexpected active behavior")
    return result

def atomic_write(content):
    mode=stat.S_IMODE(TEMPLATE.stat().st_mode)
    fd,name=tempfile.mkstemp(prefix=".mpw-two-book-links-",dir=TEMPLATE.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(content);f.flush();os.fsync(f.fileno())
        os.replace(name,TEMPLATE)
    finally:
        if os.path.exists(name):os.unlink(name)

def backup(run):
    return ROOT/(".mpw-two-book-links-"+run+".backup")

def publish(run):
    ready_environment()
    check_routes_and_book_flags()
    old=TEMPLATE.read_bytes()
    new=transform(old)
    p=backup(run)
    if p.exists() or p.is_symlink():
        raise RuntimeError("Backup path already exists")
    with p.open("xb") as f:
        os.chmod(p,0o600)
        f.write(old);f.flush();os.fsync(f.fileno())
    atomic_write(new)
    if TEMPLATE.read_bytes()!=new:
        raise RuntimeError("File integrity check failed")
    print("MPW_TWO_BOOK_LINKS="+json.dumps({"published":True,"only_store_template":True,
        "money_collected":False,"payment_configuration_changed":False,
        "old_sha256":hashlib.sha256(old).hexdigest(),"new_sha256":hashlib.sha256(new).hexdigest()}))

def rollback(run):
    ready_environment()
    p=backup(run)
    if p.is_symlink() or not p.is_file():
        raise RuntimeError("Backup not found")
    original=p.read_bytes()
    if transform(original)!=TEMPLATE.read_bytes():
        raise RuntimeError("Other edits since installation; safe rollback blocked")
    atomic_write(original)
    print("MPW_TWO_BOOK_LINKS_ROLLBACK=PASS")

def selftest():
    snippet=('before'+START+
            '<article id="mpw-sale-book72"><p class="mpw-book-price">US $7.50</p></div>'
            '<span>Catalog listing · checkout pending</span>'
            '<article id="mpw-sale-book225"><p class="mpw-book-price">US $4.00</p></div>'
            '<span>Catalog listing · checkout pending</span>'
            '<p>Payment is not open for these books yet.</p>'+END+'after').encode("utf8")
    revised=transform(snippet)
    assert revised.count(b'/store/product/72/checkout/')==1
    assert revised.count(b'/store/product/225/checkout/')==1
    assert NOTICE_OLD.encode() not in revised
    assert b'Payment is not open for these books yet.' in snippet
    try:
        transform(revised)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Duplicate modification allowed")
    print("MPW_TWO_BOOK_CHECKOUT_LINKS_SELFTEST=PASS")

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":
        selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ("publish","rollback") and re.fullmatch(r"[0-9]{8,20}",sys.argv[2]):
        (publish if sys.argv[1]=="publish" else rollback)(sys.argv[2])
    else:
        raise SystemExit("Use selftest|publish RUN_ID|rollback RUN_ID")
