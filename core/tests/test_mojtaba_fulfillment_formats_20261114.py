"""Format-specific buyer fulfillment diagnostics for the sole mojtaba.bot.ai.

Isolated synthetic Django test database only. No real orders, SMTP, TRX,
API providers, asset reads, download grants or server mutations.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.fulfillment_preflight import inspect_fulfillment_order
from core.models import Order, OrderItem, Product, PaymentIntent, PaymentWebhookEvent, LedgerEntry


class FulfillmentFormatContractTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(
            username="format-buyer", email="buyer@agri-market.org", password="synthetic-only",
        )
        self.owner = User.objects.create_superuser(
            username="format-seller", email="seller@agri-market.org", password="synthetic-only",
        )
        self.meta = {
            "rights_cleared": True, "independent_qc_reviewed": True,
            "buyer_terms_approved": True, "delivery_format": "pdf",
            "delivery_version": "1.0.0", "delivery_license": "personal-use",
            "delivery_asset_sha256": "a" * 64,
            "delivery_manifest_sha256": "b" * 64,
            "delivery_asset_ref": "asset_1234567890123456",
        }
        self.product = Product.objects.create(
            title="Synthetic farm economics reference",
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
        intent = PaymentIntent.objects.create(
            order=self.order, amount="30.00", currency="USD",
            idempotency_key="format-preflight-record-20261114",
            status="succeeded", provider="named-provider",
            provider_reference="fixture-only-not-independent-settlement",
        )
        PaymentWebhookEvent.objects.create(
            provider="named-provider", event_id="format-event-20261114",
            event_type="payment.succeeded", payment_intent=intent,
            status="processed", payload_hash="c" * 64,
            processed_at=timezone.now(),
        )
        LedgerEntry.objects.create(
            order=self.order, payment_intent=intent,
            entry_type="payment", amount="30.00", currency="USD",
            reference="payment:" + "d" * 64,
            metadata={"provider": "named-provider", "event_id": "format-event-20261114"},
        )

    def update_product(self, **meta):
        self.product.metadata = {**self.product.metadata, **meta}
        self.product.save(update_fields=["metadata"])

    def change_format(self, fmt):
        metadata = dict(self.product.metadata)
        metadata["delivery_format"] = fmt
        for key in ("delivery_asset_sha256", "delivery_manifest_sha256", "delivery_asset_ref"):
            metadata.pop(key, None)
        self.product.metadata = metadata
        self.product.save(update_fields=["metadata"])

    def license_ready(self):
        self.change_format("license_key")
        self.update_product(
            delivery_license="single-user",
            delivery_license_inventory_ref="private_inventory_ref_00000001",
            delivery_license_issuance_reviewed=True,
            delivery_license_binding="buyer_account",
        )

    def cosmetic_ready(self):
        self.change_format("in_game_cosmetic")
        self.product.product_type = "game_cosmetic"
        self.product.save(update_fields=["product_type"])
        self.update_product(
            crown_sku="cd-spectre",
            crown_checkout_verified=True,
            delivery_entitlement_ref="private_entitlement_0000000001",
            delivery_entitlement_binding="buyer_account",
            delivery_entitlement_reviewed=True,
        )

    def check_blocker(self, code):
        out = inspect_fulfillment_order(self.order)
        self.assertIn(code, out["blockers"], out)
        self.assertFalse(out["delivery_allowed"])
        self.assertFalse(out["delivery_verified"])

    def check_candidate_unverified(self):
        out = inspect_fulfillment_order(self.order)
        self.assertEqual(out["state"], "source_preflight_passed_unverified", out)
        self.assertEqual(out["blockers"], [])
        self.assertFalse(out["delivery_allowed"])
        self.assertFalse(out["delivery_verified"])
        self.assertFalse(out["independent_settlement_verified"])
        self.assertFalse(out["private_file_bytes_verified"])
        self.assertFalse(out["buyer_email_verified"])
        self.assertFalse(out["customer_download_receipt_verified"])

    def test_01_pdf_file_contract_retained(self):
        self.check_candidate_unverified()

    def test_02_epub_file_contract_supported(self):
        self.update_product(delivery_format="epub")
        self.check_candidate_unverified()

    def test_03_zip_file_contract_supported(self):
        self.update_product(delivery_format="zip")
        self.check_candidate_unverified()

    def test_04_pdf_no_asset_digest_rejected(self):
        self.update_product(delivery_asset_sha256="")
        self.check_blocker("DELIVERY_ASSET_HASH_INVALID")

    def test_05_epub_no_manifest_digest_rejected(self):
        self.update_product(delivery_format="epub", delivery_manifest_sha256=None)
        self.check_blocker("DELIVERY_MANIFEST_HASH_INVALID")

    def test_06_zip_equal_asset_and_manifest_hashes_rejected(self):
        self.update_product(delivery_format="zip", delivery_manifest_sha256="a" * 64)
        self.check_blocker("DELIVERY_ASSET_MANIFEST_NOT_DISTINCT")

    def test_07_pdf_private_asset_ref_rejects_path(self):
        self.update_product(delivery_asset_ref="../../private/sales.pdf")
        self.check_blocker("DELIVERY_PRIVATE_ASSET_REF_INVALID")

    def test_08_pdf_needs_valid_legal_license(self):
        self.update_product(delivery_license="https://other.site/reuse")
        self.check_blocker("DELIVERY_LICENSE_INVALID")

    def test_09_pdf_needs_private_rights(self):
        self.update_product(rights_cleared=False)
        self.check_blocker("DELIVERY_RIGHTS_NOT_CLEARED")

    def test_10_pdf_needs_independent_qc(self):
        self.update_product(independent_qc_reviewed=False)
        self.check_blocker("DELIVERY_INDEPENDENT_QC_MISSING")

    def test_11_pdf_needs_buyer_terms(self):
        self.update_product(buyer_terms_approved=False)
        self.check_blocker("DELIVERY_BUYER_TERMS_MISSING")

    def test_12_license_key_no_fake_binary_file_hash_required(self):
        self.license_ready()
        self.check_candidate_unverified()

    def test_13_license_missing_private_inventory_reference(self):
        self.license_ready()
        self.update_product(delivery_license_inventory_ref=None)
        self.check_blocker("DELIVERY_LICENSE_INVENTORY_REF_INVALID")

    def test_14_license_rejects_public_url_reference(self):
        self.license_ready()
        self.update_product(delivery_license_inventory_ref="https://public.example/key")
        self.check_blocker("DELIVERY_LICENSE_INVENTORY_REF_INVALID")

    def test_15_license_issuance_manual_review_required(self):
        self.license_ready()
        self.update_product(delivery_license_issuance_reviewed=False)
        self.check_blocker("DELIVERY_LICENSE_ISSUANCE_NOT_REVIEWED")

    def test_16_license_issuance_requires_exact_boolean_true(self):
        self.license_ready()
        self.update_product(delivery_license_issuance_reviewed="true")
        self.check_blocker("DELIVERY_LICENSE_ISSUANCE_NOT_REVIEWED")

    def test_17_license_must_be_bound_to_buyer_account(self):
        self.license_ready()
        self.update_product(delivery_license_binding="anonymous")
        self.check_blocker("DELIVERY_LICENSE_BUYER_BINDING_INVALID")

    def test_18_license_must_include_private_legal_license_code(self):
        self.license_ready()
        self.update_product(delivery_license="../expose")
        self.check_blocker("DELIVERY_LICENSE_INVALID")

    def test_19_cosmetic_no_fake_binary_file_hash_required(self):
        self.cosmetic_ready()
        self.check_candidate_unverified()

    def test_20_cosmetic_requires_approved_product_type(self):
        self.cosmetic_ready()
        self.product.product_type = "digital"
        self.product.save(update_fields=["product_type"])
        self.check_blocker("DELIVERY_PRODUCT_FORMAT_CONFLICT")

    def test_21_cosmetic_requires_known_sku(self):
        self.cosmetic_ready()
        self.update_product(crown_sku="unknown-skin")
        self.check_blocker("DELIVERY_COSMETIC_SKU_UNRECOGNIZED")

    def test_22_cosmetic_blocks_nonstring_sku(self):
        self.cosmetic_ready()
        self.update_product(crown_sku=["cd-spectre"])
        self.check_blocker("DELIVERY_COSMETIC_SKU_UNRECOGNIZED")

    def test_23_cosmetic_requires_crown_checkout_review(self):
        self.cosmetic_ready()
        self.update_product(crown_checkout_verified=False)
        self.check_blocker("DELIVERY_COSMETIC_CHECKOUT_UNVERIFIED")

    def test_24_cosmetic_requires_strict_true_for_checkout_review(self):
        self.cosmetic_ready()
        self.update_product(crown_checkout_verified="true")
        self.check_blocker("DELIVERY_COSMETIC_CHECKOUT_UNVERIFIED")

    def test_25_cosmetic_rejects_buyer_token_instead_of_private_ref(self):
        self.cosmetic_ready()
        self.update_product(delivery_entitlement_ref="wallet:public/secret")
        self.check_blocker("DELIVERY_COSMETIC_ENTITLEMENT_REF_INVALID")

    def test_26_cosmetic_requires_account_bound_entitlement(self):
        self.cosmetic_ready()
        self.update_product(delivery_entitlement_binding="public_download")
        self.check_blocker("DELIVERY_COSMETIC_BUYER_BINDING_INVALID")

    def test_27_cosmetic_requires_manual_entitlement_review(self):
        self.cosmetic_ready()
        self.update_product(delivery_entitlement_reviewed=False)
        self.check_blocker("DELIVERY_COSMETIC_ENTITLEMENT_NOT_REVIEWED")

    def test_28_cosmetic_no_file_license_backdoor(self):
        self.product.product_type = "game_cosmetic"
        self.product.save(update_fields=["product_type"])
        self.check_blocker("DELIVERY_PRODUCT_FORMAT_CONFLICT")

    def test_29_order_currency_iso_contract(self):
        self.order.currency = "usd"
        self.order.save(update_fields=["currency"])
        self.check_blocker("ORDER_CURRENCY_INVALID")

    def test_30_product_currency_must_match_order(self):
        self.product.currency = "EUR"
        self.product.save(update_fields=["currency"])
        self.check_blocker("DELIVERY_PRODUCT_CURRENCY_MISMATCH")

    def test_31_invoice_line_total_must_equal_order_total(self):
        self.item.unit_price = Decimal("29.00")
        self.item.save(update_fields=["unit_price"])
        self.check_blocker("DELIVERY_LINE_TOTAL_MISMATCH")

    def test_32_product_title_control_bytes_not_trusted(self):
        self.product.title = "Safe title\r\nprivate spoof"
        self.product.save(update_fields=["title"])
        self.check_blocker("PRODUCT_TITLE_MISSING")

    def test_33_review_flag_cannot_replace_independent_cash_evidence(self):
        self.license_ready()
        out = inspect_fulfillment_order(self.order)
        self.assertFalse(out["independent_settlement_verified"])
        self.assertFalse(out["delivery_verified"])

    def test_34_metadata_not_a_secret_code_delivery(self):
        self.license_ready()
        raw = repr(inspect_fulfillment_order(self.order))
        self.assertNotIn("private_inventory_ref_00000001", raw)
        self.assertNotIn("agri-market.org", raw)

    def test_35_entitlement_metadata_not_customer_grant(self):
        self.cosmetic_ready()
        raw = repr(inspect_fulfillment_order(self.order))
        self.assertNotIn("private_entitlement_0000000001", raw)
        self.assertNotIn("cd-spectre", raw)

    def test_36_unknown_format_remains_blocked(self):
        self.change_format("raw_api_secret")
        self.check_blocker("DELIVERY_FORMAT_UNSUPPORTED")

    def test_37_unhashable_list_format_is_blocked_not_500(self):
        self.change_format(["pdf", "exe"])
        self.check_blocker("DELIVERY_FORMAT_UNSUPPORTED")

    def test_38_unhashable_dict_format_is_blocked_not_500(self):
        self.change_format({"download": "pdf"})
        self.check_blocker("DELIVERY_FORMAT_UNSUPPORTED")

    def test_39_bool_format_is_blocked_not_500(self):
        self.change_format(True)
        self.check_blocker("DELIVERY_FORMAT_UNSUPPORTED")

    def test_40_missing_format_is_blocked_not_500(self):
        self.change_format(None)
        self.check_blocker("DELIVERY_FORMAT_UNSUPPORTED")

    def test_41_license_array_inventory_ref_is_not_accepted(self):
        self.license_ready()
        self.update_product(delivery_license_inventory_ref=["secret"])
        self.check_blocker("DELIVERY_LICENSE_INVENTORY_REF_INVALID")

    def test_42_cosmetic_string_entitlement_review_is_not_accepted(self):
        self.cosmetic_ready()
        self.update_product(delivery_entitlement_reviewed="true")
        self.check_blocker("DELIVERY_COSMETIC_ENTITLEMENT_NOT_REVIEWED")
