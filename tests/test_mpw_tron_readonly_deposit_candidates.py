"""Offline tests for merchant exact-amount read-only transfer indexer."""
import copy
import json
import unittest
from email.message import Message
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from services.mpw_tron_readonly_deposit_candidates import (
    find_candidate_hashes,fetch_page,NoRedirect
)
from services.mpw_tron_independent_solidified_rpc import hex_to_tron_address
from services.mpw_trx_walletless_core import PaymentHold

SENDER="41"+"11"*20
TARGET="41"+"22"*20
RECEIVER=hex_to_tron_address(TARGET)
TX="a"*64
NOW=datetime(2026,10,23,10,0,tzinfo=timezone.utc)
ISSUED=NOW
ENDS=NOW+timedelta(minutes=10)
MS=int((ISSUED+timedelta(minutes=2)).timestamp()*1000)

def transfer():
    return {"txID":TX,"block_timestamp":MS,"raw_data":{"contract":[{
        "type":"TransferContract","parameter":{"value":{
            "owner_address":SENDER,"to_address":TARGET,"amount":1234567,
        }}
    }]},"ret":[{"contractRet":"SUCCESS"}]}

def lookup(rows,*,meta=None,receiver=RECEIVER,amount=1234567):
    def fake(url):
        assert url.startswith("https://api.trongrid.io/v1/accounts/"+receiver+"/transactions?")
        assert "only_confirmed=true" in url and "only_to=true" in url
        return {"success":True,"data":rows,"meta":meta or {}}
    return find_candidate_hashes(receiver,amount,ISSUED,ENDS,fetch=fake)

class CandidateIndexerTests(unittest.TestCase):
    def test_one_exact_candidate(self):
        self.assertEqual(lookup([transfer()]),[TX])

    def test_wallet_and_amount_and_time_must_match(self):
        for mutation in ("amount","address","contract","timestamp","txid","multi"):
            tx=transfer()
            if mutation=="amount":tx["raw_data"]["contract"][0]["parameter"]["value"]["amount"]=1234568
            if mutation=="address":tx["raw_data"]["contract"][0]["parameter"]["value"]["to_address"]=SENDER
            if mutation=="contract":tx["raw_data"]["contract"][0]["type"]="TriggerSmartContract"
            if mutation=="timestamp":tx["block_timestamp"]=MS-3600000
            if mutation=="txid":tx["txID"]="a"*63
            if mutation=="multi":tx["raw_data"]["contract"].append(copy.deepcopy(tx["raw_data"]["contract"][0]))
            with self.subTest(mutation=mutation):
                self.assertEqual(lookup([tx]),[])

    def test_duplicate_candidate_deduplicated(self):
        self.assertEqual(lookup([transfer(),transfer()]),[TX])

    def test_fails_on_more_than_sixteen_distinct_matches(self):
        rows=[]
        for i in range(17):
            x=transfer();x["txID"]=format(i+1,"064x");rows.append(x)
        with self.assertRaises(PaymentHold):
            lookup(rows)

    def test_no_untrusted_recipient_or_invoice_times(self):
        for receiver,amount,from_time,to_time in (
            ("bad",1234567,ISSUED,ENDS),
            (RECEIVER,0,ISSUED,ENDS),
            (RECEIVER,1234567,ISSUED,ISSUED),
            (RECEIVER,1234567,ISSUED,ENDS+timedelta(hours=1)),
            (RECEIVER,1234567,ISSUED.replace(tzinfo=None),ENDS),
        ):
            with self.subTest(receiver=receiver,amount=amount),self.assertRaises(PaymentHold):
                find_candidate_hashes(receiver,amount,from_time,to_time,fetch=lambda _:None)

    def test_invalid_page_and_host_refused(self):
        for doc in ({},{"success":False,"data":[]},{"success":True,"data":"abc"}):
            with self.subTest(doc=doc),self.assertRaises(PaymentHold):
                find_candidate_hashes(RECEIVER,1234567,ISSUED,ENDS,fetch=lambda _:doc)
        with self.assertRaises(PaymentHold):
            fetch_page("http://api.trongrid.io/v1/accounts/evil")

    def test_only_https_json_and_bounded_content(self):
        class Response:
            status=200
            headers=Message()
            headers["Content-Type"]="application/json"
            def __init__(self,payload):self.payload=payload
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return self.payload[:n]
        class Opener:
            def __init__(self,payload):self.payload=payload
            def open(self,request,timeout):return Response(self.payload)
        valid=b'{"success":true,"data":[]}'
        with patch("services.mpw_tron_readonly_deposit_candidates.urllib.request.build_opener",return_value=Opener(valid)):
            result=fetch_page("https://api.trongrid.io/v1/accounts/ABCDE/transactions")
            self.assertEqual(result,{"success":True,"data":[]})
        huge=json.dumps({"success":True,"data":"A"*2000100}).encode()
        with patch("services.mpw_tron_readonly_deposit_candidates.urllib.request.build_opener",return_value=Opener(huge)):
            with self.assertRaises(PaymentHold):
                fetch_page("https://api.trongrid.io/v1/accounts/ABCDE/transactions")

if __name__=="__main__":unittest.main()
