#!/usr/bin/env python3
"""Read-only audit for production settlement automation and entitlement delivery."""
import os,sys,subprocess,json,ast,hashlib
from pathlib import Path
base=Path('/home/zomorod2/Saeit-staging')
def out(key,value):print(key+"="+json.dumps(value,ensure_ascii=False,default=str))
p=subprocess.run(['crontab','-l'],capture_output=True,text=True,timeout=15)
lines=[x.strip() for x in p.stdout.splitlines() if x.strip() and not x.lstrip().startswith('#')]
for i,line in enumerate(lines):
 lo=line.lower()
 out('MPW_SCHEDULE_ENTRY',{'index':i,'contains_commerce_reconcile':'mpw_commerce_reconcile' in lo,'contains_native_autopay':'mpw_native_autopay' in lo,'contains_event_loop':'mpw_native_event_loop' in lo,'contains_commerce':'mpw_commerce' in lo,'cadence':line.split()[:5] if len(line.split())>=6 else []})
out('MPW_SCHEDULE_TOTAL',{'cron_exit':p.returncode,'entries':len(lines),'commerce_reconcile_scheduled':any('mpw_commerce_reconcile' in x for x in lines),'native_autopay_scheduled':any('mpw_native_autopay' in x for x in lines)})
for rel in ('mpw_commerce/management/commands/mpw_commerce_reconcile.py','mpw_commerce/auto_reconcile.py','mpw_commerce/management/commands/mpw_commerce_fulfill_courses.py','mpw_commerce/downloads.py','mpw_commerce/entitlements.py','mpw_commerce/settlement.py','mpw_commerce/invoicing.py','mpw_commerce/checkout_views.py'):
 file=base/rel
 if not file.is_file() or file.is_symlink():
  out('MPW_AUTOMATION_FILE',{'file':rel,'exists':False});continue
 src=file.read_text('utf8','replace')
 tree=ast.parse(src)
 funcs=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
 top=[]
 for n in funcs:
  if isinstance(n,ast.ClassDef):
   meth=[x for x in n.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]
   top.append({'cls':n.name,'methods':[{'name':x.name,'lines':x.end_lineno-x.lineno+1} for x in meth]})
  else:
   top.append({'fn':n.name,'lines':n.end_lineno-n.lineno+1,'args':[x.arg for x in n.args.args]})
 sensitive=('secret','password','private_key','mnemonic','api_key','token','wallet_address')
 def clean(code):
  return ["[redacted]" if any(k in line.lower() for k in sensitive) else line[:180] for line in code]
 bodies=[]
 for n in funcs:
  if isinstance(n,ast.FunctionDef) and n.name in ('reconcile_pending_orders','can_access_purchased_digital_item','download_paid_item','handle','checkout_invoice','settle_order_invoice'):
   body=src.splitlines()[n.lineno-1:min(n.end_lineno,n.lineno+90)]
   bodies.append({'fn':n.name,'body':clean(body)})
  elif isinstance(n,ast.ClassDef):
   for fn in n.body:
    if isinstance(fn,ast.FunctionDef) and fn.name in ('handle',):
     body=src.splitlines()[fn.lineno-1:min(fn.end_lineno,fn.lineno+55)]
     bodies.append({'fn':fn.name,'body':clean(body)})
 out('MPW_AUTOMATION_FILE',{'file':rel,'sha':hashlib.sha256(src.encode()).hexdigest()[:16],'top':top[:40],'bodies':bodies})
