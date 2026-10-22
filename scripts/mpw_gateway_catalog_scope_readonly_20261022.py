#!/usr/bin/env python3
"""Read-only main-site inventory of release-qualified checkout paths. NO FINANCIAL WRITES."""
import os,sys,json,pwd
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace
APP=Path('/home/zomorod2/Saeit-staging')
SITE=Path('/home/zomorod2/mojplaywin.com')
if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Tenant identity mismatch')
if not APP.is_dir() or APP.is_symlink() or not SITE.is_dir() or SITE.is_symlink():raise RuntimeError('Wrong site')
if "APP='/home/zomorod2/Saeit-staging'" not in (SITE/'passenger_wsgi.py').read_text('utf8','replace'):raise RuntimeError('Wrong Passenger site')
os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.test import RequestFactory
from core.models import Product
from mpw_commerce.product_checkout_page import approved_for_checkout
SCOPE=(72,225,779,879)
flags=('factory_publication_permission','asset_verified','quality_approved','license_verified')
req=RequestFactory().get('/store/',secure=True,HTTP_HOST='mojplaywin.com')
req.user=SimpleNamespace(pk=-901112,is_authenticated=True,is_active=True)
base=Product.objects.filter(active=True,currency='USD',product_type__in=('digital','digital_book'))
total=base.count()
eligible=[]
approved=[]
approved_outside=[]
candidate_count=0
for product in base.select_related('knowledge_article').order_by('pk').iterator(chunk_size=50):
    meta=product.metadata if type(product.metadata) is dict else {}
    commerce=meta.get('mpw_commerce') if type(meta.get('mpw_commerce')) is dict else {}
    if (product.owner_id is None or product.knowledge_article_id is None
        or product.knowledge_article.published is not True
        or not Decimal('0') < product.price <= Decimal('1000')
        or commerce.get('enabled') is not True or commerce.get('fulfillment')!='digital'
        or any(meta.get(f) is not True for f in flags)):
        continue
    candidate_count+=1
    if not approved_for_checkout(req,product):continue
    eligible.append(product.pk)
    if product.pk in SCOPE:approved.append(product.pk)
    else:approved_outside.append(product.pk)
print('MPW_GATEWAY_CATALOG_SCOPE='+json.dumps({
  'active_usd_digital_products':total,'metadata_approved_candidates':candidate_count,
  'effective_checkout_eligible_count':len(eligible),
  'eligible_inside_legacy_allowlist':approved,
  'eligible_not_routed_by_legacy_checkout':approved_outside[:50],
  'eligible_unrouted_total':len(approved_outside),
  'financial_writes':0,'buyer_accounts_created':0
},sort_keys=True))
