#!/usr/bin/env python3
"""Production read-only audit of actual buyer checkout availability and form."""
from __future__ import annotations
import os,sys,json,hashlib
from pathlib import Path
from types import SimpleNamespace
ROOT=Path("/home/zomorod2/Saeit-staging")
SITE=Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
if ROOT.is_symlink() or not ROOT.is_dir() or "Saeit-staging" not in SITE.read_text("utf8","replace"):
    raise RuntimeError("Wrong MojPlayWin app")
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.test import RequestFactory
from django.conf import settings
from django.template.loader import get_template
from django.middleware.csrf import get_token
from django.urls import resolve
from core.models import Product
from mpw_commerce.product_checkout_page import approved_for_checkout,proven_assets

product=Product.objects.select_related("knowledge_article").filter(pk=72).first()
req=RequestFactory().get("/store/product/72/checkout/",secure=True,HTTP_HOST="mojplaywin.com")
req.user=SimpleNamespace(pk=0,is_authenticated=True,is_active=True)
proofs=proven_assets()
report={"read_only":True,"financial_writes":0,
        "product_exists":product is not None,
        "product_active":bool(getattr(product,"active",False)),
        "assets_proven":{asset:proofs.get(asset) is True for asset in ("ETH","TRX")},
        "approved_signed_in_customer":False,
        "public_native_trx_enabled":bool(getattr(settings,"MPW_WALLETLESS_TRX_PUBLIC_ENABLED",False)),
        "merchant_canary_approved":bool(getattr(settings,"MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",False))}
if product is not None:
    report["approved_signed_in_customer"]=bool(approved_for_checkout(req,product))
    req.META["CSRF_COOKIE"]=get_token(req)
    context={"product":product,"price_display":str(product.price),"mpw_trx_easy_enabled":False}
    try:
        page=get_template("mpw_commerce/product_checkout.html").render(context,request=req)
        report["checkout_template_rendered"]=True
        report["gated_payment_button_hidden_when_not_released"]="Pay securely with TRX" not in page
        report["gated_template_marker_present"]="MPW_WALLETLESS_TRX_BUTTON_V1" in page
    except Exception as exc:
        report["checkout_template_rendered"]=False
        report["template_error_type"]=type(exc).__name__
for pathname in ("/store/product/72/checkout/","/commerce/trx-easy/start/72/"):
    try:
        match=resolve(pathname)
        report["mount_"+pathname]=bool(match.func)
    except Exception:
        report["mount_"+pathname]=False
print("MPW_TRX_POSTINSTALL_READINESS="+json.dumps(report,sort_keys=True))
