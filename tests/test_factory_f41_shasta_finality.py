"""F41 independent SolidityNode safety regression; synthetic fixtures never count as live proof."""
import copy
import hashlib
import json
import os
from unittest.mock import patch
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import factory_f41_shasta_finality as finality

SAMPLE = ROOT / "factory_config" / "f41_samples" / "reconciliation.json"
RECIPIENT = "TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNQ"


def sample():
    spec = json.loads(SAMPLE.read_text("utf8"))
    spec["data"]["observations"][1]["amount_base_units"] = "25000000"
    return spec


def response(txid, amount=17000000, recipient=None):
    return {
        "txID": txid,
        "ret": [{"contractRet": "SUCCESS"}],
        "raw_data": {"contract": [{"type": "TransferContract", "parameter": {
            "type_url": "type.googleapis.com/protocol.TransferContract",
            "value": {
                "owner_address": "41" + "ab" * 20,
                "to_address": recipient or finality.tron_hex(RECIPIENT),
                "amount": amount,
            }
        }}]},
    }


def trc20_sample():
    spec = sample()
    for inv in spec["data"]["invoices"]:
        inv["asset"] = "TRC20"
        inv["token_contract"] = RECIPIENT
    for obs in spec["data"]["observations"]:
        obs["asset"] = "TRC20"
    return spec


def contract_body(txid):
    body = response(txid)
    body["raw_data"]["contract"][0]["type"] = "TriggerSmartContract"
    return body


def event_receipt(txid, *, amount=None, recipient=None, contract=None, success=True):
    if amount is None:
        amount = 17000000 if txid == "a"*64 else 25000000
    receiver = finality.tron_hex(recipient or RECIPIENT)[2:]
    sender = "ab" * 20
    contract_id = finality.tron_hex(contract or RECIPIENT)[2:]
    return {
        "id": txid, "blockNumber": 123,
        "receipt": {"result": "SUCCESS" if success else "REVERT"},
        "log": [{"address": contract_id, "topics": [
            finality.TRANSFER_TOPIC,
            "0"*24 + sender, "0"*24 + receiver],
            "data": format(amount, "064x")}],
    }


class FinalityTests(unittest.TestCase):
    def test_valid_base58_address_decodes(self):
        self.assertEqual(len(finality.tron_hex(RECIPIENT)), 42)
        self.assertTrue(finality.tron_hex(RECIPIENT).startswith("41"))

    def test_bad_checksum_rejected(self):
        bad = RECIPIENT[:-1] + ("1" if RECIPIENT[-1] != "1" else "2")
        with self.assertRaisesRegex(ValueError, "CHECKSUM"):
            finality.tron_hex(bad)

    def test_source_must_be_preexisting_reconciliation_request(self):
        spec = sample()
        spec["kind"] = "vesting"
        with self.assertRaisesRegex(ValueError, "RECONCILIATION_SPEC"):
            finality.evaluate(spec, lambda txid: {})

    def test_exact_matching_transactions_are_only_private_evidence(self):
        spec = sample()
        lookups = []
        def lookup(txid):
            lookups.append(txid)
            amount = 17000000 if txid == "a"*64 else 25000000
            return response(txid, amount)
        report = finality.evaluate(spec, lookup)
        self.assertEqual(len(lookups), 2)
        self.assertEqual(report["verified_match_count"], 2)
        self.assertTrue(report["all_invoices_finalized"])
        self.assertTrue(report["simulation_used"])
        self.assertFalse(report["customer_delivery_enabled"])
        self.assertFalse(report["quality_1000_certified"])
        self.assertFalse(any(x["delivery_authorized"] for x in report["records"]))
        self.assertFalse(report["mainnet_enabled"])

    def test_missing_transaction_is_not_paid(self):
        report = finality.evaluate(sample(), lambda txid: {})
        self.assertEqual(report["verified_match_count"], 0)
        self.assertTrue(all(x["status"] == "NOT_YET_VISIBLE_ON_SOLIDITY_NODE" for x in report["records"]))

    def test_wrong_txid_cannot_confirm(self):
        report = finality.evaluate(sample(), lambda txid: response("f" * 64))
        self.assertEqual(report["verified_match_count"], 0)
        self.assertEqual(report["records"][0]["status"], "CHAIN_TXID_INTEGRITY_FAILURE")

    def test_failed_execution_cannot_confirm(self):
        def lookup(txid):
            data = response(txid)
            data["ret"][0]["contractRet"] = "FAILED"
            return data
        report = finality.evaluate(sample(), lookup)
        self.assertEqual(report["verified_match_count"], 0)

    def test_wrong_recipient_cannot_confirm(self):
        report = finality.evaluate(sample(), lambda txid: response(txid, recipient="41" + "00"*20))
        self.assertEqual(report["verified_match_count"], 0)
        self.assertEqual(report["records"][0]["status"], "CHAIN_AMOUNT_OR_RECIPIENT_MISMATCH")

    def test_wrong_amount_cannot_confirm(self):
        report = finality.evaluate(sample(), lambda txid: response(txid, amount=1))
        self.assertEqual(report["verified_match_count"], 0)

    def test_contract_call_cannot_masquerade_as_native_trx(self):
        def lookup(txid):
            data = response(txid)
            data["raw_data"]["contract"][0]["type"] = "TriggerSmartContract"
            return data
        self.assertEqual(finality.evaluate(sample(), lookup)["verified_match_count"], 0)

    def test_multiple_contracts_cannot_confirm(self):
        def lookup(txid):
            data = response(txid)
            data["raw_data"]["contract"].append(copy.deepcopy(data["raw_data"]["contract"][0]))
            return data
        self.assertEqual(finality.evaluate(sample(), lookup)["verified_match_count"], 0)

    def test_false_or_missing_execution_receipt_cannot_confirm(self):
        for ret in ([], [{}], None):
            with self.subTest(ret=ret):
                def lookup(txid):
                    data = response(txid)
                    data["ret"] = ret
                    return data
                self.assertEqual(finality.evaluate(sample(), lookup)["verified_match_count"], 0)

    def test_offline_observation_mismatch_prevents_live_lookup(self):
        spec = sample()
        spec["data"]["observations"][0]["amount_base_units"] = "1"
        lookups = []
        report = finality.evaluate(spec, lambda txid: lookups.append(txid))
        self.assertEqual(report["records"][0]["status"], "OBSERVATION_INVOICE_MISMATCH")
        self.assertEqual(len(lookups), 1)

    def test_trc20_fails_closed_without_event_verifier(self):
        spec = sample()
        for inv in spec["data"]["invoices"]:
            inv["asset"] = "TRC20"
            inv["token_contract"] = RECIPIENT
        for obs in spec["data"]["observations"]:
            obs["asset"] = "TRC20"
        def must_not_call(txid):
            raise AssertionError("Unapproved TRC20 must not query the chain")
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": ""}):
            report = finality.evaluate(spec, must_not_call)
        self.assertTrue(all(x["status"] == "TRC20_CONTRACT_NOT_APPROVED" for x in report["records"]))

    def test_trc20_allowlisted_receipt_solidified_and_exact(self):
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": RECIPIENT}):
            report = finality.evaluate(trc20_sample(), contract_body, event_receipt)
        self.assertEqual(report["verified_match_count"], 2)
        self.assertTrue(report["all_invoices_finalized"])
        self.assertTrue(report["simulation_used"])
        self.assertFalse(report["customer_delivery_enabled"])
        self.assertFalse(report["mainnet_enabled"])

    def test_trc20_missing_contract_rejected_in_builder(self):
        spec = trc20_sample()
        del spec["data"]["invoices"][0]["token_contract"]
        with self.assertRaisesRegex(ValueError, "INVOICE_FIELDS"):
            finality.evaluate(spec, contract_body, event_receipt)

    def test_trc20_extra_contract_field_on_trx_rejected(self):
        spec = sample()
        spec["data"]["invoices"][0]["token_contract"] = RECIPIENT
        with self.assertRaisesRegex(ValueError, "INVOICE_FIELDS"):
            finality.evaluate(spec, contract_body, event_receipt)

    def test_trc20_wrong_amount_never_finalizes(self):
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": RECIPIENT}):
            report = finality.evaluate(trc20_sample(), contract_body,
                                      lambda txid: event_receipt(txid, amount=1))
        self.assertEqual(report["verified_match_count"], 0)

    def test_trc20_wrong_contract_event_never_finalizes(self):
        def wrong_contract(txid):
            receipt = event_receipt(txid)
            receipt["log"][0]["address"] = "ab"*20
            return receipt
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": RECIPIENT}):
            report = finality.evaluate(trc20_sample(), contract_body, wrong_contract)
        self.assertEqual(report["verified_match_count"], 0)

    def test_trc20_failed_execution_receipt_never_finalizes(self):
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": RECIPIENT}):
            report = finality.evaluate(trc20_sample(), contract_body,
                                      lambda txid: event_receipt(txid, success=False))
        self.assertEqual(report["verified_match_count"], 0)

    def test_trc20_receipt_without_solidified_height_never_finalizes(self):
        def no_block(txid):
            receipt = event_receipt(txid)
            receipt["blockNumber"] = 0
            return receipt
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": RECIPIENT}):
            report = finality.evaluate(trc20_sample(), contract_body, no_block)
        self.assertEqual(report["verified_match_count"], 0)

    def test_trc20_duplicate_matching_events_never_finalize(self):
        def repeated(txid):
            receipt = event_receipt(txid)
            receipt["log"].append(copy.deepcopy(receipt["log"][0]))
            return receipt
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": RECIPIENT}):
            report = finality.evaluate(trc20_sample(), contract_body, repeated)
        self.assertTrue(all(x["status"] == "TRC20_DUPLICATE_MATCHING_EVENTS" for x in report["records"]))
        self.assertEqual(report["verified_match_count"], 0)

    def test_trc20_non_trigger_body_stops_before_receipt_query(self):
        def no_receipt(_):
            self.fail("A plain TRX transfer must not trigger token receipt lookup")
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": RECIPIENT}):
            report = finality.evaluate(trc20_sample(),
                                      lambda txid: response(txid), no_receipt)
        self.assertEqual(report["verified_match_count"], 0)

    def test_trc20_wrong_receipt_txid_never_finalizes(self):
        def replay(txid):
            receipt = event_receipt(txid)
            receipt["id"] = "f"*64
            return receipt
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": RECIPIENT}):
            report = finality.evaluate(trc20_sample(), contract_body, replay)
        self.assertEqual(report["verified_match_count"], 0)

    def test_trc20_wrong_event_signature_never_finalizes(self):
        def bad_signature(txid):
            receipt = event_receipt(txid)
            receipt["log"][0]["topics"][0] = "f"*64
            return receipt
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": RECIPIENT}):
            report = finality.evaluate(trc20_sample(), contract_body, bad_signature)
        self.assertEqual(report["verified_match_count"], 0)

    def test_trc20_malformed_sender_encoding_never_finalizes(self):
        def bad_sender(txid):
            receipt = event_receipt(txid)
            receipt["log"][0]["topics"][1] = "f"*64
            return receipt
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": RECIPIENT}):
            report = finality.evaluate(trc20_sample(), contract_body, bad_sender)
        self.assertEqual(report["verified_match_count"], 0)

    def test_trc20_untrusted_allowlist_fails_closed(self):
        with patch.dict(os.environ, {"F41_SHASTA_TRC20_ALLOWLIST": "INVALID"}):
            report = finality.evaluate(trc20_sample(), contract_body, event_receipt)
        self.assertEqual(report["verified_match_count"], 0)
        self.assertTrue(all("CONFIG_INVALID" in x["status"] for x in report["records"]))

    def test_network_failure_is_never_finalized(self):
        def fail(txid):
            raise TimeoutError("offline")
        report = finality.evaluate(sample(), fail)
        self.assertEqual(report["verified_match_count"], 0)
        self.assertTrue(all(x["status"] == "SOLIDITY_NODE_UNAVAILABLE_OR_INVALID" for x in report["records"]))

    def test_duplicate_transaction_rejected_before_lookup(self):
        spec = sample()
        spec["data"]["observations"][1]["txid"] = spec["data"]["observations"][0]["txid"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            finality.evaluate(spec, lambda txid: response(txid))

    def test_unsupported_visible_format_rejected(self):
        def lookup(txid):
            result = response(txid)
            result["visible"] = True
            return result
        self.assertEqual(finality.evaluate(sample(), lookup)["verified_match_count"], 0)

    def test_restricts_network_host_and_no_broadcast_functions(self):
        self.assertEqual(finality.NODE, "https://api.shasta.trongrid.io/walletsolidity/gettransactionbyid")
        self.assertNotIn("broadcast", finality.solidity_lookup.__code__.co_names)
        self.assertNotIn("sign", finality.solidity_lookup.__code__.co_names)
        self.assertEqual(hashlib.sha256(finality.canonical({})).hexdigest(), finality.checksum(finality.canonical({})))


if __name__ == "__main__":
    unittest.main()
