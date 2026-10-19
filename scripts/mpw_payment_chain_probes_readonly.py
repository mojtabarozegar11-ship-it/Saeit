#!/usr/bin/env python3
"""Non-mutating diagnostic for real ETH and TRX chain observers and settlement CLI."""
import os,sys,time,json,inspect,subprocess
from pathlib import Path
base=Path("/home/zomorod2/Saeit-staging")
os.chdir(base);sys.path.insert(0,str(base));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.utils import timezone
from mpw_commerce.auto_reconcile import discover_eth, discover_trx, reconcile_pending_orders
from mpw_commerce.models import CommerceInvoice
def emit(k,v):print(k+"="+json.dumps(v,ensure_ascii=False,default=str))
emit("MPW_SETTLEMENT_PENDING",{"awaiting":CommerceInvoice.objects.filter(status=CommerceInvoice.Status.AWAITING).count(),"eth_trx_probers":"read-only","transactions_created":0})
for label,fn in [("ETH",discover_eth),("TRX",discover_trx)]:
 sig=str(inspect.signature(fn))
 started=time.monotonic()
 try:
  res=fn(now_ms=int(time.time()*1000),lookback_s=60)
  emit("MPW_CHAIN_PROVIDER",{"asset":label,"status":"success","object_type":type(res).__name__,"events":len(res) if hasattr(res,"__len__") else None,"runtime_seconds":round(time.monotonic()-started,2),"signature":sig})
 except Exception as exc:
  emit("MPW_CHAIN_PROVIDER",{"asset":label,"status":"unavailable","error_type":type(exc).__name__,"runtime_seconds":round(time.monotonic()-started,2),"signature":sig})
try:
 result=reconcile_pending_orders()
 emit("MPW_SETTLEMENT_IDLE_EXECUTION",result)
except Exception as exc:
 emit("MPW_SETTLEMENT_IDLE_EXECUTION",{"error_type":type(exc).__name__})
