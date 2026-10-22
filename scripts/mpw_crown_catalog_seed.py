#!/usr/bin/env python3
"""One-time Crown premium cosmetic catalogue seed, with private reversible receipt.

Five original cosmetics are priced and active for DISCOVERY ONLY. This script
never sets rights_cleared/crown_checkout_verified, enables a payment flag, or
creates an order. The live checkout must remain disabled until independently
proven chain settlement and game entitlement delivery work.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sys

SPECS = (
    ("cd-spectre", "X-22 Spectre · Crown Defender Airframe", Decimal("4.99")),
    ("cd-valkyrie", "V-35 Valkyrie · Crown Defender Airframe", Decimal("5.99")),
    ("cd-tempest", "T-60 Tempest · Crown Defender Airframe", Decimal("7.99")),
    ("cd-phoenix", "P-77 Phoenix · Crown Defender Airframe", Decimal("9.99")),
    ("cd-sovereign", "S-99 Sovereign · Crown Defender Airframe", Decimal("12.99")),
)
STAMP = "crown-prelaunch-20261022"
BACKUPS = Path("/home/zomorod2/.mpw-crown-catalog-receipts")
SKUS = {s[0] for s in SPECS}


def _halt(message):
    raise RuntimeError("CROWN_CATALOG_SAFE_ABORT: " + message)


def _digest(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _expected_metadata(sku):
    return {"crown_sku": sku, "crown_checkout_verified": False,
            "rights_cleared": False, "prelaunch_catalog": STAMP}


def _matching_products(Product):
    result = {sku: [] for sku in SKUS}
    # Inspect all Product rows, including inactive, to catch collisions before
    # writing; no DB-specific JSON path lookup is required.
    for product in Product.objects.only("id", "title", "product_type", "price",
                                        "currency", "active", "metadata").iterator():
        md = product.metadata if isinstance(product.metadata, dict) else {}
        sku = md.get("crown_sku")
        if sku in result:
            result[sku].append(product)
    return result


def _validate_existing(existing):
    for sku, title, price in SPECS:
        rows = existing[sku]
        if len(rows) > 1:
            _halt("Duplicate cosmetic SKU already exists: " + sku)
        if not rows:
            continue
        obj = rows[0]
        if (obj.product_type != "game_cosmetic" or obj.title != title
                or obj.currency != "USD" or obj.price != price or not obj.active):
            _halt("Existing SKU requires manual review, preserving row: " + sku)
        md = obj.metadata if isinstance(obj.metadata, dict) else {}
        if md.get("crown_sku") != sku:
            _halt("Corrupt cosmetic product metadata")
        # Existing approved products are never changed by this seed.


@contextmanager
def _db_lock(connection):
    # MySQL advisory lock serializes even the absent-row creation case.
    # SQLite is allowed only for offline tests, not live deployment.
    if connection.vendor != "mysql":
        _halt("MariaDB connection required for live catalogue mutation")
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 5)", ["mpw-crown-catalog-v1"])
        if cursor.fetchone() != (1,):
            _halt("Could not acquire catalogue advisory lock")
        try:
            yield
        finally:
            cursor.execute("SELECT RELEASE_LOCK(%s)", ["mpw-crown-catalog-v1"])


def create_catalogue(Product):
    """Pure ORM mutation inside caller-owned transaction; returns created ids."""
    existing = _matching_products(Product)
    _validate_existing(existing)
    new_ids = {}
    for sku, title, price in SPECS:
        if existing[sku]:
            continue
        obj = Product.objects.create(
            title=title, product_type="game_cosmetic", currency="USD", price=price,
            active=True, metadata=_expected_metadata(sku),
        )
        new_ids[sku] = obj.pk
    _validate_existing(_matching_products(Product))
    return new_ids


def _public_check(Product):
    existing = _matching_products(Product)
    _validate_existing(existing)
    if any(len(existing[sku]) != 1 for sku in SKUS):
        _halt("Catalogue incomplete")
    from core.crown_fleet import catalogue
    items = catalogue()
    if {i["sku"] for i in items} != SKUS:
        _halt("Game fleet contract differs from catalogue")
    if any(item["available"] or item["checkout"] is not None for item in items):
        _halt("A paid checkout unexpectedly became active")
    expected = {sku: format(price, ".2f") for sku, _, price in SPECS}
    if {i["sku"]: i["price"] for i in items} != expected:
        _halt("Public catalogue prices do not match stored products")
    return {"sku_prices": expected, "available": False}


def _receipt_path(run):
    if not re.fullmatch(r"[0-9]{8,20}", run):
        _halt("Invalid release run identifier")
    if BACKUPS.is_symlink():
        _halt("Unsafe private receipt directory")
    return BACKUPS / (run + ".json")


def _store_receipt(path, document):
    BACKUPS.mkdir(mode=0o700, parents=False, exist_ok=True)
    if BACKUPS.is_symlink() or path.exists() or path.is_symlink():
        _halt("Unsafe or duplicated private release receipt")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(document, out, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _open_receipt(path, run):
    if path.is_symlink() or not path.is_file():
        _halt("Missing private release receipt")
    document = json.loads(path.read_text("utf-8"))
    if document.get("run") != run or document.get("stamp") != STAMP:
        _halt("Receipt identity mismatch")
    ids = document.get("created_ids")
    if not isinstance(ids, dict) or not set(ids).issubset(SKUS) or any(type(pk) is not int or pk <= 0 for pk in ids.values()):
        _halt("Invalid receipt product identifiers")
    check = dict(document)
    digest = check.pop("digest", "")
    if _digest(check) != digest:
        _halt("Receipt has been altered")
    return document


def install(run):
    from django.db import connection, transaction
    from core.models import Product
    path = _receipt_path(run)
    if path.exists():
        _halt("This release run has already been used")
    with _db_lock(connection):
        with transaction.atomic():
            ids = create_catalogue(Product)
            proof = _public_check(Product)
            document = {"run": run, "stamp": STAMP, "created_ids": ids, "proof": proof}
            document["digest"] = _digest(document)
            # Write before commit so a process crash after COMMIT retains a
            # rollback receipt; a pre-commit crash may leave harmless receipt.
            _store_receipt(path, document)
    print("CROWN_CATALOG_CREATED_COUNT=" + str(len(ids)))
    print("CROWN_CATALOG_PRICE_CONTRACT=PASS")
    print("CROWN_CATALOG_PURCHASES_ENABLED=NO")


def verify(run):
    from core.models import Product
    _open_receipt(_receipt_path(run), run)
    _public_check(Product)
    print("CROWN_CATALOG_READBACK=PASS")
    print("CROWN_CATALOG_PURCHASES_ENABLED=NO")


def rollback(run):
    from django.db import connection, transaction
    from core.models import Product, OrderItem
    document = _open_receipt(_receipt_path(run), run)
    with _db_lock(connection), transaction.atomic():
        for sku, pk in document["created_ids"].items():
            p = Product.objects.select_for_update().filter(pk=pk).first()
            if p is None:
                continue
            if (p.metadata != _expected_metadata(sku) or p.product_type != "game_cosmetic"
                    or not p.active or p.currency != "USD"
                    or p.price != dict((s,pr) for s,_,pr in SPECS)[sku]
                    or OrderItem.objects.filter(product=p).exists()):
                _halt("Product changed or has orders; refuse destructive rollback: " + sku)
            p.delete()
    print("CROWN_CATALOG_ROLLBACK=PASS")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("install", "verify", "rollback"):
        _halt("Usage: install|verify|rollback RUN_ID")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    {"install": install, "verify": verify, "rollback": rollback}[sys.argv[1]](sys.argv[2])
