#!/usr/bin/env python3
"""No-write live audit of MojPlayWin real invoice, chain evidence, and download orchestration."""
import os, sys, json, ast, re, inspect
from pathlib import Path
base=Path('/home/zomorod2/Saeit-staging')
assert base.is_dir() and not base.is_symlink()
os.chdir(base);sys.path.insert(0,str(base));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.urls import get_resolver
from django.conf import settings
from django.db import connection
from django.apps import apps
from core.models import Product
def safe(m):
    return json.dumps(m,ensure_ascii=False,default=str,sort_keys=True)
public=[]
for m in (
 'mpw_commerce.product_checkout_page','mpw_commerce.buyer_orders',
 'mpw_commerce.invoicing','mpw_commerce.auto_reconcile','mpw_commerce.settlement',
 'mpw_commerce.downloads','mpw_commerce.checkout_views',
 'mpw_commerce.wallet_ownership','mpw_commerce.rate_providers',
 'mpw_commerce.models','mpw_native_checkout.autopay_worker',
):
 try:
  mod=__import__(m,fromlist=['_'])
  p=Path(getattr(mod,'__file__',''))
  tree=ast.parse(p.read_text('utf8','replace'))
  fns=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
  entries=[]
  for n in fns:
   if not any(t in n.name.lower() for t in ('quote','buyer','cart','payment','invoice','order','reconcil','settle','verify','rate','download','wallet','paid','safeguard','eligible')):
    continue
   calls=sorted({ast.unparse(c.func)[:60] for c in ast.walk(n) if isinstance(c,ast.Call) and any(k in ast.unparse(c.func).lower() for k in ('chain','verify','rate','sender','invoice','sign','notify','send','receipt','oracle','rpc','reconcil'))})
   entries.append(dict(fn=n.name,args=[a.arg for a in n.args.args],lines=n.end_lineno-n.lineno+1,dependent_calls=calls[:22]))
  print('MPW_PAYMENT_RUNTIME_MODULE='+safe(dict(module=m,present=True,functions=entries[:55])))
 except Exception as e:
  print('MPW_PAYMENT_RUNTIME_MODULE='+safe(dict(module=m,error=type(e).__name__)))
for app,model in [('mpw_commerce','CommerceInvoice'),('mpw_commerce','CommerceReceipt'),('mpw_commerce','CommerceOrder'),('mpw_commerce','CommerceCart'),('mpw_commerce','CommerceRate'),('mpw_commerce','LedgerEntry')]:
 try:
  c=apps.get_model(app,model);print('MPW_PAYMENT_RUNTIME_MODEL='+safe(dict(app=app,model=model,count=c.objects.count(),fields=[x.name for x in c._meta.fields])))
 except Exception as e: print('MPW_PAYMENT_RUNTIME_MODEL='+safe(dict(app=app,model=model,error=type(e).__name__)))
for pk in (72,225):
 p=Product.objects.get(pk=pk)
 m=p.metadata or {}
 whitelist=('mpw_commerce','pricing','payment_live','checkout_enabled','quality_approved','license_verified','asset_verified','factory_publication_permission','rights_cleared')
 values={k:m.get(k) for k in whitelist}
 # Defense in depth: don't output private keys, addresses, paths, or tokens.
 def redact(v):
  if isinstance(v,dict):return {k:('<redacted>' if any(x in k.lower() for x in ('wallet','path','secret','address','key','token','file','sha')) else redact(val)) for k,val in v.items()}
  if isinstance(v,list):return [redact(x) for x in v[:15]]
  if isinstance(v,(bool,int,float,str,type(None))):return (v[:140] if isinstance(v,str) else v)
  return type(v).__name__
 print('MPW_PAYMENT_LIVE_PRODUCT='+safe(dict(id=pk,metadata=redact(values))))
for k in ('MPW_COMMERCE_REAL_RPC_ENABLED','MPW_COMMERCE_AUTORECONCILE_ENABLED','MPW_COMMERCE_BUYER_SIGNATURE_ENABLED','MPW_COMMERCE_DOWNLOADS_ENABLED','MPW_COMMERCE_INVOICING_ENABLED','MPW_COMMERCE_SETTLEMENT_ENABLED'):
 print('MPW_PAYMENT_FLAG='+safe({'key':k,'is_true':getattr(settings,k,False) is True}))
for p in (base/'mpw_commerce/management/commands',base/'mpw_native_checkout/management/commands'):
 if p.is_dir():
  print('MPW_PAYMENT_COMMANDS='+safe({'module':str(p.relative_to(base)),'commands':sorted(x.stem for x in p.iterdir() if x.suffix=='.py' and x.name!='__init__.py')}))
print('MPW_PAYMENT_READONLY=PASS')
