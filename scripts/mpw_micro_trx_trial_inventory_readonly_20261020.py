#!/usr/bin/env python3
"""Read-only inspect 0.03 USD purchase-product prerequisites; no customer data."""
import os,sys,json,ast,inspect,stat
from pathlib import Path
from decimal import Decimal
APP=Path('/home/zomorod2/Saeit-staging')
assert APP.is_dir() and not APP.is_symlink()
os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.apps import apps
from django.urls import reverse
from django.conf import settings
from django.test import RequestFactory
from core.models import Product
def log(name,ob):print(name+'='+json.dumps(ob,default=str,sort_keys=True))
for name in ('Product','KnowledgeArticle'):
 try:m=apps.get_model('core',name)
 except Exception as e:
  log('MPW_MICRO_MODEL_MISSING',{'model':name,'error':str(e)[:200]});continue
 fields=[{'name':f.name,'type':f.get_internal_type(),'null':f.null,'blank':f.blank,'has_default':f.has_default(),'required':not (f.null or f.blank or f.has_default() or f.auto_created)} for f in m._meta.fields]
 log('MPW_MICRO_MODEL',{'model':name,'fields':fields,'unique':str([x.name for x in m._meta.fields if x.unique])})
p=Product.objects.select_related('knowledge_article').get(pk=225)
fields={}
for k in ('name','slug','title','description','summary','category','product_type','currency','price','active','owner_id','knowledge_article_id','file','download_url','thumbnail'):
 try:
  v=getattr(p,k)
  fields[k]='present' if k in ('file','download_url','thumbnail') and v else (str(v)[:180] if isinstance(v,(str,Decimal,int,bool,type(None))) else type(v).__name__)
 except AttributeError:pass
log('MPW_MICRO_EXISTING_PRODUCT_SHAPE',fields)
if p.knowledge_article_id:
 a=p.knowledge_article
 article={}
 for f in a._meta.fields:
  if f.get_internal_type() in ('CharField','TextField','BooleanField','SlugField','PositiveIntegerField','IntegerField') and f.name.lower() not in ('body','content','text'):
   v=getattr(a,f.name,None)
   article[f.name]=(v[:150] if type(v) is str else v if type(v) in (bool,int,type(None)) else type(v).__name__)
 log('MPW_MICRO_ARTICLE_SHAPE',article)
for rel,fn in [('mpw_commerce/downloads.py','_private_file'),('mpw_commerce/policy.py','_private_file'),('mpw_commerce/entitlements.py','can_access_purchased_digital_item'),('mpw_commerce/product_checkout_page.py','approved_for_checkout')]:
 q=APP/rel
 if not q.is_file() or q.is_symlink():continue
 t=q.read_text('utf8','replace');tree=ast.parse(t)
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==fn:
   src=(ast.get_source_segment(t,node) or '').splitlines()
   rows=[line[:220] if not any(term in line.lower() for term in ('secret','password','private_key','mnemonic','api_key','bearer')) else '[REDACTED]' for line in src[:130]]
   log('MPW_MICRO_SOURCE',{'file':rel,'function':fn,'lines':rows})
log('MPW_MICRO_ROUTES',{'checkout':reverse('mpw_commerce:book',kwargs={'product_id':225}),'purchases':reverse('mpw_commerce:purchases')})
print('MPW_MICRO_PREFLIGHT_READONLY=PASS')
