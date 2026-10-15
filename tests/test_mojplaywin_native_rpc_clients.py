"""Pure tests for server-pinned read-only blockchain RPC adapters."""
import json
from pathlib import Path
import sys
from unittest.mock import patch
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import mojplaywin_native_rpc_clients as r

ETH_HASH="0x"+"a"*64
TRON_HASH="b"*64


class RpcGuardTests(unittest.TestCase):
    def test_eth_rpc_correct_mainnet_response(self):
        with patch.object(r,"_http_json",return_value={"jsonrpc":"2.0","id":1,"result":"0x1"}) as fetch:
            value=r.ethereum_rpc("eth_chainId",[])
        self.assertEqual(value,"0x1")
        self.assertEqual(fetch.call_args.args[0],r.ETH_RPC_URL)

    def test_block_height_only_not_full_transactions(self):
        with patch.object(r,"_http_json",return_value={"jsonrpc":"2.0","id":1,"result":{"hash":"0x"+"a"*64}}):
            self.assertIn("hash",r.ethereum_rpc("eth_getBlockByNumber",["0x64",False]))
        with self.assertRaises(r.NativeRpcUnavailable):
            r.ethereum_rpc("eth_getBlockByNumber",["0x64",True])

    def test_cannot_broadcast_eth_transaction(self):
        with self.assertRaises(r.NativeRpcUnavailable):
            r.ethereum_rpc("eth_sendRawTransaction",["0x1234"])

    def test_invalid_eth_hash_rejected_before_request(self):
        with self.assertRaises(r.NativeRpcUnavailable):
            r.ethereum_rpc("eth_getTransactionReceipt",["0x1234"])

    def test_tron_receipt_pinned_host(self):
        with patch.object(r,"_http_json",return_value={"id":TRON_HASH}) as fetch:
            value=r.tron_solidity_rpc("/walletsolidity/gettransactioninfobyid",{"value":TRON_HASH})
        self.assertEqual(value["id"],TRON_HASH)
        self.assertEqual(fetch.call_args.args[0],r.TRX_RPC_URL+"/walletsolidity/gettransactioninfobyid")

    def test_cannot_sign_or_broadcast_tron(self):
        with self.assertRaises(r.NativeRpcUnavailable):
            r.tron_solidity_rpc("/wallet/broadcasttransaction",{"value":TRON_HASH})

    def test_tron_hash_must_be_exact_64_hex_chars(self):
        with self.assertRaises(r.NativeRpcUnavailable):
            r.tron_solidity_rpc("/walletsolidity/gettransactionbyid",{"value":"oops"})

    def test_invalid_rpc_json_cannot_succeed(self):
        class FakeResponse:
            def __init__(self, payload): self.payload=payload
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return self.payload
        with self.assertRaises(r.NativeRpcUnavailable):
            r._http_json("https://example.com",{},opener=lambda *args,**kw: FakeResponse(b"not-json"))

    def test_oversized_response_rejected(self):
        class FakeResponse:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return b"Z"*(r.MAX_RPC_BYTES+1)
        with self.assertRaises(r.NativeRpcUnavailable):
            r._http_json("https://example.com",{},opener=lambda *args,**kw:FakeResponse())

    def test_rpc_error_object_blocks(self):
        class FakeResponse:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return b'{"error":{"code":-1,"message":"bad"}}'
        with self.assertRaises(r.NativeRpcUnavailable):
            r._http_json("https://example.com",{},opener=lambda *args,**kw:FakeResponse())


if __name__=="__main__":
    unittest.main()
