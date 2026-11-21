#!/usr/bin/env python3
"""Read-only metadata for production TRX checkout integration; no secrets/rows."""
import os,sys,json,inspect,importlib,pkgutil
from pathlib import Path
ROOT=Path("/home/zomorod2/Saeit-staging")
SITE=Path("/home/zomorod2/mojplaywin.com")
if not ROOT.is_dir() or ROOT.is_symlink() or SITE.is_symlink():
    raise RuntimeError("Unexpected host")
assert "APP='/home/zomorod2/Saeit-staging'" in (SITE/"passenger_wsgi.py").read_text("utf8","replace")
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.conf import settings
from django.urls import get_resolver
from core.models import Product
from mpw_commerce import buyer_orders,product_checkout_page,settlement
from mpw_commerce.invoicing import RECEIVERS
from mpw_commerce.models import CommerceFulfillment

def callable_info(func):
    if not callable(func):
        return {"available":False}
    module=getattr(func,"__module__","")
    code=getattr(func,"__code__",None)
    return {"available":True,"module":str(module)[:110],"args":list(code.co_varnames[:code.co_argcount]) if code else []}

raw=[]
def walk(patterns,prefix="",depth=0):
    if depth>3:return
    for route in patterns:
        pattern=str(route.pattern)
        if not prefix and pattern.startswith("admin"):continue
        if getattr(route,"url_patterns",None) is not None:
            if any(x in (prefix+pattern).lower() for x in ("commerce","store","checkout","trx","wallet","account","crypto")):
                walk(route.url_patterns,prefix+pattern,depth+1)
        else:
            desc=prefix+pattern
            if any(t in desc.lower() for t in ("commerce","store","checkout","trx","wallet","crypto","download")):
                raw.append({"pattern":desc[:170],"name":str(route.name or "")[:75],
                            "module":str(getattr(route.callback,"__module__",""))[:110]})
walk(get_resolver().url_patterns)

private=buyer_orders.__dict__.get("_private_file")
report={
 "scope":"read_only_django_route_imports","writes":0,
 "buyer_orders_private_file":callable_info(private),
 "checkout_page_private_file":callable_info(product_checkout_page.__dict__.get("_private_file")),
 "settlement_private_file":callable_info(settlement.__dict__.get("_private_file")),
 "private_delivery_modules":[item.name for item in pkgutil.iter_modules([str(ROOT/"mpw_commerce")]) if any(x in item.name for x in ("deliver","fulfill","download","asset","file","private","order","buyer","checkout","wallet","quote","rate"))],
 "live_commerce_routes":raw[:100],
 "commerce_fulfillment_fields":[{"field":f.name,"null":bool(f.null),"unique":bool(f.unique)} for f in CommerceFulfillment._meta.fields],
 "receiver_tuple_length":len(RECEIVERS.get("TRX",())) if isinstance(RECEIVERS.get("TRX"),(tuple,list)) else 0,
 "receiver_asset_has_valid_address":bool(RECEIVERS.get("TRX") and isinstance(RECEIVERS["TRX"][1],str) and len(RECEIVERS["TRX"][1])==34),
}
prod=Product.objects.filter(pk=72).first()
if prod is not None and private is not None:
    from types import SimpleNamespace
    try:
        f=private(SimpleNamespace(product=prod))
        report["book_72_file_ready"]=bool(f.is_file() and not f.is_symlink())
    except Exception as exc:
        report["book_72_file_error"]=type(exc).__name__
print("MPW_TRX_LIVE_CONTRACT="+json.dumps(report,sort_keys=True))
