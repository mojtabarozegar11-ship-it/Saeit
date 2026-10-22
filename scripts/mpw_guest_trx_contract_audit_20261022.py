#!/usr/bin/env python3
"""Read-only model, API and chain proof contract for a separate guest-TRX design. No user data."""
import ast,json,os,sys,pwd
from pathlib import Path
p=Path('/home/zomorod2/Saeit-staging')
site=Path('/home/zomorod2/mojplaywin.com')
if pwd.getpwuid(os.getuid()).pw_name!='zomorod2' or p.is_symlink() or site.is_symlink():raise RuntimeError('identity')
if "APP='/home/zomorod2/Saeit-staging'" not in (site/'passenger_wsgi.py').read_text('utf8','replace'):raise RuntimeError('passenger')
os.chdir(p);sys.path.insert(0,str(p));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.apps import apps
for app,model in [('mpw_commerce','CommerceInvoice'),('mpw_commerce','CommerceReceipt'),('mpw_commerce','CommerceFulfillment'),('core','Order'),('core','OrderItem')]:
 try:
  m=apps.get_model(app,model)
  out={'fields':[{'name':f.name,'type':f.get_internal_type(),'null':f.null,'unique':f.unique,'default':f.has_default(),'pk':f.primary_key} for f in m._meta.fields],
  'constraints':[{'name':c.name,'class':type(c).__name__,'fields':list(getattr(c,'fields',[]))} for c in m._meta.constraints],
  'indexes':[{'name':idx.name,'fields':idx.fields} for idx in m._meta.indexes]}
  print('GUEST_MODEL='+json.dumps({'model':model,**out},sort_keys=True))
 except Exception as e:print('GUEST_MODEL_UNAVAILABLE='+json.dumps({'model':model,'exception':type(e).__name__}))
targets={
'mpw_commerce/invoicing.py':['reserve_order_invoice','invoice_from_verified_buyer'],
'mpw_commerce/checkout_views.py':['checkout_invoice','checkout_challenge','checkout_verify','_ready'],
'mpw_commerce/buyer_orders.py':['create_digital_order','_eligible','_private_file'],
'mpw_commerce/auto_reconcile.py':['reconcile_pending_orders','discover_trx'],
'mpw_commerce/settlement.py':['settle_order_invoice'],
'mpw_commerce/buyer_wallets.py':['fetch_server_rate'],
'mpw_commerce/models.py':[],
'mpw_commerce/urls.py':[],
}
for name,names in targets.items():
 path=p/name
 if not path.is_file():continue
 text=path.read_text('utf8','replace')
 tree=ast.parse(text)
 for item in tree.body:
  if not isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):continue
  if names and item.name not in names:continue
  if not names and name.endswith('models.py') and item.name not in ('CommerceInvoice','CommerceReceipt'):continue
  if not names and name.endswith('urls.py'):continue
  signature=[x.arg for x in item.args.args] if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)) else []
  imported=[]
  if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)):
   imported=sorted(set(ast.unparse(n.func) for n in ast.walk(item) if isinstance(n,ast.Call)))[:48]
  print('GUEST_API='+json.dumps({'file':name,'name':item.name,'signature':signature,'calls':imported,'lines':item.end_lineno-item.lineno+1},sort_keys=True))
 if name.endswith('urls.py'):
  print('GUEST_URLS='+json.dumps({'source':text[:4500]}))
for name in ('MPW_COMMERCE_RELEASE_READY','MPW_COMMERCE_INVOICING_ENABLED','MPW_COMMERCE_REAL_RPC_ENABLED','MPW_COMMERCE_AUTORECONCILE_ENABLED','MPW_COMMERCE_SETTLEMENT_ENABLED'):
 from django.conf import settings
 print('GUEST_FLAG='+json.dumps({'name':name,'true':getattr(settings,name,False) is True}))
print('GUEST_AUDIT_READONLY=PASS')
