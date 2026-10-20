#!/usr/bin/env python3
import os,sys,json,ast,hashlib
from pathlib import Path
app=Path('/home/zomorod2/Saeit-staging');os.chdir(app);sys.path.insert(0,str(app));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.urls import resolve
from django.conf import settings
for rel in ('scripts/mojplaywin_native_chain_verify.py','mpw_commerce/rate_oracle.py','mpw_commerce/rates.py','mpw_commerce/market_rates.py','mpw_commerce/quote.py','mpw_commerce/checkout_views.py','mpw_commerce/rate_providers.py','mpw_commerce/urls.py','config/urls.py','core/cryptopay_checkout.py'):
 p=app/rel
 if not p.is_file():continue
 t=p.read_text('utf8')
 tree=ast.parse(t)
 defs=[]
 for n in tree.body:
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
   defs.append({'name':n.name,'args':[x.arg for x in n.args.args] if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) else [],'line':n.lineno,'end':n.end_lineno})
 print('MPW_GUEST_DEEP='+json.dumps({'path':rel,'defs':defs[:80],'length':len(t),'sha':hashlib.sha256(t.encode()).hexdigest()[:18]}))
 if rel in ('mpw_commerce/urls.py','config/urls.py'):
  for lineno,line in enumerate(t.splitlines(),1):
   if 'path(' not in line and 're_path(' not in line:continue
   if any(x in line.lower() for x in ('checkout','wallet','store/product','commer','mpw','guest')):
    # Do not print arbitrary string arguments; only route and view symbols without sensitive path variables.
    print('MPW_GUEST_ROUTE='+json.dumps({'file':rel,'line':lineno,'code':line[:260]}))
 if rel=='mpw_commerce/checkout_views.py':
  for line in t.splitlines()[:65]:
   if line.startswith(('import ','from ','HOSTS','DOMAIN_ALLOWLIST','FLAGS','def _ready','    return','    if ')):
    print('MPW_GUEST_IMPORT='+json.dumps({'file':rel,'line':line[:200]}))
from django.test import RequestFactory
from mpw_commerce.product_checkout_page import approved_for_checkout
from core.models import Product
for pid in (72,225):
 p=Product.objects.select_related('knowledge_article').get(pk=pid)
 r=RequestFactory().get('/store/product/%d/checkout/'%pid,secure=True,HTTP_HOST='mojplaywin.com')
 r.user=__import__('django.contrib.auth.models',fromlist=['AnonymousUser']).AnonymousUser()
 try:eligible=approved_for_checkout(r,p)
 except Exception as e:eligible=type(e).__name__
 print('MPW_GUEST_ANON_ALLOWED='+json.dumps({'product':pid,'allowed':eligible}))
print('MPW_GUEST_DEEP_READONLY=PASS')
