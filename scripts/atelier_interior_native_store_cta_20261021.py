#!/usr/bin/env python3
"""Minimal exact-product buyer CTA and curated-store link, protected by byte-for-byte rollback."""
from __future__ import annotations
import hashlib,json,os,pwd,stat,sys,tempfile
from pathlib import Path
APP=Path("/home/zomorod2/Saeit-staging")
SAFE=Path("/home/zomorod2/.private_mojplaywin_digital_products")
P=APP/"core/templates/brands/mojplaywin/product.html"
S=APP/"core/templates/mojplaywin/store.html"
MARKER="{% elif product.pk == 72 or product.pk == 225 %}"
STORE_MARK="<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_END -->"
PRODUCT_ADDITION="""{% elif product.pk == 879 %}
<p>Original Vector Edition: an editable HTML/CSS/JavaScript website kit with five original SVG interior illustrations, setup guide and a one-site/client usage license. Demo photos are not included.</p>
<p>Price: $6.80 USD. Sign in to create your secure ETH/TRX order-specific invoice. Access to the private ZIP follows confirmed payment.</p>
<a class="primary" href="/store/product/879/checkout/">Buy website kit — $6.80</a>
<a href="/accounts/register/">New customer? Create an account</a>
"""
STORE_ADDITION="""
<section class="mpw-two-books" id="atelier-original-vector-879" aria-label="Original digital website kit">
  <article class="mpw-sale-book">
    <div class="mpw-book-cover" aria-hidden="true"><span>ORIGINAL VECTOR EDITION</span><strong>ATELIER INTERIOR</strong></div>
    <div>
      <h3>Atelier Interior — Client-Ready Website Kit</h3>
      <p>Editable responsive portfolio and inquiry page for an interior-design studio, with five original SVG room illustrations, setup instructions and license. Demo photographs are not included.</p>
      <p class="mpw-book-price">US $6.80</p>
      <p class="mpw-book-cta"><a href="/store/product/879/">View website kit details ↗</a> <a href="/store/product/879/checkout/">Go to secure checkout ↗</a></p>
      <p>Pay only using your verified order-specific ETH/TRX invoice. Private ZIP download follows confirmed payment.</p>
    </div>
  </article>
</section>
"""
BACKUPS={P:SAFE/"atelier-879-product-before-cta.html",S:SAFE/"atelier-879-store-before-cta.html"}
def sha(data):return hashlib.sha256(data).hexdigest()
def transformed(path,original):
    s=original.decode("utf8")
    if path==P:
        if s.count(MARKER)!=1 or "product.pk == 879" in s:raise RuntimeError("PRODUCT_TEMPLATE_MARKER_OR_CONFLICT")
        return s.replace(MARKER,PRODUCT_ADDITION+MARKER,1).encode("utf8")
    if path==S:
        if s.count(STORE_MARK)!=1 or 'id="atelier-original-vector-879"' in s:raise RuntimeError("STORE_TEMPLATE_MARKER_OR_CONFLICT")
        return s.replace(STORE_MARK,STORE_MARK+"\n"+STORE_ADDITION,1).encode("utf8")
    raise RuntimeError("UNEXPECTED_TEMPLATE")
def setup():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("OWNER_MISMATCH")
    if not SAFE.is_dir() or SAFE.is_symlink() or stat.S_IMODE(SAFE.stat().st_mode)&0o077:raise RuntimeError("UNSAFE_BACKUP_ROOT")
    if APP.is_symlink() or not (APP/"manage.py").is_file():raise RuntimeError("APP_NOT_VERIFIED")
    for p in (P,S):
        if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(APP.resolve()):raise RuntimeError("WRONG_TEMPLATE_TARGET")
    os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    import django;django.setup()
def atomically_set(path,data):
    current=path.stat()
    fd,name=tempfile.mkstemp(prefix=".atelier-879-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            os.fchmod(f.fileno(),stat.S_IMODE(current.st_mode));f.write(data);f.flush();os.fsync(f.fileno())
        if path.is_symlink():raise RuntimeError("TEMPLATE_BECAME_SYMLINK")
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
def snapshot(path,before):
    bk=BACKUPS[path]
    if bk.is_symlink():raise RuntimeError("BACKUP_IS_SYMLINK")
    if bk.exists():
        if not bk.is_file() or bk.read_bytes()!=before:raise RuntimeError("BACKUP_CONFLICT")
    else:
        with bk.open("xb") as f:
            os.fchmod(f.fileno(),0o600);f.write(before);f.flush();os.fsync(f.fileno())
def activate():
    if os.environ.get("ATELIER_OWNER_EXACT_CTA")!="20261021-owner-879":raise PermissionError("OWNER_NOT_APPROVED")
    setup()
    from core.models import Product
    from mpw_commerce.product_checkout_page import approved_for_checkout
    from types import SimpleNamespace
    p=Product.objects.select_related("knowledge_article").get(pk=879)
    mock=SimpleNamespace(is_secure=lambda:True,get_host=lambda:"mojplaywin.com",user=SimpleNamespace(is_authenticated=True,is_active=True))
    if p.title!="Atelier Interior — Client-Ready Website Kit" or p.product_type!="digital" or not approved_for_checkout(mock,p):
        raise RuntimeError("DO_NOT_PROMOTE_A_CHECKOUT_THAT_REJECTS_PRODUCT")
    before={p:p.read_bytes() for p in (P,S)}
    after={p:transformed(p,before[p]) for p in (P,S)}
    for p in (P,S):snapshot(p,before[p])
    try:
        for p in (P,S):
            if p.read_bytes()!=before[p]:raise RuntimeError("CONCURRENT_TEMPLATE_CHANGE")
            atomically_set(p,after[p])
        from django.template.loader import get_template
        get_template("brands/mojplaywin/product.html")
        get_template("mojplaywin/store.html")
    except Exception:
        for p in (P,S):
            if p.read_bytes()==after[p]:atomically_set(p,before[p])
        raise
    print("ATELIER_PUBLIC_STORE_BUY_CTA_INSTALLED="+json.dumps({
      "product_id":879,"exact_product_template_only":True,"store_curated_card_only":True,
      "checkout_gate_real_verified":True,"store_card_link":"/store/product/879/",
      "checkout_link":"/store/product/879/checkout/","rollback_files_available":True,
      "other_templates_changed":False,"paid_customer_tested":False},sort_keys=True))
def rollback():
    if os.environ.get("ATELIER_OWNER_EXACT_CTA_ROLLBACK")!="20261021-owner-879":raise PermissionError("ROLLBACK_NOT_APPROVED")
    setup()
    for p in (P,S):
        bk=BACKUPS[p]
        if bk.is_symlink() or not bk.is_file():raise RuntimeError("MISSING_ROLLBACK_BACKUP")
        original=bk.read_bytes()
        expected=transformed(p,original)
        if p.read_bytes()==expected:atomically_set(p,original)
        elif p.read_bytes()==original:continue
        else:raise RuntimeError("TEMPLATE_CONCURRENT_CHANGE_ABORT_ROLLBACK")
    print("ATELIER_EXACT_BUY_CTA_ROLLED_BACK=PREVIOUS_TEMPLATES_RESTORED")
if __name__=="__main__":
    arg=sys.argv[1] if len(sys.argv)==2 else ""
    if arg=="selftest":
        assert "/store/product/879/checkout/" in PRODUCT_ADDITION
        assert "atelier-original-vector-879" in STORE_ADDITION
        print("ATELIER_TEMPLATE_CTA_SELFTEST=PASS")
    elif arg=="activate":activate()
    elif arg=="rollback":rollback()
    else:raise SystemExit("selftest|activate|rollback")
