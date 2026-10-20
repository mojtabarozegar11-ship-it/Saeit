#!/usr/bin/env python3
import os,sys,json,inspect,ast
from pathlib import Path
b=Path('/home/zomorod2/Saeit-staging');os.chdir(b);sys.path.insert(0,str(b));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from scripts.mojplaywin_native_chain_verify import LockedQuote,verify_trx_transfer
from mpw_commerce.chain_rpc import verify_with_trusted_rpc
from mpw_commerce.buyer_rates import quote_rate
for obj in (LockedQuote,verify_trx_transfer,verify_with_trusted_rpc,quote_rate):
 try:
  src=inspect.getsource(obj)
  # Code primitives only; no configured wallet literals or credentials.
  print('MPW_GUEST_VERIFIER_SOURCE='+json.dumps({'module':obj.__module__,'name':obj.__name__,'source':src[:13000]}))
 except Exception as e:print('MPW_GUEST_VERIFIER_MISSING='+json.dumps({'name':getattr(obj,'__name__','unknown'),'reason':type(e).__name__}))
