"""Offline safe canonical TRON SolidityNode verification tests; no money or network."""
import copy
import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal

from services.mpw_tron_independent_solidified_rpc import (
    RpcProvider,PaymentHold,parse_solidified_native_trx,hex_to_tron_address,
    verify_distinct_provider_config,query_solidified_transfer,verified_live_pair,
)
from services.mpw_trx_walletless_core import InvoiceIntent
TX="a"*64
HEX_FROM="41"+"11"*20
HEX_TO="41"+"22"*20
MS=1792642200000
SOURCE_A=RpcProvider("rpc-one","operator-a","https://node-a.example.org")
SOURCE_B=RpcProvider("rpc-two","operator-b","https://node-b.example.com")


def tx_body(**changes):
    body={"txID":TX,"raw_data":{"timestamp":MS-5000,"contract":[{
         "type":"TransferContract","parameter":{"value":{
         "owner_address":HEX_FROM,"to_address":HEX_TO,"amount":123456}}}]},
         "ret":[{"contractRet":"SUCCESS"}]}
    body.update(changes)
    return body


def tx_info(**changes):
    info={"id":TX,"blockNumber":70000001,"blockTimeStamp":MS,
          "receipt":{"net_fee":1}}
    info.update(changes)
    return info


class ReadOnlyTronVerifierTests(unittest.TestCase):
    def setUp(self):
        self.body=tx_body()
        self.info=tx_info()

    def run_parse(self):
        return parse_solidified_native_trx(TX,self.body,self.info,source_id="rpc-one")

    def test_valid_native_transfer_verified_from_body_and_solidified_receipt(self):
        rec=self.run_parse()
        self.assertEqual(rec.amount_sun,123456)
        self.assertEqual(rec.sender,hex_to_tron_address(HEX_FROM))
        self.assertEqual(rec.recipient,hex_to_tron_address(HEX_TO))
        self.assertEqual(rec.block_time,datetime.fromtimestamp(MS/1000,timezone.utc))
        self.assertTrue(rec.solidified and rec.execution_success and rec.transfer_contract)

    def test_malformed_or_foreign_hash_rejected(self):
        for value in ("a"*63,"b"*64,"a"*64+"f"):
            with self.subTest(value=value),self.assertRaises(PaymentHold):
                parse_solidified_native_trx(value,self.body,self.info,source_id="rpc-one")

    def test_unverified_solidity_receipt_never_passes(self):
        for info in ({},{"id":TX},{"id":TX,"blockNumber":99,"blockTimeStamp":MS},
                     tx_info(id="b"*64),tx_info(blockNumber=0),tx_info(result="FAILED"),
                     tx_info(receipt={"result":"FAILED"}),tx_info(blockTimeStamp=0)):
            with self.subTest(info=info),self.assertRaises(PaymentHold):
                parse_solidified_native_trx(TX,self.body,info,source_id="rpc-one")

    def test_smart_contracts_and_multiple_contracts_rejected(self):
        self.body["raw_data"]["contract"][0]["type"]="TriggerSmartContract"
        with self.assertRaises(PaymentHold):self.run_parse()
        self.body=tx_body()
        self.body["raw_data"]["contract"].append(copy.deepcopy(self.body["raw_data"]["contract"][0]))
        with self.assertRaises(PaymentHold):self.run_parse()

    def test_failed_or_missing_tx_ret_rejected(self):
        for ret in ([],[{}],[{"contractRet":"OUT_OF_ENERGY"}],None):
            self.body=tx_body(ret=ret)
            with self.subTest(ret=ret),self.assertRaises(PaymentHold):self.run_parse()

    def test_bad_native_amount_and_address_rejected(self):
        for amt in ("100",0,True,-1,123.1):
            self.body=tx_body()
            self.body["raw_data"]["contract"][0]["parameter"]["value"]["amount"]=amt
            with self.subTest(amt=amt),self.assertRaises(PaymentHold):self.run_parse()
        self.body=tx_body()
        self.body["raw_data"]["contract"][0]["parameter"]["value"]["to_address"]="41deadbeef"
        with self.assertRaises(PaymentHold):self.run_parse()

    def test_bad_timestamp_rejected(self):
        self.body["raw_data"]["timestamp"]=MS+120000
        with self.assertRaises(PaymentHold):self.run_parse()

    def test_rpc_operator_independence_required(self):
        verify_distinct_provider_config(SOURCE_A,SOURCE_B)
        for b in (
            RpcProvider("rpc-two","operator-a","https://node-c.example.net"),
            RpcProvider("rpc-one","operator-b","https://node-c.example.net"),
            RpcProvider("rpc-two","operator-b","https://node-a.example.org"),
            RpcProvider("rpc-two","operator-b","http://node-b.example.com"),
            RpcProvider("rpc-two","operator-b","https://localhost"),
            RpcProvider("rpc-two","operator-b","https://127.0.0.1"),
            RpcProvider("rpc-two","operator-b","https://node-b.example.com/evil"),
        ):
            with self.subTest(endpoint=b.endpoint),self.assertRaises(PaymentHold):
                verify_distinct_provider_config(SOURCE_A,b)

    def test_unattested_pair_never_created(self):
        with self.assertRaises(PaymentHold):
            verified_live_pair(SOURCE_A,SOURCE_B,trusted_operator_attestation=False)

    def test_no_network_transport_queries_both_solidified_methods(self):
        calls=[]
        def transport(provider,path,txid):
            calls.append((provider.source_id,path,txid))
            return copy.deepcopy(self.body if path.endswith("gettransactionbyid") else self.info)
        r=query_solidified_transfer(SOURCE_A,TX,transport=transport)
        self.assertEqual(r.amount_sun,123456)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(s[2]==TX and s[1].startswith("/walletsolidity/") for s in calls))

    def test_authenticated_dual_source_proof_integration_no_payment_written(self):
        recipient=hex_to_tron_address(HEX_TO)
        invoice=InvoiceIntent(
            order_id=5,customer_id=8,network="tron-mainnet",recipient=recipient,
            amount_sun=123456,usd_total=Decimal("0.03"),
            issued_at=datetime.fromtimestamp((MS-9000)/1000,timezone.utc),
            expires_at=datetime.fromtimestamp((MS-9000)/1000,timezone.utc)+timedelta(minutes=10),
            quote_usd_per_trx=Decimal("0.25"),
        )
        def transport(provider,path,txid):
            return copy.deepcopy(self.body if path.endswith("gettransactionbyid") else self.info)
        pair=verified_live_pair(SOURCE_A,SOURCE_B,trusted_operator_attestation=True,transport=transport)
        self.assertEqual(pair.verify(invoice,TX,lambda n,h:False),(TX,hex_to_tron_address(HEX_FROM)))
        with self.assertRaises(PaymentHold):
            pair.verify(invoice,TX,lambda n,h:True)

    def test_disagreement_or_rpc_application_error_denied(self):
        def transport(provider,path,txid):
            if provider.source_id=="rpc-two" and path.endswith("gettransactioninfobyid"):
                return tx_info(blockTimeStamp=MS+3000)
            return copy.deepcopy(self.body if path.endswith("gettransactionbyid") else self.info)
        pair=verified_live_pair(SOURCE_A,SOURCE_B,trusted_operator_attestation=True,transport=transport)
        inv=InvoiceIntent(1,1,"tron-mainnet",hex_to_tron_address(HEX_TO),123456,Decimal("0.02"),
                          datetime.fromtimestamp((MS-9000)/1000,timezone.utc),
                          datetime.fromtimestamp((MS-9000)/1000,timezone.utc)+timedelta(minutes=10),Decimal("0.2"))
        with self.assertRaises(PaymentHold):
            pair.verify(inv,TX,lambda n,h:False)
        def err(provider,path,txid):
            return {"Error":"RPC unavailable"}
        with self.assertRaises(PaymentHold):
            query_solidified_transfer(SOURCE_A,TX,transport=err)


if __name__=="__main__":unittest.main()
