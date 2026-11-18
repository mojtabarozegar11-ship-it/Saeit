"""Authoritative Django DB tests, no TRX broadcast and no live charges."""
from datetime import datetime, timezone as utc, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO
from django.test import TestCase, override_settings
from django.utils import timezone

from services.mojprop_commercial_lanes import LegalEvidence
from prop_firm.plan1_v141_native_checkout import (
    issue_private_foreign_invoice, confirm_native_trx_and_deliver,
    CheckoutRejected, RECEIVER, _addr_hex, _solidity_base_urls,
)
from prop_firm.plan1_v141_native_watcher import reconcile_pending_invoices, _candidates
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
    MOJPROP_TRX_GLOBAL_LEDGER_RECONCILED=True,
    MOJPROP_V141_NATIVE_TERMS_VERSION=VERSION,
    MOJPROP_V141_NATIVE_TERMS_SHA256=D,
    MOJPROP_V141_TRON_RECEIVER=RECEIVER,
    MOJPROP_V141_ORDER_SIGNING_KEY="CI-only-local-test-key-" + "7" * 48,
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
            seller_cross_border_lawful_basis_reviewed=True,
            fee_based_independent_evaluation_approved=True,
            full_terms_accepted_and_verified=True,
            refunds_and_consumer_rights_cleared=True,
            authorized_receiving_account_verified=True,
            payment_method_legally_cleared=True,
            compliance_reference="EXTERNAL-REGULATOR-REFERENCE-001",
            seller_role="natural_person_independent_service",
            seller_role_verified=True,
            iran_foreign_trx_settlement_lawfulness_reviewed=True,
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

    @override_settings(ROOT_URLCONF="mojprop_isolated.urls",
                       MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED=True,
                       MOJ_PROP_V141_PORTFOLIO_ENABLED=True)
    def test_buyer_dashboard_scope_and_payment_pause(self):
        from django.test import Client
        other = get_user_model().objects.create_user(username="other-buyer")
        mine = self.invoice()
        theirs = self.invoice(buyer=other)
        c = Client(HTTP_HOST="mojplaywin.com")
        c.force_login(self.buyer)
        path = "/moj-prop-v141/"
        response = c.get(path, secure=True)
        self.assertContains(response, mine.reference)
        self.assertNotContains(response, theirs.reference)
        self.assertNotContains(response, mine.recipient)
        self.assertContains(response, "Invoice available")
        with override_settings(MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED=False):
            self.assertContains(c.get(path, secure=True), "Payment paused")
        body, receipt = self.proof(mine)
        self.checked_confirm(mine, TX_A, body, receipt)
        response = c.get(path, secure=True)
        self.assertContains(response, "Payment confirmed")
        self.assertContains(response, "/moj-prop-v141/statement/" + mine.reference + "/")
        self.assertNotContains(response, theirs.reference)
        self.assertNotContains(response, TX_A)
        with override_settings(MOJ_PROP_V141_PORTFOLIO_ENABLED=False):
            self.assertNotContains(c.get(path, secure=True), "/moj-prop-v141/statement/")
        c.force_login(other)
        response = c.get(path, secure=True)
        self.assertNotContains(response, mine.reference)
        self.assertContains(response, theirs.reference)

    def test_invoice_only_in_released_merchant(self):
        with override_settings(MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED=False):
            with self.assertRaises(CheckoutRejected):
                self.invoice()
        self.assertEqual(PropV141NativeOrder.objects.count(), 0)

    def test_missing_legacy_global_replay_reconciliation_blocks_invoice(self):
        with override_settings(MOJPROP_TRX_GLOBAL_LEDGER_RECONCILED=False):
            with self.assertRaises(CheckoutRejected):
                self.invoice()
        self.assertEqual(PropV141NativeOrder.objects.count(), 0)

    def test_missing_secret_disallows_invoice(self):
        with override_settings(MOJPROP_V141_ORDER_SIGNING_KEY="weak"):
            with self.assertRaises(CheckoutRejected):
                self.invoice()
        self.assertEqual(PropV141NativeOrder.objects.count(), 0)

    def test_modified_signed_invoice_rejected_before_receipt(self):
        i = self.invoice()
        # Simulates illegal direct ORM mutation rather than service issuance.
        PropV141NativeOrder.objects.filter(pk=i.pk).update(
            payer_hex41="41" + "b1" * 20)
        with self.assertRaises(CheckoutRejected):
            confirm_native_trx_and_deliver(reference=i.reference, txid=TX_A)
        self.assertEqual(PropGlobalTRXSettlement.objects.count(), 0)
        self.assertEqual(PropV141VirtualBook.objects.count(), 0)

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
            dict(legal_evidence=self.legal_evidence(iran_foreign_trx_settlement_lawfulness_reviewed=False)),
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
        self.assertEqual(len(i.order_hmac_sha256), 64)
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

    def indexed_transfer(self, order, txid=TX_A, **changes):
        body, receipt = self.proof(order, txid=txid)
        row = dict(body, block_timestamp=receipt["blockTimeStamp"])
        if "amount" in changes:
            row["raw_data"]["contract"][0]["parameter"]["value"]["amount"] = changes["amount"]
        if "recipient" in changes:
            row["raw_data"]["contract"][0]["parameter"]["value"]["to_address"] = changes["recipient"]
        return row

    def test_watcher_discovers_and_delivers_with_two_solidified_nodes(self):
        i = self.invoice()
        body, receipt = self.proof(i)
        row = dict(body, block_timestamp=receipt["blockTimeStamp"])
        with patch("prop_firm.plan1_v141_native_watcher._indexer_configuration",
                   return_value=("https://api.trongrid.io", "")), \
             patch("prop_firm.plan1_v141_native_watcher._get_page",
                   return_value=([row], {})), \
             patch("prop_firm.plan1_v141_native_checkout._query_solidified",
                   side_effect=self.mock_sources(body, receipt)), \
             patch("prop_firm.plan1_v141_native_checkout.timezone.now",
                   return_value=i.issued_at + timedelta(seconds=10)):
            result = reconcile_pending_invoices()
        self.assertEqual(result["settled"], 1)
        self.assertEqual(result["pending"], 0)
        self.assertEqual(PropV141NativeReceipt.objects.count(), 1)
        self.assertEqual(PropV141VirtualBook.objects.get().owner_id, self.buyer.pk)

    def test_watcher_bad_duplicate_cannot_hide_valid_indexer_candidate(self):
        """Malformed account-index records never suppress later valid TXID."""
        i = self.invoice()
        row = self.indexed_transfer(i)
        invalid_shape = dict(row, raw_data=[])
        invalid_amount = self.indexed_transfer(i, amount=29_999_999)
        with patch("prop_firm.plan1_v141_native_watcher._indexer_configuration",
                   return_value=("https://api.trongrid.io", "")), \
             patch("prop_firm.plan1_v141_native_watcher._get_page",
                   return_value=([invalid_shape, invalid_amount, row], {})):
            result = reconcile_pending_invoices(dry_run=True)
        self.assertEqual(result["candidate_txids"], 1)
        self.assertEqual(result["settled"], 0)
        self.assertEqual(PropGlobalTRXSettlement.objects.count(), 0)

    def test_watcher_dry_run_is_nonpayable(self):
        i = self.invoice()
        body, receipt = self.proof(i)
        row = dict(body, block_timestamp=receipt["blockTimeStamp"])
        with patch("prop_firm.plan1_v141_native_watcher._indexer_configuration",
                   return_value=("https://api.trongrid.io", "")), \
             patch("prop_firm.plan1_v141_native_watcher._get_page",
                   return_value=([row], {})), \
             patch("prop_firm.plan1_v141_native_checkout._query_solidified") as verify:
            result = reconcile_pending_invoices(dry_run=True)
        self.assertEqual(result["candidate_txids"], 1)
        self.assertEqual(result["settled"], 0)
        self.assertEqual(result["pending"], 1)
        verify.assert_not_called()
        self.assertEqual(PropGlobalTRXSettlement.objects.count(), 0)

    def test_watcher_ambiguous_invoice_from_same_wallet_never_credits(self):
        i1 = self.invoice()
        i2 = self.invoice()
        row = self.indexed_transfer(i1)
        with patch("prop_firm.plan1_v141_native_watcher._indexer_configuration",
                   return_value=("https://api.trongrid.io", "")), \
             patch("prop_firm.plan1_v141_native_watcher._get_page",
                   return_value=([row], {})):
            result = reconcile_pending_invoices()
        self.assertEqual(result["ambiguous"], 1)
        self.assertEqual(result["settled"], 0)
        self.assertEqual(PropV141NativeReceipt.objects.count(), 0)

    def test_watcher_wrong_recipient_never_credits(self):
        i = self.invoice()
        row = self.indexed_transfer(i, recipient="41" + "b0" * 20)
        with patch("prop_firm.plan1_v141_native_watcher._indexer_configuration",
                   return_value=("https://api.trongrid.io", "")), \
             patch("prop_firm.plan1_v141_native_watcher._get_page",
                   return_value=([row], {})):
            result = reconcile_pending_invoices()
        self.assertEqual(result["candidate_txids"], 0)
        self.assertEqual(PropGlobalTRXSettlement.objects.count(), 0)

    def test_watcher_wrong_native_trx_amount_never_credits(self):
        i = self.invoice()
        row = self.indexed_transfer(i, amount=30_000_001)
        with patch("prop_firm.plan1_v141_native_watcher._indexer_configuration",
                   return_value=("https://api.trongrid.io", "")), \
             patch("prop_firm.plan1_v141_native_watcher._get_page",
                   return_value=([row], {})):
            result = reconcile_pending_invoices()
        self.assertEqual(result["settled"], 0)

    def test_watcher_missing_full_page_cursor_fails_closed(self):
        i = self.invoice()
        row = self.indexed_transfer(i)
        with patch("prop_firm.plan1_v141_native_watcher.PAGE_LIMIT", 1), \
             patch("prop_firm.plan1_v141_native_watcher._indexer_configuration",
                   return_value=("https://api.trongrid.io", "")), \
             patch("prop_firm.plan1_v141_native_watcher._get_page",
                   return_value=([row], {})):
            with self.assertRaises(CheckoutRejected):
                reconcile_pending_invoices()
        self.assertEqual(PropV141NativeReceipt.objects.count(), 0)

    def test_watcher_repeated_cursor_fails_closed(self):
        i = self.invoice()
        row = self.indexed_transfer(i)
        with patch("prop_firm.plan1_v141_native_watcher.PAGE_LIMIT", 1), \
             patch("prop_firm.plan1_v141_native_watcher._indexer_configuration",
                   return_value=("https://api.trongrid.io", "")), \
             patch("prop_firm.plan1_v141_native_watcher._get_page",
                   return_value=([row], {"fingerprint": "abcabcabcabc"})):
            with self.assertRaises(CheckoutRejected):
                reconcile_pending_invoices()
        self.assertEqual(PropV141NativeReceipt.objects.count(), 0)

    def test_watcher_release_off_never_queries_indexer(self):
        self.invoice()
        with override_settings(MOJPROP_TRX_GLOBAL_LEDGER_RECONCILED=False), \
             patch("prop_firm.plan1_v141_native_watcher._get_page") as network:
            with self.assertRaises(CheckoutRejected):
                reconcile_pending_invoices()
        network.assert_not_called()

    @override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "testserver"])
    def test_private_invoice_only_current_authenticated_buyer(self):
        i = self.invoice()
        page = "/moj-prop-v141/payment/" + i.reference + "/"
        self.client.force_login(self.buyer)
        response = self.client.get(page, secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "30.000000 TRX")
        self.assertContains(response, RECEIVER)
        self.assertContains(response, i.reference)
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertIn("private", response.headers["Cache-Control"])
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("max-age=0", response.headers["Cache-Control"])
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(page, secure=True,
                                        HTTP_HOST="mojplaywin.com").status_code, 404)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(page, secure=False,
                                        HTTP_HOST="mojplaywin.com").status_code, 404)
        self.assertEqual(self.client.get(page + "?token=secret", secure=True,
                                        HTTP_HOST="mojplaywin.com").status_code, 404)
        self.assertEqual(self.client.post(page, secure=True,
                                         HTTP_HOST="mojplaywin.com").status_code, 405)

    @override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "testserver"])
    def test_private_invoice_no_wallet_if_release_off(self):
        i = self.invoice()
        self.client.force_login(self.buyer)
        with override_settings(MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED=False):
            response = self.client.get(
                "/moj-prop-v141/payment/" + i.reference + "/",
                secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, RECEIVER)
        self.assertNotContains(response, "30.000000 TRX")
        self.assertContains(response, "Payment not available")

    @override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "testserver"])
    def test_private_receipt_displays_only_verified_txid(self):
        i = self.invoice()
        body, receipt = self.proof(i)
        self.checked_confirm(i, TX_A, body, receipt)
        self.client.force_login(self.buyer)
        response = self.client.get(
            "/moj-prop-v141/payment/" + i.reference + "/",
            secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment confirmed")
        self.assertContains(response, TX_A)
        self.assertNotContains(response, RECEIVER)

    def test_private_watcher_command_not_enabled_by_default(self):
        with self.assertRaises(CommandError):
            call_command("mojprop_reconcile_native_trx", stdout=StringIO())

    def test_private_watcher_command_uses_mariadb_advisory_lock(self):
        self.invoice()
        output = StringIO()
        with override_settings(MOJPROP_TRX_AUTORECONCILE_ENABLED=True), \
             patch("prop_firm.management.commands.mojprop_reconcile_native_trx.reconcile_pending_invoices",
                   return_value={"checked_invoices": 1, "settled": 0, "dry_run": True}):
            call_command("mojprop_reconcile_native_trx", "--dry-run",
                         stdout=output)
        self.assertIn('"checked_invoices": 1', output.getvalue())
        self.assertIn('"dry_run": true', output.getvalue())

    def test_sqlite_nonimmediate_cannot_issue_payment(self):
        from prop_firm.plan1_v141_native_checkout import _require_serializable_payment_write
        with patch("django.db.connection") as conn:
            conn.vendor = "sqlite"
            conn.transaction_mode = "DEFERRED"
            with self.assertRaises(CheckoutRejected):
                _require_serializable_payment_write()
            conn.transaction_mode = None
            with self.assertRaises(CheckoutRejected):
                _require_serializable_payment_write()

    def test_sqlite_immediate_or_mariadb_allows_serialized_write(self):
        from prop_firm.plan1_v141_native_checkout import _require_serializable_payment_write
        with patch("django.db.connection") as conn:
            conn.vendor = "sqlite"
            conn.transaction_mode = "IMMEDIATE"
            self.assertIsNone(_require_serializable_payment_write())
            conn.vendor = "mysql"
            conn.transaction_mode = None
            self.assertIsNone(_require_serializable_payment_write())
            conn.vendor = "postgresql"
            with self.assertRaises(CheckoutRejected):
                _require_serializable_payment_write()
