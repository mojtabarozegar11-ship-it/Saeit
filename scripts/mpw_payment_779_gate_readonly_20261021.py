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
from html.parser import HTMLParser
from html import unescape
import re

class CheckoutMarkupAudit(HTMLParser):
 def __init__(self):
  super().__init__()
  self.form_count=0
  self.post_form_count=0
  self.submit_count=0
  self.button_text=[]
  self._in_button=False
  self._button=[]
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if tag=='form':
   self.form_count+=1
   if attrs.get('method','get').lower()=='post': self.post_form_count+=1
  elif tag=='button':
   self._in_button=True; self._button=[]
   if attrs.get('type','').lower()=='submit': self.submit_count+=1
  elif tag=='input' and attrs.get('type','').lower()=='submit':
   self.submit_count+=1
 def handle_data(self,data):
  if self._in_button:self._button.append(data)
 def handle_endtag(self,tag):
  if tag=='button' and self._in_button:
   self.button_text.append(' '.join(''.join(self._button).split()).lower())
   self._in_button=False

def checkout_markup_signals(response):
 body=response.content.decode('utf8','replace')
 parser=CheckoutMarkupAudit(); parser.feed(body)
 low=body.lower()
 cta_terms=('buy','purchase','pay','checkout','create invoice','create order','continue to payment','place order')
 labels=parser.button_text
 return {
  'form_count':parser.form_count,
  'post_form_count':parser.post_form_count,
  'submit_control_count':parser.submit_count,
  'has_invoice_container':'id="invoice"' in low or "id='invoice'" in low,
  'has_invoice_or_challenge_endpoint':('/commerce/checkout/invoice/' in low or '/commerce/checkout/challenge/' in low),
  'has_visible_checkout_call_to_action':any(any(term in label for term in cta_terms) for label in labels),
  'has_create_invoice_text':'create invoice' in low,
  'button_label_count':len(labels),
  'read_only':True,
  'writes':0,
 }

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
   data['checkout_markup']=checkout_markup_signals(response)
  results.append(data)
 except Exception as ex:
  results.append({'product':pk,'error_type':type(ex).__name__})
print('MPW_THREE_PRODUCTS_PURCHASE_ELIGIBILITY='+json.dumps(results,sort_keys=True))
print('MPW_THREE_PRODUCTS_FINANCIAL_WRITES=0')
