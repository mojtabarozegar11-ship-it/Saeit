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
             "forms":re.findall(r'<form\b[^>]{0,500}>',body,re.I)[:5],
             "form_excerpt":re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",(re.findall(r'<form\b[^>]*>.*?</form>',body,re.I|re.S) or [""])[0]))[:400],
             "submit_buttons":re.findall(r'<button\b[^>]*>.*?</button>',body,re.I|re.S)[:8],
             "trx_button":bool(re.search(r"Pay securely with TRX",body,re.I)),
             "read_only":True,"orders_created":False},ensure_ascii=False))
    except Exception as e:
        print("MPW_ACTIVE_CHECKOUT_RENDER="+json.dumps({"product":pid,"error":type(e).__name__,"read_only":True}))
# Read-only aggregate of active buyer records; no customer identity fields.
from django.db.models import Count
from core.models import Order, PaymentIntent
for label,model in (("Order",Order),("PaymentIntent",PaymentIntent)):
    aggregate={"model":label,"count":model.objects.count()}
    if any(field.name=="status" for field in model._meta.fields):
        aggregate["status_counts"]={str(row["status"]):row["n"] for row in model.objects.values("status").annotate(n=Count("pk"))}
    print("MPW_LIVE_ORDER_AGGREGATE="+json.dumps(aggregate,ensure_ascii=False))

# In-memory execution of the real order selector; production ORM writes are replaced.
import contextlib, tempfile
from unittest.mock import patch
from django.db import transaction
import core.models as core_models
import mpw_commerce.downloads as download_module
import services.mpw_trx_commercial_web as commercial
class EmptyQuery:
    def select_for_update(self): return self
    def filter(self,**kwargs): return self
    def order_by(self,*args): return self
    def first(self): return None
    def __getitem__(self,item): return []
class FakeUserManager:
    def select_for_update(self): return self
    def get(self,**kwargs): return SimpleNamespace(pk=987654)
class FakeUserModel: objects=FakeUserManager()
class FakeProductManager:
    def select_for_update(self): return self
    def get(self,**kwargs): return actual_product
class FakeOrder:
    objects=None
    def __init__(self,pk=987650,**kwargs): self.pk=pk; self.__dict__.update(kwargs)
class FakeOrderManager:
    creates=[]
    def select_for_update(self): return self
    def filter(self,**kwargs): return EmptyQuery()
    def create(self,**kwargs):
        item=FakeOrder(**kwargs); self.creates.append(item); return item
FakeOrder.objects=FakeOrderManager()
class FakeItemManager:
    creates=[]
    def create(self,**kwargs):
        item=SimpleNamespace(pk=987651,id=987651,**kwargs); self.creates.append(item); return item
class FakeItemModel: objects=FakeItemManager()
class FakeIntentQuery:
    def filter(self,**kwargs): return self
    def first(self): return None
class FakeIntentManager:
    def filter(self,**kwargs): return FakeIntentQuery()
class FakeIntentModel: objects=FakeIntentManager()
actual_product=Product.objects.select_related("knowledge_article").get(pk=72)
with tempfile.TemporaryDirectory(prefix="mpw-readonly-order-sim-") as tmp:
    fakefile=Path(tmp)/"product.pdf"
    fakefile.write_bytes(b"%PDF-1.4\n% SIMULATION ONLY\n%%EOF\n")
    fakefile.chmod(0o600)
    intent_calls=[]
    def fake_reserve(*args,**kwargs): intent_calls.append({"args":len(args),"kwargs":sorted(kwargs)}); return (987652,None,None)
    patches=[
        patch.object(core_models,"Product",SimpleNamespace(objects=FakeProductManager())),
        patch.object(core_models,"Order",FakeOrder),
        patch.object(core_models,"OrderItem",FakeItemModel),
        patch.object(core_models,"PaymentIntent",FakeIntentModel),
        patch("django.contrib.auth.get_user_model",return_value=FakeUserModel),
        patch.object(transaction,"atomic",side_effect=lambda **kwargs:contextlib.nullcontext()),
        patch.object(download_module,"_private_file",return_value=fakefile),
        patch.object(commercial,"reserve_commercial_intent",side_effect=fake_reserve),
    ]
    with contextlib.ExitStack() as stack:
        for item in patches: stack.enter_context(item)
        produced=commercial._select_order(72,987654,connection)
    assert produced==987652 and len(FakeOrderManager.creates)==1 and len(FakeItemManager.creates)==1 and len(intent_calls)==1
    print("MPW_ACTIVE_ORDER_INTENT_SIMULATION="+json.dumps({"product":72,"order_created_in_memory":True,
          "item_created_in_memory":True,"payment_intent_created_in_memory":True,"intent_id_returned":produced,
          "production_db_writes":False,"money_transferred":False},ensure_ascii=False))

# Exercise the real start endpoint and decorators with order selection mocked.
request=RequestFactory().post("/commerce/trx-easy/start/72/",secure=True,HTTP_HOST="mojplaywin.com")
request.user=SimpleNamespace(pk=987654,is_authenticated=True,is_active=True)
with patch.object(commercial,"_ensure_live",return_value=connection), patch.object(commercial,"_select_order",return_value=987652):
    response=resolve("/commerce/trx-easy/start/72/").func(request,product_id=72)
assert response.status_code in (301,302,303,307,308) and response["Location"]=="/commerce/trx-easy/invoice/987652/"
print("MPW_ACTIVE_START_POST_SIMULATION="+json.dumps({"status":response.status_code,
      "redirect":response["Location"],"selection_mocked":True,"production_db_writes":False},ensure_ascii=False))
print("GUEST_READONLY=PASS")

