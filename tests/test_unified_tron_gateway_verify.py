"""Deterministic proof tests. No credentials, network access, or transfers."""
import copy
import unittest

from core.tron_gateway_verify import (
    MAINNET_RECEIVER, SOURCES, PaymentNotFinal, address_hex, verify_native_trx,
)

TX = "a" * 64
TO = "414fd76fc6fb6370dcc86170e9695610ebf559ddad"
OWNER = "41" + "c" * 40
ISSUED = 1800000000000
EXPIRES = ISSUED + 1800000
SUN = 1200456


class TronProofTests(unittest.TestCase):
    def setUp(self):
        self.body = {
            "txID": TX,
            "raw_data": {"contract": [
                {"type": "TransferContract",
                 "parameter": {"value": {
                     "owner_address": OWNER, "to_address": TO, "amount": SUN}}}]},
            "ret": [{"contractRet": "SUCCESS"}],
        }
        self.receipt = {
            "id": TX, "blockNumber": 1234567,
            "blockTimeStamp": ISSUED + 60000, "receipt": {"result": "SUCCESS"},
        }

    def fake_rpc(self, base, endpoint, txid):
        self.assertIn(base, [source[1] for source in SOURCES])
        self.assertEqual(txid, TX)
        if endpoint.endswith("gettransactionbyid"):
            return copy.deepcopy(self.body)
        return copy.deepcopy(self.receipt)

    def verify(self):
        return verify_native_trx(
            TX, MAINNET_RECEIVER, SUN, ISSUED, EXPIRES, rpc=self.fake_rpc)

    def test_wallet_from_owner_screenshot_is_valid_mainnet_address(self):
        self.assertEqual(address_hex(MAINNET_RECEIVER), TO)

    def test_independent_solidified_exact_trx_paid(self):
        proof = self.verify()
        self.assertEqual(proof["txid"], TX)
        self.assertEqual(proof["finality"], "solidified")
        self.assertEqual(len(proof["proof_digest"]), 64)

    def test_incorrect_destination_not_paid(self):
        self.body["raw_data"]["contract"][0]["parameter"]["value"]["to_address"] = "41" + "0"*40
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_incorrect_amount_not_paid(self):
        self.body["raw_data"]["contract"][0]["parameter"]["value"]["amount"] = SUN - 1
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_failed_receipt_not_paid(self):
        self.receipt["receipt"]["result"] = "FAILED"
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_contract_token_not_native_trx(self):
        self.body["raw_data"]["contract"][0]["type"] = "TriggerSmartContract"
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_pre_invoice_deposit_not_paid(self):
        self.receipt["blockTimeStamp"] = ISSUED - 60000
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_late_deposit_not_paid(self):
        self.receipt["blockTimeStamp"] = EXPIRES + 60001
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_wrong_transaction_id_not_paid(self):
        self.body["txID"] = "b"*64
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_non_hex_txid_not_paid(self):
        with self.assertRaises(PaymentNotFinal):
            verify_native_trx("a"*63+"z", MAINNET_RECEIVER, SUN,
                              ISSUED, EXPIRES, rpc=self.fake_rpc)

    def test_bool_amount_not_accepted(self):
        with self.assertRaises(PaymentNotFinal):
            verify_native_trx(TX, MAINNET_RECEIVER, True, ISSUED,
                              EXPIRES, rpc=self.fake_rpc)

    def test_malformed_second_rpc_never_credits(self):
        calls = 0

        def two_rpc(base, endpoint, txid):
            nonlocal calls
            calls += 1
            if base == SOURCES[1][1]:
                return {}
            return self.fake_rpc(base, endpoint, txid)

        with self.assertRaises(PaymentNotFinal):
            verify_native_trx(TX, MAINNET_RECEIVER, SUN,
                              ISSUED, EXPIRES, rpc=two_rpc)
        self.assertGreaterEqual(calls, 3)

    def test_disagreeing_finalized_providers_never_credit(self):
        def disagreement(base, endpoint, txid):
            value = self.fake_rpc(base, endpoint, txid)
            if base == SOURCES[1][1] and endpoint.endswith("gettransactioninfobyid"):
                value["blockNumber"] += 1
            return value

        with self.assertRaises(PaymentNotFinal):
            verify_native_trx(TX, MAINNET_RECEIVER, SUN,
                              ISSUED, EXPIRES, rpc=disagreement)


    def test_unsafe_receiver_checksum_is_rejected(self):
        with self.assertRaises(PaymentNotFinal):
            address_hex(MAINNET_RECEIVER[:-1] + "4")

    def test_unsafe_receiver_alphabet_is_rejected(self):
        with self.assertRaises(PaymentNotFinal):
            address_hex("0" + MAINNET_RECEIVER[1:])

    def test_zero_amount_is_rejected(self):
        with self.assertRaises(PaymentNotFinal):
            verify_native_trx(TX, MAINNET_RECEIVER, 0, ISSUED,
                              EXPIRES, rpc=self.fake_rpc)

    def test_invoice_expiry_before_issue_is_rejected(self):
        with self.assertRaises(PaymentNotFinal):
            verify_native_trx(TX, MAINNET_RECEIVER, SUN, EXPIRES,
                              ISSUED, rpc=self.fake_rpc)

    def test_malformed_raw_data_is_rejected(self):
        self.body["raw_data"] = ["malicious-non-dict"]
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_malformed_parameter_is_rejected(self):
        self.body["raw_data"]["contract"][0]["parameter"] = ["not-an-object"]
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_malformed_recipient_type_is_rejected(self):
        self.body["raw_data"]["contract"][0]["parameter"]["value"]["to_address"] = 1234
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_boolean_onchain_sun_amount_is_rejected(self):
        self.body["raw_data"]["contract"][0]["parameter"]["value"]["amount"] = True
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_failed_transaction_body_is_rejected(self):
        self.body["ret"][0]["contractRet"] = "OUT_OF_ENERGY"
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_top_level_failed_receipt_is_rejected(self):
        self.receipt["result"] = "FAILED"
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_malformed_receipt_result_is_rejected(self):
        self.receipt["receipt"] = ["broken"]
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_missing_block_height_is_rejected(self):
        del self.receipt["blockNumber"]
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_wrong_sender_format_is_rejected(self):
        self.body["raw_data"]["contract"][0]["parameter"]["value"]["owner_address"] = "T" * 34
        with self.assertRaises(PaymentNotFinal):
            self.verify()

    def test_provider_timestamp_disagreement_is_rejected(self):
        def disagreement(base, endpoint, txid):
            value = self.fake_rpc(base, endpoint, txid)
            if base == SOURCES[1][1] and endpoint.endswith("gettransactioninfobyid"):
                value["blockTimeStamp"] += 1000
            return value
        with self.assertRaises(PaymentNotFinal):
            verify_native_trx(TX, MAINNET_RECEIVER, SUN,
                              ISSUED, EXPIRES, rpc=disagreement)

    def test_same_provider_twice_is_not_independent(self):
        from unittest.mock import patch
        with patch("core.tron_gateway_verify.SOURCES", (SOURCES[0], SOURCES[0])):
            with self.assertRaises(PaymentNotFinal):
                self.verify()


if __name__ == "__main__":
    unittest.main()
