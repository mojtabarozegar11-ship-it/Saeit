"""MOJ-PROP-01 future solidified TRX proof; no actual sale or funded grant."""
from __future__ import annotations
from dataclasses import replace
import copy
from types import MappingProxyType
import unittest

from services.mojprop_real_plan1_tron_candidate import (
    Plan1PersistedInvoice, NativeTRXMatchRejected,
    NATIVE_AMOUNT_SUN, PRODUCT, _hex_recipient,
    assess_solidified_native_transfer, validate_persisted_order
)

OWNER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
PAYER = "411111111111111111111111111111111111111111"
TXID = "a" * 64
START = 1_790_000_000
END = START + 3600


class RealPlan1TRXContractTests(unittest.TestCase):
    def setUp(self):
        self.invoice = Plan1PersistedInvoice(
            product=PRODUCT, order_ref="MOJPROP01-ABCDEF123456",
            merchant_domain="mojplaywin.com", merchant_id="mojplaywin-store",
            network="tron-mainnet", recipient=OWNER, amount_sun=NATIVE_AMOUNT_SUN,
            issued_at_sec=START, expires_at_sec=END,
            buyer_terms_acceptance="terms-accepted-12452",
            contract_version="2026-11-15/v1.2",
            precontract_sha256="a" * 64,
            payer_hex41=PAYER,
        )
        self.body = {
            "txID": TXID,
            "raw_data": {"contract": [{"type": "TransferContract", "parameter": {
                "type_url": "type.googleapis.com/protocol.TransferContract",
                "value": {"owner_address": PAYER,
                          "to_address": _hex_recipient(OWNER),
                          "amount": NATIVE_AMOUNT_SUN}}}]},
            "ret": [{"contractRet": "SUCCESS"}]
        }
        self.receipt = {
            "id": TXID, "blockNumber": 5000,
            "blockTimeStamp": (START + 600) * 1000,
            "receipt": {"result": "SUCCESS"}
        }

    def match(self, **kwargs):
        data = dict(
            txid=TXID, solidity_transaction=self.body,
            solidity_receipt=self.receipt,
            body_endpoint="/walletsolidity/gettransactionbyid",
            receipt_endpoint="/walletsolidity/gettransactioninfobyid",
            trusted_node_network="tron-mainnet",
            already_assigned_txids=frozenset())
        data.update(kwargs)
        return assess_solidified_native_transfer(self.invoice, **data)

    def test_valid_pair_is_candidate_not_a_revenue_receipt(self):
        result = self.match()
        self.assertTrue(result["candidate_matches_persisted_order"])
        self.assertFalse(result["buyer_entitlement_granted"])
        self.assertFalse(result["revenue_booked"])
        self.assertTrue(result["requires_atomic_unique_ledger_assignment"])

    def test_real_funded_sku_not_educational_product(self):
        self.assertEqual(PRODUCT, "MOJ-PROP-01")
        self.assertNotEqual(PRODUCT, "MOJPROP-STARTER30")
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, product="MOJPROP-STARTER30"))

    def test_legacy_educational_order_reference_is_not_funded_order(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice,
                                              order_ref="MOJPROP30-ABCDEF123456"))

    def test_matching_proof_is_only_a_plan1_candidate(self):
        response = self.match()
        self.assertEqual(response["schema"], "mojprop.plan1.tron.match.v1")
        self.assertEqual(response["product"], "MOJ-PROP-01")
        self.assertEqual(response["contract_version"], "2026-11-15/v1.2")
        self.assertEqual(response["precontract_sha256"], "a" * 64)
        self.assertFalse(response["buyer_entitlement_granted"])
        self.assertFalse(response["revenue_booked"])
        self.assertFalse(response["merchant_legal_release_proven_by_this_module"])

    def test_wrong_contract_version_is_denied(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice,
                                              contract_version="2026-11-14/v1.1"))

    def test_missing_contract_version_denied(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, contract_version=""))

    def test_wrong_type_contract_version_denied(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, contract_version=120))

    def test_missing_bilingual_precontract_fingerprint_denied(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, precontract_sha256=""))

    def test_zero_bilingual_precontract_fingerprint_denied(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, precontract_sha256="0" * 64))

    def test_bad_bilingual_precontract_fingerprint_denied(self):
        for value in ("a" * 63, "A" * 64, "not-a-digest", None, True):
            with self.subTest(value=value):
                with self.assertRaises(NativeTRXMatchRejected):
                    validate_persisted_order(replace(self.invoice, precontract_sha256=value))

    def test_merchant_registry_cannot_substitute_brand(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice,
                                              merchant_id="zomorodmelal"))

    def test_invoice_before_valid_start_epoch_denied(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice,
                                              issued_at_sec=1499999999))

    def test_global_duplicate_txid_across_any_sku_denied(self):
        # Global txid inventory must encompass educational and all other
        # products, rather than a separate product-specific paid ledger.
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(already_assigned_txids=frozenset({TXID}))

    def test_own_wallet_base58check_decodes_to_41_hex(self):
        decoded = _hex_recipient(OWNER)
        self.assertEqual(len(decoded), 42)
        self.assertTrue(decoded.startswith("41"))

    def test_quote_exact_native_30_trx_sun(self):
        self.assertEqual(NATIVE_AMOUNT_SUN, 30_000_000)

    def test_different_product_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, product="MOJPROP-100"))

    def test_usd_instead_of_native_trx_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, amount_sun=149))

    def test_30_trx_as_float_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, amount_sun=30e6))

    def test_true_boolean_amount_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, amount_sun=True))

    def test_cross_host_www_not_implicitly_enabled(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, merchant_domain="www.mojplaywin.com"))

    def test_merchant_id_mismatch_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, merchant_id="mojprop"))

    def test_tron_testnet_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, network="shasta"))

    def test_missing_unique_order_ref_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, order_ref=""))

    def test_untrusted_order_ref_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, order_ref="MOJPROP01-../../secrets"))

    def test_missing_buyer_acceptance_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, buyer_terms_acceptance=""))

    def test_invalid_receiver_checksum_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, recipient=OWNER[:-1] + "Z"))

    def test_invoice_expiry_before_issue_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, expires_at_sec=START-1))

    def test_invoice_more_than_day_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, expires_at_sec=START+86401))

    def test_pre_registered_payer_malformed_rejected(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(self.invoice, payer_hex41="bad"))

    def test_absent_payer_not_enough_for_customer_attribution(self):
        self.invoice = replace(self.invoice, payer_hex41=None)
        with self.assertRaisesRegex(NativeTRXMatchRejected, "payer ownership"):
            self.match()

    def test_mismatched_registered_payer_rejected(self):
        self.invoice = replace(self.invoice, payer_hex41="412222222222222222222222222222222222222222")
        with self.assertRaises(NativeTRXMatchRejected):
            self.match()

    def test_empty_fullnode_latest_head_not_solidified(self):
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_transaction={})

    def test_broadcast_success_not_proof(self):
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_transaction={"result": True,"txid":TXID})

    def test_wrong_body_endpoint_refused(self):
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(body_endpoint="/wallet/gettransactionbyid")

    def test_wrong_receipt_endpoint_refused(self):
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(receipt_endpoint="/wallet/gettransactioninfobyid")

    def test_node_claimed_testnet_refused(self):
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(trusted_node_network="tron-shasta")

    def test_replayed_txid_refused(self):
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(already_assigned_txids=frozenset({TXID}))

    def test_wrong_replay_collection_type_refused(self):
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(already_assigned_txids=set())

    def test_mismatched_txid_body_rejected(self):
        other = copy.deepcopy(self.body)
        other["txID"] = "b" * 64
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_transaction=other)

    def test_mismatched_receipt_txid_rejected(self):
        other = copy.deepcopy(self.receipt)
        other["id"] = "b" * 64
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_receipt=other)

    def test_failed_contract_ret_refused(self):
        other = copy.deepcopy(self.body)
        other["ret"][0]["contractRet"] = "FAILED"
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_transaction=other)

    def test_trc20_smart_contract_refused(self):
        other = copy.deepcopy(self.body)
        other["raw_data"]["contract"][0]["type"] = "TriggerSmartContract"
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_transaction=other)

    def test_multiple_contracts_refused(self):
        other = copy.deepcopy(self.body)
        other["raw_data"]["contract"].append(copy.deepcopy(other["raw_data"]["contract"][0]))
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_transaction=other)

    def test_wrong_recipient_refused(self):
        other = copy.deepcopy(self.body)
        other["raw_data"]["contract"][0]["parameter"]["value"]["to_address"] = "412222222222222222222222222222222222222222"
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_transaction=other)

    def test_wrong_sun_amount_refused(self):
        other = copy.deepcopy(self.body)
        other["raw_data"]["contract"][0]["parameter"]["value"]["amount"] -= 1
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_transaction=other)

    def test_overpaid_different_amount_requires_review(self):
        other = copy.deepcopy(self.body)
        other["raw_data"]["contract"][0]["parameter"]["value"]["amount"] += 1
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_transaction=other)

    def test_bad_amount_bool_refused(self):
        other = copy.deepcopy(self.body)
        other["raw_data"]["contract"][0]["parameter"]["value"]["amount"] = True
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_transaction=other)

    def test_self_transfer_refused(self):
        other = copy.deepcopy(self.body)
        other["raw_data"]["contract"][0]["parameter"]["value"]["owner_address"] = _hex_recipient(OWNER)
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_transaction=other)

    def test_missing_receipt_refused(self):
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_receipt={})

    def test_smart_contract_failed_receipt_refused(self):
        other = copy.deepcopy(self.receipt)
        other["receipt"]["result"] = "REVERT"
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_receipt=other)

    def test_failed_top_level_receipt_refused(self):
        other = copy.deepcopy(self.receipt)
        other["result"] = "FAILED"
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_receipt=other)

    def test_unrecognized_top_level_receipt_outcome_refused(self):
        for outcome in ("REVERT", "OUT_OF_ENERGY", "PENDING", "ERROR", "", True, 1):
            with self.subTest(outcome=outcome):
                other = copy.deepcopy(self.receipt)
                other["result"] = outcome
                with self.assertRaises(NativeTRXMatchRejected):
                    self.match(solidity_receipt=other)

    def test_pre_invoice_block_timestamp_refused(self):
        other = copy.deepcopy(self.receipt)
        other["blockTimeStamp"] = (START-1) * 1000
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_receipt=other)

    def test_expired_payment_time_refused(self):
        other = copy.deepcopy(self.receipt)
        other["blockTimeStamp"] = END * 1000
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_receipt=other)

    def test_no_block_number_refused(self):
        other = copy.deepcopy(self.receipt)
        other["blockNumber"] = None
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_receipt=other)

    def test_node_error_refused_even_with_good_body(self):
        other = copy.deepcopy(self.receipt)
        other["Error"] = "rate limit"
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(solidity_receipt=other)

    def test_txid_canonical_lowercase_enforced(self):
        with self.assertRaises(NativeTRXMatchRejected):
            self.match(txid=TXID.upper())

    def test_source_cannot_send_or_book_a_sale(self):
        report = self.match()
        self.assertFalse(report["receipt_sent"])
        self.assertFalse(report["revenue_booked"])
        self.assertFalse(report["node_authentication_proven_by_this_module"])
        self.assertFalse(report["merchant_legal_release_proven_by_this_module"])

    def test_matching_two_proofs_never_mutate_inputs(self):
        before_body = copy.deepcopy(self.body)
        before_receipt = copy.deepcopy(self.receipt)
        self.match()
        self.assertEqual(before_body, self.body)
        self.assertEqual(before_receipt, self.receipt)


if __name__ == "__main__":
    unittest.main()
