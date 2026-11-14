"""Isolated Django buyer fulfillment preflight and Crown crash regressions.

No SMTP, payment, real delivery, blockchain call or product download. This
tests diagnosis and denial, not a production-delivery certification.
"""
import json
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.crown_fleet import owned_skus
from core.economic_master_agent import EconomicMasterAgent
from core.fulfillment_preflight import (
    inspect_fulfillment_order, fulfillment_preflight_snapshot,
)
from core.models import (
    Order, OrderItem, PaymentIntent, PaymentWebhookEvent, Product, LedgerEntry,
)


class FulfillmentReadinessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(
            username="client", email="buyer@agri-market.org", password="offline-only",
        )
        self.owner = User.objects.create_superuser(
            username="seller", email="seller@agri-market.org",
            password="offline-only",
        )
        self.employee = User.objects.create_user(
            username="staff", email="staff@agri-market.org", password="offline-only",
            is_staff=True,
        )
        self.meta = {
            "rights_cleared": True, "independent_qc_reviewed": True,
            "buyer_terms_approved": True, "delivery_format": "pdf",
            "delivery_asset_sha256": "a" * 64,
            "delivery_manifest_sha256": "b" * 64,
            "delivery_version": "1.0.0", "delivery_license": "personal-use",
            "delivery_asset_ref": "asset_1234567890123456",
        }
        self.product = Product.objects.create(
            title="Qualified agricultural economics eBook",
            product_type="digital", price="30.00", currency="USD",
            active=True, owner=self.owner, metadata=dict(self.meta),
        )
        self.order = Order.objects.create(
            customer=self.buyer, status="paid", total=Decimal("30.00"), currency="USD",
        )
        self.item = OrderItem.objects.create(
            order=self.order, product=self.product, quantity=1,
            unit_price="30.00", currency="USD",
        )
        self.intent = PaymentIntent.objects.create(
            order=self.order, amount="30.00", currency="USD",
            idempotency_key="fulfillment-identity-v1",
            status="succeeded", provider="named-provider",
            provider_reference="external-event-requires-verification",
        )
        self.webhook = PaymentWebhookEvent.objects.create(
            provider="named-provider", event_id="event-fulfill-1",
            event_type="payment.succeeded", payment_intent=self.intent,
            status="processed", payload_hash="c"*64,
            processed_at=timezone.now(),
        )
        self.ledger = LedgerEntry.objects.create(
            order=self.order, payment_intent=self.intent,
            entry_type="payment", amount="30.00", currency="USD",
            reference="payment:" + "d"*64,
            metadata={"provider": "named-provider", "event_id": "event-fulfill-1"},
        )

    def result(self):
        return inspect_fulfillment_order(self.order)

    def check(self, code):
        self.assertIn(code, self.result()["blockers"])

    def change_meta(self, key, value):
        self.product.metadata = {**self.product.metadata, key: value}
        self.product.save(update_fields=["metadata"])

    def test_01_source_check_passed_not_delivery(self):
        out = self.result()
        self.assertEqual(out["state"], "source_preflight_passed_unverified")
        self.assertEqual(out["blockers"], [])

    def test_02_no_download_or_auto_delivery_authorized(self):
        out = self.result()
        self.assertFalse(out["delivery_allowed"])
        self.assertFalse(out["delivery_verified"])
        self.assertFalse(out["private_file_bytes_verified"])
        self.assertFalse(out["independent_settlement_verified"])

    def test_03_order_pending(self):
        self.order.status = "pending"; self.order.save(update_fields=["status"])
        self.check("ORDER_NOT_PAID")

    def test_04_order_zero(self):
        self.order.total = Decimal("0"); self.order.save(update_fields=["total"])
        self.check("ORDER_AMOUNT_INVALID")

    def test_05_order_negative(self):
        self.order.total = Decimal("-1"); self.order.save(update_fields=["total"])
        self.check("ORDER_AMOUNT_INVALID")

    def test_06_missing_buyer_email(self):
        self.buyer.email = ""; self.buyer.save(update_fields=["email"])
        self.check("BUYER_EMAIL_INVALID_OR_PLACEHOLDER")

    def test_07_placeholder_buyer_email(self):
        self.buyer.email = "guest@example.com"; self.buyer.save(update_fields=["email"])
        self.check("BUYER_EMAIL_INVALID_OR_PLACEHOLDER")

    def test_08_unvalidated_email_domain(self):
        self.buyer.email = "buyer@localhost"; self.buyer.save(update_fields=["email"])
        self.check("BUYER_EMAIL_INVALID_OR_PLACEHOLDER")

    def test_09_inactive_buyer(self):
        self.buyer.is_active = False; self.buyer.save(update_fields=["is_active"])
        self.check("BUYER_INACTIVE")

    def test_10_privileged_staff_buyer(self):
        self.buyer.is_staff = True; self.buyer.save(update_fields=["is_staff"])
        self.check("BUYER_PRIVILEGED_ACCOUNT")

    def test_11_privileged_superuser_buyer(self):
        self.buyer.is_superuser = True; self.buyer.save(update_fields=["is_superuser"])
        self.check("BUYER_PRIVILEGED_ACCOUNT")

    def test_12_no_order_item(self):
        self.item.delete()
        self.check("DELIVERY_ITEM_MISSING")

    def test_13_multiple_items_need_separate_receipts(self):
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=1,
            unit_price="1.00", currency="USD",
        )
        self.check("DELIVERY_MULTI_ITEM_NEEDS_SEPARATE_RECEIPTS")

    def test_14_more_than_one_copy_needs_separate_receipts(self):
        self.item.quantity = 2; self.item.save(update_fields=["quantity"])
        self.check("DELIVERY_QUANTITY_UNSUPPORTED")

    def test_15_item_currency_mismatch(self):
        self.item.currency = "IRR"; self.item.save(update_fields=["currency"])
        self.check("DELIVERY_CURRENCY_MISMATCH")

    def test_16_item_price_mismatch(self):
        self.item.unit_price = Decimal("29")
        self.item.save(update_fields=["unit_price"])
        self.check("DELIVERY_PRICE_MISMATCH")

    def test_17_product_inactive(self):
        self.product.active = False; self.product.save(update_fields=["active"])
        self.check("PRODUCT_NOT_ACTIVE")

    def test_18_product_title_missing(self):
        self.product.title = ""; self.product.save(update_fields=["title"])
        self.check("PRODUCT_TITLE_MISSING")

    def test_19_product_owner_missing(self):
        self.product.owner = None; self.product.save(update_fields=["owner"])
        self.check("PRODUCT_OWNER_NOT_AUTHORIZED")

    def test_20_product_owner_inactive(self):
        self.owner.is_active = False; self.owner.save(update_fields=["is_active"])
        self.check("PRODUCT_OWNER_NOT_AUTHORIZED")

    def test_21_product_owner_not_superuser(self):
        self.owner.is_superuser = False; self.owner.save(update_fields=["is_superuser"])
        self.check("PRODUCT_OWNER_NOT_AUTHORIZED")

    def test_22_nonobject_metadata(self):
        self.product.metadata = ["not-an-object"]
        self.product.save(update_fields=["metadata"])
        self.check("PRODUCT_METADATA_NOT_OBJECT")

    def test_23_rights_not_cleared(self):
        self.change_meta("rights_cleared", False)
        self.check("DELIVERY_RIGHTS_NOT_CLEARED")

    def test_24_independent_quality_review_missing(self):
        self.change_meta("independent_qc_reviewed", False)
        self.check("DELIVERY_INDEPENDENT_QC_MISSING")

    def test_25_buyer_terms_unapproved(self):
        self.change_meta("buyer_terms_approved", False)
        self.check("DELIVERY_BUYER_TERMS_MISSING")

    def test_26_unknown_format(self):
        self.change_meta("delivery_format", "exe")
        self.check("DELIVERY_FORMAT_UNSUPPORTED")

    def test_27_boolean_format(self):
        self.change_meta("delivery_format", True)
        self.check("DELIVERY_FORMAT_UNSUPPORTED")

    def test_28_missing_asset_hash(self):
        self.change_meta("delivery_asset_sha256", "")
        self.check("DELIVERY_ASSET_HASH_INVALID")

    def test_29_zero_asset_hash(self):
        self.change_meta("delivery_asset_sha256", "0"*64)
        self.check("DELIVERY_ASSET_HASH_INVALID")

    def test_30_uppercase_asset_hash(self):
        self.change_meta("delivery_asset_sha256", "A"*64)
        self.check("DELIVERY_ASSET_HASH_INVALID")

    def test_31_missing_manifest_hash(self):
        self.change_meta("delivery_manifest_sha256", None)
        self.check("DELIVERY_MANIFEST_HASH_INVALID")

    def test_32_asset_manifest_hash_collision(self):
        self.change_meta("delivery_manifest_sha256", "a"*64)
        self.check("DELIVERY_ASSET_MANIFEST_NOT_DISTINCT")

    def test_33_invalid_version(self):
        self.change_meta("delivery_version", "../../etc/1")
        self.check("DELIVERY_VERSION_INVALID")

    def test_34_invalid_license(self):
        self.change_meta("delivery_license", "https://example.org")
        self.check("DELIVERY_LICENSE_INVALID")

    def test_35_absolute_path_asset_ref_denied(self):
        self.change_meta("delivery_asset_ref", "/private/file.pdf")
        self.check("DELIVERY_PRIVATE_ASSET_REF_INVALID")

    def test_36_public_url_asset_ref_denied(self):
        self.change_meta("delivery_asset_ref", "https://cdn.example/file.pdf")
        self.check("DELIVERY_PRIVATE_ASSET_REF_INVALID")

    def test_37_unreconciled_payment_records(self):
        self.ledger.delete()
        self.check("DELIVERY_PAYMENT_RECORDS_UNRECONCILED")

    def test_38_reversed_payment_does_not_pass(self):
        LedgerEntry.objects.create(
            order=self.order, entry_type="refund", amount="30.00",
            currency="USD", reference="refund:synthetic-1",
        )
        self.check("DELIVERY_PAYMENT_RECORDS_UNRECONCILED")

    def test_39_deactivated_gateway_status_denied(self):
        self.intent.status = "ready_for_gateway"
        self.intent.save(update_fields=["status"])
        self.check("DELIVERY_PAYMENT_RECORDS_UNRECONCILED")

    def test_40_no_proof_of_buyer_email_ownership(self):
        self.assertFalse(self.result()["buyer_email_verified"])
        self.assertFalse(self.result()["customer_download_receipt_verified"])

    def test_41_snapshot_counts_and_no_revenue_claim(self):
        data = fulfillment_preflight_snapshot()
        self.assertEqual(data["sampled_orders"], 1)
        self.assertEqual(data["states"]["source_preflight_passed_unverified"], 1)
        self.assertFalse(data["delivery_enabled"])

    def test_42_snapshot_does_not_expose_buyer_identity(self):
        raw = json.dumps(fulfillment_preflight_snapshot())
        self.assertNotIn("buyer@agri-market.org", raw)
        self.assertNotIn("external-event-requires-verification", raw)
        self.assertNotIn(str(self.order.pk) + "-payment", raw)

    def test_43_snapshot_never_extrapolates(self):
        Order.objects.create(customer=self.buyer, total="1.00", currency="USD")
        data = fulfillment_preflight_snapshot(limit=1)
        self.assertEqual(data["sampled_orders"], 1)
        self.assertFalse(data["sample_complete"])

    def test_44_invalid_days_denied(self):
        with self.assertRaises(ValueError):
            fulfillment_preflight_snapshot(days=0)

    def test_45_boolean_limit_denied(self):
        with self.assertRaises(ValueError):
            fulfillment_preflight_snapshot(limit=True)

    def test_46_anonymous_endpoint_denied(self):
        r = self.client.get("/staff/command-center/api/bot/fulfillment-preflight/")
        self.assertEqual(r.status_code, 403)

    def test_47_staff_endpoint_denied(self):
        self.client.force_login(self.employee)
        r = self.client.get("/staff/command-center/api/bot/fulfillment-preflight/")
        self.assertEqual(r.status_code, 403)

    def test_48_owner_endpoint_private_read_only(self):
        self.client.force_login(self.owner)
        r = self.client.get("/staff/command-center/api/bot/fulfillment-preflight/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["bot_id"], "mojtaba.bot.ai")
        self.assertIn("no-store", r["Cache-Control"])
        self.assertNotIn("buyer@agri-market.org", r.content.decode())

    def test_49_post_endpoint_denied(self):
        self.client.force_login(self.owner)
        r = self.client.post("/staff/command-center/api/bot/fulfillment-preflight/", {})
        self.assertEqual(r.status_code, 405)

    def test_50_cli_and_master_have_identical_readonly_contract(self):
        s = StringIO()
        call_command("mojtaba_fulfillment_preflight_readonly", stdout=s)
        cli = json.loads(s.getvalue())
        bot = EconomicMasterAgent().inspect_fulfillment_preflight_readonly()
        self.assertEqual(cli["bot_id"], bot["bot_id"])
        self.assertEqual(cli["states"], bot["states"])
        self.assertFalse(cli["automated_fulfillment_released"])

    def test_51_no_db_mutation_from_preflight(self):
        before = (Order.objects.count(), OrderItem.objects.count(),
                  PaymentIntent.objects.count(), LedgerEntry.objects.count())
        inspect_fulfillment_order(self.order)
        fulfillment_preflight_snapshot()
        self.assertEqual(before, (Order.objects.count(), OrderItem.objects.count(),
                                  PaymentIntent.objects.count(), LedgerEntry.objects.count()))

    def test_52_invalid_order_no_exceptions_or_leaks(self):
        out = inspect_fulfillment_order(None)
        self.assertEqual(out["state"], "invalid_record")
        self.assertFalse(out["delivery_allowed"])

    def test_53_missing_payment_intent_flags_source(self):
        new_order = Order.objects.create(
            customer=self.buyer, status="paid", total="30.00", currency="USD",
        )
        OrderItem.objects.create(
            order=new_order, product=self.product, quantity=1,
            unit_price="30.00", currency="USD",
        )
        out = inspect_fulfillment_order(new_order)
        self.assertIn("DELIVERY_PAYMENT_RECORDS_UNRECONCILED", out["blockers"])

    def test_54_crown_paid_order_without_intent_no_500(self):
        skin = Product.objects.create(
            title="Spectre", product_type="game_cosmetic", price="4.00",
            currency="USD", active=True, metadata={"crown_sku": "cd-spectre"},
        )
        order = Order.objects.create(
            customer=self.buyer, status="paid", total="4.00", currency="USD",
        )
        OrderItem.objects.create(order=order, product=skin, quantity=1,
                                 unit_price="4.00", currency="USD")
        self.assertEqual(owned_skus(self.buyer), [])

    def test_55_crown_corrupt_metadata_no_500_or_entitlement(self):
        skin = Product.objects.create(
            title="Spectre", product_type="game_cosmetic", price="4.00",
            currency="USD", active=True, metadata=["untrusted"],
        )
        order = Order.objects.create(
            customer=self.buyer, status="paid", total="4.00", currency="USD",
        )
        OrderItem.objects.create(order=order, product=skin, quantity=1,
                                 unit_price="4.00", currency="USD")
        self.assertEqual(owned_skus(self.buyer), [])
