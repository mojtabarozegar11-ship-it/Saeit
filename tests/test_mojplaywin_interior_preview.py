"""Preview-only storefront contract for the interior design website kit."""
import json
from pathlib import Path

from django.test import SimpleTestCase

from core.mojplaywin_views import PRODUCTS


MANIFEST = Path(__file__).resolve().parents[1] / "catalog" / "mojplaywin" / "atelier-interior-kit-v1.json"


class AtelierPreviewTests(SimpleTestCase):
    def test_card_is_an_external_demo_not_a_checkout(self):
        matching = [p for p in PRODUCTS if p["title"].startswith("Atelier Interior")]
        self.assertEqual(len(matching), 1)
        card = matching[0]
        self.assertTrue(card["url"].startswith("https://atelier-interior-kit-demo."))
        self.assertEqual(card["external"], True)
        self.assertIn("preview", card["availability_note"].lower())
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
