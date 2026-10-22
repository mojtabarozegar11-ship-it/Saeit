from decimal import Decimal
from types import SimpleNamespace

import pytest

from scripts.mpw_crown_catalog_seed import (
    SPECS, _expected_metadata, _matching_products, _public_check,
    _validate_existing, create_catalogue,
)
from core.models import Product


def test_specs_are_unique_usd_and_safe_prices():
    skus = [item[0] for item in SPECS]
    assert len(skus) == len(set(skus)) == 5
    assert all(Decimal("4.00") <= price <= Decimal("20.00") for _, _, price in SPECS)
    assert all(not _expected_metadata(sku)["rights_cleared"]
               and not _expected_metadata(sku)["crown_checkout_verified"] for sku in skus)


@pytest.mark.django_db
def test_idempotent_seeding_and_unverified_purchase_gate():
    first = create_catalogue(Product)
    assert len(first) == 5
    assert create_catalogue(Product) == {}
    assert Product.objects.filter(product_type="game_cosmetic").count() == 5
    report = _public_check(Product)
    assert report["available"] is False
    assert report["sku_prices"]["cd-spectre"] == "4.99"


@pytest.mark.django_db
def test_existing_unrelated_products_are_untouched():
    unrelated = Product.objects.create(
        title="Unrelated", product_type="book", currency="USD", price="31.00",
        active=True, metadata={"notes": "keep"},
    )
    create_catalogue(Product)
    unrelated.refresh_from_db()
    assert unrelated.metadata == {"notes": "keep"}
    assert unrelated.price == Decimal("31.00")


@pytest.mark.django_db
@pytest.mark.parametrize("damage", ["duplicate", "wrong_price", "wrong_type", "inactive"])
def test_existing_conflicts_fail_closed_without_mutation(damage):
    sku, title, price = SPECS[0]
    Product.objects.create(title=title, product_type="game_cosmetic", price=price,
        currency="USD", active=True, metadata=_expected_metadata(sku))
    p = Product.objects.get(metadata__crown_sku=sku)
    if damage == "duplicate":
        Product.objects.create(title=title, product_type="game_cosmetic", price=price,
            currency="USD", active=True, metadata=_expected_metadata(sku))
    elif damage == "wrong_price":
        p.price = Decimal("0.01"); p.save()
    elif damage == "wrong_type":
        p.product_type = "book"; p.save()
    else:
        p.active = False; p.save()
    before = Product.objects.count()
    with pytest.raises(RuntimeError, match="CROWN_CATALOG_SAFE_ABORT"):
        create_catalogue(Product)
    assert Product.objects.count() == before
