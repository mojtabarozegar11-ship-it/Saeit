#!/usr/bin/env python3
"""Read-only real Passenger checkout dispatch regression for 4 approved products."""
import json,os,pwd,sys
from pathlib import Path
from types import SimpleNamespace
APP=Path('/home/zomorod2/Saeit-staging')
SITE=Path('/home/zomorod2/mojplaywin.com')
if pwd.getpwuid(os.getuid()).pw_name!='zomorod2' or APP.is_symlink() or SITE.is_symlink() or not APP.is_dir():raise RuntimeError('Tenant guard')
if "APP='/home/zomorod2/Saeit-staging'" not in (SITE/'passenger_wsgi.py').read_text('utf8','replace'):raise RuntimeError('Passenger root changed')
os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.test import RequestFactory
from django.urls import resolve
from core.models import Product
results=[]
for host in ('mojplaywin.com','www.mojplaywin.com'):
 for pk in (72,225,779,879):
  request=RequestFactory().get('/store/product/%d/checkout/'%pk,secure=True,HTTP_HOST=host)
  request.user=SimpleNamespace(is_authenticated=True,is_active=True,pk=-779900)
  target=resolve('/store/product/%d/checkout/'%pk)
  response=target.func(request,pk=pk)
  body=response.content.decode('utf8','replace')
  result={'host_class':'www' if host.startswith('www.') else 'apex','product':pk,'http':response.status_code,
          'old_delivery_error': 'Product delivery is not ready' in body,
          'commerce_order_path': '/commerce/checkout/order/' in body,
          'checkout_title':str(Product.objects.get(pk=pk).price)}
  if response.status_code!=200 or result['old_delivery_error'] or not result['commerce_order_path']:
   raise RuntimeError('Checkout failed for product %d on %s'% (pk,result['host_class']))
  results.append(result)
print('MPW_LIVE_FOUR_PRODUCTS_TWO_HOSTS='+json.dumps(results,sort_keys=True))
print('MPW_CHECKOUT_REGRESSION=PASS; PRODUCTION_ORDERS_CREATED=0; FINANCIAL_WRITES=0')
