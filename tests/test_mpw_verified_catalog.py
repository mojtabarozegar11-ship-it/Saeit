"""Test real MojPlayWin catalog classification without Django, DB or payments."""
from __future__ import annotations

import importlib.util
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "core/mojplaywin_catalog.py"
SPEC = importlib.util.spec_from_file_location("mpw_safe_catalog", MODULE)
assert SPEC is not None and SPEC.loader is not None
catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog)


def item(*, pk=991, price="0", currency="USD", active=True, metadata=None, published=True):
    return SimpleNamespace(
        pk=pk, title="Verified agricultural tool", product_type="toolkit",
        price=Decimal(price), currency=currency, active=active,
        knowledge_article=SimpleNamespace(published=published),
        metadata={} if metadata is None else metadata,
    )


def free_metadata():
    return {
        "summary": "An original free agricultural tool",
        "factory_origin": "saeit_vps", "factory_storefront": "mojplaywin",
        "factory_status": "published_free",
        "factory_commercial_status": "published_free_download_no_checkout",
        "factory_publication_permission": True, "factory_software_qa": "passed",
        "factory_bridge_sha256": "a" * 64,
        "factory_public_url":
            "/factory-releases/farm-enterprise-economics-v1/index.html",
        "factory_public_download_url":
            "/factory-releases/farm-enterprise-economics-v1/Farm_Enterprise_Economics_Toolkit_Free_v1.zip",
    }


def paid_metadata():
    return {
        "summary": "Independent digital publication",
        "sales_enabled": True, "rights_cleared": True,
        "publication_approved": True,
        "sha256": "a" * 64, "rights_asset_sha256": "a" * 64,
        "rights_document_sha256": "b" * 64,
    }


class VerifiedCatalogTests(unittest.TestCase):
    def test_verified_free_release_can_be_discovered(self):
        card = catalog.catalog_card(item(metadata=free_metadata()), frozenset())
        self.assertIsNotNone(card)
        self.assertEqual(card["price"], "FREE")
        self.assertEqual(
            card["url"],
            "/factory-releases/farm-enterprise-economics-v1/index.html",
        )

    def test_private_or_unapproved_free_release_not_listed(self):
        meta = free_metadata()
        variants = (
            item(metadata=meta, active=False),
            item(metadata=meta, published=False),
            item(metadata=dict(meta, factory_publication_permission=False)),
            item(metadata=dict(meta, factory_software_qa="unverified")),
            item(metadata=dict(meta, factory_bridge_sha256="not-a-digest")),
            item(metadata=dict(meta, factory_status="draft")),
        )
        for product in variants:
            with self.subTest(metadata=product.metadata, active=product.active):
                self.assertIsNone(catalog.catalog_card(product, frozenset()))

    def test_external_path_and_traversal_never_become_links(self):
        meta = free_metadata()
        for bad in (
            "https://attacker.example/factory-releases/file",
            "//attacker.example/factory-releases/file",
            "/factory-releases/../private/secrets.zip",
            "/factory-releases/farm-enterprise-economics-v1/%2e%2e/private.zip",
            "/factory-releases/farm-enterprise-economics-v1/index.html?token=secret",
        ):
            with self.subTest(path=bad):
                altered = dict(meta, factory_public_url=bad)
                self.assertIsNone(catalog.catalog_card(item(metadata=altered), frozenset()))

    def test_mismatched_factory_release_dirs_fail_closed(self):
        meta = dict(free_metadata())
        meta["factory_public_download_url"] = (
            "/factory-releases/some-other-release/else.zip"
        )
        self.assertIsNone(catalog.catalog_card(item(metadata=meta), frozenset()))

    def test_paid_product_must_be_allowed_and_rights_matched(self):
        product = item(price="12.00", metadata=paid_metadata())
        self.assertIsNone(catalog.catalog_card(product, frozenset()))
        card = catalog.catalog_card(product, frozenset((991,)))
        self.assertEqual(card["url"], "/store/product/991/")
        self.assertEqual(card["price"], "12.00 USD")
        altered = dict(paid_metadata(), rights_asset_sha256="c" * 64)
        self.assertIsNone(catalog.catalog_card(
            item(price="12.00", metadata=altered), frozenset((991,))
        ))

    def test_featured_product_is_not_duplicated_in_dynamic_catalog(self):
        for pk in (72, 225, 879):
            with self.subTest(id=pk):
                self.assertIsNone(catalog.catalog_card(
                    item(pk=pk, price="12.00", metadata=paid_metadata()),
                    frozenset((pk,))
                ))

    def test_bad_currencies_and_unpublished_products_do_not_appear(self):
        for product in (
            item(price="12.00", currency="IRR", metadata=paid_metadata()),
            item(price="12.00", active=False, metadata=paid_metadata()),
            item(price="0", metadata={}),
        ):
            self.assertIsNone(catalog.catalog_card(product, frozenset((991,))))

    def test_approved_products_continue_through_multiple_pages(self):
        products = [
            item(pk=1100 - number, price="12.00", metadata=paid_metadata())
            for number in range(70)
        ]
        allowed = frozenset(p.pk for p in products)
        page1, next1 = catalog._page_cards(products, allowed)
        self.assertEqual(len(page1), catalog.PAGE_SIZE)
        self.assertEqual(next1, products[catalog.PAGE_SIZE - 1].pk)
        page2, next2 = catalog._page_cards(
            [p for p in products if p.pk < next1], allowed
        )
        self.assertEqual(len(page2), catalog.PAGE_SIZE)
        self.assertIsNotNone(next2)
        page3, next3 = catalog._page_cards(
            [p for p in products if p.pk < next2], allowed
        )
        self.assertEqual(len(page3), 22)
        self.assertIsNone(next3)
        self.assertEqual(
            len({r["id"] for r in page1 + page2 + page3}), 70
        )

    def test_unapproved_products_do_not_consume_page_slots(self):
        published = [
            item(pk=1100 - i, price="12.00",
                 metadata=paid_metadata() if i % 2 else {})
            for i in range(64)
        ]
        allowed = frozenset(p.pk for p in published)
        first, cursor = catalog._page_cards(published, allowed)
        self.assertEqual(len(first), catalog.PAGE_SIZE)
        self.assertIsNotNone(cursor)
        self.assertTrue(all(r["id"] in allowed for r in first))

    def test_store_has_verified_catalog_keyset_navigation(self):
        source = (ROOT / "core/mojplaywin_views.py").read_text(encoding="utf-8")
        template = (ROOT / "core/templates/mojplaywin/store.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('verified_catalog_cards(before_id=before)', source)
        self.assertIn("catalog_next_id", template)
        self.assertIn("Browse older verified releases", template)
        self.assertIn("Newest verified releases", template)

    def test_store_renders_optional_verified_catalog_without_exposing_customer_data(self):
        source = (ROOT / "core/mojplaywin_views.py").read_text(encoding="utf-8")
        template = (ROOT / "core/templates/mojplaywin/store.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('"verified_catalog":verified', source)
        self.assertIn("except Exception as exc:", source)
        self.assertIn("{% for item in verified_catalog %}", template)
        self.assertIn("{{ item.url }}", template)
        self.assertNotIn("{{ item.metadata }}", template)


if __name__ == "__main__":
    unittest.main()
