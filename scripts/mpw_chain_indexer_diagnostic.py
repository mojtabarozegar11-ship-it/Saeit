#!/usr/bin/env python3
"""Inspect payment indexer failure causes without exposing credentials or addresses."""
import os,sys,inspect,ast,json,re,subprocess
from pathlib import Path
app=Path('/home/zomorod2/Saeit-staging');os.chdir(app);sys.path.insert(0,str(app));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
import mpw_native_checkout
import mpw_commerce.auto_reconcile as ar
from django.conf import settings
from mpw_commerce.auto_reconcile import discover_eth, discover_trx
def emit(k,v):print(k+"="+json.dumps(v,ensure_ascii=False,default=str))
for fn in (discover_eth,discover_trx):
 file=inspect.getsourcefile(fn); source=inspect.getsource(fn)
 lines=[]
 for raw in source.splitlines():
  if any(x in raw.lower() for x in ('password','token','secret','api_key','private_key','mnemonic')):
   lines.append("[credential-related statement redacted]")
  else: lines.append(raw[:220])
 emit('MPW_CHAIN_SOURCE',{'function':fn.__name__,'file':str(Path(file).relative_to(app)) if file.startswith(str(app)) else '<external>','lines':lines[:110]})
try:
 from mpw_native_checkout.chain_indexer import fetch_indexer
except Exception:
 try:
  from mpw_native_checkout.indexer import fetch_indexer
 except Exception:
  fetch_indexer=None
if fetch_indexer is not None:
 source=inspect.getsource(fetch_indexer)
 lines=[]
 for raw in source.splitlines():
  if any(x in raw.lower() for x in ('password','token','secret','api_key','private_key','mnemonic','authorization')):
   lines.append("[credential-related statement redacted]")
  else: lines.append(raw[:220])
 emit('MPW_CHAIN_SOURCE',{'function':fetch_indexer.__name__,'file':str(Path(inspect.getsourcefile(fetch_indexer)).relative_to(app)),'lines':lines[:140]})
inspect_dir=app/'mpw_native_checkout'
for name in ('indexer.py','chain_indexer.py','chain_observer.py','indexer_client.py','chain_discovery.py'):
 p=inspect_dir/name
 if not p.is_file() or p.is_symlink():continue
 s=p.read_text('utf8','replace')
 tree=ast.parse(s)
 keys=set()
 for n in ast.walk(tree):
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('getenv','get') and n.args:
   arg=n.args[0]
   if isinstance(arg,ast.Constant) and isinstance(arg.value,str) and any(t in arg.value.upper() for t in ('INDEX','RPC','ETH','TRX','TRON','API','CHAIN')):
    keys.add(arg.value)
 emit('MPW_CHAIN_MODULE_AUDIT',{'file':name,'referenced_environment_keys':sorted(keys),'provided_environment':{key:bool(os.environ.get(key)) for key in keys},'size':len(s)})
emit('MPW_CHAIN_NETWORK_AUDIT_END',{'secret_values_printed':False})
