#!/usr/bin/env python3
"""Read-only audit of the real MojPlayWin paid delivery chain: no writes or funds."""
import os,sys,json,ast,subprocess,datetime,hashlib
from pathlib import Path
ROOT=Path('/home/zomorod2/Saeit-staging')
SITE=Path('/home/zomorod2/mojplaywin.com')
assert ROOT.is_dir() and not ROOT.is_symlink() and SITE.is_dir() and not SITE.is_symlink()
assert "APP='/home/zomorod2/Saeit-staging'" in (SITE/'passenger_wsgi.py').read_text("utf8","replace")
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.conf import settings
from django.apps import apps
def out(name,obj):print(name+'='+json.dumps(obj,sort_keys=True,ensure_ascii=False,default=str))
files={
'auto_reconcile':'mpw_commerce/auto_reconcile.py',
'settlement':'mpw_commerce/settlement.py',
'entitlements':'mpw_commerce/entitlements.py',
'downloads':'mpw_commerce/downloads.py',
'checkout_views':'mpw_commerce/checkout_views.py',
'reconciler_cmd':'mpw_commerce/management/commands/mpw_commerce_reconcile.py'}
targets={
'auto_reconcile':('reconcile_pending_orders','discover_trx','discover_eth'),
'settlement':('settle_order_invoice','_verify_evidence'),
'entitlements':('can_access_purchased_digital_item',),
'downloads':('download_paid_item',),
'checkout_views':('checkout_status',),
'reconciler_cmd':('handle',)}
for label,path in files.items():
 p=ROOT/path
 if not p.is_file() or p.is_symlink():
  out('MPW_DELIVERY_SOURCE',{'part':label,'exists':False});continue
 code=p.read_text('utf8','replace');nodes=ast.parse(code).body
 methods=[]
 for n in nodes:
  if isinstance(n,ast.ClassDef):
   options=[(m,'class:'+n.name) for m in n.body if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef))]
  elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
   options=[(n,'module')]
  else:continue
  for fn,owner in options:
   if fn.name not in targets[label]:continue
   lines=code.splitlines()[fn.lineno-1:fn.end_lineno]
   safe=[]
   for line in lines:
    lower=line.lower()
    if any(marker in lower for marker in ('private_key','mnemonic','password','apikey','api_key','secret','authorization:','receiver =','wallet_addr','address =','bearer')):
     safe.append('    [redacted sensitive statement]')
    else:safe.append(line[:210])
   methods.append({'function':fn.name,'parent':owner,'source':'\n'.join(safe)[:8000]})
 out('MPW_DELIVERY_SOURCE',{'part':label,'sha256_prefix':hashlib.sha256(code.encode()).hexdigest()[:12],'methods':methods})
for app,model in [('mpw_commerce','CommerceInvoice'),('mpw_commerce','CommerceReceipt'),('mpw_commerce','LedgerEntry'),('mpw_commerce','CommerceOrder')]:
 try:
  cls=apps.get_model(app,model)
  fields=[x.name for x in cls._meta.fields]
  x={'model':model,'row_count':cls.objects.count(),'fields':fields}
  if 'status' in fields:
   from django.db.models import Count
   x['status_count']={str(q['status']):q['n'] for q in cls.objects.values('status').annotate(n=Count('pk'))}
  out('MPW_DELIVERY_AGGREGATE',x)
 except Exception as e:out('MPW_DELIVERY_AGGREGATE',{'model':model,'exception':type(e).__name__})
try:
 result=subprocess.run(['crontab','-l'],capture_output=True,text=True,timeout=7)
 lines=result.stdout.splitlines() if result.returncode==0 else []
 match=[l for l in lines if 'mpw_commerce_live_inbound_reconciler.py' in l and not l.lstrip().startswith('#')]
 out('MPW_DELIVERY_CRON',{'crontab_readable':result.returncode==0,'active_entries':len(match),
  'every_minute_any':any(l.strip().startswith('* * * * *') for l in match),
  'has_lock':all('flock' in l for l in match),'no_private_entry_output':True})
except Exception as e:out('MPW_DELIVERY_CRON',{'error_type':type(e).__name__})
log=Path('/home/zomorod2/.private_mojplaywin_main_agents/mpw_commerce_reconcile_20261019.log')
if log.is_file() and not log.is_symlink():
 stat=log.stat()
 out('MPW_DELIVERY_WORKER_LOG',{'exists':True,'modified_utc':datetime.datetime.fromtimestamp(stat.st_mtime,datetime.timezone.utc).isoformat(),
  'age_seconds':int(datetime.datetime.now(datetime.timezone.utc).timestamp()-stat.st_mtime),'size':stat.st_size})
else:out('MPW_DELIVERY_WORKER_LOG',{'exists':False})
out('MPW_DELIVERY_AUDIT_SCOPE',{'read_only':True,'orders_modified':0,'chain_transfers':0})
