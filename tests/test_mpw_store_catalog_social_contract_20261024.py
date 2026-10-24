"""Read-only storefront discovery and social metadata contract.

No network, credentials, orders, invoice reservations, or payment mutations.
This is a template/source regression suite; it is NOT a real payment test.
"""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "core/templates/mojplaywin/store.html"
BASE = ROOT / "core/templates/mojplaywin/site_base.html"
VIEWS = ROOT / "core/mojplaywin_views.py"


def featured_products():
    tree = ast.parse(VIEWS.read_text(encoding="utf-8"))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "PRODUCTS"
            for target in statement.targets
        ):
            return ast.literal_eval(statement.value)
    raise AssertionError("PRODUCTS literal not found")


class MojPlayWinStoreContracts(unittest.TestCase):
    def test_buyer_catalog_has_exact_live_product_details(self):
        catalog = featured_products()
        items = {item["title"]: item for item in catalog}
        self.assertEqual(
            items["Atelier Interior — Client-Ready Website Kit"]["url"],
            "/store/product/879/",
        )
        self.assertTrue(
            items["Atelier Interior — Client-Ready Website Kit"]["image_url"].startswith(
                "https://mojplaywin.com/static/"
            )
        )
        self.assertEqual(len(items), len(catalog))
        self.assertNotIn(
            "checkout and paid download are not yet available",
            str(catalog),
        )

    def test_store_keeps_kit_details_separate_from_purchase(self):
        html = STORE.read_text(encoding="utf-8")
        self.assertIn('href="/store/product/879/"', html)
        self.assertNotIn('href="/store/product/879/checkout/"', html)
        for sku in (72, 225):
            self.assertIn(f'href="/store/product/{sku}/checkout/"', html)
        self.assertIn("Sign in or create an account", html)

    def test_store_overrides_social_metadata_without_duplicate_tags(self):
        base = BASE.read_text(encoding="utf-8")
        store = STORE.read_text(encoding="utf-8")
        for key in ("og_title", "og_description"):
            self.assertIn("{% block " + key + " %}", base)
            self.assertIn("{% block " + key + " %}", store)
        self.assertEqual(base.count('<meta property="og:title"'), 1)
        self.assertEqual(base.count('<meta property="og:description"'), 1)
        self.assertIn("Digital Store | MojPlayWin", store)


if __name__ == "__main__":
    unittest.main()
