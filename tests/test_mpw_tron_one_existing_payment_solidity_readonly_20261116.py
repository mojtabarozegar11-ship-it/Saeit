"""No real HTTP calls: test native TRX on-chain matching and zero-spend RPC boundaries."""
import unittest
from pathlib import Path

from scripts.mpw_tron_one_existing_payment_solidity_readonly_20261116 import (
    OWNER_RECEIVER, API, MAX_RESPONSE, TIMEOUT_SEC,
    base58check_to_hex, compare_solidified,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mpw_tron_one_existing_payment_solidity_readonly_20261116.py"
WORKFLOW = ROOT / ".github/workflows/mpw-trx-safe-flags-evidence-20261115.yml"
TXID = "a" * 64
PAYER = "41" + "b" * 40
RECEIVER = base58check_to_hex(OWNER_RECEIVER)
SUN = 9000000


def fixture():
    body = {
        "txID": TXID,
        "ret": [{"contractRet": "SUCCESS"}],
        "raw_data": {"contract": [{
            "type": "TransferContract",
            "parameter": {
                "type_url": "type.googleapis.com/protocol.TransferContract",
                "value": {
                    "owner_address": PAYER,
                    "to_address": RECEIVER,
                    "amount": SUN,
                },
            },
        }]},
    }
    receipt = {
        "id": TXID, "blockNumber": 188,
        "blockTimeStamp": 1715314602000,
        "receipt": {"result": "SUCCESS"},
    }
    return body, receipt


def accepted(body=None, receipt=None, **kwargs):
    b, r = fixture()
    return compare_solidified(
        b if body is None else body,
        r if receipt is None else receipt,
        txid=kwargs.get("txid", TXID),
        payer=kwargs.get("payer", PAYER),
        receiver=kwargs.get("receiver", RECEIVER),
        sun=kwargs.get("sun", SUN),
    )


class NativeTrxSolidityReadOnlyTests(unittest.TestCase):
    def test_public_wallet_decodes_to_expected_41_prefix(self):
        self.assertEqual(base58check_to_hex(OWNER_RECEIVER), "414fd76fc6fb6370dcc86170e9695610ebf559ddad")

    def test_wallet_lookalike_has_invalid_checksum(self):
        with self.assertRaises(ValueError):
            base58check_to_hex(OWNER_RECEIVER.replace("Uksd2Un", "UksdZUn"))

    def test_bad_wallet_char_fails(self):
        with self.assertRaises(ValueError):
            base58check_to_hex(OWNER_RECEIVER[:-1] + "0")

    def test_synthetic_matched_native_transfer_passes_pure_match(self):
        self.assertTrue(accepted())

    def test_txid_mismatch_fails(self):
        self.assertFalse(accepted(txid="c" * 64))

    def test_invalid_txid_not_accepted(self):
        self.assertFalse(accepted(txid="z" * 64))

    def test_wrong_sender_does_not_receive_buyer_credit(self):
        self.assertFalse(accepted(payer="41" + "d" * 40))

    def test_wrong_recipient_not_accepted(self):
        self.assertFalse(accepted(receiver="41" + "c" * 40))

    def test_wrong_amount_not_accepted(self):
        self.assertFalse(accepted(sun=SUN + 1))

    def test_bool_amount_never_accepted(self):
        self.assertFalse(accepted(sun=True))

    def test_missing_solidified_body_fails(self):
        self.assertFalse(accepted(body={}))

    def test_missing_solidified_receipt_fails(self):
        self.assertFalse(accepted(receipt={}))

    def test_rpc_error_not_payment(self):
        self.assertFalse(accepted(body={"Error": "node error"}))

    def test_non_native_trc20_fails(self):
        b, r = fixture()
        b["raw_data"]["contract"][0]["type"] = "TriggerSmartContract"
        self.assertFalse(accepted(body=b))

    def test_multiple_contracts_fails(self):
        b, r = fixture()
        b["raw_data"]["contract"].append(b["raw_data"]["contract"][0])
        self.assertFalse(accepted(body=b))

    def test_contract_reverted_not_payment(self):
        b, r = fixture()
        b["ret"][0]["contractRet"] = "REVERT"
        self.assertFalse(accepted(body=b))

    def test_failed_receipt_not_payment(self):
        b, r = fixture()
        r["receipt"]["result"] = "REVERT"
        self.assertFalse(accepted(receipt=r))

    def test_failed_top_level_receipt_not_payment(self):
        b, r = fixture()
        r["result"] = "FAILED"
        self.assertFalse(accepted(receipt=r))

    def test_missing_block_number_not_final(self):
        b, r = fixture()
        r.pop("blockNumber")
        self.assertFalse(accepted(receipt=r))

    def test_missing_block_timestamp_not_final(self):
        b, r = fixture()
        r.pop("blockTimeStamp")
        self.assertFalse(accepted(receipt=r))

    def test_sender_cannot_equal_receiver(self):
        self.assertFalse(accepted(payer=RECEIVER))

    def test_transport_is_fixed_trongrid_mainnet_and_bounded(self):
        self.assertEqual(API, "https://api.trongrid.io")
        self.assertLessEqual(TIMEOUT_SEC, 10)
        self.assertLessEqual(MAX_RESPONSE, 100000)

    def test_source_has_only_two_allowed_readonly_method_names(self):
        s = SCRIPT.read_text("utf-8")
        self.assertIn('"/walletsolidity/gettransactionbyid"', s)
        self.assertIn('"/walletsolidity/gettransactioninfobyid"', s)
        for value in ("broadcasttransaction", "createtransaction", "sendrawtransaction",
                      "triggerSmartContract", "private_key", "mnemonic",
                      ".save(", ".delete(", "objects.create("):
            self.assertNotIn(value, s)

    def test_one_existing_event_selected_with_no_customer_or_amount_output(self):
        s = SCRIPT.read_text("utf-8")
        self.assertIn("paid[:25]", s)
        self.assertIn('"no_customer_delivery_asserted": True', s)
        self.assertIn('"actual_external_buyer_proven": False', s)
        self.assertIn('"no_paid_checkout_or_broadcast": True', s)
        self.assertNotIn("print(txid)", s)
        self.assertNotIn("print(intent)", s)
        self.assertNotIn("print(sender)", s)
        self.assertNotIn("print(amount)", s)

    def test_no_api_key_or_redirect_and_tls_host_fixed(self):
        s = SCRIPT.read_text("utf-8")
        self.assertIn("class NoRedirect(urllib.request.HTTPRedirectHandler)", s)
        self.assertIn("urllib.request.ProxyHandler({})", s)
        self.assertIn("API + path", s)
        self.assertNotIn("TRON_PRO_API_KEY", s)
        self.assertNotIn("Authorization", s)

    def test_workflow_checks_reviewer_blob(self):
        s = WORKFLOW.read_text("utf-8")
        self.assertIn("scripts/mpw_tron_one_existing_payment_solidity_readonly_20261116.py", s)
        self.assertIn("tests.test_mpw_tron_one_existing_payment_solidity_readonly_20261116", s)
        self.assertIn("MPW_TRON_PRIOR_RECEIPT_SOLIDITY_READONLY=", s)
        self.assertIn("permissions:\n  contents: read", s)
        self.assertNotIn("  push:", s)
        self.assertNotIn("  workflow_dispatch:", s)


if __name__ == "__main__":
    unittest.main()
