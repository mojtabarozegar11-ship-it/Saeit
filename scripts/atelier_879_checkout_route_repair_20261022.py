#!/usr/bin/env python3
"""Strictly scoped MojPlayWin 879 checkout routing with reversible cPanel deployment."""
import ast,hashlib,json,os,pwd,stat,sys,tempfile
from pathlib import Path
APP=Path("/home/zomorod2/Saeit-staging")
VHOST=Path("/home/zomorod2/mojplaywin.com")
TARGET=APP/"core/cryptopay_checkout.py"
MARKER=VHOST/"tmp/restart.txt"
SAFE=Path("/home/zomorod2/.private_mojplaywin_digital_products")
BACKUP=SAFE/"atelier-879-legacy-checkout-before-route.py"
OLD='if request.get_host().split(":")[0].lower() in ("mojplaywin.com","www.mojplaywin.com") and pk in (72,225):'
NEW='if request.get_host().split(":")[0].lower() in ("mojplaywin.com","www.mojplaywin.com") and pk in (72,225,879):'
def changed(before):
    raw=before.decode("utf-8")
    if raw.count(OLD)!=1 or NEW in raw:raise RuntimeError("LEGACY_CHECKOUT_ROUTING_CONFLICT")
    updated=raw.replace(OLD,NEW,1)
    ast.parse(updated)
    return updated.encode("utf-8")
def setup():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("OWNER_MISMATCH")
    if APP.is_symlink() or VHOST.is_symlink():raise RuntimeError("SYMLINK_ROOT")
    if not (APP/"manage.py").is_file() or not (VHOST/"passenger_wsgi.py").is_file():raise RuntimeError("APP_OR_VHOST_NOT_VERIFIED")
    if not TARGET.is_file() or TARGET.is_symlink() or not TARGET.resolve().is_relative_to(APP.resolve()):raise RuntimeError("INVALID_TARGET")
    if not SAFE.is_dir() or SAFE.is_symlink() or stat.S_IMODE(SAFE.stat().st_mode)&0o077:raise RuntimeError("UNSAFE_PRIVATE_BACKUP")
    if not MARKER.is_file() or MARKER.is_symlink() or MARKER.stat().st_uid!=os.getuid():raise RuntimeError("INVALID_PASSENGER_RESTART_MARKER")
def ready():
    os.chdir(APP);sys.path.insert(0,str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    import django;django.setup()
    from core.models import Product
    from mpw_commerce.product_checkout_page import approved_for_checkout
    from mpw_commerce.downloads import _private_file
    from types import SimpleNamespace
    p=Product.objects.select_related("knowledge_article").get(pk=879)
    req=SimpleNamespace(is_secure=lambda:True,get_host=lambda:"mojplaywin.com",user=SimpleNamespace(is_authenticated=True,is_active=True))
    if p.product_type!="digital" or str(p.price)!="6.80" or not approved_for_checkout(req,p):
        raise RuntimeError("NATIVE_CHECKOUT_NOT_READY")
    file=_private_file(SimpleNamespace(product=p))
    expected=(p.metadata.get("mpw_commerce") or {}).get("sha256")
    if file.suffix.lower()!=".zip" or not isinstance(expected,str) or hashlib.sha256(file.read_bytes()).hexdigest().lower()!=expected.lower():
        raise RuntimeError("PRIVATE_ZIP_INTEGRITY_FAILED")
def write(path,data):
    mode=stat.S_IMODE(path.stat().st_mode)
    fd,tmp=tempfile.mkstemp(prefix=".atelier-879-route-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as out:
            os.fchmod(out.fileno(),mode);out.write(data);out.flush();os.fsync(out.fileno())
        if path.is_symlink():raise RuntimeError("UNEXPECTED_SYMLINK")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def reload():
    MARKER.touch(exist_ok=True)
def smoke():
    from django.test import RequestFactory
    from types import SimpleNamespace
    # Use the live Python module/function and a safe GET. No order or payment is created.
    from core.cryptopay_checkout import checkout
    request=RequestFactory().get("/store/product/879/checkout/",secure=True,HTTP_HOST="mojplaywin.com")
    request.user=SimpleNamespace(is_authenticated=True,is_active=True)
    response=checkout(request,879)
    body=getattr(response,"content",b"").decode("utf-8","replace")
    if response.status_code!=200 or "/api/" not in body or "6.80" not in body:
        raise RuntimeError("SIGNED_IN_NATIVE_GET_FAILED_"+str(response.status_code))
    return {"status":response.status_code,"price_visible":True,"api_present":True}
def activate():
    if os.environ.get("ATELIER_OWNER_REPAIR_879_ROUTE")!="20261022-owner-879":
        raise PermissionError("OWNER_GUARD_REQUIRED")
    setup();ready()
    before=TARGET.read_bytes()
    after=changed(before)
    if BACKUP.is_symlink():raise RuntimeError("BACKUP_IS_SYMLINK")
    if BACKUP.exists():
        if not BACKUP.is_file() or BACKUP.read_bytes()!=before:raise RuntimeError("BACKUP_MISMATCH")
    else:
        with BACKUP.open("xb") as out:
            os.fchmod(out.fileno(),0o600);out.write(before);out.flush();os.fsync(out.fileno())
    if TARGET.read_bytes()!=before:raise RuntimeError("CONCURRENT_SOURCE_EDIT")
    write(TARGET,after)
    reload()
    trial=smoke()
    print("ATELIER_879_CHECKOUT_ROUTE_REPAIRED="+json.dumps({"exact_source_only":True,"other_products_72_225_preserved":True,"legacy_USD12_for_others_preserved":True,"private_zip_integrity":True,"signed_in_get":trial,"guest_payment_unmodified":True,"paid_buyer_tested":False,"before_sha":hashlib.sha256(before).hexdigest()[:16],"after_sha":hashlib.sha256(after).hexdigest()[:16]},sort_keys=True))
def rollback():
    if os.environ.get("ATELIER_OWNER_REPAIR_879_ROUTE_ROLLBACK")!="20261022-owner-879":
        raise PermissionError("ROLLBACK_GUARD_REQUIRED")
    setup()
    if not BACKUP.is_file() or BACKUP.is_symlink():raise RuntimeError("BACKUP_MISSING")
    before=BACKUP.read_bytes()
    expected=changed(before)
    current=TARGET.read_bytes()
    if current==expected:write(TARGET,before)
    elif current!=before:raise RuntimeError("CONCURRENT_CHANGE_ROLLBACK_REFUSED")
    reload()
    print("ATELIER_879_ROUTE_RESTORED=EXACT_ORIGINAL")
def selftest():
    sample='def checkout(request,pk):\n    '+OLD+'\n        pass\n'
    out=changed(sample.encode()).decode()
    assert OLD not in out and out.count(NEW)==1
    assert all(str(k) in NEW for k in (72,225,879))
    print("ATELIER_879_EXACT_ROUTE_PATCH_SELFTEST=PASS")
if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)==2 else ""
    if mode=="activate":activate()
    elif mode=="rollback":rollback()
    elif mode=="selftest":selftest()
    else:raise SystemExit("selftest|activate|rollback")
