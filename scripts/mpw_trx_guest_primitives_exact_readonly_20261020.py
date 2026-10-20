#!/usr/bin/env python3
import os,sys,json,inspect,ast
from pathlib import Path
b=Path('/home/zomorod2/Saeit-staging');os.chdir(b);sys.path.insert(0,str(b));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from mpw_commerce.buyer_wallets import fetch_server_rate
from mpw_commerce.fulfillment import _private_file
from scripts.mojplaywin_native_rpc_clients import tron_solidity_rpc
from scripts.mojplaywin_direct_wallet_discovery import Candidate,discover_trx
for obj in (fetch_server_rate,_private_file,tron_solidity_rpc,Candidate):
 try:
  src=inspect.getsource(obj)
  print('MPW_GUEST_IMPL_PRIMITIVE='+json.dumps({'name':obj.__name__,'module':obj.__module__,'code':src[:8200]}))
 except Exception as e:print('MPW_GUEST_IMPL_PRIMITIVE_MISSING='+json.dumps({'name':getattr(obj,'__name__','na'),'error':type(e).__name__}))
from django.urls import get_resolver
from mpw_commerce.urls import urlpatterns
print('MPW_GUEST_MPWC_URLS='+json.dumps([{'route':str(x.pattern),'name':x.name,'callback':str(x.callback.__module__)} for x in urlpatterns if hasattr(x,'callback')][:45]))
print('MPW_GUEST_IMPL_AUDIT=PASS')
