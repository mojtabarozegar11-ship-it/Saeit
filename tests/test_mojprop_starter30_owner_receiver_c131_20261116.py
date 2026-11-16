"""No-charge, offline regression: reject a valid stranger TRON receiver.

This checks pure persisted invoice matching only. Does NOT create invoices,
query blockchain nodes, broadcast funds, grant access or book revenue.
"""
from dataclasses import replace
from unittest.mock import patch
import copy
import unittest

from services.mojprop_starter30_tron_settlement import (
    Starter30PersistedInvoice, NativeTRXMatchRejected, PRODUCT,
    MERCHANT_DOMAIN, MERCHANT_ID, NETWORK, NATIVE_AMOUNT_SUN,
    validate_persisted_order, assess_solidified_native_transfer, _hex_recipient,
)
from services.mpw_trx_merchant_binding import validate_tron_recipient
from services.mojtaba_tron_owner_receiver import approved_recipient

# Generated from a fixed synthetic 0x41 + 0x22*20 test payload. No private key.
OTHER_CHECKSUMMED = "TD5gsCwxykWsLN9aPrq2TAfNjByuZKYp4E"
BUYER = "411111111111111111111111111111111111111111"
TX = "a" * 64


def invoice():
    return Starter30PersistedInvoice(
        product=PRODUCT,
        order_ref="MOJPROP30-ABCDEF123456",
        merchant_domain=MERCHANT_DOMAIN,
        merchant_id=MERCHANT_ID,
        network=NETWORK,
        recipient=approved_recipient(),
        amount_sun=NATIVE_AMOUNT_SUN,
        issued_at_sec=1_790_000_000,
        expires_at_sec=1_790_003_600,
        buyer_terms_acceptance="terms-consented-12345",
        payer_hex41=BUYER,
    )


def proofs(order):
    return (
        {
            "txID": TX,
            "raw_data": {
                "contract": [{
                    "type": "TransferContract",
                    "parameter": {
                        "type_url": "type.googleapis.com/protocol.TransferContract",
                        "value": {
                            "owner_address": BUYER,
                            "to_address": _hex_recipient(order.recipient),
                            "amount": NATIVE_AMOUNT_SUN,
                        },
                    },
                }],
            },
            "ret": [{"contractRet": "SUCCESS"}],
        },
        {
            "id": TX,
            "blockNumber": 5000,
            "blockTimeStamp": 1_790_000_600_000,
            "receipt": {"result": "SUCCESS"},
        },
    )


def match(order, transaction, receipt):
    return assess_solidified_native_transfer(
        order,
        txid=TX,
        solidity_transaction=transaction,
        solidity_receipt=receipt,
        body_endpoint="/walletsolidity/gettransactionbyid",
        receipt_endpoint="/walletsolidity/gettransactioninfobyid",
        trusted_node_network=NETWORK,
        already_assigned_txids=frozenset(),
    )


class OwnerRecipientBoundSettlementTests(unittest.TestCase):
    def test_owner_recipient_is_checksumming_and_approved(self):
        self.assertEqual(validate_tron_recipient(approved_recipient()),
                         approved_recipient())
        validate_persisted_order(invoice())

    def test_valid_other_address_is_not_a_valid_owner_invoice(self):
        self.assertEqual(validate_tron_recipient(OTHER_CHECKSUMMED),
                         OTHER_CHECKSUMMED)
        self.assertNotEqual(OTHER_CHECKSUMMED, approved_recipient())
        with self.assertRaisesRegex(NativeTRXMatchRejected, "unauthorized"):
            validate_persisted_order(replace(
                invoice(), recipient=OTHER_CHECKSUMMED))

    def test_other_recipient_cannot_be_charged_even_when_chain_matches(self):
        alien = replace(invoice(), recipient=OTHER_CHECKSUMMED)
        tx, receipt = proofs(alien)
        with self.assertRaises(NativeTRXMatchRejected):
            match(alien, tx, receipt)

    def test_owner_wallet_registry_absent_fails_closed(self):
        with patch("services.mojprop_starter30_tron_settlement.approved_recipient",
                   side_effect=ValueError("invalid wallet registry")):
            with self.assertRaises(NativeTRXMatchRejected):
                validate_persisted_order(invoice())

    def test_owner_wallet_registry_changed_does_not_retarget_saved_invoice(self):
        old_invoice = invoice()
        with patch("services.mojprop_starter30_tron_settlement.approved_recipient",
                   return_value=OTHER_CHECKSUMMED):
            with self.assertRaises(NativeTRXMatchRejected):
                validate_persisted_order(old_invoice)

    def test_valid_proof_only_candidate_no_paid_order_or_receipt(self):
        order = invoice()
        tx, receipt = proofs(order)
        result = match(order, tx, receipt)
        self.assertTrue(result["candidate_matches_persisted_order"])
        self.assertFalse(result["buyer_entitlement_granted"])
        self.assertFalse(result["receipt_sent"])
        self.assertFalse(result["revenue_booked"])
        self.assertTrue(result["requires_atomic_unique_ledger_assignment"])

    def test_empty_error_field_in_transaction_is_failure(self):
        order = invoice()
        original, receipt = proofs(order)
        for value in ("", None, 0, False, [], {}):
            with self.subTest(error_type=type(value).__name__):
                tx = copy.deepcopy(original)
                tx["Error"] = value
                with self.assertRaisesRegex(NativeTRXMatchRejected, "node returned an error"):
                    match(order, tx, receipt)

    def test_empty_error_field_in_solidified_receipt_is_failure(self):
        order = invoice()
        tx, original = proofs(order)
        for value in ("", None, 0, False, [], {}):
            with self.subTest(error_type=type(value).__name__):
                receipt = copy.deepcopy(original)
                receipt["Error"] = value
                with self.assertRaisesRegex(NativeTRXMatchRejected, "node returned an error"):
                    match(order, tx, receipt)

    def test_missing_node_observations_never_become_success(self):
        order = invoice()
        tx, receipt = proofs(order)
        with self.assertRaises(NativeTRXMatchRejected):
            match(order, {}, receipt)
        with self.assertRaises(NativeTRXMatchRejected):
            match(order, tx, {})

    def test_chain_payer_is_not_authenticated_by_merchant_address_only(self):
        order = replace(invoice(), payer_hex41=None)
        tx, receipt = proofs(order)
        with self.assertRaisesRegex(NativeTRXMatchRejected, "payer ownership"):
            match(order, tx, receipt)

    def test_merchant_domain_subsite_never_implicit_owner_binding(self):
        with self.assertRaises(NativeTRXMatchRejected):
            validate_persisted_order(replace(
                invoice(), merchant_domain="www.mojplaywin.com"))

    def test_candidate_does_not_mutate_verified_node_data(self):
        order = invoice()
        tx, receipt = proofs(order)
        t_before, r_before = copy.deepcopy(tx), copy.deepcopy(receipt)
        match(order, tx, receipt)
        self.assertEqual(tx, t_before)
        self.assertEqual(receipt, r_before)


if __name__ == "__main__":
    unittest.main()
