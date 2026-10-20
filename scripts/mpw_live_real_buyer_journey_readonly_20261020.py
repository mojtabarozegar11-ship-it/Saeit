#!/usr/bin/env python3
"""Read-only live buyer journey inspector; prints no DB rows, wallet addresses, credentials."""
import ast,inspect,json,os,sys
from pathlib import Path
ROOT=Path('/home/zomorod2/Saeit-staging')
assert ROOT.is_dir() and not ROOT.is_symlink()
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.urls import resolve
from mpw_commerce.models import CommerceReceipt
def out(k,v):print(k+'='+json.dumps(v,ensure_ascii=False,sort_keys=True,default=str))
def redact(lines,limit=165):
 cleaned=[]
 for line in lines[:limit]:
  low=line.lower()
  if any(p in low for p in ('private_key','secret','password','mnemonic','api_key','authorization','token=')):
   cleaned.append('[REDACTED]')
  else:cleaned.append(line[:220])
 return cleaned
for route in ('/store/product/72/checkout/','/commerce/book/72/','/commerce/my-purchases/','/store/order/123/download/'):
 try:
  m=resolve(route);f=inspect.unwrap(m.func)
  out('MPW_ROUTE_DIVERGENCE',dict(route=route,module=f.__module__,function=f.__name__,args=m.kwargs))
  mod=__import__(f.__module__,fromlist=['_'])
  src=Path(mod.__file__).read_text('utf8','replace')
  tree=ast.parse(src)
  selected=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==f.__name__]
  if selected:out('MPW_ROUTE_HANDLER_SOURCE',dict(route=route,lines=redact((ast.get_source_segment(src,selected[0]) or '').splitlines())))
 except Exception as e:out('MPW_ROUTE_DIVERGENCE',dict(route=route,error=type(e).__name__))
mod=__import__('mpw_commerce.settlement',fromlist=['_']);src=Path(mod.__file__).read_text('utf8','replace')
tree=ast.parse(src)
for node in tree.body:
 if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name=='settle_order_invoice':
  out('MPW_SETTLEMENT_RECEIPT_CODE',redact((ast.get_source_segment(src,node) or '').splitlines(),220))
out('MPW_RECEIPT_SCHEMA',[(f.name,f.get_internal_type()) for f in CommerceReceipt._meta.fields])
p=ROOT/'mpw_commerce/templates/mpw_commerce/product_checkout.html'
if p.is_file() and not p.is_symlink():
 lines=p.read_text('utf8','replace').splitlines()
 focus=[i for i,line in enumerate(lines) if any(s in line for s in ('checkout/status/','can_access_purchased_items','receipt','my-purchases','setInterval','invoice_id'))]
 shown=[]
 for i in sorted(set(j for x in focus for j in range(max(0,x-5),min(len(lines),x+8)))):
  shown.append(str(i+1)+': '+lines[i][:240])
 out('MPW_BUYER_CHECKOUT_STATUS_UI',redact(shown,250))
if p.is_file() and not p.is_symlink():
 lines=p.read_text('utf8','replace').splitlines()
 out('MPW_BUYER_PAYMENT_CONFIRM_UI_FULL',redact([str(i+1)+': '+lines[i][:220] for i in range(160,min(len(lines),265))],110))
print('MPW_REAL_CUSTOMER_PATH_SOURCE_READONLY=PASS')
