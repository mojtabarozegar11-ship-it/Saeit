"""Authoritative Django DB tests, no TRX broadcast and no live charges."""
from datetime import datetime, timezone as utc, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from services.mojprop_commercial_lanes import LegalEvidence
from prop_firm.plan1_v141_native_checkout import (
    issue_private_foreign_invoice, confirm_native_trx_and_deliver,
    CheckoutRejected, RECEIVER, _addr_hex, _solidity_base_urls,
)
from prop_firm.plan1_v141_native_payment_models import (
    PropV141NativeOrder, PropV141NativeReceipt, PropGlobalTRXSettlement,
)
from prop_firm.plan1_v141_persistence_models import PropV141SimState
from prop_firm.plan1_v141_virtual_tenant_models import PropV141VirtualBook

TX_A = "a" * 64
TX_B = "b" * 64
PAYER = "41" + "a1" * 20
D = "c" * 64
VERSION = "2026-11-18/v1.5-commercial"

SETTINGS = dict(
    MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED=True,
    MOJPROP_V141_NATIVE_TERMS_VERSION=VERSION,
    MOJPROP_V141_NATIVE_TERMS_SHA256=D,
    MOJPROP_V141_TRON_RECEIVER=RECEIVER,
    MOJPROP_V141_TRON_SOLIDITY_PROVIDERS=(
        "https://api.trongrid.io", "https://tron-node.example.org"
    ),
)


@override_settings(**SETTINGS)
class RealNativePaymentStorageTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.operator = U.objects.create_user(
            username="mojprop_admin", email="op@example.org")
        self.operator.is_superuser = True
        self.operator.is_staff = True
        self.operator.save(update_fields=["is_superuser", "is_staff"])
        self.buyer = U.objects.create_user(
            username="foreign_customer_1", email="buyer@example.org")

    @staticmethod
    def legal_evidence(**changes):
        from dataclasses import replace
        evidence = LegalEvidence(
            merchant_owner_verified=True, merchant_residence_country="IR",
            buyer_residence_verified=True, buyer_residence_country="AE",
            customer_country_permitted=True,
            seller_cross_border_permission_verified=True,
            fee_based_independent_evaluation_approved=True,
            full_terms_accepted_and_verified=True,
            refunds_and_consumer_rights_cleared=True,
            authorized_receiving_account_verified=True,
            payment_method_legally_cleared=True,
            compliance_reference="EXTERNAL-REGULATOR-REFERENCE-001",
            seller_role="natural_person_independent_service",
            seller_role_verified=True,
            iran_foreign_trx_receipt_rights_verified=True,
            us_person_and_us_nexus_excluded=True,
            relevant_sanctions_screen_verified=True,
        )
        return replace(evidence, **changes)

    def invoice(self, **changes):
        data = dict(
            operator=self.operator, buyer=self.buyer, foreign_country="AE",
            payer_hex41=PAYER, wallet_owner_attestation_sha256=D,
            buyer_contract_acceptance_sha256=D,
            compliance_document_sha256=D,
            compliance_ref="EXTERNAL-REGULATOR-REFERENCE-001",
            terms_version=VERSION, terms_sha256=D,
            legal_evidence=self.legal_evidence(),
        )
        data.update(changes)
        return issue_private_foreign_invoice(**data)

    def proof(self, invoice, txid=TX_A, amount=30_000_000,
              receiver=None, sender=PAYER, result="SUCCESS", millis=None):
        if millis is None:
            millis = int((invoice.issued_at + timedelta(seconds=5)).timestamp() * 1000)
        body = {
            "txID": txid,
            "ret": [{"contractRet": result}],
            "raw_data": {
                "contract": [{
                    "type": "TransferContract",
                    "parameter": {"type_url": "type.googleapis.com/protocol.TransferContract",
                                  "value": {
                                      "owner_address": sender,
                                      "to_address": receiver or _addr_hex(invoice.recipient),
                                      "amount": amount,
                                  }},
                }],
            },
        }
        receipt = {"id": txid, "blockNumber": 12345,
                   "blockTimeStamp": millis,
                   "receipt": {"result": result}}
        return body, receipt

    @staticmethod
    def mock_sources(body, receipt):
        def node(base, path, txid):
            return body if path.endswith("/gettransactionbyid") else receipt
        return node

    def checked_confirm(self, i, txid, body, receipt):
        # Explicit synthetic clock: solidified block 5s AFTER issue and the
        # server verifier clock 10s after issue; never depend on CI timing.
        with patch("prop_firm.plan1_v141_native_checkout._query_solidified",
                   side_effect=self.mock_sources(body, receipt)), \
             patch("prop_firm.plan1_v141_native_checkout.timezone.now",
                   return_value=i.issued_at + timedelta(seconds=10)):
            return confirm_native_trx_and_deliver(reference=i.reference, txid=txid)

    def test_invoice_only_in_released_merchant(self):
        with override_settings(MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED=False):
            with self.assertRaises(CheckoutRejected):
                self.invoice()
        self.assertEqual(PropV141NativeOrder.objects.count(), 0)

    def test_no_iranian_or_us_buyer(self):
        for country in ("IR", "US", "ir", "USA", "", "1R"):
            with self.assertRaises(CheckoutRejected, msg=country):
                self.invoice(foreign_country=country)
        self.assertEqual(PropV141NativeOrder.objects.count(), 0)

    def test_no_invoice_without_verified_operator(self):
        self.operator.is_superuser = False
        with self.assertRaises(CheckoutRejected):
            self.invoice()
        self.assertEqual(PropV141NativeOrder.objects.count(), 0)

    def test_no_unpublished_terms_or_foreign_permission(self):
        for bad in (
            dict(legal_evidence=self.legal_evidence(iran_foreign_trx_receipt_rights_verified=False)),
            dict(legal_evidence=self.legal_evidence(seller_role="licensed_crypto_broker")),
            dict(legal_evidence=self.legal_evidence(relevant_sanctions_screen_verified=False)),
            dict(terms_version=VERSION + "-DRAFT"),
            dict(terms_sha256="0" * 64),
            dict(wallet_owner_attestation_sha256="bad"),
            dict(buyer_contract_acceptance_sha256="0" * 64),
            dict(compliance_document_sha256="x" * 64),
            dict(payer_hex41="41" + "a" * 37),
        ):
            with self.assertRaises(CheckoutRejected, msg=str(bad)):
                self.invoice(**bad)
        self.assertEqual(PropV141NativeOrder.objects.count(), 0)

    def test_customer_country_bound_to_verified_evidence(self):
        with self.assertRaises(CheckoutRejected):
            self.invoice(foreign_country="GB", legal_evidence=self.legal_evidence())
        self.assertEqual(PropV141NativeOrder.objects.count(), 0)

    def test_type2_crypto_broker_cannot_accept_native_payment(self):
        with self.assertRaises(CheckoutRejected):
            self.invoice(legal_evidence=self.legal_evidence(
                seller_role="licensed_crypto_broker"))
        self.assertEqual(PropV141NativeOrder.objects.count(), 0)

    def test_invoice_fields_persist_exact_fee_wallet_legal_terms(self):
        i = self.invoice()
        i.refresh_from_db()
        self.assertEqual(i.amount_sun, 30_000_000)
        self.assertEqual(i.recipient, RECEIVER)
        self.assertEqual(i.terms_sha256, D)
        self.assertEqual(i.payer_wallet_attestation_sha256, D)
        self.assertEqual(i.status, "issued")
        self.assertFalse(hasattr(i, "native_receipt"))

    def test_real_finality_creates_one_paid_book(self):
        i = self.invoice()
        body, receipt = self.proof(i)
        r = self.checked_confirm(i, TX_A, body, receipt)
        i.refresh_from_db()
        self.assertEqual(i.status, "settled")
        self.assertEqual(PropGlobalTRXSettlement.objects.count(), 1)
        self.assertEqual(PropV141NativeReceipt.objects.count(), 1)
        self.assertEqual(PropV141SimState.objects.count(), 1)
        self.assertEqual(PropV141VirtualBook.objects.count(), 1)
        self.assertEqual(r.order_id, i.pk)
        self.assertEqual(r.book.owner_id, self.buyer.pk)
        self.assertEqual(r.book.max_unlocked_stage, 1)
        self.assertEqual(r.state.challenge_ref, i.reference)

    def test_duplicate_same_order_is_idempotent(self):
        i = self.invoice()
        body, receipt = self.proof(i)
        r1 = self.checked_confirm(i, TX_A, body, receipt)
        r2 = confirm_native_trx_and_deliver(reference=i.reference, txid=TX_A)
        self.assertEqual(r1.pk, r2.pk)
        self.assertEqual(PropV141NativeReceipt.objects.count(), 1)
        self.assertEqual(PropGlobalTRXSettlement.objects.count(), 1)

    def test_invoice_cannot_use_second_txid(self):
        i = self.invoice()
        body, receipt = self.proof(i)
        self.checked_confirm(i, TX_A, body, receipt)
        with self.assertRaises(CheckoutRejected):
            confirm_native_trx_and_deliver(reference=i.reference, txid=TX_B)

    def test_cross_order_txid_replay_is_denied(self):
        i1 = self.invoice()
        i2 = self.invoice()
        body, receipt = self.proof(i1)
        self.checked_confirm(i1, TX_A, body, receipt)
        with patch("prop_firm.plan1_v141_native_checkout._query_solidified",
                   side_effect=self.mock_sources(body, receipt)), \
             patch("prop_firm.plan1_v141_native_checkout.timezone.now",
                   return_value=i2.issued_at + timedelta(seconds=10)):
            with self.assertRaises(CheckoutRejected):
                confirm_native_trx_and_deliver(reference=i2.reference, txid=TX_A)
        self.assertEqual(PropGlobalTRXSettlement.objects.count(), 1)
        self.assertEqual(PropV141VirtualBook.objects.count(), 1)

    def test_wrong_native_amount_denied_without_book(self):
        i = self.invoice()
        body, receipt = self.proof(i, amount=29_999_999)
        with patch("prop_firm.plan1_v141_native_checkout._query_solidified",
                   side_effect=self.mock_sources(body, receipt)):
            with self.assertRaises(CheckoutRejected):
                confirm_native_trx_and_deliver(reference=i.reference, txid=TX_A)
        self.assertEqual(PropGlobalTRXSettlement.objects.count(), 0)

    def test_wrong_recipient_denied_without_book(self):
        i = self.invoice()
        body, receipt = self.proof(i, receiver="41" + "ff" * 20)
        with patch("prop_firm.plan1_v141_native_checkout._query_solidified",
                   side_effect=self.mock_sources(body, receipt)):
            with self.assertRaises(CheckoutRejected):
                confirm_native_trx_and_deliver(reference=i.reference, txid=TX_A)
        self.assertEqual(PropV141VirtualBook.objects.count(), 0)

    def test_other_payer_denied_without_book(self):
        i = self.invoice()
        body, receipt = self.proof(i, sender="41" + "ef" * 20)
        with patch("prop_firm.plan1_v141_native_checkout._query_solidified",
                   side_effect=self.mock_sources(body, receipt)):
            with self.assertRaises(CheckoutRejected):
                confirm_native_trx_and_deliver(reference=i.reference, txid=TX_A)
        self.assertEqual(PropV141NativeReceipt.objects.count(), 0)

    def test_failed_receipt_denied_without_book(self):
        i = self.invoice()
        body, receipt = self.proof(i, result="FAILED")
        with patch("prop_firm.plan1_v141_native_checkout._query_solidified",
                   side_effect=self.mock_sources(body, receipt)):
            with self.assertRaises(CheckoutRejected):
                confirm_native_trx_and_deliver(reference=i.reference, txid=TX_A)

    def test_disagreeing_providers_denied(self):
        i = self.invoice()
        body, receipt = self.proof(i)
        bad_receipt = dict(receipt, blockNumber=receipt["blockNumber"] + 1)
        calls = [body, receipt, body, bad_receipt]
        with patch("prop_firm.plan1_v141_native_checkout._query_solidified",
                   side_effect=calls), \
             patch("prop_firm.plan1_v141_native_checkout.timezone.now",
                   return_value=i.issued_at + timedelta(seconds=10)):
            with self.assertRaises(CheckoutRejected):
                confirm_native_trx_and_deliver(reference=i.reference, txid=TX_A)
        self.assertEqual(PropGlobalTRXSettlement.objects.count(), 0)

    def test_pre_invoice_flag_revocation_disables_confirmation(self):
        i = self.invoice()
        with override_settings(MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED=False):
            with self.assertRaises(CheckoutRejected):
                confirm_native_trx_and_deliver(reference=i.reference, txid=TX_A)

    def test_invalid_or_duplicate_rpc_providers_denied(self):
        for sources in (
            (), ("https://api.trongrid.io",), ("https://a.com", "https://a.com"),
            ("http://a.com", "https://b.com"),
            ("https://a.com:8080", "https://b.com"),
            ("https://a.com/path", "https://b.com"),
        ):
            with override_settings(MOJPROP_V141_TRON_SOLIDITY_PROVIDERS=sources):
                with self.assertRaises(CheckoutRejected):
                    _solidity_base_urls()
