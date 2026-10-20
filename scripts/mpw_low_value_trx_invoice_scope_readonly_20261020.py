#!/usr/bin/env python3
"""Read-only commercial small-value TRX feasibility; no financial records or wallet material printed."""
import os,sys,json,ast
from decimal import Decimal
from pathlib import Path
ROOT=Path('/home/zomorod2/Saeit-staging')
assert ROOT.is_dir() and not ROOT.is_symlink()
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from core.models import Product
def out(k,v):print(k+'='+json.dumps(v,sort_keys=True,default=str))
def source(name,selected):
 p=ROOT/('mpw_commerce/'+name+'.py')
 if not p.is_file() or p.is_symlink():return
 t=p.read_text('utf8','replace'); tree=ast.parse(t)
 for f in tree.body:
  if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and (f.name in selected or any(k in f.name for k in selected)):
   lines=(ast.get_source_segment(t,f) or '').splitlines()
   code=[]
   for line in lines[:115]:
    lower=line.lower()
    if any(z in lower for z in ('private_key','password','api_key','mnemonic','secret','receiver_address','recipient_address','seed_phrase')):code.append('[REDACTED]')
    else:code.append(line[:240])
   out('MPW_SMALL_TRX_SOURCE',dict(module=name,function=f.name,lines=code))
for name,functions in [('buyer_orders',('_eligible','create_digital_order')),('invoicing',('reserve_order_invoice','invoice_from_verified_buyer')),('order_policy',('order_snapshot',)),('policy',('order_snapshot','approved_for_checkout')),('product_checkout_page',('approved_for_checkout',))]:
 source(name,functions)
for attr in ('MPW_COMMERCE_RELEASE_READY','MPW_COMMERCE_INVOICING_ENABLED','MPW_COMMERCE_REAL_RPC_ENABLED'):
 out('MPW_SMALL_TRX_FLAG',dict(key=attr,enabled=getattr(settings,attr,False) is True))
for pk in (72,225):
 p=Product.objects.get(pk=pk)
 out('MPW_SMALL_TRX_PRODUCT',dict(pk=pk,price_usd=str(p.price),currency=p.currency,active=p.active,product_type=p.product_type,checkout_enabled=bool((p.metadata or {}).get('checkout_enabled'))))
out('MPW_SMALL_TRX_PRICE_SCHEME',dict(price_type=Product._meta.get_field('price').get_internal_type(),count_active_below_1_usd=Product.objects.filter(active=True,currency='USD',price__gt=0,price__lt=Decimal('1.00')).count()))
print('MPW_SMALL_TRX_READONLY=PASS')
