"""Prepare the two real MojPlayWin books without enabling or accepting payments.

Never modifies existing products from other sites. No live import occurs unless
an isolated staging operator explicitly opts in. New products remain inactive
until final private-delivery/payment checks have passed.
"""
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import Product
from core.mojplaywin_discount_books import DISCOUNT_BOOKS


def private_file_ok(root, filename):
    if not root:
        return False
    root_path = Path(root)
    if not root_path.is_absolute() or root_path.is_symlink() or not root_path.is_dir():
        return False
    rel = Path(filename)
    if rel.is_absolute() or ".." in rel.parts or rel.suffix.lower() != ".pdf":
        return False
    root_path = root_path.resolve()
    path = (root_path / rel).resolve()
    try:
        return (
            path.is_relative_to(root_path) and path.is_file()
            and not path.is_symlink()
            and 50_000 < path.stat().st_size < 80_000_000
        )
    except OSError:
        return False


class Command(BaseCommand):
    help = "Preview/import approved two-book MojPlayWin discounted products in an isolated staging database only."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Requires isolated staging opt-in; does not publish.")

    def handle(self, *args, **opts):
        root = getattr(settings, "MOJPLAYWIN_PRIVATE_ASSET_ROOT", "")
        for book in DISCOUNT_BOOKS:
            self.stdout.write(
                f"{book['sku']}: regular_usd={book['original_usd']}, "
                f"sale_usd={book['sale_usd']}, savings_usd={book['savings_usd']}, "
                f"discount={book['discount_percent']}%, "
                f"private_file_ready={str(private_file_ok(root, book['private_pdf'])).lower()}"
            )
        if not opts["apply"]:
            self.stdout.write("DRY_RUN: no products or offers created; payments remain disabled.")
            return
        if os.environ.get("MOJPLAYWIN_ISOLATED_BOOK_STAGE") != "1":
            raise CommandError("Only a verified MojPlayWin isolated staging deployment can import products.")
        for book in DISCOUNT_BOOKS:
            if not private_file_ok(root, book["private_pdf"]):
                raise CommandError("Approved private PDF unavailable. No changes made.")
        # Imported rows are deliberately INACTIVE and have NO checkout offers.
        # A separate reviewed deployment must activate only MojPlayWin offers.
        with transaction.atomic():
            for book in DISCOUNT_BOOKS:
                found = list(Product.objects.select_for_update().filter(
                    metadata__mojplaywin_book_sku=book["sku"]
                ))
                if len(found) > 1:
                    raise CommandError("Duplicate MojPlayWin product identifiers; no changes made.")
                meta = {
                    "mojplaywin_book_sku": book["sku"],
                    "mojplaywin_exclusive": True,
                    "original_price_usd": str(book["original_usd"]),
                    "discount_usd": str(book["savings_usd"]),
                    "discount_percent": book["discount_percent"],
                    "private_file": book["private_pdf"],
                    "payment_activation_reviewed": False,
                }
                if found:
                    product = found[0]
                    if product.active:
                        raise CommandError("A product is already active; refusing to modify it.")
                    if product.owner_id is not None or product.knowledge_article_id is not None:
                        raise CommandError("An existing product has external ownership/dependencies.")
                    product.title = book["title"]
                    product.price = book["sale_usd"]
                    product.currency = "USD"
                    product.product_type = "ebook"
                    product.metadata = meta
                    product.save(update_fields=["title", "price", "currency", "product_type", "metadata", "updated_at"])
                else:
                    Product.objects.create(
                        title=book["title"], price=book["sale_usd"],
                        currency="USD", product_type="ebook",
                        active=False, metadata=meta,
                    )
        self.stdout.write("STAGED: two MojPlayWin products remain inactive; payment is NOT enabled.")
