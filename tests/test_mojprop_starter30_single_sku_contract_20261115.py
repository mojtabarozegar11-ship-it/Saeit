"""Fail closed if parallel cycles give one Starter30 SKU two products/prices.

Static assertions only. This module sends no HTTP requests, mail, payments,
TRX transactions, trading orders or customer data anywhere.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "templates/moj-prop-v4"
# The educational purchase proposal is archived as a source-only test
# fixture. The active homepage is exclusively the real funded Plan1 prelaunch.
HOME = ROOT / "tests/fixtures/mojprop-starter30-home-before-plan1-20261117.html"
ACTIVE_HOME = SITE / "index.html"
CATALOG = SITE / "catalog/index.html"
DETAIL = SITE / "starter-30-trx/index.html"
CANONICAL = ROOT / "docs/mojprop/starter30-first-product-release.md"
ARCHIVED = ROOT / "content/mojprop/starter-30-trx-delivery-manual-v1.md"
QUOTE = ROOT / "core/mojprop_offer_draft.py"


class Starter30SingleSkuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = HOME.read_text(encoding="utf-8")
        cls.catalog = CATALOG.read_text(encoding="utf-8")
        cls.detail = DETAIL.read_text(encoding="utf-8")
        cls.contract = CANONICAL.read_text(encoding="utf-8")
        cls.archived = ARCHIVED.read_text(encoding="utf-8")

    def test_real_funded_home_does_not_reissue_historical_education_sku(self):
        actual = ACTIVE_HOME.read_text("utf-8")
        self.assertIn("MOJ-PROP-01", actual)
        self.assertNotIn("MOJPROP-STARTER30", actual)
        self.assertNotIn("starter-30-trx", actual)
        self.assertIn("No wallet or payment collection now.", actual)

    def test_one_educational_ten_session_service_not_funded_prop_challenge(self):
        self.assertIn("Ten consecutive self-reported sessions", self.contract)
        self.assertIn("journal guidance/template", self.contract)
        self.assertIn("deterministic risk report", self.contract)
        self.assertIn("30 native TRX", self.contract)
        self.assertIn("10 self-reported simulated sessions", self.catalog)
        self.assertIn("10-session self-reported simulation journal", self.home)
        self.assertIn("Ten-session journal template", self.detail)
        self.assertNotIn("two-page", self.home.lower())
        self.assertNotIn("two-page", self.catalog.lower())
        self.assertNotIn("two-page", self.detail.lower())

    def test_public_catalog_exactly_one_starter30_card_with_unpayable_amount(self):
        marker = '<article class="card" id="starter-30">'
        self.assertEqual(self.catalog.count(marker), 1)
        starter = self.catalog.split(marker, 1)[1].split("</article>", 1)[0]
        self.assertIn("30 native TRX", starter)
        self.assertIn("Not payable yet", starter)
        self.assertNotIn("US$149", starter)
        self.assertIn("package=starter-30-trx#request", starter)
        self.assertIn("30 TRX", self.detail)
        self.assertIn("Payment not enabled", self.detail)

    def test_single_consent_based_crm_route_and_no_unmarked_149_dollar_quote(self):
        for page in (self.home, self.catalog, self.detail):
            self.assertIn("package=starter-30-trx#request", page)
        self.assertNotIn("mailto:", self.detail)
        code = QUOTE.read_text(encoding="utf-8")
        self.assertIn("MOJPROP-STARTER30", code)
        self.assertIn("Price WITHHELD: ambiguous Starter30", code)
        self.assertIn("Requested Starter30 reference: 30 native TRX INDICATIVE", code)
        self.assertIn("Payment: DISABLED", code)

    def test_archived_two_page_plan_is_never_canonical_30_trx(self):
        self.assertTrue(self.archived.startswith("# ⚠️ ARCHIVED NONCANONICAL DESIGN"))
        self.assertIn("NOT FOR BUYER OFFER OR FULFILMENT", self.archived)
        self.assertIn("**not** the unique sellable 30 TRX Starter30", self.archived)
        self.assertIn("as historical research", self.archived)
        self.assertIn("10-session simulated trading journal", self.archived)

    def test_existing_free_signals_remain_separate_not_starter_or_paid(self):
        self.assertIn("freeTierRequested", self.home)
        self.assertIn("Requested free educational example:", self.home)
        self.assertIn("No automatic newsletter, payment or signal delivery", self.home)
        self.assertIn("starterRequested=requestedService==='blueprint'", self.home)
        self.assertIn("MOJPROP-STARTER30", self.home)

    def test_no_wallet_key_trading_or_payment_in_starter_detail(self):
        lower = self.detail.lower()
        for blocked in ("<script", "tronweb", "walletconnect", "private key", "send trx now"):
            self.assertNotIn(blocked, lower)
        self.assertIn("Do not send TRX", self.detail)
        self.assertIn("No funded account is included", self.detail)


if __name__ == "__main__":
    unittest.main()
