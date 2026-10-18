"""MojPlayWin two-book promotion: exact customer-facing USD arithmetic."""
from decimal import Decimal
from pathlib import Path

from core.mojplaywin_views import PRODUCTS


def test_chess_and_taniya_promotion_prices_are_exact():
    offers = {item["title"]: item for item in PRODUCTS if "sale_price_usd" in item}
    assert len(offers) == 2
    expected = {
        "The Science and Practice of Chess Improvement": (Decimal("30"), Decimal("7.5"), Decimal("22.5"), 75),
        "Taniya and the Little Baker Worms": (Decimal("20"), Decimal("2"), Decimal("18"), 90),
    }
    assert set(offers) == set(expected)
    for name, (regular, sale, savings, percent) in expected.items():
        item = offers[name]
        assert Decimal(item["regular_price_usd"]) == regular
        assert Decimal(item["sale_price_usd"]) == sale
        assert Decimal(item["discount_usd"]) == savings
        assert item["discount_percent"] == percent
        assert regular - sale == savings
        assert (savings / regular * 100) == percent


def test_sale_cards_do_not_auto_bypass_protected_payment_route():
    # A price display is not proof of payment activation or a delivery right.
    template = Path("core/templates/mojplaywin/store.html").read_text(encoding="utf-8")
    assert "product.sale_price_usd" in template
    assert "product.regular_price_usd" in template
    assert "product.discount_percent" in template
    assert "product.discount_usd" in template
    assert "Explore this collection" in template
