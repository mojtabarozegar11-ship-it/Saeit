"""Bounded, read-only discovery of incoming native TRX candidates.

This module cannot recognize a payment or deliver an asset. Candidates must be
validated independently against finalized chain body and receipt.
"""
from datetime import datetime,timedelta
import json
import re
import urllib.parse
import urllib.request
from services.mpw_trx_walletless_core import ADDRESS,TX_ID,PaymentHold
from services.mpw_tron_independent_solidified_rpc import hex_to_tron_address

ORIGIN="https://api.trongrid.io"
MAX_PAGE=200
MAX_BYTES=2000000
HEX_ADDRESS=re.compile(r"^41[0-9a-fA-F]{40}$")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def fetch_page(url):
    if not url.startswith(ORIGIN+"/v1/accounts/") or len(url)>2048:
        raise PaymentHold("Invalid read-only indexer origin")
    request=urllib.request.Request(url,method="GET",headers={
        "Accept":"application/json",
        "User-Agent":"MojPlayWin-TRX-Readonly/1.0",
    })
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=10) as response:
            if response.status!=200 or response.headers.get_content_type()!="application/json":
                raise PaymentHold("Unexpected incoming transfer index response")
            data=response.read(MAX_BYTES+1)
    except OSError as exc:
        raise PaymentHold("Read-only indexer unavailable") from exc
    if len(data)>MAX_BYTES:
        raise PaymentHold("Indexer JSON overflow")
    try:
        page=json.loads(data)
    except (ValueError,UnicodeDecodeError) as exc:
        raise PaymentHold("Unreadable indexer response") from exc
    if type(page) is not dict or page.get("success") is not True or type(page.get("data")) is not list:
        raise PaymentHold("Malformed incoming transaction page")
    return page

def find_candidate_hashes(recipient,amount_sun,issued_at,expires_at,*,fetch=fetch_page):
    if not isinstance(recipient,str) or ADDRESS.fullmatch(recipient) is None:
        raise PaymentHold("Invalid server-owned TRX recipient")
    if type(amount_sun) is not int or not 0<amount_sun<10**18:
        raise PaymentHold("Invalid atomic amount")
    if not isinstance(issued_at,datetime) or not isinstance(expires_at,datetime):
        raise PaymentHold("Expected aware invoice times")
    if (issued_at.tzinfo is None or expires_at.tzinfo is None
        or issued_at.utcoffset() is None or expires_at.utcoffset() is None
        or not timedelta(0)<expires_at-issued_at<=timedelta(minutes=15)):
        raise PaymentHold("Invalid invoice interval")
    start=int(issued_at.timestamp()*1000)
    end=int(expires_at.timestamp()*1000)
    if start<1:
        raise PaymentHold("Invalid invoice issue time")
    found=set()
    fingerprint=""
    for _page in range(4):
        params={"only_confirmed":"true","only_to":"true","limit":str(MAX_PAGE),
                "min_block_timestamp":str(max(1,start-30000)),
                "order_by":"block_timestamp,desc"}
        if fingerprint:
            params["fingerprint"]=fingerprint
        url=ORIGIN+"/v1/accounts/"+recipient+"/transactions?"+urllib.parse.urlencode(params)
        result=fetch(url)
        if not isinstance(result,dict) or result.get("success") is not True:
            raise PaymentHold("Untrusted candidate listing")
        rows=result.get("data")
        if not isinstance(rows,list) or len(rows)>MAX_PAGE:
            raise PaymentHold("Unbounded candidate listing")
        for entry in rows:
            if not isinstance(entry,dict):
                continue
            txid=entry.get("txID")
            ts=entry.get("block_timestamp")
            if (not isinstance(txid,str) or not TX_ID.fullmatch(txid)
                or type(ts) is not int or not start<=ts<=end):
                continue
            contracts=entry.get("raw_data",{}).get("contract",[])
            if not isinstance(contracts,list) or len(contracts)!=1 or not isinstance(contracts[0],dict):
                continue
            contract=contracts[0]
            if contract.get("type")!="TransferContract":
                continue
            value=contract.get("parameter",{}).get("value",{})
            if not isinstance(value,dict) or value.get("amount")!=amount_sun:
                continue
            target=value.get("to_address")
            if not isinstance(target,str) or not HEX_ADDRESS.fullmatch(target):
                continue
            if hex_to_tron_address(target)!=recipient:
                continue
            found.add(txid)
            if len(found)>16:
                raise PaymentHold("Ambiguous matching incoming transfers")
        if len(rows)<MAX_PAGE:
            break
        next_token=result.get("meta",{}).get("fingerprint")
        if (not isinstance(next_token,str) or len(next_token)>512
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,512}",next_token)
            or next_token==fingerprint):
            raise PaymentHold("Unsafe indexer pagination")
        fingerprint=next_token
    else:
        raise PaymentHold("Read-only indexer page limit reached")
    return sorted(found)
