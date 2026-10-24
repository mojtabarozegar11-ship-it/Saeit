#!/usr/bin/env python3
"""Restricted read-only merchant guest TRX implementation inventory. No credentials or wallets in output."""
import os,sys,json,ast,inspect,hashlib,re
from pathlib import Path
base=Path("/home/zomorod2/Saeit-staging")
root=Path("/home/zomorod2/mojplaywin.com")
os.chdir(base);sys.path.insert(0,str(base));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django;django.setup()
from django.conf import settings
from django.urls import resolve
from core.models import Product
from mpw_commerce.invoicing import RECEIVERS
from django.db import connection
for k,v in RECEIVERS.items():
    addr=v[1]
    print("GUEST_WALLET="+json.dumps({"asset":k,"network":v[0],"configured":bool(addr),"address_hash_prefix":hashlib.sha256(str(addr).encode()).hexdigest()[:12],"atomic_decimals":v[2]}))
for pid in (72,225):
    obj=Product.objects.get(pk=pid);data=obj.metadata or {}
    print("GUEST_ITEM="+json.dumps({"product":pid,"price":str(obj.price),"is_active":obj.active,"has_file":bool(data.get('private_file')),"has_sha":bool(data.get('sha256')),"flags":{k:data.get(k) is True for k in ('asset_verified','license_verified','quality_approved','factory_publication_permission','rights_cleared')} }))
for module in ("core/cryptopay_checkout.py","mpw_commerce/product_checkout_page.py","mpw_commerce/checkout_views.py","mpw_commerce/urls.py","mpw_commerce/models.py","mpw_commerce/invoicing.py","mpw_commerce/auto_reconcile.py","mpw_commerce/entitlements.py","scripts/mojplaywin_direct_wallet_discovery.py","config/urls.py"):
    path=base/module
    if not path.exists():continue
    raw=path.read_text("utf8","replace")
    tr=ast.parse(raw)
    definitions=[]
    for n in tr.body:
        if isinstance(n,(ast.FunctionDef,ast.ClassDef)):
            definitions.append({"name":n.name,"start":n.lineno,"end":n.end_lineno})
    keys=[x for x in ("path('store/product/","cryptopay_checkout.checkout","mpw_commerce.urls","checkout/","main_only") if x in raw]
    print("GUEST_FILE="+json.dumps({"file":module,"sha":hashlib.sha256(raw.encode()).hexdigest()[:20],"defs":definitions[:90],"signals":keys}))
for rel,names in {
"core/cryptopay_checkout.py":("checkout","product_delivery_ready","_file_for"),
"mpw_commerce/auto_reconcile.py":("discover_trx","reconcile_pending_orders"),
"mpw_commerce/checkout_views.py":("checkout_invoice","checkout_challenge"),
"mpw_commerce/product_checkout_page.py":("approved_for_checkout","product_checkout_page"),
"scripts/mojplaywin_direct_wallet_discovery.py":("discover_trx","fetch_indexer")
}.items():
    p=base/rel
    if not p.exists():continue
    tree=ast.parse(p.read_text("utf8"))
    for n in tree.body:
        if not isinstance(n,ast.FunctionDef) or n.name not in names:continue
        out=[]
        for line in ast.unparse(n).splitlines():
            t=line.strip()
            if not t or any(term in t.lower() for term in ("address","secret","private","password","api_key","token","wallet","hostname","endpoint","urlopen","uri","tx_hash")):
                continue
            out.append(t[:155])
        print("GUEST_LOGIC="+json.dumps({"file":rel,"name":n.name,"lines":out[:75]}))
# Current public routes are provided by services modules outside the static repo.
# Inspect only bounded control flow and render the active GET handler with a synthetic user.
import importlib, inspect, re
from django.test import RequestFactory
from types import SimpleNamespace
for modname in ("services.mpw_trx_public_pages","services.mpw_trx_commercial_web"):
    try:
        mod=importlib.import_module(modname)
        file=Path(mod.__file__)
        code=file.read_text("utf8","replace")
        tree=ast.parse(code)
        funcs=[]
        for node in tree.body:
            if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
            n=node.name.lower()
            if not any(k in n for k in ("product_checkout","trx","invoice","start","status","reconcile","purchase","select_order")):continue
            calls=sorted({ast.unparse(c.func).split(".")[-1] for c in ast.walk(node) if isinstance(c,ast.Call)})
            route_actions=[]
            for stmt in ast.walk(node):
                if isinstance(stmt,ast.If):
                    cond=ast.unparse(stmt.test)
                    route_actions.append(cond[:170])
            if node.name=="_select_order": calls=sorted(set(calls)|{"_select_order"})
            sensitive=re.compile(r"password|private.?key|secret|token|wallet|address|recipient|receiver|mnemonic|api.?key|authorization|credential",re.I)
            source_lines=[]
            for line in ast.unparse(node).splitlines()[:75]:
                source_lines.append("[REDACTED_SENSITIVE_LINE]" if sensitive.search(line) else line[:230])
            mutators=sorted({ast.unparse(c.func).split(".")[-1] for c in ast.walk(node)
                             if isinstance(c,ast.Call) and ast.unparse(c.func).split(".")[-1] in
                             ("create","save","update","delete","get_or_create","update_or_create","bulk_create")})
            funcs.append({"name":node.name,"line":node.lineno,"lines":node.end_lineno-node.lineno+1,
                          "calls":calls[:28],"mutators":mutators,"conditions":route_actions[:16],
                          "source_lines":source_lines})
        print("MPW_ACTIVE_SERVICE_MODULE="+json.dumps({"module":modname,"exists":True,"functions":funcs[:50]},ensure_ascii=False))
    except Exception as e:
        print("MPW_ACTIVE_SERVICE_MODULE="+json.dumps({"module":modname,"error":type(e).__name__}))
for route in ("/store/product/72/checkout/","/store/product/225/checkout/",
              "/commerce/trx-easy/start/72/","/commerce/trx-easy/invoice/1/",
              "/commerce/checkout/order/","/commerce/checkout/challenge/",
              "/commerce/checkout/verify/","/commerce/checkout/invoice/"):
    try:
        match=resolve(route); target=inspect.unwrap(match.func)
        print("MPW_ACTIVE_SERVICE_ROUTE="+json.dumps({"path":route,"module":target.__module__,
              "function":target.__name__,"name":match.url_name},ensure_ascii=False))
    except Exception as e:
        print("MPW_ACTIVE_SERVICE_ROUTE="+json.dumps({"path":route,"error":type(e).__name__}))
for pid in (72,225):
    request=RequestFactory().get("/store/product/%d/checkout/"%pid,secure=True,HTTP_HOST="mojplaywin.com")
    request.user=SimpleNamespace(pk=-1000,is_authenticated=True,is_active=True,username="readonly-buyer")
    try:
        response=resolve(request.path).func(request,product_id=pid)
        body=response.content.decode("utf8","replace")
        print("MPW_ACTIVE_CHECKOUT_RENDER="+json.dumps({"product":pid,"status":response.status_code,
             "bytes":len(response.content),"login_redirect":"login" in getattr(response,"url","").lower(),
             "has_trx_easy_form":"/commerce/trx-easy/start/%d/"%pid in body,
             "has_invoice_api":"/commerce/checkout/invoice/" in body,
             "has_challenge_api":"/commerce/checkout/challenge/" in body,
             "has_signup_return":("/accounts/register/?next=/store/product/%d/checkout/"%pid in body),
             "forms":re.findall(r'<form\\b[^>]{0,500}>',body,re.I)[:5],
             "trx_button":bool(re.search(r"Pay securely with TRX",body,re.I)),
             "read_only":True,"orders_created":False},ensure_ascii=False))
    except Exception as e:
        print("MPW_ACTIVE_CHECKOUT_RENDER="+json.dumps({"product":pid,"error":type(e).__name__,"read_only":True}))
print("GUEST_READONLY=PASS")

