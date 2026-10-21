#!/usr/bin/env python3
"""Read-only signed-in GET render of the real native checkout; no order creation or money movement."""
import os,sys,pwd,json
from pathlib import Path
from types import SimpleNamespace
APP=Path("/home/zomorod2/Saeit-staging")
if pwd.getpwuid(os.getuid()).pw_name!="zomorod2" or APP.is_symlink() or not (APP/"manage.py").is_file():
    raise RuntimeError("UNVERIFIED_APP_OR_USER")
os.chdir(APP);sys.path.insert(0,str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
os.environ["PYTHONDONTWRITEBYTECODE"]="1"
import django;django.setup()
from core.models import Product
from django.test import RequestFactory
from mpw_commerce.product_checkout_page import approved_for_checkout,product_checkout_page
p=Product.objects.select_related("knowledge_article").get(pk=879)
req=RequestFactory().get("/store/product/879/checkout/",secure=True,HTTP_HOST="mojplaywin.com")
req.user=SimpleNamespace(is_authenticated=True,is_active=True)
if not approved_for_checkout(req,p):raise RuntimeError("ZIP_NATIVE_CHECKOUT_GATE_REJECTED")
response=product_checkout_page(req,879)
data=response.content.decode("utf8","replace")
if response.status_code!=200 or "Atelier Interior" not in data or "6.80" not in data or "/commerce/checkout/order/" not in data:
    raise RuntimeError("REAL_SIGNED_IN_CHECKOUT_PAGE_GET_NOT_RENDERED")
print("ATELIER_NATIVE_CHECKOUT_AUTHENTICATED_READONLY_GET="+json.dumps({
   "product_id":879,"http":response.status_code,"actual_web_template_rendered":True,
   "price_usd":"6.80","invoice_order_api_present":True,"paid_order_created":False,
   "customer_real_purchase_tested":False,"post_payment_zip_delivery_tested":False},sort_keys=True))
