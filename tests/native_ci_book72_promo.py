"""Isolated MySQL tests for owner-declared chess discount; never touch production."""
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from core.models import KnowledgeArticle, Product
from scripts.mpw_book72_apply_promo import update_book72_promo, ASSET, SHA, PRICING


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"], MPW_COMMERCE_RELEASE_READY=False)
class Book72PromotionTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        owner=get_user_model().objects.create_user(username="promo-seller")
        article=KnowledgeArticle.objects.create(
            title="Chess draft",slug="chess-promo-draft",content="pre-release",published=False,
        )
        self.product=Product.objects.create(
            pk=72,title="Chess Improvement",product_type="digital_book",
            currency="USD",price=Decimal("7.50"),active=False,
            owner=owner,knowledge_article=article,
            metadata={"asset_sha256":SHA,
                      "mpw_commerce":{"enabled":False,"private_file":ASSET}},
        )

    def test_promo_sets_exact_list_discount_without_changing_payment(self):
        self.assertEqual(update_book72_promo(backup_root=self.temp.name),"draft_promotion_saved")
        self.product.refresh_from_db()
        self.assertEqual(self.product.metadata["pricing"],PRICING)
        self.assertEqual(self.product.price,Decimal("7.50"))
        self.assertFalse(self.product.active)
        self.assertEqual(update_book72_promo(backup_root=self.temp.name),"already_verified")

    def test_changed_or_active_product_denied(self):
        self.product.active=True
        self.product.save(update_fields=["active"])
        with self.assertRaises(RuntimeError):
            update_book72_promo(backup_root=self.temp.name)
        self.product.active=False
        self.product.price=Decimal("30.00")
        self.product.save(update_fields=["active","price"])
        with self.assertRaises(RuntimeError):
            update_book72_promo(backup_root=self.temp.name)

    def test_unverified_asset_denied(self):
        self.product.metadata["asset_sha256"]="wrong"
        self.product.save(update_fields=["metadata"])
        with self.assertRaises(RuntimeError):
            update_book72_promo(backup_root=self.temp.name)
