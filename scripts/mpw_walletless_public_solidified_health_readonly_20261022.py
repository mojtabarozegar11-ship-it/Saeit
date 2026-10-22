#!/usr/bin/env python3
"""Private read-only mainnet SOLIDITY head reachability, no payment and no secrets.

Compare TronGrid and Nodit (separately named infrastructure operators);
this DOES NOT attest two providers as fully production ready.
Never print the URL, key, wallet address or any RPC response body.
"""
import json,os,pwd,urllib.request,urllib.error,socket,time
from datetime import datetime,timezone
from pathlib import Path

APP=Path('/home/zomorod2/Saeit-staging')
SITE=Path('/home/zomorod2/mojplaywin.com')
if pwd.getpwuid(os.getuid()).pw_name!='zomorod2' or APP.is_symlink() or SITE.is_symlink():
 raise RuntimeError('Not the approved cPanel tenant')
if "APP='/home/zomorod2/Saeit-staging'" not in (SITE/'passenger_wsgi.py').read_text('utf8','replace'):
 raise RuntimeError('Passenger routing mismatch')
pairs=[
 ('TronGrid','https://api.trongrid.io/walletsolidity/getnowblock'),
 ('Nodit','https://tron-mainnet.nodit.io/walletsolidity/getnowblock')
]
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**kw):
  return None

opener=urllib.request.build_opener(NoRedirect())
results=[]
for label,url in pairs:
 result={'provider':label,'reachable':False,'solidified_block':False,
         'fresh_under_10min':False,'auth_required_or_error':False}
 try:
  headers={'Accept':'application/json'}
  if label=='Nodit':headers['X-API-KEY']='nodit-demo'  # documented public demo credential; never use for production
  req=urllib.request.Request(url,method='GET',headers=headers)
  with opener.open(req,timeout=12) as response:
   if response.status!=200:raise RuntimeError('not 200')
   raw=response.read(120001)
   if len(raw)>120000:raise RuntimeError('response too large')
   payload=json.loads(raw)
   header=payload.get('block_header',{}).get('raw_data',{})
   number=header.get('number')
   millis=header.get('timestamp')
   if type(number) is not int or number<1000000 or type(millis) is not int:
    raise RuntimeError('solidified block metadata missing')
   age=abs(time.time()-millis/1000)
   result.update(reachable=True,solidified_block=True,fresh_under_10min=age<600)
 except (urllib.error.HTTPError,urllib.error.URLError,RuntimeError,ValueError,KeyError,TimeoutError,OSError) as exc:
  result['auth_required_or_error']=True
  result['error_class']=type(exc).__name__
  if isinstance(exc,urllib.error.HTTPError): result['http_status']=exc.code
 results.append(result)
print('MPW_WALLETLESS_TRON_REAL_PROVIDERS='+json.dumps({
 'sources':results,
 'real_provider_count_reachable':sum(1 for x in results if x['reachable'] and x['fresh_under_10min']),
 'source_operators_separately_named':True,
 'operator_security_review_completed':False,
 'native_transfer_dual_receipt_roundtrip_proven':False,
 'finance_mutations':0,
 'public_activation':False},sort_keys=True))
