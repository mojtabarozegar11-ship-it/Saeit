#!/usr/bin/env python3
"""Production READ-ONLY checkout eligibility audit, no orders/payments or personal data."""
import os,sys,json
from pathlib import Path
p=Path('/home/zomorod2/Saeit-staging')
assert p.is_dir() and not p.is_symlink()
os.chdir(p);sys.path.insert(0,str(p))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.test import RequestFactory
from core.models import Product
from mpw_commerce.product_checkout_page import approved_for_checkout,product_checkout_page
from mpw_commerce.buyer_orders import _eligible
from types import SimpleNamespace
req=RequestFactory().get('/commerce/book/779/',secure=True,HTTP_HOST='mojplaywin.com')
req.user=SimpleNamespace(is_authenticated=True,is_active=True,pk=-840003,username='read-only-gateway-auditor')
results=[]
for pk in (72,225,779):
 try:
  product=Product.objects.select_related('knowledge_article').get(pk=pk)
  m=product.metadata if isinstance(product.metadata,dict) else {}
  config=m.get('mpw_commerce') if isinstance(m.get('mpw_commerce'),dict) else {}
  req.path='/commerce/book/%d/'%pk
  allowed=approved_for_checkout(req,product) is True
  meta={x:m.get(x) is True for x in
        ('asset_verified','license_verified','quality_approved','factory_publication_permission')}
  data={'product':pk,'active':product.active,'currency':product.currency,'price':str(product.price),
        'approved_for_checkout':allowed,'eligible_for_order':_eligible(product) is True,
        'mpw_config_enabled':config.get('enabled') is True,
        'fulfillment_digital':config.get('fulfillment')=='digital','proof_flags':meta}
  if allowed:
   response=product_checkout_page(req,pk)
   data['authenticated_readonly_render_http']=response.status_code
   data['has_invoice_link']=b'id="invoice"' in response.content
  results.append(data)
 except Exception as ex:
  results.append({'product':pk,'error_type':type(ex).__name__})
print('MPW_THREE_PRODUCTS_PURCHASE_ELIGIBILITY='+json.dumps(results,sort_keys=True))
print('MPW_THREE_PRODUCTS_FINANCIAL_WRITES=0')
