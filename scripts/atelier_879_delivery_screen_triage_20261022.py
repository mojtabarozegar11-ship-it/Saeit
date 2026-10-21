#!/usr/bin/env python3
"""Read-only triage for customer screenshot: 'Product delivery is not ready.'"""
import hashlib,inspect,json,os,sys,urllib.request,urllib.error
from pathlib import Path
APP=Path("/home/zomorod2/Saeit-staging")
VHOST=Path("/home/zomorod2/mojplaywin.com")
assert (APP/"manage.py").is_file() and (VHOST/"passenger_wsgi.py").is_file()
os.chdir(APP);sys.path.insert(0,str(APP))
os.environ["DJANGO_SETTINGS_MODULE"]="config.settings";os.environ["PYTHONDONTWRITEBYTECODE"]="1"
import django;django.setup()
from django.urls import resolve
from core.models import Product
p=Product.objects.get(pk=879)
md=p.metadata if isinstance(p.metadata,dict) else {}
print("ATELIER_DELIVERY_PRODUCT="+json.dumps({"id":p.pk,"active":p.active,"type":p.product_type,"price":str(p.price),"metadata_keys":sorted(md.keys()),"delivery_metadata_flags":{k:v for k,v in md.items() if isinstance(v,(bool,int)) and any(w in k.lower() for w in ("delivery","download","sale","checkout","approval","quality"))}},sort_keys=True))
for relroot in ["mpw_commerce","core","config"]:
    root=APP/relroot
    count=0
    for f in root.rglob("*.py"):
        count+=1
        if count>2200:break
        if f.stat().st_size>400000:continue
        try:body=f.read_text("utf-8",errors="replace")
        except OSError:continue
        if "Product delivery is not ready" in body or "delivery is not ready" in body.lower():
            print("ATELIER_MESSAGE_SOURCE="+json.dumps({"file":str(f.relative_to(APP)),"matches":[{"line":n+1,"text":line.strip()[:240]} for n,line in enumerate(body.splitlines()) if "delivery is not ready" in line.lower()][:8]}))
for relroot in ["design-preview-20261017"]:
    root=VHOST/relroot
    count=0
    if root.is_dir():
        for f in root.rglob("*.php"):
            count+=1
            if count>80:break
            if f.stat().st_size>500000:continue
            try:body=f.read_text("utf-8",errors="replace")
            except OSError:continue
            if "delivery is not ready" in body.lower():
                print("ATELIER_PHP_MESSAGE_SOURCE="+str(f.relative_to(VHOST)))
paths=["/commerce/download/879/","/store/product/879/download/","/store/product/879/checkout/","/store/product/879/","/accounts/login/"]
for route in paths:
    try:
        match=resolve(route)
        view=match.func
        source=inspect.getsource(view)
        print("ATELIER_RESOLVE="+json.dumps({"route":route,"source":str(Path(inspect.getsourcefile(view) or "").relative_to(APP)) if str(inspect.getsourcefile(view) or "").startswith(str(APP)) else str(inspect.getsourcefile(view) or ""),"function":getattr(view,"__qualname__",""),"source_mentions_delivery_not_ready":"delivery is not ready" in source.lower()}))
    except Exception as ex:
        print("ATELIER_RESOLVE_ERROR="+json.dumps({"route":route,"error":type(ex).__name__}))
for route in paths:
    try:
        req=urllib.request.Request("https://mojplaywin.com"+route,headers={"User-Agent":"Atelier-Owner-ReadOnly-Delivery-Diagnostic/1.0"})
        opener=urllib.request.build_opener(urllib.request.HTTPHandler())
        response=opener.open(req,timeout=15)
        data=response.read(70000).decode("utf-8","replace")
        print("ATELIER_PUBLIC_GET="+json.dumps({"route":route,"status":response.status,"effective_path":response.url.split("mojplaywin.com",1)[-1][:100],"delivery_not_ready":"Product delivery is not ready" in data,"has_checkout":"/store/product/879/checkout/" in data,"content_type":response.headers.get("Content-Type","")[:60]}))
    except urllib.error.HTTPError as ex:
        data=ex.read(70000).decode("utf-8","replace")
        print("ATELIER_PUBLIC_GET="+json.dumps({"route":route,"status":ex.code,"delivery_not_ready":"Product delivery is not ready" in data}))
    except Exception as ex:
        print("ATELIER_PUBLIC_GET_ERROR="+json.dumps({"route":route,"error":type(ex).__name__}))
print("ATELIER_READ_ONLY_SCREENSHOT_TRIAGE=COMPLETE")
# Focused source view: legacy vs native checkout, read-only.
import importlib
for dotted in ("core.cryptopay_checkout.checkout","mpw_commerce.product_checkout_page.product_checkout_page","mpw_commerce.product_checkout_page.approved_for_checkout","mpw_commerce.product_checkout_page._private_file"):
    try:
        module,name=dotted.rsplit(".",1)
        fn=getattr(importlib.import_module(module),name)
        src=inspect.getsource(fn).splitlines()
        selected=[]
        for idx,line in enumerate(src,1):
            clean=line.strip()
            if any(w in clean.lower() for w in ("password","secret","token","private_key","api_key")):
                continue
            if idx<=150 and any(w in clean.lower() for w in ("def ","product","asset","ready","file","if ","return ","render(","redirect","invoice","order","payment","checkout","download","metadata","path(","getattr","exists","is_file","user","request")):
                selected.append({"line":idx,"source":clean[:240]})
        origin=inspect.getsourcefile(fn)
        print("ATELIER_TWO_CHECKOUT_SOURCES="+json.dumps({"handler":dotted,"relative_source":str(Path(origin).relative_to(APP)) if origin and origin.startswith(str(APP)) else "external","relevant_lines":selected},sort_keys=True))
    except Exception as ex:
        print("ATELIER_TWO_CHECKOUT_SOURCE_ERROR="+json.dumps({"handler":dotted,"type":type(ex).__name__}))
for key in ("private_file","mpw_commerce","fulfillment_status","digital_asset_format"):
    val=md.get(key)
    if key=="private_file":
        path=Path(str(val)) if isinstance(val,str) else None
        print("ATELIER_DIGITAL_FILE_SAFETY="+json.dumps({"metadata_value_is_str":isinstance(val,str),"absolute":bool(path and path.is_absolute()),"exists":bool(path and path.is_file()),"suffix":path.suffix if path else None,"size":path.stat().st_size if path and path.is_file() else None}))
    elif key=="mpw_commerce":
        print("ATELIER_COMMERCE_CONFIG_KEYS="+json.dumps({"is_dict":isinstance(val,dict),"keys":sorted(val.keys()) if isinstance(val,dict) else []}))
    else:
        print("ATELIER_DELIVERY_META="+json.dumps({"key":key,"value":str(val)[:120]}))
