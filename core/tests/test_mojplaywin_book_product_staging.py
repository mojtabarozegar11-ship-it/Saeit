"""A staged book must never silently unlock payments or change sibling sites."""
from pathlib import Path
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from core.models import Product
from core.mojplaywin_discount_books import DISCOUNT_BOOKS


@pytest.fixture
def book_folder(tmp_path):
    for book in DISCOUNT_BOOKS:
        path = tmp_path / book["private_pdf"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.7\n" + b"synthetic-fixture-" * 4000)
    return tmp_path


@pytest.mark.django_db
def test_discount_book_import_is_dry_run_without_opt_in(book_folder):
    with override_settings(MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(book_folder)):
        output = StringIO()
        call_command("mojplaywin_prepare_discount_books", stdout=output)
        assert "DRY_RUN" in output.getvalue()
    assert Product.objects.count() == 0


@pytest.mark.django_db
def test_book_staging_requires_explicit_isolation(book_folder, monkeypatch):
    monkeypatch.delenv("MOJPLAYWIN_ISOLATED_BOOK_STAGE", raising=False)
    with override_settings(MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(book_folder)):
        with pytest.raises(CommandError, match="isolated"):
            call_command("mojplaywin_prepare_discount_books", "--apply")
    assert Product.objects.count() == 0


@pytest.mark.django_db
def test_book_stage_creates_only_two_inactive_products_idempotently(book_folder, monkeypatch):
    monkeypatch.setenv("MOJPLAYWIN_ISOLATED_BOOK_STAGE", "1")
    with override_settings(MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(book_folder)):
        call_command("mojplaywin_prepare_discount_books", "--apply", stdout=StringIO())
        ids = list(Product.objects.values_list("pk", flat=True).order_by("pk"))
        assert len(ids) == 2
        call_command("mojplaywin_prepare_discount_books", "--apply", stdout=StringIO())
        assert list(Product.objects.values_list("pk", flat=True).order_by("pk")) == ids
    expected = {item["sku"]: item for item in DISCOUNT_BOOKS}
    for p in Product.objects.all():
        assert p.active is False
        assert p.currency == "USD"
        assert p.price == expected[p.metadata["mojplaywin_book_sku"]]["sale_usd"]
        assert p.metadata["payment_activation_reviewed"] is False
        assert p.metadata["private_file"] == expected[p.metadata["mojplaywin_book_sku"]]["private_pdf"]


@pytest.mark.django_db
def test_missing_private_file_aborts_entire_book_import(book_folder, monkeypatch):
    monkeypatch.setenv("MOJPLAYWIN_ISOLATED_BOOK_STAGE", "1")
    (book_folder / DISCOUNT_BOOKS[1]["private_pdf"]).unlink()
    with override_settings(MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(book_folder)):
        with pytest.raises(CommandError, match="PDF unavailable"):
            call_command("mojplaywin_prepare_discount_books", "--apply")
    assert Product.objects.count() == 0
