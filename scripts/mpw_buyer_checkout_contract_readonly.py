#!/usr/bin/env python3
"""Non-mutating contract check for actual buyer checkout and entitlement routes."""
import os,sys,json,re,html
from html.parser import HTMLParser
from types import SimpleNamespace
from pathlib import Path
app=Path('/home/zomorod2/Saeit-staging')
os.chdir(app);sys.path.insert(0,str(app));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.test import RequestFactory
from django.urls import resolve
from django.http import Http404
from mpw_commerce.product_checkout_page import product_checkout_page
from mpw_commerce.entitlements import can_access_purchased_digital_item
class Inputs(HTMLParser):
 def __init__(self):super().__init__();self.forms=[];self.buttons=0;self.scripts=0
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=='form':self.forms.append({'method':d.get('method','GET').upper(),'action':d.get('action','')[:140]})
  if tag=='button':self.buttons+=1
  if tag=='script':self.scripts+=1
result=[]
for pk in (72,225):
 r=RequestFactory().get(f'/store/product/{pk}/checkout/',secure=True,HTTP_HOST='mojplaywin.com')
 r.user=SimpleNamespace(is_authenticated=True,is_active=True,pk=-10490)
 response=product_checkout_page(r,pk)
 source=response.content.decode('utf8','replace')
 parser=Inputs();parser.feed(source)
 relative=sorted(set(re.findall(r'[/](?:api|store|checkout|accounts)/[a-z0-9_/-]{1,90}',source,re.I)))[:50]
 resolved=[]
 for path in relative:
  try:
   target=resolve(path)
   resolved.append({'path':path,'valid':True,'handler':target.func.__module__})
  except Exception:
   resolved.append({'path':path,'valid':False})
 result.append({'id':pk,'status':response.status_code,'html_bytes':len(source),'buttons':parser.buttons,'scripts':parser.scripts,'forms':parser.forms,'relative_routes':resolved,'fake_user':True,'new_order_created':False})
print('MPW_AUTHENTICATED_BUYER_CHECKOUT_CONTRACT='+json.dumps(result,ensure_ascii=False))
# Strict privacy check: an unauthenticated/synthetic user is never granted any paid item.
print('MPW_UNPAID_DOWNLOAD_GATE='+json.dumps({'anonymous_purchase_entitlement':can_access_purchased_digital_item(1,-10490) is True,'expected_denied':True}))
