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
             "trx_button":bool(re.search(r"Create invoice and pay with TRX",body,re.I)),
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

# Privacy-preserving product-level funnel counts; never emit customer identifiers.
from django.db.models import Sum,Min,Max,Q
from core.models import OrderItem,LedgerEntry,PaymentWebhookEvent
for pid in (72,225):
    rows=OrderItem.objects.filter(product_id=pid).values(
        "order__status","order__payment_intent__status","order__payment_intent__provider",
        "order__payment_intent__provider_reference"
    ).annotate(
        order_count=Count("order_id",distinct=True),
        units=Sum("quantity"),
        # Keep legacy account-holder count for compatibility, but never present
        # staff-owned checkout attempts as independent external customers.
        distinct_buyers=Count("order__customer_id",distinct=True),
        nonstaff_orders=Count(
            "order_id", distinct=True,
            filter=Q(order__customer__is_staff=False,
                     order__customer__is_superuser=False)),
        distinct_nonstaff_buyers=Count(
            "order__customer_id", distinct=True,
            filter=Q(order__customer__is_staff=False,
                     order__customer__is_superuser=False)),
        first_order=Min("order__created_at"),
        last_order=Max("order__created_at"),
    ).order_by("order__status","order__payment_intent__status")
    safe_rows=[]
    for row in rows:
        safe_rows.append({
            "order_status":row["order__status"],
            "payment_status":row["order__payment_intent__status"],
            "payment_provider":row["order__payment_intent__provider"],
            "provider_reference_present":bool(row["order__payment_intent__provider_reference"]),
            "orders":row["order_count"],"units":row["units"],
            "distinct_buyers":row["distinct_buyers"],
            "nonstaff_orders":row["nonstaff_orders"],
            "distinct_nonstaff_buyers":row["distinct_nonstaff_buyers"],
            "buyer_count_scope": "nonstaff excludes is_staff and is_superuser; not proof of human purchase",
            "first_order":row["first_order"].isoformat() if row["first_order"] else None,
            "last_order":row["last_order"].isoformat() if row["last_order"] else None,
        })
    print("MPW_BOOK_ORDER_FUNNEL="+json.dumps({"product":pid,"rows":safe_rows},ensure_ascii=False))
    ledger=LedgerEntry.objects.filter(order__items__product_id=pid).values("entry_type").annotate(count=Count("pk")).order_by("entry_type")
    print("MPW_BOOK_LEDGER="+json.dumps({"product":pid,"entry_counts":list(ledger)},ensure_ascii=False))
    hooks=PaymentWebhookEvent.objects.filter(payment_intent__order__items__product_id=pid).values(
        "provider","event_type","status"
    ).annotate(count=Count("pk")).order_by("provider","event_type","status")
    print("MPW_BOOK_WEBHOOKS="+json.dumps({"product":pid,"event_counts":list(hooks)},ensure_ascii=False))

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
from django.conf import settings as django_settings
from django.middleware.csrf import _get_new_csrf_string, _mask_cipher_secret
csrf_secret=_get_new_csrf_string()
csrf_token=_mask_cipher_secret(csrf_secret)
request=RequestFactory().post("/commerce/trx-easy/start/72/",{"csrfmiddlewaretoken":csrf_token},
    secure=True,HTTP_HOST="mojplaywin.com",
    HTTP_REFERER="https://mojplaywin.com/store/product/72/checkout/",
    HTTP_ORIGIN="https://mojplaywin.com")
request.COOKIES[django_settings.CSRF_COOKIE_NAME]=csrf_secret
request.META["CSRF_COOKIE"]=csrf_secret
request.user=SimpleNamespace(pk=987654,is_authenticated=True,is_active=True)
with patch.object(commercial,"_ensure_live",return_value=connection), patch.object(commercial,"_select_order",return_value=987652):
    response=resolve("/commerce/trx-easy/start/72/").func(request,product_id=72)
location=response.get("Location","")
print("MPW_ACTIVE_START_RESPONSE="+json.dumps({"status":response.status_code,"location":location[:180]},ensure_ascii=False))
assert response.status_code in (301,302,303,307,308) and location.startswith("/commerce/trx-easy/invoice/")
print("MPW_ACTIVE_START_POST_SIMULATION="+json.dumps({"status":response.status_code,
      "redirect":location,"selection_mocked":True,"production_db_writes":False},ensure_ascii=False))
print("GUEST_READONLY=PASS")


# Read-only source inspection for the live invoice status-polling pause.
import importlib
for modname, wanted in {
    "mpw_commerce.invoicing":("render_one_tap_invoice",),
    "services.mpw_trx_commercial_chain":("read_only_independent_pair",),
    "services.mpw_tron_readonly_deposit_candidates":("find_candidate_hashes",),
    "mpw_commerce.buyer_orders":("commercial_buyer_status","reconcile_commercial_intent_from_candidates"),
}.items():
    try:
        mod=importlib.import_module(modname)
        path=Path(mod.__file__)
        raw=path.read_text("utf8","replace")
        tree=ast.parse(raw)
        selected=[]
        for node in tree.body:
            if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) or node.name not in wanted: continue
            lines=[]
            sensitive=re.compile(r"password|private.?key|secret|token|wallet|address|recipient|receiver|mnemonic|api.?key|authorization|credential",re.I)
            for line in ast.unparse(node).splitlines()[:180]:
                lines.append("[REDACTED_SENSITIVE_LINE]" if sensitive.search(line) else line[:240])
            selected.append({"name":node.name,"line":node.lineno,"calls":sorted({ast.unparse(c.func).split(".")[-1] for c in ast.walk(node) if isinstance(c,ast.Call)})[:40],"conditions":[ast.unparse(n.test)[:200] for n in ast.walk(node) if isinstance(n,ast.If)][:30],"source_lines":lines})
        print("MPW_STATUS_SOURCE="+json.dumps({"module":modname,"exists":True,"functions":selected},ensure_ascii=False))
    except Exception as exc:
        print("MPW_STATUS_SOURCE="+json.dumps({"module":modname,"error":type(exc).__name__},ensure_ascii=False))
# Configuration presence only; never emit secret values.
for name in sorted(k for k in os.environ if any(t in k.lower() for t in ("tron","trx","indexer","provider","rpc"))):
    print("MPW_STATUS_ENV="+json.dumps({"name":name,"configured":bool(os.environ.get(name))},ensure_ascii=False))

# Resolve public support and expired-invoice UI source without modifying production.
needles=("Support that starts with the actual problem","Game and account support will expand alongside released products","Automatic status checks paused","invoice expires","contact support with this order number")
sensitive=re.compile(r"password|private.?key|secret|token|wallet|address|recipient|receiver|mnemonic|api.?key|authorization|credential",re.I)
for root in (base,Path("/home/zomorod2/mojplaywin.com")):
    if not root.is_dir() or root.is_symlink(): continue
    hits=[]
    for p in root.rglob("*"):
        if p.is_symlink() or not p.is_file() or p.suffix.lower() not in (".html",".py",".js",".txt"): continue
        try:
            if p.stat().st_size>3_000_000: continue
            raw=p.read_text("utf8","replace")
        except (OSError,UnicodeError): continue
        for needle in needles:
            start=0
            while True:
                i=raw.find(needle,start)
                if i<0: break
                start=i+len(needle)
                snippet=raw[max(0,i-100):min(len(raw),i+len(needle)+180)].replace("\\n"," ")
                if sensitive.search(snippet): snippet="[REDACTED_SENSITIVE_CONTEXT]"
                hits.append({"file":str(p.relative_to(root)),"needle":needle,"context":snippet[:360]})
                if len(hits)>=50: break
            if len(hits)>=50: break
        if len(hits)>=50: break
    print("MPW_UI_SOURCE_HITS="+json.dumps({"root":str(root),"hits":hits},ensure_ascii=False))
# Check whether the third visible TRX product is independently marked eligible in the catalog.
try:
    item=Product.objects.get(pk=879); data=item.metadata or {}
    from mpw_commerce.buyer_orders import _eligible
    file=_private_file(SimpleNamespace(product=item))
    print("MPW_ITEM_879="+json.dumps({"product":879,"active":item.active,"currency":item.currency,"price":str(item.price),
        "eligible":bool(_eligible(item)),"file_present":file.is_file() and not file.is_symlink(),
        "flags":{k:data.get(k) is True for k in ("asset_verified","license_verified","quality_approved","factory_publication_permission","rights_cleared")}},ensure_ascii=False))
except Exception as exc:
    print("MPW_ITEM_879="+json.dumps({"error":type(exc).__name__},ensure_ascii=False))

# Exact product-879 public-sale eligibility and UI wording, still read-only.
from core.models import Product
from mpw_commerce.buyer_orders import _eligible
from mpw_commerce.downloads import _private_file
from types import SimpleNamespace
try:
    item=Product.objects.get(pk=879); data=item.metadata or {}; file=_private_file(SimpleNamespace(product=item))
    print("MPW_ITEM_879="+json.dumps({"active":item.active,"currency":item.currency,"price":str(item.price),
        "eligible":bool(_eligible(item)),"file_present":file.is_file() and not file.is_symlink(),
        "flags":{k:data.get(k) is True for k in ("asset_verified","license_verified","quality_approved","factory_publication_permission","rights_cleared")}},ensure_ascii=False))
except Exception as exc: print("MPW_ITEM_879="+json.dumps({"error":type(exc).__name__},ensure_ascii=False))
try:
    import core.brand_views as b
    block=getattr(b,"PAGES",{}).get("support",{})
    print("MPW_SUPPORT_COPY="+json.dumps({k:block.get(k) for k in ("headline","body","cards")},ensure_ascii=False))
except Exception as exc: print("MPW_SUPPORT_COPY="+json.dumps({"error":type(exc).__name__},ensure_ascii=False))
try:
    import services.mpw_trx_walletless_checkout_ui as ui
    p=Path(ui.__file__); raw=p.read_text("utf8","replace")
    print("MPW_INVOICE_UI_SOURCE="+json.dumps({"sha":hashlib.sha256(raw.encode()).hexdigest(),"lines":[{"n":i+1,"text":line[:1200]} for i,line in enumerate(raw.splitlines()) if "Automatic status checks paused" in line or "status_path" in line or "invoice expires" in line]},ensure_ascii=False))
except Exception as exc: print("MPW_INVOICE_UI_SOURCE="+json.dumps({"error":type(exc).__name__},ensure_ascii=False))
