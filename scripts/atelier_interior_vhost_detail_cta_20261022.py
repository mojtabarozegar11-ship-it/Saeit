#!/usr/bin/env python3
"""Exact product detail CTA + CORRECT vhost Passenger restart marker (not staging marker)."""
import hashlib,json,os,pwd,stat,sys,tempfile
from pathlib import Path
APP=Path("/home/zomorod2/Saeit-staging")
VHOST=Path("/home/zomorod2/mojplaywin.com")
MARKER=VHOST/"tmp/restart.txt"
TARGET=APP/"core/templates/brands/mojplaywin/product.html"
SAFE=Path("/home/zomorod2/.private_mojplaywin_digital_products")
BACKUP=SAFE/"atelier-879-product-before-cta.html"
HOOK="{% elif product.pk == 72 or product.pk == 225 %}"
ADD="""{% elif product.pk == 879 %}
<p>Original Vector Edition: an editable HTML/CSS/JavaScript website kit with five original SVG interior illustrations, setup guide and one-site/client usage license. Demo photographs are NOT included.</p>
<p>Price: US $6.80. Sign in to create a secure order-specific ETH/TRX invoice. Private ZIP access follows independently confirmed payment.</p>
<a class="primary" href="/store/product/879/checkout/">Buy website kit — secure checkout at $6.80</a>
<a href="/accounts/register/">New customer? Create an account</a>
"""
def changed(original):
    txt=original.decode("utf8")
    if txt.count(HOOK)!=1 or "product.pk == 879" in txt:raise RuntimeError("DETAIL_TEMPLATE_CONFLICT")
    return txt.replace(HOOK,ADD+HOOK,1).encode("utf8")
def setup():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("UNEXPECTED_OWNER")
    if APP.is_symlink() or VHOST.is_symlink():raise RuntimeError("UNTRUSTED_APP_ROOT")
    if not (APP/"manage.py").is_file() or not (VHOST/"passenger_wsgi.py").is_file():
        raise RuntimeError("UNRECOGNIZED_VHOST_OR_APP")
    if not TARGET.is_file() or TARGET.is_symlink() or not TARGET.resolve().is_relative_to(APP.resolve()):
        raise RuntimeError("UNTRUSTED_TEMPLATE")
    if not SAFE.is_dir() or SAFE.is_symlink() or stat.S_IMODE(SAFE.stat().st_mode)&0o077:
        raise RuntimeError("UNSAFE_BACKUP_FOLDER")
    if not MARKER.is_file() or MARKER.is_symlink() or MARKER.stat().st_uid!=os.getuid():
        raise RuntimeError("ACTUAL_PASSENGER_MARKER_NOT_VERIFIED")
def write(path,data):
    mode=stat.S_IMODE(path.stat().st_mode)
    fd,tmp=tempfile.mkstemp(prefix=".atelier-879-detail-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as out:
            os.fchmod(out.fileno(),mode)
            out.write(data);out.flush();os.fsync(out.fileno())
        if path.is_symlink():raise RuntimeError("SYMLINK_AFTER_SNAPSHOT")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def reload_vhost():
    old=MARKER.stat().st_mtime_ns
    MARKER.touch(exist_ok=True)
    if MARKER.stat().st_mtime_ns<old:raise RuntimeError("RESTART_MARKER_CLOCK_REGRESSED")
def signed_in_ready():
    os.chdir(APP);sys.path.insert(0,str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    import django;django.setup()
    from core.models import Product
    from mpw_commerce.product_checkout_page import approved_for_checkout
    from types import SimpleNamespace
    p=Product.objects.select_related("knowledge_article").get(pk=879)
    req=SimpleNamespace(is_secure=lambda:True,get_host=lambda:"mojplaywin.com",
         user=SimpleNamespace(is_authenticated=True,is_active=True))
    if p.product_type!="digital" or str(p.price)!="6.80" or not approved_for_checkout(req,p):
        raise RuntimeError("PRODUCT_NOT_ELIGIBLE_FOR_NATIVE_CHECKOUT")
def activate():
    if os.environ.get("ATELIER_OWNER_ACTUAL_PRODUCT_CTA")!="20261022-owner-879":
        raise PermissionError("UNAPPROVED_DETAIL_CHANGE")
    setup();signed_in_ready()
    before=TARGET.read_bytes();after=changed(before)
    if BACKUP.is_symlink():raise RuntimeError("BACKUP_SYMLINK")
    if BACKUP.exists():
        if not BACKUP.is_file() or BACKUP.read_bytes()!=before:raise RuntimeError("PRIOR_BACKUP_MISMATCH")
    else:
        with BACKUP.open("xb") as out:
            os.fchmod(out.fileno(),0o600)
            out.write(before);out.flush();os.fsync(out.fileno())
    if TARGET.read_bytes()!=before:raise RuntimeError("CONCURRENT_TEMPLATE_MODIFICATION")
    write(TARGET,after)
    reload_vhost()
    print("ATELIER_ACTUAL_PRODUCT_DETAIL_CTA_UPDATED="+json.dumps({"product":879,
      "correct_restart_root":"mojplaywin.com","exact_detail_template_only":True,
      "other_template_files_changed":False,"signed_in_checkout_ready":True,
      "before_sha":hashlib.sha256(before).hexdigest()[:18],
      "after_sha":hashlib.sha256(after).hexdigest()[:18],"paid_buyer_tested":False},sort_keys=True))
def rollback():
    if os.environ.get("ATELIER_OWNER_ACTUAL_PRODUCT_CTA_ROLLBACK")!="20261022-owner-879":
        raise PermissionError("UNAPPROVED_ROLLBACK")
    setup()
    if not BACKUP.is_file() or BACKUP.is_symlink():raise RuntimeError("BACKUP_MISSING")
    before=BACKUP.read_bytes();expected=changed(before);current=TARGET.read_bytes()
    if current==expected:write(TARGET,before)
    elif current!=before:raise RuntimeError("CONCURRENT_DETAIL_EDIT_REFUSED")
    reload_vhost()
    print("ATELIER_ACTUAL_PRODUCT_DETAIL_CTA_ROLLED_BACK=EXACT_ORIGINAL")
if __name__=="__main__":
    arg=sys.argv[1] if len(sys.argv)==2 else ""
    if arg=="activate":activate()
    elif arg=="rollback":rollback()
    elif arg=="selftest":
        b=b"abc {% elif product.pk == 72 or product.pk == 225 %} xyz"
        assert b"/store/product/879/checkout/" in changed(b)
        assert "/home/zomorod2/mojplaywin.com" in str(MARKER)
        print("ATELIER_ACTUAL_PASSENGER_ROOT_SELFTEST=PASS")
    else:raise SystemExit("selftest|activate|rollback")
