"""Narrow source-only regression for MojPlayWin main storefront product discovery.

No database, network, checkout activation, shared deployment, or tenant changes.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / "core" / "mojplaywin_views.py"
TEMPLATE = ROOT / "core" / "templates" / "mojplaywin" / "store.html"


def _catalog():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "PRODUCTS"
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("MojPlayWin initial catalog was not found")


def test_two_existing_books_link_to_verified_public_product_pages():
    products = _catalog()
    expected = {
        "The Science and Practice of Chess Improvement": (72, "/store/product/72/"),
        "Taniya and the Little Baker Worms": (225, "/store/product/225/"),
    }
    assert len(products) == 6
    book_cards = {p["title"]: (p.get("product_id"), p["url"])
                  for p in products if "product_id" in p}
    assert book_cards == expected
    assert all(p["url"].startswith("/store/product/") for p in products
               if "product_id" in p)


def test_other_four_collections_are_still_nontransactional():
    products = _catalog()
    previews = [p for p in products if "product_id" not in p]
    assert len(previews) == 4
    assert {p["title"] for p in previews} == {
        "Farm Enterprise Economics Toolkit",
        "Applied AI Learning Path",
        "Original Browser Games",
        "Research & Digital Project Services",
    }
    assert all("/checkout/" not in p["url"] for p in previews)


def test_store_explains_actual_checkout_requirement_without_claiming_payment():
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "{% if product.product_id %}" in template
    assert "View product price &amp; checkout information" in template
    assert "current checkout requires a customer account" in template
    assert "a live checkout is not confirmed for this card" in template
    assert "an order-specific invoice" in template
    assert "mpw_managed_offers.html" in template
    assert "store_ten_buyer_guides_20261018.html" in template
    assert "Buy now" not in template
    assert "Buy securely" not in template
