#!/usr/bin/env python3
"""Verify ONE newly signed real Shasta native transfer, with no key access.

Public test receipt is read from VPS journal metadata only. Solidiﬁed body,
receipt, sender, recipient, amount, block and age are checked against it.
This cannot pay a mainnet invoice or create merchant fulfillment.
"""
from __future__ import annotations
from datetime import datetime,timezone
import json,sys,time,urllib.request,urllib.error
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from services.mpw_tron_independent_solidified_rpc import (
    parse_solidified_native_trx,PaymentHold,
)
from services.mpw_trx_walletless_core import ADDRESS,TX_ID
NODE="https://api.shasta.trongrid.io"
MAX_TX=150000
MAX_HEAD=2_000_000

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise PaymentHold("Unexpected Shasta provider redirect")

def rpc(path,txid=""):
    if path not in ("/walletsolidity/getnowblock",
        "/walletsolidity/gettransactionbyid",
        "/walletsolidity/gettransactioninfobyid"):
        raise PaymentHold("Untrusted Shasta request")
    get=path.endswith("getnowblock")
    payload=None if get else json.dumps({"value":txid,"visible":False},
                      separators=(",",":")).encode("utf8")
    request=urllib.request.Request(NODE+path,method="GET" if get else "POST",
        data=payload,headers={
            "Accept":"application/json","Content-Type":"application/json",
            "User-Agent":"MojPlayWin-Shasta-Canary-Readonly/1.0",
        })
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=12) as response:
        if response.status!=200 or response.headers.get_content_type()!="application/json":
            raise PaymentHold("Unexpected Shasta response")
        cap=MAX_HEAD if get else MAX_TX
        raw=response.read(cap+1)
    if len(raw)>cap:
        raise PaymentHold("Oversized Shasta evidence")
    doc=json.loads(raw)
    if type(doc) is not dict or doc.get("Error"):
        raise PaymentHold("Invalid Shasta evidence")
    return doc

def verify(receipt):
    if (type(receipt) is not dict or receipt.get("network")!="tron-shasta"
        or receipt.get("test_only") is not True
        or type(receipt.get("amount_sun")) is not int
        or not 0<receipt["amount_sun"]<=2_000_000
        or not isinstance(receipt.get("txid"),str)
        or not TX_ID.fullmatch(receipt["txid"])
        or not isinstance(receipt.get("sender"),str)
        or not ADDRESS.fullmatch(receipt["sender"])
        or not isinstance(receipt.get("recipient"),str)
        or not ADDRESS.fullmatch(receipt["recipient"])):
        raise PaymentHold("Untrusted VPS public test receipt")
    for attempt in range(15):
        try:
            now=datetime.now(timezone.utc)
            head=rpc("/walletsolidity/getnowblock")
            metadata=head.get("block_header",{}).get("raw_data",{})
            height=metadata.get("number")
            timestamp=metadata.get("timestamp")
            if type(height) is not int or height<=0 or type(timestamp) is not int:
                raise PaymentHold("No solidified testnet header")
            freshness=now.timestamp()-timestamp/1000
            if not -60<=freshness<=600:
                raise PaymentHold("Stale testnet solidity head")
            body=rpc("/walletsolidity/gettransactionbyid",receipt["txid"])
            info=rpc("/walletsolidity/gettransactioninfobyid",receipt["txid"])
            tx=parse_solidified_native_trx(
                receipt["txid"],body,info,
                source_id="official-shasta-test-rpc",network="tron-shasta",
            )
            if (tx.recipient!=receipt["recipient"] or tx.sender!=receipt["sender"]
                or tx.amount_sun!=receipt["amount_sun"]
                or not tx.execution_success or not tx.solidified
                or info.get("blockNumber",height+1)>height):
                raise PaymentHold("On-chain test transfer differs from invoice")
            return {"status":"SHASTA_TEST_TRX_FINALIZED",
                "test_network":"tron-shasta",
                "transaction_id":receipt["txid"],
                "atomic_amount_sun":tx.amount_sun,
                "matching_sender":True,"matching_recipient":True,
                "finalized_receipt":True,"test_only":True,
                "mainnet_payment_recognized":False,"production_writes":0}
        except (PaymentHold,ValueError,TypeError,KeyError,OSError,urllib.error.URLError):
            if attempt==14:
                raise PaymentHold("Shasta finality test unresolved; do not resend payment")
            time.sleep(4)

if __name__=="__main__":
    inp=Path(sys.argv[1])
    if not inp.is_file() or inp.stat().st_size>10000:
        raise SystemExit("No bounded public journal receipt")
    try:
        print("MPW_SHASTA_REAL_PAYMENT_VERIFY="+json.dumps(verify(json.loads(inp.read_text("utf8"))),sort_keys=True))
    except PaymentHold as exc:
        print("MPW_SHASTA_REAL_PAYMENT_VERIFY="+json.dumps({
            "status":"UNCONFIRMED_TEST_TRANSFER","error_type":type(exc).__name__,
            "mainnet_payment_recognized":False,
        },sort_keys=True))
        raise SystemExit(2)
