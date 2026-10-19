#!/usr/bin/env python3
"""Review effective live buyer flow and safe gates without writes or addresses."""
import os,sys,json,ast,re
from pathlib import Path
app=Path("/home/zomorod2/Saeit-staging")
os.chdir(app);sys.path.insert(0,str(app));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django;django.setup()
from django.conf import settings
from django.urls import resolve
modules={
"core/cryptopay_checkout.py":("checkout","private_download","product_delivery_ready"),
"mpw_commerce/product_checkout_page.py":("approved_for_checkout","product_checkout_page"),
"mpw_commerce/buyer_orders.py":("_eligible","create_digital_order"),
"mpw_commerce/invoicing.py":("reserve_order_invoice",),
"mpw_commerce/checkout_views.py":("checkout_status",),
"mpw_commerce/settlement.py":("settle_order_invoice","_verify_evidence"),
"mpw_commerce/downloads.py":("download_paid_item",),
}
blocked=("password","secret","private_key","token","wallet_address","receiver","sender_address","merchant_address","recipient_address","api_key","mnemonic")
for fn, selected in modules.items():
    p=app/fn
    if not p.is_file() or p.is_symlink():
        print("MPW_CHECKOUT_RUNTIME_MODULE="+json.dumps({"file":fn,"missing":True}));continue
    tree=ast.parse(p.read_text("utf8","replace"))
    entries=[]
    for node in tree.body:
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) or node.name not in selected:continue
        selected_if=[]
        for stmt in ast.walk(node):
            if isinstance(stmt,ast.If):
                condition=ast.unparse(stmt.test)
                if any(x in condition.lower() for x in blocked):
                    condition="[sensitive condition redacted]"
                else:
                    condition=condition[:210]
                selected_if.append({"line_rel":stmt.lineno-node.lineno+1,"condition":condition})
        entries.append({"fn":node.name,"args":[a.arg for a in node.args.args],
            "lines":node.end_lineno-node.lineno+1,"gates":selected_if[:50]})
    print("MPW_CHECKOUT_RUNTIME_MODULE="+json.dumps({"file":fn,"functions":entries},ensure_ascii=False))
results={}
for setting in ("CRYPTO_PAYMENT_ENABLED","CRYPTO_PAYMENT_LIVE","CRYPTO_PAYMENTS_ENABLED","CRYPTO_CHECKOUT_ENABLED","CRYPTO_PAYMENT_MAINNET","CRYPTO_TRON_MAINNET_ENABLED","MPW_COMMERCE_RELEASE_READY","MPW_COMMERCE_CUSTOMER_HTTP_ENABLED","MPW_COMMERCE_INVOICING_ENABLED","MPW_COMMERCE_SETTLEMENT_ENABLED","MPW_COMMERCE_REAL_RPC_ENABLED","MPW_COMMERCE_AUTORECONCILE_ENABLED","MPW_COMMERCE_DOWNLOADS_ENABLED"):
    results[setting]={"exists":hasattr(settings,setting),"enabled":getattr(settings,setting,None) is True}
print("MPW_CHECKOUT_SWITCH_INVENTORY="+json.dumps(results))
for path in ("/store/product/72/checkout/","/store/product/225/checkout/"):
    r=resolve(path)
    func=r.func
    print("MPW_CHECKOUT_ACTUAL_HANDLER="+json.dumps({"path":path,"module":func.__module__,
        "function":getattr(func,"__name__","view"),"wrapped_count":int(bool(getattr(func,"__wrapped__",None)))}))


from django.test import RequestFactory
from types import SimpleNamespace
from core.models import Product
from mpw_commerce.product_checkout_page import approved_for_checkout
request = RequestFactory().get("/store/product/72/checkout/", secure=True, HTTP_HOST="mojplaywin.com")
request.user = SimpleNamespace(is_authenticated=True,is_active=True,pk=-1000)
for pk in (72,225):
    p=Product.objects.get(pk=pk)
    request.path=f"/store/product/{pk}/checkout/"
    try:
        approved=approved_for_checkout(request,p)
        print("MPW_BOOK_AUTHENTICATED_DRY_GATE="+json.dumps({"product":pk,"allowed":approved is True,"result_type":type(approved).__name__,"read_only":True}))
    except Exception as e:
        print("MPW_BOOK_AUTHENTICATED_DRY_GATE="+json.dumps({"product":pk,"error_type":type(e).__name__,"read_only":True}))
source=(app/"core/cryptopay_checkout.py").read_text("utf8","replace")
checkout_ast=next((n for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=="checkout"),None)
if checkout_ast:
    first=source.splitlines()[checkout_ast.lineno-1:min(checkout_ast.end_lineno,checkout_ast.lineno+19)]
    first=[("[REDACTED]" if any(b in x.lower() for b in blocked) else x[:180]) for x in first]
    print("MPW_ACTIVE_CHECKOUT_DISPATCH_FIRST_LINES="+json.dumps(first,ensure_ascii=False))


from mpw_commerce.product_checkout_page import product_checkout_page
from django.test import RequestFactory
from types import SimpleNamespace
product_module=ast.parse((app/"mpw_commerce/product_checkout_page.py").read_text("utf8","replace"))
product_view=next(n for n in product_module.body if isinstance(n,ast.FunctionDef) and n.name=="product_checkout_page")
mutable_call_names={"create","bulk_create","update","delete","save","get_or_create","update_or_create","send","post","transfer"}
unsafe=[ast.unparse(call.func).split(".")[-1] for call in ast.walk(product_view) if isinstance(call,ast.Call) and ast.unparse(call.func).split(".")[-1] in mutable_call_names]
if unsafe:raise RuntimeError("Product page is not proven read-only: "+str(sorted(set(unsafe))))
for pk in (72,225):
    rq=RequestFactory().get(f"/store/product/{pk}/checkout/",secure=True,HTTP_HOST="mojplaywin.com")
    rq.user=SimpleNamespace(is_authenticated=True,is_active=True,pk=-1000)
    try:
        response=product_checkout_page(rq,pk)
        payload=response.content.decode("utf8","replace")
        print("MPW_BOOK_FAKE_SIGNED_IN_RENDER="+json.dumps({"product":pk,
            "http_status":response.status_code,"html_rendered":len(payload)>500,
            "contains_product_title":("Chess" in payload if pk==72 else "Taniya" in payload),
            "read_only":True,"real_customer_authenticated":False,
            "order_or_payment_created":False}))
    except Exception as exc:
        print("MPW_BOOK_FAKE_SIGNED_IN_RENDER="+json.dumps({"product":pk,
            "error_type":type(exc).__name__,"read_only":True}))
