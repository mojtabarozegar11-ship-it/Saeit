"""Public service descriptions must never imply an authorized charge or trade."""
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import Client, TestCase, override_settings

from core.models import MojPropRequest
from core.mojprop_catalog_contract import public_service_catalog


class MojPropServiceOfferContractTests(TestCase):
    def test_all_four_routes_have_exactly_one_real_selling_sample(self):
        offers = public_service_catalog()
        self.assertEqual(len(offers), 4)
        self.assertEqual(
            {row["route"] for row in offers},
            {route for route, _ in MojPropRequest.ROUTE_CHOICES},
        )
        for row in offers:
            with self.subTest(row=row["route"]):
                path = (Path(settings.BASE_DIR) / "templates/moj-prop-v4"
                        / row["sample_url"].removeprefix("/moj-prop/")
                        / "index.html")
                self.assertTrue(path.is_file(), str(path))
                self.assertEqual(row["central_service_agent"], "mojtaba.bot.ai")
                self.assertFalse(row["checkout_enabled"])
                self.assertFalse(row["automated_trading_enabled"])
                self.assertGreater(row["indicative_from_usd"], 0)

    @override_settings(ALLOWED_HOSTS=["localhost", "127.0.0.1", "mojplaywin.com"])
    def test_real_https_csrf_endpoint_advertises_only_approved_routes(self):
        response = Client().get(
            "/moj-prop-intake/", secure=True, HTTP_HOST="mojplaywin.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service_catalog"], public_service_catalog())
        self.assertTrue(response.json()["csrf_token"])
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_companion_digital_sku_inquiry_does_not_disable_four_service_get(self):
        # PR #2362 introduces a real, unpriced product inquiry: a different
        # request category, never a fifth marketed paid service.
        with patch.object(MojPropRequest, "ROUTE_CHOICES", (
            *MojPropRequest.ROUTE_CHOICES,
            ("digital", "Digital product purchase inquiry"),
        )):
            offers = public_service_catalog()
            self.assertEqual({offer["route"] for offer in offers},
                             {"blueprint", "signals", "brief", "audit"})
            self.assertEqual(len(offers), 4)
            self.assertFalse(any(offer["checkout_enabled"] for offer in offers))

    def test_unreviewed_new_route_still_fails_closed(self):
        with patch.object(MojPropRequest, "ROUTE_CHOICES", (
            *MojPropRequest.ROUTE_CHOICES,
            ("live_trading", "Auto trading without consent"),
        )):
            with self.assertRaisesRegex(RuntimeError, "route contract differ"):
                public_service_catalog()

    def test_mislabeled_digital_inquiry_fails_closed(self):
        with patch.object(MojPropRequest, "ROUTE_CHOICES", (
            *MojPropRequest.ROUTE_CHOICES,
            ("digital", "Fake instant product checkout"),
        )):
            with self.assertRaisesRegex(RuntimeError, "route contract differ"):
                public_service_catalog()

    def test_catalog_does_not_hold_undisclosed_wallet_or_order_capability(self):
        offers = public_service_catalog()
        for row in offers:
            self.assertNotIn("receiver", row)
            self.assertNotIn("wallet", row)
            self.assertNotIn("tx_id", row)
            self.assertEqual(row["offer_status"], "written_quote_required")

    def test_public_catalog_matches_all_four_html_links(self):
        html = (Path(settings.BASE_DIR) / "templates/moj-prop-v4/catalog/index.html").read_text("utf-8")
        for row in public_service_catalog():
            self.assertIn('href="' + row["sample_url"] + '"', html)
