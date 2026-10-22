#!/usr/bin/env python3
"""Read-only TRON RPC source inventory for walletless payment safety.

NO URL, private address, key, secret, endpoint path, or HTTP response body is printed.
Distinct hostname hints alone do not establish independent control.
"""
import inspect,ast,os,pwd,sys,json,re
from pathlib import Path
P=Path('/home/zomorod2/Saeit-staging')
S=Path('/home/zomorod2/mojplaywin.com')
if pwd.getpwuid(os.getuid()).pw_name!='zomorod2' or P.is_symlink() or S.is_symlink():raise RuntimeError('Wrong account')
if "APP='/home/zomorod2/Saeit-staging'" not in (S/'passenger_wsgi.py').read_text('utf8','replace'):raise RuntimeError('Wrong Passenger')
os.chdir(P);sys.path.insert(0,str(P));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
paths=('scripts/mojplaywin_native_rpc_clients.py','scripts/mojplaywin_native_chain_verify.py',
       'mpw_commerce/auto_reconcile.py')
for path in paths:
 f=P/path
 if not f.is_file():continue
 source=f.read_text('utf8','replace')
 tree=ast.parse(source)
 defs=[]
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
   if any(t in node.name.lower() for t in ('tron','rpc','solidity','verify','indexer','discover')):
    calls=sorted({ast.unparse(x.func)[:55] for x in ast.walk(node) if isinstance(x,ast.Call)})
    defs.append({'function':node.name,'calls':calls[:25],'lines':node.end_lineno-node.lineno+1})
 envkeys=sorted({m.group(1) for m in re.finditer(r'(?:getenv|environ\.get)\(\s*["\']([A-Z0-9_]+)["\']',source)})
 print('MPW_TRON_RPC_MODULE='+json.dumps({'module':path,'functions':defs[:25],
  'environment_variable_names_only':envkeys[:25],
  'source_lines':len(source.splitlines()),'never_dump_endpoints':True},sort_keys=True))
try:
 from scripts import mojplaywin_native_rpc_clients as rpc
 fn=getattr(rpc,'tron_solidity_rpc',None)
 print('MPW_TRON_RPC_CURRENT_FUNCTION='+json.dumps({
   'present':callable(fn),'function_origin':fn.__module__ if callable(fn) else None,
   'registered_provider_count_independently_attested':0,
   'reasons':'Two externally governed provider identities cannot be established from a callable or URL count alone.',
   'real_payment_enabled_by_this_check':False},sort_keys=True))
except Exception as e:
 print('MPW_TRON_RPC_CURRENT_FUNCTION='+json.dumps({'present':False,'exception_type':type(e).__name__}))
print('MPW_TRON_RPC_INVENTORY_READONLY=PASS')
