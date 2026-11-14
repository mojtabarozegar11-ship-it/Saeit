"""Real Django paid one-bot signal read-access regressions; synthetic TRX only.

No network requests, SMTP, message dispatch, broker trade or live mainnet fund.
"""
import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.http import Http404
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from core.models import LedgerEntry, Product, PaymentWebhookEvent, OrderItem
from core.tron_gateway_invoice import TronGatewayInvoice
from core.tron_gateway_verify import MAINNET_RECEIVER
from core.tron_gateway_web import _new_invoice, _record_paid, _email_key, _read_product
from core.mojtaba_signal_paid_access import (
    CANONICAL_BOT, PLAN_SKUS, REQUIRED_APPROVALS,
    paid_signal_access, approved_signal_offer_snapshot,
)

SKU="moj-signals-standard"
PROOF={"txid":"b"*64, "sender_hex":"41"+"d"*40, "block_height":788889,
       "block_time_ms":1800000000000, "proof_digest":"e"*64,
       "finality":"solidified"}
REGISTRY={"mojplaywin.com":{
    "tenant_id":"mojplaywin_site",
    "receiver":MAINNET_RECEIVER, "network":"tron-mainnet", "asset":"TRX",
    "approved":True,
}}
CACHE={"default":{"BACKEND":"django.core.cache.backends.redis.RedisCache",
                  "LOCATION":"redis://localhost:6379/0"}}

@override_settings(
    TRON_UNIFIED_SITE_MERCHANTS=REGISTRY,
    TRON_UNIFIED_PUBLIC_ENABLED=True,
    TRON_UNIFIED_SHARED_RATE_LIMIT_READY=True,
    TRON_UNIFIED_ALLOWED_HOSTS=["mojplaywin.com"],
    MOJ_SIGNAL_BOT_PRODUCT_CHECKOUT_ENABLED=True,
    MOJ_SIGNAL_BOT_PAID_DELIVERY_ENABLED=True,
    ALLOWED_HOSTS=["mojplaywin.com","testserver"],
    CACHES=CACHE,
)
class PaidSignalAccessC29Tests(TestCase):
    def setUp(self):
        md={
            "rights_cleared":True,"publication_approved":True,
            "sales_enabled":True,"in_stock":True,"fulfillment_ready":True,
            "fulfillment_type":"service",
            "tron_price_sun":1800000,"tron_price_currency":"USD",
            "tron_price_reference_amount":"12.00",
            "tron_quote_valid_until_ms":int(time.time()*1000)+600000,
            "mojtaba_signal_plan_sku":SKU,"signal_term_days":30,
            **{x:True for x in REQUIRED_APPROVALS},
        }
        self.product=Product.objects.create(
            title="Only bot signals verified test rights",product_type="service",
            active=True,price=Decimal("12.00"),currency="USD",metadata=md)
        self.factory=RequestFactory()

    def issue(self):
        invoice,token=_new_invoice(
            "owner-verified@example.test", "mojplaywin.com", "en", self.product.pk)
        self.assertTrue(token)
        return invoice

    def paid(self):
        invoice=self.issue()
        TronGatewayInvoice.objects.filter(pk=invoice.pk).update(
            status="awaiting_payment")
        self.assertTrue(_record_paid(invoice.pk,PROOF))
        return TronGatewayInvoice.objects.select_related(
            "order","payment_intent").get(pk=invoice.pk)

    def buyer_request(self, invoice, *, email_key=None, host="mojplaywin.com"):
        request=self.factory.get("/bot/signals/",HTTP_HOST=host,secure=True)
        request.session={
            "tron_verified_email":email_key if email_key is not None else
                _email_key(invoice.buyer_email),
            "tron_verified_host":host,
            "tron_verified_at":int(time.time()),
        }
        return request

    def decision(self, invoice, **overrides):
        return paid_signal_access(self.buyer_request(invoice),invoice.pk,
                                  SKU,**overrides)

    def test_01_exact_paid_session_and_mainnet_credit_grants_read_only_access(self):
        invoice=self.paid()
        d=self.decision(invoice)
        self.assertTrue(d.permitted)
        self.assertEqual(d.bot_identity,CANONICAL_BOT)
        self.assertEqual(d.sku,SKU)
        self.assertEqual(d.issuer_host,"mojplaywin.com")
        self.assertFalse(d.sends_messages)
        self.assertFalse(d.creates_orders)
        self.assertFalse(d.executes_trades)

    def test_02_invoice_binds_signal_sku_and_bounded_period(self):
        invoice=self.issue()
        self.assertEqual(invoice.signal_sku_snapshot,SKU)
        self.assertEqual(invoice.signal_term_days_snapshot,30)
        self.assertEqual(invoice.merchant_tenant_id,"mojplaywin_site")

    def test_03_ledger_snapshot_matches_original_signal_contract(self):
        invoice=self.paid()
        data=LedgerEntry.objects.get(order=invoice.order).metadata
        self.assertEqual(data["signal_sku_snapshot"],SKU)
        self.assertEqual(data["signal_term_days_snapshot"],30)

    def test_04_checkout_off_by_default_blocks_signal_invoice(self):
        with override_settings(MOJ_SIGNAL_BOT_PRODUCT_CHECKOUT_ENABLED=False):
            with self.assertRaises(Http404):
                self.issue()

    def test_05_delivery_off_by_default_blocks_even_settled_invoice(self):
        inv=self.paid()
        with override_settings(MOJ_SIGNAL_BOT_PAID_DELIVERY_ENABLED=False):
            self.assertFalse(self.decision(inv).permitted)

    def test_06_unpaid_invoice_never_grants_subscriber_access(self):
        invoice=self.issue()
        self.assertFalse(self.decision(invoice).permitted)

    def test_07_foreign_email_session_cannot_open_invoice(self):
        invoice=self.paid()
        request=self.buyer_request(invoice,email_key=_email_key("other@abc.invalid"))
        self.assertFalse(paid_signal_access(request,invoice.pk,SKU).permitted)

    def test_08_other_host_does_not_inherit_existing_paid_entitlement(self):
        invoice=self.paid()
        request=self.buyer_request(invoice,host="zomorodmelal.ir")
        self.assertFalse(paid_signal_access(request,invoice.pk,SKU).permitted)

    def test_09_wrong_signal_product_sku_is_denied(self):
        invoice=self.paid()
        self.assertFalse(paid_signal_access(
            self.buyer_request(invoice),invoice.pk,
            "moj-signals-professional").permitted)

    def test_10_unrecognized_plan_is_denied(self):
        invoice=self.paid()
        self.assertFalse(paid_signal_access(
            self.buyer_request(invoice),invoice.pk,"unapproved-signal").permitted)

    def test_11_expired_thirty_day_paid_term_denied(self):
        invoice=self.paid()
        later=invoice.verified_at+timedelta(days=30,seconds=1)
        self.assertFalse(self.decision(invoice,now=later).permitted)

    def test_12_exact_expiry_boundary_denied(self):
        invoice=self.paid()
        self.assertFalse(self.decision(
            invoice,now=invoice.verified_at+timedelta(days=30)).permitted)

    def test_13_missing_webhook_event_denied(self):
        invoice=self.paid()
        PaymentWebhookEvent.objects.all().delete()
        self.assertFalse(self.decision(invoice).permitted)

    def test_14_missing_ledger_credit_denied(self):
        invoice=self.paid()
        LedgerEntry.objects.all().delete()
        self.assertFalse(self.decision(invoice).permitted)

    def test_15_reversed_payment_denies_paid_signal_access(self):
        invoice=self.paid()
        LedgerEntry.objects.create(
            order=invoice.order,payment_intent=invoice.payment_intent,
            entry_type="refund",amount=Decimal("12.00"),currency="USD",
            reference="refund-only-c29")
        self.assertFalse(self.decision(invoice).permitted)

    def test_16_wrong_source_merchant_tenant_blocks(self):
        invoice=self.paid()
        TronGatewayInvoice.objects.filter(pk=invoice.pk).update(
            merchant_tenant_id="stolen_subsite")
        self.assertFalse(self.decision(invoice).permitted)

    def test_17_modified_ledger_sku_denies_buyer_access(self):
        invoice=self.paid()
        row=LedgerEntry.objects.get(order=invoice.order)
        row.metadata={**row.metadata,"signal_sku_snapshot":"moj-signals-plus"}
        row.save(update_fields=["metadata"])
        self.assertFalse(self.decision(invoice).permitted)

    def test_18_rights_revocation_denies_past_receipt_delivery(self):
        invoice=self.paid()
        self.product.metadata["rights_revoked"]=True
        self.product.save(update_fields=["metadata"])
        self.assertFalse(self.decision(invoice).permitted)

    def test_19_suspended_delivery_denies_existing_subscriber(self):
        invoice=self.paid()
        self.product.metadata["delivery_suspended"]=True
        self.product.save(update_fields=["metadata"])
        self.assertFalse(self.decision(invoice).permitted)

    def test_20_no_signal_advertised_without_independent_history_audit(self):
        self.product.metadata["independent_signal_history_audited"]=False
        self.product.save(update_fields=["metadata"])
        with self.assertRaises(Http404):
            self.issue()

    def test_21_false_approval_strings_deny_invoice(self):
        for key in REQUIRED_APPROVALS:
            with self.subTest(key=key):
                self.product.metadata[key]="approved"
                self.product.save(update_fields=["metadata"])
                with self.assertRaises(Http404):
                    self.issue()
                self.product.metadata[key]=True

    def test_22_all_three_plans_are_only_one_bot_identity(self):
        self.assertEqual(len(PLAN_SKUS),3)
        self.assertEqual(CANONICAL_BOT,"mojtaba.bot.ai")

    def test_23_regular_service_does_not_get_signal_contract_snapshot(self):
        self.product.metadata.pop("mojtaba_signal_plan_sku")
        self.product.save(update_fields=["metadata"])
        invoice=self.issue()
        self.assertEqual(invoice.signal_sku_snapshot,"")
        self.assertEqual(invoice.signal_term_days_snapshot,0)

    def test_24_future_clock_and_unaware_time_cannot_forge_current_access(self):
        invoice=self.paid()
        self.assertFalse(self.decision(invoice,now=invoice.verified_at-timedelta(seconds=1)).permitted)
        self.assertFalse(self.decision(invoice,now=invoice.verified_at.replace(tzinfo=None)).permitted)

    def test_25_unverified_email_cannot_recover_duplicate_brand_entitlement(self):
        invoice=self.paid()
        self.assertFalse(paid_signal_access(
            self.buyer_request(invoice,email_key="f"*64),invoice.pk,SKU).permitted)
