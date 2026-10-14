"""Offline USDT ERC-20/TRC-20 verifier regressions; no RPC or live payment."""
import copy
import unittest
from scripts.mojplaywin_usdt_chain_verify import (
    USDT_ETH, USDT_TRON, ETH_RECEIVER, TRON_RECEIVER, TRANSFER_EVENT,
    TRANSFER_SELECTOR, USDTQuote, USDTVerificationError,
    verify_ethereum_usdt, verify_tron_usdt,
)
from scripts.mojplaywin_native_chain_verify import tron_address_to_hex

AMOUNT = 7_500_000
TX = "0x" + "c" * 64
BLOCK_HASH = "0x" + "b" * 64
ETH_SENDER = "0x" + "1" * 40
TRON_SENDER = TRON_RECEIVER  # controlled placeholder only for an offline test


def call_data(recipient20, amount=AMOUNT):
    return "0x" + TRANSFER_SELECTOR + "0" * 24 + recipient20 + format(amount, "064x")


def event(contract, sender20, recipient20, amount=AMOUNT):
    return {
        "address": contract,
        "topics": ["0x" + TRANSFER_EVENT, "0x" + "0" * 24 + sender20, "0x" + "0" * 24 + recipient20],
        "data": "0x" + format(amount, "064x"),
    }


def eth_fixture():
    quote = USDTQuote(72, "ethereum-mainnet", AMOUNT, ETH_SENDER, 100000, 200000)
    tx = {
        "hash": TX, "from": ETH_SENDER, "to": USDT_ETH,
        "value": "0x0", "input": call_data(ETH_RECEIVER[2:]),
        "blockNumber": "0x64", "blockHash": BLOCK_HASH,
    }
    receipt = {
        "transactionHash": TX, "status": "0x1", "blockNumber": "0x64",
        "blockHash": BLOCK_HASH,
        "logs": [event(USDT_ETH, ETH_SENDER[2:], ETH_RECEIVER[2:])],
    }
    def rpc(method, params):
        return {
            "eth_chainId": "0x1", "eth_getTransactionByHash": tx,
            "eth_getTransactionReceipt": receipt, "eth_blockNumber": "0x70",
            "eth_getBlockByNumber": {"hash": BLOCK_HASH, "timestamp": "0x96"},
        }[method]
    return quote, tx, receipt, rpc


def tron_fixture():
    sender = tron_address_to_hex(TRON_SENDER).lower()
    recipient = tron_address_to_hex(TRON_RECEIVER).lower()
    contract = tron_address_to_hex(USDT_TRON).lower()
    quote = USDTQuote(72, "tron-mainnet", AMOUNT, TRON_SENDER, 100000, 200000)
    tx = {
        "txID": TX[2:], "ret": [{"contractRet": "SUCCESS"}],
        "raw_data": {"contract": [{
            "type": "TriggerSmartContract",
            "parameter": {"value": {
                "owner_address": sender, "contract_address": contract,
                "data": call_data(recipient[2:]),
            }},
        }]},
    }
    info = {
        "id": TX[2:], "receipt": {"result": "SUCCESS"},
        "blockNumber": 123, "blockTimeStamp": 150000,
        "log": [event(contract[2:], sender[2:], recipient[2:])],
    }
    def solidity(path, data):
        return {
            "/walletsolidity/gettransactionbyid": tx,
            "/walletsolidity/gettransactioninfobyid": info,
        }[path]
    return quote, tx, info, solidity


class EthereumUSDTTests(unittest.TestCase):
    def test_valid_usdt_transfer(self):
        q, tx, receipt, rpc = eth_fixture()
        result = verify_ethereum_usdt(TX, q, rpc)
        self.assertEqual((result["asset"], result["amount_atomic"]), ("USDT", AMOUNT))
        self.assertEqual(result["confirmed_blocks"], 13)

    def test_reject_lookalike_contract(self):
        q, tx, receipt, rpc = eth_fixture()
        tx["to"] = "0x" + "f" * 40
        with self.assertRaises(USDTVerificationError):
            verify_ethereum_usdt(TX, q, rpc)

    def test_reject_missing_token_event(self):
        q, tx, receipt, rpc = eth_fixture()
        receipt["logs"] = []
        with self.assertRaises(USDTVerificationError):
            verify_ethereum_usdt(TX, q, rpc)

    def test_reject_wrong_token_amount(self):
        q, tx, receipt, rpc = eth_fixture()
        receipt["logs"][0]["data"] = "0x" + format(AMOUNT - 1, "064x")
        with self.assertRaises(USDTVerificationError):
            verify_ethereum_usdt(TX, q, rpc)

    def test_reject_wrong_wallet(self):
        q, tx, receipt, rpc = eth_fixture()
        tx["from"] = "0x" + "2" * 40
        with self.assertRaises(USDTVerificationError):
            verify_ethereum_usdt(TX, q, rpc)

    def test_reject_short_confirmations(self):
        q, tx, receipt, rpc = eth_fixture()
        with self.assertRaises(USDTVerificationError):
            verify_ethereum_usdt(TX, q, rpc, minimum_confirmations=5)

    def test_reject_reverted(self):
        q, tx, receipt, rpc = eth_fixture()
        receipt["status"] = "0x0"
        with self.assertRaises(USDTVerificationError):
            verify_ethereum_usdt(TX, q, rpc)

    def test_reject_wrong_network(self):
        q, tx, receipt, rpc = eth_fixture()
        q = USDTQuote(q.order_id, "tron-mainnet", q.amount_micro, q.expected_sender, q.issued_at_ms, q.expires_at_ms)
        with self.assertRaises(USDTVerificationError):
            verify_ethereum_usdt(TX, q, rpc)

    def test_reject_wrong_calldata_recipient(self):
        q, tx, receipt, rpc = eth_fixture()
        tx["input"] = call_data("f" * 40)
        with self.assertRaises(USDTVerificationError):
            verify_ethereum_usdt(TX, q, rpc)


class TronUSDTTests(unittest.TestCase):
    def test_valid_solidified_usdt_transfer(self):
        q, tx, info, rpc = tron_fixture()
        result = verify_tron_usdt(TX[2:], q, rpc)
        self.assertEqual(result["finality"], "tron-solidity")
        self.assertEqual(result["amount_atomic"], AMOUNT)

    def test_reject_native_trx(self):
        q, tx, info, rpc = tron_fixture()
        tx["raw_data"]["contract"][0]["type"] = "TransferContract"
        with self.assertRaises(USDTVerificationError):
            verify_tron_usdt(TX[2:], q, rpc)

    def test_reject_fake_trc20_token(self):
        q, tx, info, rpc = tron_fixture()
        tx["raw_data"]["contract"][0]["parameter"]["value"]["contract_address"] = "41" + "f" * 40
        with self.assertRaises(USDTVerificationError):
            verify_tron_usdt(TX[2:], q, rpc)

    def test_reject_wrong_token_amount(self):
        q, tx, info, rpc = tron_fixture()
        info["log"][0]["data"] = "0x" + format(AMOUNT - 1, "064x")
        with self.assertRaises(USDTVerificationError):
            verify_tron_usdt(TX[2:], q, rpc)

    def test_reject_unsolidified_transaction(self):
        q, tx, info, rpc = tron_fixture()
        info["blockNumber"] = 0
        with self.assertRaises(USDTVerificationError):
            verify_tron_usdt(TX[2:], q, rpc)

    def test_reject_event_from_other_contract(self):
        q, tx, info, rpc = tron_fixture()
        info["log"][0]["address"] = "f" * 40
        with self.assertRaises(USDTVerificationError):
            verify_tron_usdt(TX[2:], q, rpc)

    def test_reject_late_payment(self):
        q, tx, info, rpc = tron_fixture()
        info["blockTimeStamp"] = q.expires_at_ms + 1
        with self.assertRaises(USDTVerificationError):
            verify_tron_usdt(TX[2:], q, rpc)

    def test_reject_duplicate_events(self):
        q, tx, info, rpc = tron_fixture()
        info["log"].append(copy.deepcopy(info["log"][0]))
        with self.assertRaises(USDTVerificationError):
            verify_tron_usdt(TX[2:], q, rpc)


if __name__ == "__main__":
    unittest.main()
