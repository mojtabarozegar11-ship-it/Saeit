#!/usr/bin/env python3
import os,sys,json,inspect,ast
from pathlib import Path
b=Path('/home/zomorod2/Saeit-staging');os.chdir(b);sys.path.insert(0,str(b));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from scripts.mojplaywin_native_chain_verify import LockedQuote,verify_trx_transfer
for obj in (LockedQuote,verify_trx_transfer):
 try:
  src=inspect.getsource(obj)
  # Code primitives only; no configured wallet literals or credentials.
  print('MPW_GUEST_VERIFIER_SOURCE='+json.dumps({'module':obj.__module__,'name':obj.__name__,'source':src[:13000]}))
 except Exception as e:print('MPW_GUEST_VERIFIER_MISSING='+json.dumps({'name':getattr(obj,'__name__','unknown'),'reason':type(e).__name__}))

for folder in ('mpw_commerce','scripts'):
 for file in (b/folder).glob('*.py'):
  if any(x in file.name for x in ('quote','rate','rpc','chain','provider','wallet','invoic')):
   try:tree=ast.parse(file.read_text('utf8'))
   except Exception:continue
   defs=[n.name for n in tree.body if isinstance(n,ast.FunctionDef) and any(k in n.name for k in ('quote','verify','rate','rpc'))]
   if defs:print('MPW_GUEST_REUSE_FUNCTIONS='+json.dumps({'file':str(file.relative_to(b)),'functions':defs[:30]}))
