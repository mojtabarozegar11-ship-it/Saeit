"""Preview-only commercial contract with safe live product discovery."""
import json
from pathlib import Path
from decimal import Decimal

from django.test import SimpleTestCase

from core.mojplaywin_views import PRODUCTS


MANIFEST = Path(__file__).resolve().parents[1] / "catalog" / "mojplaywin" / "atelier-interior-kit-v1.json"


class AtelierPreviewTests(SimpleTestCase):
    def test_card_is_a_product_detail_link_not_a_checkout(self):
        matching = [p for p in PRODUCTS if p["title"].startswith("Atelier Interior")]
        self.assertEqual(len(matching), 1)
        card = matching[0]
        self.assertEqual(card["url"], "/store/product/879/")
        self.assertIn("current availability and terms", card["text"].lower())
        self.assertNotIn("checkout_url", card)
        self.assertNotIn("price", card)

    def test_public_manifest_never_activates_paid_delivery(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "preview_only")
        self.assertIsNone(data["price"])
        self.assertIs(data["checkout_enabled"], False)
        self.assertIs(data["paid_delivery_enabled"], False)
        self.assertIs(data["sellable_asset_in_public_repository"], False)
        self.assertEqual(len(data["private_download_sha256"]), 64)
        self.assertIn("customer_download", data["evidence"])
        prices = data["pricing_recommendation"]
        original = Decimal(str(prices["regular_price"]))
        discount = Decimal(str(prices["discount_percent"]))
        payable = Decimal(str(prices["discounted_price"]))
        self.assertEqual(original, Decimal("17"))
        self.assertEqual(discount, Decimal("60"))
        self.assertEqual(payable, Decimal("6.8"))
        self.assertEqual((original * (Decimal("100") - discount) / Decimal("100")).quantize(Decimal("0.01")), payable)

