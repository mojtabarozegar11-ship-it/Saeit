"""Read-only chess launch preflight: no live funds, host keys or public PDF."""
import io
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.models import KnowledgeArticle, Product
from mpw_commerce.management.commands.mpw_chess_launch_audit import (
    EXPECTED_RELATIVE_PATH, FLAGS, audit,
)


class ReadOnlyChessLaunchAuditTests(TestCase):
    def test_no_product_never_approves_checkout(self):
        before = Product.objects.count()
        doc = audit()
        self.assertIs(doc["checks"]["product_exists"], False)
        self.assertIs(doc["public_paid_sales_go"], False)
        self.assertEqual(Product.objects.count(), before)
        self.assertNotIn("private_path", json.dumps(doc))

    def test_inactive_product_with_asset_does_not_pass_go_gates(self):
        book = Product.objects.create(
            pk=72, title="The Science and Practice of Chess Improvement",
            product_type="digital_book", currency="USD",
            price=Decimal("7.50"), active=False,
            metadata={
                "product_id":"mojplaywin-chess-improvement-2026",
                "rights_owner_attested":True,
                "mpw_commerce":{
                    "enabled":False,"fulfillment":"digital",
                    "private_file":EXPECTED_RELATIVE_PATH,
                },
            },
        )
        before = dict(book.metadata)
        with patch("mpw_commerce.management.commands.mpw_chess_launch_audit._verified_file",
                   return_value=True):
            doc = audit()
        self.assertTrue(doc["checks"]["private_pdf_matches_exact_sha256"])
        self.assertFalse(doc["checks"]["digital_fulfillment_enabled"])
        self.assertFalse(doc["checks"]["article_published"])
        self.assertFalse(doc["public_paid_sales_go"])
        book.refresh_from_db()
        self.assertEqual(book.metadata, before)
        self.assertFalse(book.active)

    def test_all_synthetic_technical_checks_still_not_a_real_mainnet_sale(self):
        user = get_user_model().objects.create_user(username="chess-release-seller")
        article = KnowledgeArticle.objects.create(
            slug="chess-release-review-fixture",
            title="Chess research review fixture", content="fixture", published=True
        )
        metadata = {
            "product_id":"mojplaywin-chess-improvement-2026",
            "rights_owner_attested":True,
            "mpw_commerce":{
                "enabled":True, "fulfillment":"digital",
                "private_file":EXPECTED_RELATIVE_PATH,
            },
            "factory_publication_permission":True,
            "asset_verified":True,
            "quality_approved":True,
            "license_verified":True,
        }
        Product.objects.create(
            pk=72,title="The Science and Practice of Chess Improvement",
            product_type="digital_book",currency="USD",
            price=Decimal("7.50"),active=True,
            owner=user,knowledge_article=article,
            metadata=metadata,
        )
        live_flags={name:True for name in FLAGS}
        with override_settings(**live_flags, ROOT_URLCONF="tests.native_checkout_root_urls"), patch(
            "mpw_commerce.management.commands.mpw_chess_launch_audit._verified_file",
            return_value=True
        ), patch("mpw_native_checkout.wallet_ownership.proven_assets",
                 return_value={"ETH":True,"TRX":True}):
            doc=audit()
        self.assertTrue(doc["technical_preflight_passed"])
        self.assertFalse(doc["public_paid_sales_go"])
        self.assertFalse(doc["live_mainnet_end_to_end_sale_verified"])
        self.assertFalse(doc["independent_editorial_and_service_terms_review_verified"])
        self.assertTrue(all(doc["checks"].values()))

    def test_strict_returns_error_instead_of_false_success(self):
        with self.assertRaises(CommandError):
            call_command("mpw_chess_launch_audit", strict=True, stdout=io.StringIO())

    def test_json_command_output_and_no_secret_information(self):
        output=io.StringIO()
        call_command("mpw_chess_launch_audit", stdout=output)
        doc=json.loads(output.getvalue())
        self.assertEqual(doc["product_id"],72)
        self.assertNotIn("recipient", output.getvalue())
        self.assertNotIn("private_key", output.getvalue())
        self.assertIs(doc["public_paid_sales_go"], False)
