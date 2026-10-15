"""Tests for the staged native ETH/TRX receipt verifier; no network or real payments."""
import copy
import importlib.util
import pathlib
import sys
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "mojplaywin_native_chain_verify.py"
spec = importlib.util.spec_from_file_location("mpw_chain_verify", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

ETH_TX_HASH = "0x" + "a" * 64
TRX_TX_HASH = "c" * 64
ETH_SENDER = "0x" + "d" * 40
TRX_SENDER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
CREATED = 1_700_000_000_000
EXPIRES = 1_700_000_060_000


class NativeChainVerifierTests(unittest.TestCase):
    def setUp(self):
        self.eth_quote = m.LockedQuote(
            order_id=72, network="ethereum-mainnet", smallest_units=12345000,
            expected_sender=ETH_SENDER, created_at_ms=CREATED, expires_at_ms=EXPIRES)
        self.trx_quote = m.LockedQuote(
            order_id=72, network="tron-mainnet", smallest_units=12345678,
            expected_sender=TRX_SENDER, created_at_ms=CREATED, expires_at_ms=EXPIRES)
        self.eth = {
            "eth_chainId": "0x1",
            "eth_getTransactionByHash": {
                "hash": ETH_TX_HASH,
                "from": ETH_SENDER, "to": m.ETH_RECEIVER,
                "value": hex(self.eth_quote.smallest_units),
                "blockNumber": hex(100),
                "blockHash": "0x" + "b" * 64,
            },
            "eth_getTransactionReceipt": {
                "transactionHash": ETH_TX_HASH,
                "status": "0x1",
                "blockNumber": hex(100),
                "blockHash": "0x" + "b" * 64,
            },
            "eth_blockNumber": hex(111),
            "eth_getBlockByNumber": {
                "hash": "0x" + "b" * 64,
                "timestamp": hex(1_700_000_010),
            }
        }
        self.tron = {
            "/walletsolidity/gettransactionbyid": {
                "txID": TRX_TX_HASH,
                "ret": [{"contractRet": "SUCCESS"}],
                "raw_data": {"contract": [{
                    "type": "TransferContract",
                    "parameter": {"value": {
                        "owner_address": m.tron_address_to_hex(TRX_SENDER),
                        "to_address": m.tron_address_to_hex(m.TRX_RECEIVER),
                        "amount": self.trx_quote.smallest_units,
                    }},
                }]}
            },
            "/walletsolidity/gettransactioninfobyid": {
                "id": TRX_TX_HASH,
                "receipt": {"result": "SUCCESS"},
                "blockNumber": 1_000_000,
                "blockTimeStamp": 1_700_000_010_000,
            }
        }

    def eth_rpc(self, method, params):
        return copy.deepcopy(self.eth[method])

    def tron_rpc(self, method, params):
        return copy.deepcopy(self.tron[method])

    def test_valid_eth_receipt_requires_exact_sender_recipient_value_finality(self):
        proof=m.verify_eth_transfer(ETH_TX_HASH, self.eth_quote, self.eth_rpc)
        self.assertEqual(proof["confirmed_blocks"], 12)
        self.assertEqual(proof["order_id"], 72)

    def test_eth_rejects_wrong_chain(self):
        self.eth["eth_chainId"]="0x38"
        with self.assertRaises(m.VerificationError):
            m.verify_eth_transfer(ETH_TX_HASH, self.eth_quote, self.eth_rpc)

    def test_eth_rejects_wrong_receiver(self):
        self.eth["eth_getTransactionByHash"]["to"]=ETH_SENDER
        with self.assertRaises(m.VerificationError):
            m.verify_eth_transfer(ETH_TX_HASH, self.eth_quote, self.eth_rpc)

    def test_eth_rejects_wrong_sender(self):
        self.eth["eth_getTransactionByHash"]["from"]="0x"+"e"*40
        with self.assertRaises(m.VerificationError):
            m.verify_eth_transfer(ETH_TX_HASH, self.eth_quote, self.eth_rpc)

    def test_eth_rejects_amount_mismatch(self):
        self.eth["eth_getTransactionByHash"]["value"]=hex(12344999)
        with self.assertRaises(m.VerificationError):
            m.verify_eth_transfer(ETH_TX_HASH, self.eth_quote, self.eth_rpc)

    def test_eth_rejects_reverted_receipt(self):
        self.eth["eth_getTransactionReceipt"]["status"]="0x0"
        with self.assertRaises(m.VerificationError):
            m.verify_eth_transfer(ETH_TX_HASH, self.eth_quote, self.eth_rpc)

    def test_eth_rejects_unfinalized(self):
        self.eth["eth_blockNumber"]=hex(110)
        with self.assertRaises(m.VerificationError):
            m.verify_eth_transfer(ETH_TX_HASH, self.eth_quote, self.eth_rpc)

    def test_eth_rejects_reorged_block(self):
        self.eth["eth_getBlockByNumber"]["hash"]="0x"+"f"*64
        with self.assertRaises(m.VerificationError):
            m.verify_eth_transfer(ETH_TX_HASH, self.eth_quote, self.eth_rpc)

    def test_eth_rejects_old_payment(self):
        self.eth["eth_getBlockByNumber"]["timestamp"]=hex(1_699_999_999)
        with self.assertRaises(m.VerificationError):
            m.verify_eth_transfer(ETH_TX_HASH, self.eth_quote, self.eth_rpc)

    def test_eth_rejects_unverified_sender_quote(self):
        quote=m.LockedQuote(72,"ethereum-mainnet",12345000,"",CREATED,EXPIRES)
        with self.assertRaises(m.VerificationError):
            m.verify_eth_transfer(ETH_TX_HASH, quote, self.eth_rpc)

    def test_trx_recipient_base58check(self):
        self.assertEqual(m.tron_address_to_hex(m.TRX_RECEIVER)[:2],"41")
        with self.assertRaises(m.VerificationError):
            m.tron_address_to_hex(m.TRX_RECEIVER[:-1]+"4")

    def test_trx_valid_solidity_transfer(self):
        proof=m.verify_trx_transfer(TRX_TX_HASH,self.trx_quote,self.tron_rpc)
        self.assertEqual(proof["finality"],"tron-solidity")

    def test_trx_rejects_token_contract(self):
        self.tron["/walletsolidity/gettransactionbyid"]["raw_data"]["contract"][0]["type"]="TriggerSmartContract"
        with self.assertRaises(m.VerificationError):
            m.verify_trx_transfer(TRX_TX_HASH,self.trx_quote,self.tron_rpc)

    def test_trx_rejects_wrong_receiver(self):
        self.tron["/walletsolidity/gettransactionbyid"]["raw_data"]["contract"][0]["parameter"]["value"]["to_address"]="41"+"e"*40
        with self.assertRaises(m.VerificationError):
            m.verify_trx_transfer(TRX_TX_HASH,self.trx_quote,self.tron_rpc)

    def test_trx_rejects_wrong_amount(self):
        self.tron["/walletsolidity/gettransactionbyid"]["raw_data"]["contract"][0]["parameter"]["value"]["amount"]=12345677
        with self.assertRaises(m.VerificationError):
            m.verify_trx_transfer(TRX_TX_HASH,self.trx_quote,self.tron_rpc)

    def test_trx_rejects_pending_unverified_tx(self):
        self.tron["/walletsolidity/gettransactionbyid"]={}
        with self.assertRaises(m.VerificationError):
            m.verify_trx_transfer(TRX_TX_HASH,self.trx_quote,self.tron_rpc)

    def test_trx_rejects_wrong_time(self):
        self.tron["/walletsolidity/gettransactioninfobyid"]["blockTimeStamp"]=1_699_999_990_000
        with self.assertRaises(m.VerificationError):
            m.verify_trx_transfer(TRX_TX_HASH,self.trx_quote,self.tron_rpc)


if __name__ == "__main__":
    unittest.main()
