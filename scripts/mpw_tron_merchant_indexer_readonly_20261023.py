#!/usr/bin/env python3
"""Read-only TEST of merchant-bound account transaction listing.

Never prints merchant address, transaction identity, prices, RPC bodies or
credentials. Does not create an order or change production commerce.
"""
from __future__ import annotations
import json,os,sys,urllib.error,urllib.parse,urllib.request
from pathlib import Path
APP=Path("/home/zomorod2/Saeit-staging")
ROOT=Path("/home/zomorod2/mojplaywin.com")
if not APP.is_dir() or APP.is_symlink() or ROOT.is_symlink():
    raise SystemExit("Unexpected source")
if "APP='/home/zomorod2/Saeit-staging'" not in (ROOT/"passenger_wsgi.py").read_text("utf8","replace"):
    raise SystemExit("Unexpected passenger config")
os.chdir(APP);sys.path.insert(0,str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from mpw_commerce.invoicing import RECEIVERS
from scripts.mojplaywin_native_chain_verify import tron_address_to_hex
v=RECEIVERS.get("TRX")
if not isinstance(v,(list,tuple)) or len(v)!=3 or v[0]!="tron-mainnet":
    raise SystemExit("Unverified merchant TRX tuple")
receiver=v[1]
tron_address_to_hex(receiver)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None
query=urllib.parse.urlencode({"only_to":"true","only_confirmed":"true","limit":"10",
                             "order_by":"block_timestamp,desc"})
url="https://api.trongrid.io/v1/accounts/"+receiver+"/transactions?"+query
r={"scope":"merchant-account-history-readonly","merchant_address_valid":True,
   "writes":0,"checkout_changed":False,"indexer_ok":False}
req=urllib.request.Request(url,headers={"Accept":"application/json",
   "User-Agent":"MojPlayWin-TRX-Gateway/1.0"},method="GET")
try:
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=15) as f:
        r["http_status"]=f.status
        raw=f.read(2_000_001)
        if len(raw)>2_000_000 or f.headers.get_content_type()!="application/json":
            raise ValueError("Untrusted JSON reply")
    data=json.loads(raw)
    if type(data) is not dict or type(data.get("data")) is not list or data.get("success") is not True:
        raise ValueError("Indexer response not usable")
    r["indexer_ok"]=True
    r["page_records"]=len(data["data"])
    r["pagination_available"]=bool(data.get("meta",{}).get("fingerprint"))
except urllib.error.HTTPError as exc:
    r["status"]="HTTP_DENIED";r["http_status"]=exc.code
except Exception as exc:
    r["status"]="FAILED";r["error_class"]=type(exc).__name__
print("MPW_MERCHANT_INDEXER="+json.dumps(r,sort_keys=True))
if not r["indexer_ok"]:raise SystemExit(2)
