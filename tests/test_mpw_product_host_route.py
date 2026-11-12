"""Executable, Django-independent regression checks for cross-brand product routes.

Exercise the actual unmodified AST function bodies against a minimal fake ORM;
never touch production data, payment services, or network.
"""
from __future__ import annotations

import ast
import json
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from core.mojplaywin_catalog import FEATURED_IDS, catalog_card


SOURCE = Path(__file__).resolve().parents[1] / "core/product_seo_views.py"
TEMPLATE = Path(__file__).resolve().parents[1] / "core/templates/core/product_detail.html"


class NotFound(Exception):
    pass


class FakeProducts:
    def __init__(self, product):
        self.product = product

    def filter(self, *, pk, active):
        product = self.product
        found = (
            product if product is not None
            and product.pk == pk and product.active is active
            else None
        )
        return SimpleNamespace(first=lambda: found)


def load_functions(product, *, checkout_ready=False):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    names = {
        "public_product_url", "public_product_description",
        "storefront_for_host", "approved_guest_checkout_route", "product_detail",
    }
    functions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    assert {node.name for node in functions} == names
    def fake_resolve(path):
        if not checkout_ready:
            raise NotFound
        def product_checkout(request, product_id):
            return None
        product_checkout.__module__ = "services.mpw_trx_guest_commerce"
        product_id = int(path.split("/")[3])
        return SimpleNamespace(
            kwargs={"product_id": product_id}, func=product_checkout,
        )

    namespace = {
        "Http404": NotFound,
        "Resolver404": NotFound,
        "resolve": fake_resolve,
        "bridge_backend_ready": lambda: checkout_ready,
        "settings": SimpleNamespace(MPW_TRX_PUBLIC_PRODUCT_IDS=(72, 225, 879, 991), MPW_WALLETLESS_TRX_PUBLIC_ENABLED=True),
        "FEATURED_IDS": FEATURED_IDS,
        "catalog_card": catalog_card,
        "Product": SimpleNamespace(objects=FakeProducts(product)),
        "json": json,
        "strip_tags": lambda x: x.replace("<", "").replace(">", ""),
        "render": lambda request, template, data: {"template": template, "context": data},
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["product_detail"]


def request(host):
    return SimpleNamespace(get_host=lambda: host)


def item(**changes):
    values = {
        "pk": 72, "active": True, "title": "Original Chess Manual",
        "product_type": "digital_book", "price": Decimal("7.50"),
        "currency": "USD", "metadata": {"summary": "Original learning book"},
    }
    values.update(changes)
    return SimpleNamespace(**values)


class ProductDetailHostTests(unittest.TestCase):
    def test_active_usd_mojplaywin_product_detail_is_not_blocked(self):
        result = load_functions(item())(request("mojplaywin.com"), 72)
        self.assertEqual(result["template"], "core/product_detail.html")
        self.assertTrue(result["context"]["mojplaywin_store"])
        self.assertEqual(
            result["context"]["canonical"],
            "https://mojplaywin.com/store/product/72/",
        )
        self.assertFalse(result["context"]["can_list_offer"])
        self.assertIsNone(result["context"]["checkout_url"])
        self.assertNotIn("offers", json.loads(result["context"]["schema_json"]))

    def test_both_www_and_port_domains_are_supported(self):
        fn = load_functions(item())
        for host in ("www.mojplaywin.com", "mojplaywin.com:443"):
            with self.subTest(host=host):
                self.assertTrue(fn(request(host), 72)["context"]["mojplaywin_store"])

    def test_zomorod_detail_remains_available(self):
        fn = load_functions(item(currency="IRR", price=Decimal("450000")))
        result = fn(request("zomorodmelal.ir"), 72)
        self.assertFalse(result["context"]["mojplaywin_store"])
        self.assertEqual(result["context"]["canonical"],
                         "https://zomorodmelal.ir/store/product/72/")

    def test_unrelated_host_and_wrong_currency_stay_private(self):
        for host, product in (
            ("attacker.example", item()),
            ("mojplaywin.com", item(currency="IRR")),
            ("mojplaywin.com", item(active=False)),
        ):
            with self.subTest(host=host, currency=product.currency, active=product.active):
                with self.assertRaises(NotFound):
                    load_functions(product)(request(host), 72)

    def test_disabled_payment_switch_hides_offer_claims_without_hiding_product(self):
        sha = "a" * 64
        metadata = {
            "rights_cleared": True, "publication_approved": True,
            "sha256": sha, "rights_asset_sha256": sha,
            "rights_document_sha256": "b" * 64,
        }
        product = item(pk=991, metadata=metadata)
        fn = load_functions(product)
        fn.__globals__["settings"].MPW_WALLETLESS_TRX_PUBLIC_ENABLED = False
        response = fn(request("mojplaywin.com"), 991)
        self.assertFalse(response["context"]["can_list_offer"])
        self.assertIsNone(response["context"]["checkout_url"])
        self.assertNotIn("offers", json.loads(response["context"]["schema_json"]))

    def test_approved_guest_checkout_link_requires_real_resolved_handler(self):
        sha = "a" * 64
        metadata = {
            "sales_enabled": True, "rights_cleared": True,
            "publication_approved": True,
            "sha256": sha, "rights_asset_sha256": sha,
            "rights_document_sha256": "b" * 64,
        }
        product = item(pk=991, metadata=metadata)
        no_route = load_functions(product)(request("mojplaywin.com"), 991)
        self.assertTrue(no_route["context"]["can_list_offer"])
        self.assertIsNone(no_route["context"]["checkout_url"])

        ready = load_functions(product, checkout_ready=True)(
            request("mojplaywin.com"), 991
        )
        self.assertEqual(
            ready["context"]["checkout_url"], "/store/product/991/checkout/"
        )

    def test_unreleased_product_never_gets_checkout_link_even_if_url_exists(self):
        product = item(pk=991, metadata={"sales_enabled": True})
        with self.assertRaises(NotFound):
            load_functions(product, checkout_ready=True)(
                request("mojplaywin.com"), 991
            )

    def test_description_without_product_summary_uses_correct_brand(self):
        product = item(metadata={})
        fn = load_functions(product)
        moj = fn(request("mojplaywin.com"), 72)
        zom = fn(request("zomorodmelal.ir"), 72)
        self.assertIn("MojPlayWin", moj["context"]["description"])
        self.assertNotIn("Zomorod Melal", moj["context"]["description"])
        self.assertIn("Zomorod Melal", zom["context"]["description"])

    def test_arbitrary_active_usd_zomorod_product_is_not_leaked(self):
        product = item(pk=101, metadata={"description": "Zomorod only"})
        with self.assertRaises(NotFound):
            load_functions(product)(request("mojplaywin.com"), 101)
        result = load_functions(product)(request("zomorodmelal.ir"), 101)
        self.assertFalse(result["context"]["mojplaywin_store"])

    def test_allowlisted_unfeatured_paid_item_is_visible_only_when_approved(self):
        valid = "a" * 64
        approved = {
            "summary": "Rights-verified digital item",
            "sales_enabled": True, "rights_cleared": True,
            "publication_approved": True,
            "sha256": valid, "rights_asset_sha256": valid,
            "rights_document_sha256": "b" * 64,
        }
        product = item(pk=991, metadata=approved)
        page = load_functions(product)(request("mojplaywin.com"), 991)
        self.assertTrue(page["context"]["mojplaywin_store"])
        self.assertTrue(page["context"]["can_list_offer"])
        denied = item(pk=991, metadata={**approved, "rights_asset_sha256": "c" * 64})
        with self.assertRaises(NotFound):
            load_functions(denied)(request("mojplaywin.com"), 991)

    def test_nonexistent_product_is_never_exposed(self):
        with self.assertRaises(NotFound):
            load_functions(None)(request("mojplaywin.com"), 72)

    def test_rights_and_sale_claim_require_matched_digest(self):
        valid = "a" * 64
        approved = {
            "sales_enabled": True,
            "rights_cleared": True, "publication_approved": True,
            "sha256": valid, "rights_asset_sha256": valid,
            "rights_document_sha256": "b" * 64, "in_stock": True,
        }
        fn = load_functions(item(metadata=approved))
        response = fn(request("mojplaywin.com"), 72)
        self.assertTrue(response["context"]["can_list_offer"])
        self.assertEqual(
            json.loads(response["context"]["schema_json"])["offers"]["price"],
            "7.50",
        )
        altered = dict(approved, rights_asset_sha256="c" * 64)
        response = load_functions(item(metadata=altered))(request("mojplaywin.com"), 72)
        self.assertFalse(response["context"]["can_list_offer"])
        self.assertNotIn("offers", json.loads(response["context"]["schema_json"]))

    def test_mojplaywin_template_has_clear_nonpayable_state(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("{% if mojplaywin_store %}", template)
        self.assertIn("{% if can_list_offer %}", template)
        self.assertIn("A verified checkout is not yet available", template)
        self.assertIn("Continue to secure TRX checkout", template)
        self.assertIn("{% if checkout_url %}", template)
        self.assertIn("بازگشت به فهرست محصولات", template)


if __name__ == "__main__":
    unittest.main()
