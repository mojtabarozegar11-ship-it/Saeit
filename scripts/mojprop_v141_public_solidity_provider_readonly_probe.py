#!/usr/bin/env python3
"""Live public TRON SolidityNode API connectivity probe; zero wallet data.

One GET to each source for getnowblock (never broadcasts any TRX). Return only
HTTP status, whether the node supports chain-confirmed block and chain height
range. Does not claim providers are free for merchant production without
published terms, rate limits, and audit.
"""
from datetime import datetime,timezone,timedelta
from urllib.request import Request,urlopen,HTTPRedirectHandler,build_opener
from urllib.error import HTTPError,URLError
import json

HOSTS=(
 "https://api.trongrid.io",
 "https://tron-rpc.publicnode.com",
)
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):
  return None

opener=build_opener(NoRedirect)
report={"schema":"mojprop.two-mainnet-solidity-node.readonly.v1",
        "broadcast_performed":False,"wallet_or_customer_data_read":False,
        "private_api_key_used":False,"results":[]}
for base in HOSTS:
 item={"provider_host":base.removeprefix("https://"),"http":None,
       "supports_solidified_block":False,"has_recent_block":False,
       "block_height_positive":False,"error_kind":None}
 try:
  path="/walletsolidity/getnowblock"
  req=Request(base+path,method="GET",
              headers={"Content-Type":"application/json",
                       "Accept":"application/json"})
  with opener.open(req,timeout=12) as response:
   item["http"]=response.status
   if response.geturl()!=base+path:
    raise ValueError("Unexpected HTTP redirection")
   raw=response.read(300001)
  if len(raw)>300000:
   raise ValueError("Oversized provider answer")
  d=json.loads(raw.decode("utf8"))
  number=d.get("block_header",{}).get("raw_data",{}).get("number")
  timestamp=d.get("block_header",{}).get("raw_data",{}).get("timestamp")
  now=int(datetime.now(timezone.utc).timestamp()*1000)
  item["block_height_positive"]=type(number) is int and number>0
  item["has_recent_block"]=type(timestamp) is int and 0<now-timestamp<900000
  item["supports_solidified_block"]=(
      item["http"]==200 and item["block_height_positive"]
      and item["has_recent_block"] and bool(d.get("blockID")))
 except HTTPError as e:
  item["http"]=e.code
  item["error_kind"]="HTTPError"
 except (ValueError,URLError,UnicodeError,OSError,TimeoutError) as e:
  item["error_kind"]=type(e).__name__
 report["results"].append(item)
report["two_independent_hosts_reachable"]=all(
 r["supports_solidified_block"] for r in report["results"])
print("MOJPROP_PUBLIC_SOLIDITY_READONLY="+json.dumps(report,sort_keys=True))
# A failure is valuable diagnostic evidence and never triggers a live release.
if not report["two_independent_hosts_reachable"]:
 raise SystemExit(1)
