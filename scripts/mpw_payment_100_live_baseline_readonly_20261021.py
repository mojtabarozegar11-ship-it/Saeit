#!/usr/bin/env python3
"""Live READ-ONLY MojPlayWin payment 100/100 prerequisite inventory.

Do not create orders, inspect/print secrets, perform payments, modify settings,
or declare commercial readiness based on this inspection.
"""
import os,sys,json,inspect,hashlib
from pathlib import Path

APP=Path('/home/zomorod2/Saeit-staging')
SITE=Path('/home/zomorod2/mojplaywin.com')
WSGI=SITE/'passenger_wsgi.py'
if not APP.is_dir() or APP.is_symlink() or SITE.is_symlink() or not WSGI.is_file():
 raise RuntimeError("Unverified MojPlayWin production root")
if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8","replace"):
 raise RuntimeError("Passenger entrypoint does not match audited app")
os.chdir(APP)
sys.path.insert(0,str(APP))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.urls import resolve,Resolver404
from django.conf import settings
from django.test import Client
from django.apps import apps

routes=['/accounts/login/','/accounts/register/','/store/',
        '/store/product/72/checkout/','/commerce/book/72/','/commerce/book/779/']
route_report={}
for path in routes:
 try:
  obj=resolve(path)
  fn=inspect.unwrap(obj.func)
  route_report[path]={
   "resolves":True,
   "module":fn.__module__,
   "function":fn.__name__,
  }
 except (Resolver404,LookupError):
  route_report[path]={"resolves":False}
c=Client(enforce_csrf_checks=True)
auth={}
for path in ['/accounts/login/','/accounts/register/']:
 try:
  response=c.get(path,secure=True,HTTP_HOST='mojplaywin.com')
  body=response.content.decode('utf8','replace')
  auth[path]={
   'GET_HTTP':response.status_code,
   'csrf_input': 'name="csrfmiddlewaretoken"' in body,
   'csrf_cookie_set': 'csrftoken' in response.cookies,
  }
 except Exception as exc:
  auth[path]={'error_type':type(exc).__name__}
files={}
for label,rel in (
  ("modern_checkout","mpw_commerce/templates/mpw_commerce/product_checkout.html"),
  ("legacy_checkout","core/templates/brands/mojplaywin/checkout.html"),
):
 f=APP/rel
 if f.is_file() and not f.is_symlink():
  t=f.read_text('utf8','replace')
  files[label]={
   "sha_prefix":hashlib.sha256(t.encode()).hexdigest()[:14],
   "has_security_form":'{% csrf_token %}' in t,
   "modern_theme_link":'mpw-fintech-checkout-v2.css' in t,
   "contains_old_static_12_usdt":"12 USDT" in t,
   "has_hardcoded_provider_key":'NOWPAYMENTS_API_KEY=' in t,
  }
 else:
  files[label]={'file_present':False}
env_signals={
 "nowpayments_api_key_runtime":bool(os.environ.get('NOWPAYMENTS_API_KEY')),
 "nowpayments_webhook_secret_runtime":bool(os.environ.get('NOWPAYMENTS_IPN_SECRET')),
 "fiat_onramp_approval_runtime":os.environ.get('MPW_FIAT_ONRAMP_APPROVED')=='1',
 "trx_payout_verified_runtime":os.environ.get('MPW_FIAT_TRX_PAYOUT_VERIFIED')=='1',
}
# Runtime flag checks are informational only: apps may use other credential loaders.
try:
 from command_center.mpw_public import feature_enabled
 env_signals['general_checkout_feature_enabled']=feature_enabled('MPW_ENABLE_CHECKOUT') is True
except (ImportError,AttributeError,RuntimeError):
 env_signals['general_checkout_feature_enabled']=None
print('MPW_PAYMENT_100_LIVE_BASELINE='+json.dumps({
 "tenant":"mojplaywin.com","routes":route_report,"login":auth,
 "templates":files,"runtime_signals":env_signals,
 "live_paid_end_to_end_verified_by_this_probe":False,
 "fiat_card_to_native_trx_verified_by_this_probe":False,
 "gateway_acceptance":"BLOCKED_NOT_100",
 "writes":0,"private_data_emitted":False,
},sort_keys=True))
if any(not v.get('resolves') for v in route_report.values()):
 raise SystemExit('MPW_PAYMENT_BASELINE_ROUTES_FAILED')
print('MPW_PAYMENT_100_BASELINE_READONLY=PASS; COMMERCIAL_ACCEPTANCE=BLOCKED')
