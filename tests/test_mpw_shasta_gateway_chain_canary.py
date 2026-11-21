"""Offline fixture: public Shasta canary is never a live checkout receipt."""
import unittest
from datetime import datetime, timezone

from scripts.mpw_shasta_gateway_chain_canary_20261022 import (
    audit, CANARY_SUN, CANARY_TXID, WALLET, TESTNET,
)
from services.mpw_tron_independent_solidified_rpc import PaymentHold

WHEN = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
BLOCK_TIME = int(WHEN.timestamp() * 1000) - 20_000
TX_TIME = BLOCK_TIME - 30_000


def fixture(method, path, payload=None):
    if path.endswith("getnowblock"):
        return {"block_header": {"raw_data": {"number": 7000, "timestamp": BLOCK_TIME}}}
    if path.endswith("getaccount"):
        return {"address": WALLET, "balance": 1389281200}
    if path.endswith("gettransactionbyid"):
        return {"txID": CANARY_TXID, "raw_data": {"timestamp": TX_TIME,
            "contract": [{"type": "TransferContract", "parameter": {"value": {
                "owner_address": "41d093f24888ab06073a4bdffbb8107db1ea9dc0a0",
                "to_address": "41e0ad376afffdf139779d3be13676dc338ff7831a",
                "amount": CANARY_SUN}}}]}, "ret": [{"contractRet": "SUCCESS"}]}
    if path.endswith("gettransactioninfobyid"):
        return {"id": CANARY_TXID, "blockNumber": 6999,
                "blockTimeStamp": TX_TIME + 1000, "receipt": {"net_fee": 100_000}}
    raise AssertionError("unexpected external operation")


class ShastaCanaryTests(unittest.TestCase):
    def test_readonly_chain_and_native_transfer(self):
        result = audit(read=fixture, now=WHEN)
        self.assertEqual(result["network"], TESTNET)
        self.assertEqual(result["status"], "SHASTA_CHAIN_READONLY_PASSED")
        self.assertTrue(result["historical_native_transfer_solidified"])
        self.assertEqual(result["testnet_transfers_broadcast"], 0)
        self.assertFalse(result["test_invoice_paid"])
        self.assertFalse(result["gateway_financial_settlement_verified"])

    def test_wrong_destination_or_amount_fails_closed(self):
        def tampered(method, path, payload=None):
            reply = fixture(method, path, payload)
            if path.endswith("gettransactionbyid"):
                reply["raw_data"]["contract"][0]["parameter"]["value"]["amount"] = 42
            return reply
        with self.assertRaises(PaymentHold):
            audit(read=tampered, now=WHEN)

    def test_contract_call_is_never_native_payment(self):
        def contract(method, path, payload=None):
            reply = fixture(method, path, payload)
            if path.endswith("gettransactionbyid"):
                reply["raw_data"]["contract"][0]["type"] = "TriggerSmartContract"
            return reply
        with self.assertRaises(PaymentHold):
            audit(read=contract, now=WHEN)

    def test_unsolidified_or_stale_head_rejected(self):
        def stale(method, path, payload=None):
            reply = fixture(method, path, payload)
            if path.endswith("getnowblock"):
                reply["block_header"]["raw_data"]["timestamp"] -= 700_000
            return reply
        with self.assertRaises(PaymentHold):
            audit(read=stale, now=WHEN)


if __name__ == "__main__":
    unittest.main()
