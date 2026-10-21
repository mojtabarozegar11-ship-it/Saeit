#!/usr/bin/env python3
"""Owner-authorized, single-record INACTIVE Atelier product registration.

Purpose: one isolated, transactionally inserted Product record after exact ZIP
hash and owner checks. Never enables public checkout, payment, paid downloads,
routing or Passenger restart. No database schema updates or existing row edits.
The idempotent new record can be removed later only after separate approval.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import zipfile
from decimal import Decimal
from pathlib import Path

APP = Path("/home/zomorod2/Saeit-staging")
PRIVATE = Path("/home/zomorod2/.private_mojplaywin_digital_products")
ARCHIVE = PRIVATE / "atelier-interior-kit-v1-repacked.zip"
SHA256 = "98bffad4ccf36f84c7924ca77e4a8b473b42f33a8fce4d85cefe2367afc097aa"
SKU = "atelier-interior-kit-v1"
TITLE = "Atelier Interior — Client-Ready Website Kit"
REGULAR = Decimal("17.00")
SALE = Decimal("6.80")


def validate_stock():
    if APP.is_symlink() or not (APP / "manage.py").is_file():
        raise RuntimeError("Expected Django application missing")
    if PRIVATE.is_symlink() or not PRIVATE.is_dir() or PRIVATE.stat().st_mode & 0o077:
        raise RuntimeError("Private delivery directory unavailable")
    if ARCHIVE.is_symlink() or not ARCHIVE.is_file() or ARCHIVE.stat().st_mode & 0o077:
        raise RuntimeError("Private delivery asset permission mismatch")
    if not 1000 < ARCHIVE.stat().st_size < 15_000_000:
        raise RuntimeError("Private digital stock size invalid")
    h = hashlib.sha256()
    with ARCHIVE.open("rb") as handle:
        for block in iter(lambda: handle.read(131072), b""):
            h.update(block)
    if h.hexdigest() != SHA256:
        raise RuntimeError("Private stock SHA256 mismatch")
    with zipfile.ZipFile(ARCHIVE) as z:
        names = z.namelist()
        if len(names) != 11 or z.testzip() is not None:
            raise RuntimeError("Private stock ZIP corruption")
        if not set(("index.html", "styles.css", "app.js", "config.js", "README.md")).issubset(names):
            raise RuntimeError("Private stock ZIP missing required files")


def intended_metadata():
    return {
        "sku": SKU,
        "product_id": SKU,
        "author": "Mojtaba Roozegar",
        "format": "ZIP",
        "language": "en",
        "slug": "atelier-interior-client-ready-website-kit",
        "short_description": "Responsive interior design studio website kit with editable identity, portfolio and WhatsApp lead handoff.",
        "regular_price": "17.00",
        "discount_percentage": 60,
        "private_file": str(ARCHIVE),
        "sha256": SHA256,
        "asset_verified": True,
        "license_verified": False,
        "quality_approved": False,
        "factory_publication_permission": False,
        "checkout_enabled": False,
        "payment_live": False,
        "sales_enabled": False,
        "owner_approved_inactive_registration": "2026-10-21",
        "in_stock": False,
        "rights_review_status": "independent_evidence_pending",
        "mpw_commerce": {
            "enabled": False,
            "fulfillment": "digital",
            "main_host_only": True,
            "private_file": str(ARCHIVE),
            "filename": ARCHIVE.name,
            "sha256": SHA256,
        },
        "catalog_state": "private_native_draft_no_public_sales",
    }


def main():
    if os.environ.get('ATELIER_INACTIVE_OWNER_APPROVAL') != '2026-10-21':
        raise PermissionError('Owner-scoped inactive-only permission missing')
    validate_stock()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    import django
    django.setup()
    from core.models import Product
    from django.db import transaction
    ref = list(Product.objects.filter(pk__in=(72, 225)).values_list("id", "owner_id"))
    if len(ref) != 2 or any(owner is None for _, owner in ref) or ref[0][1] != ref[1][1]:
        raise RuntimeError("Existing native commercial ownership not independently matched")
    owner = ref[0][1]
    wanted = intended_metadata()
    with transaction.atomic():
        found = list(Product.objects.select_for_update().filter(title=TITLE)[:3])
        if len(found) > 1:
            raise RuntimeError("Ambiguous existing Atelier title; no mutation")
        if found:
            p = found[0]
            m = p.metadata if isinstance(p.metadata, dict) else {}
            if not (m.get("sku") == SKU and p.currency == "USD"
                    and p.price == SALE and p.owner_id == owner
                    and p.active is False and m.get("sha256") == SHA256
                    and m.get("checkout_enabled") is False
                    and m.get("mpw_commerce", {}).get("enabled") is False):
                raise RuntimeError("Existing native record diverges; never overwrite")
            state = "already_registered_without_mutation"
        else:
            fields = {f.name for f in Product._meta.get_fields() if getattr(f, "concrete", False)}
            kwargs = dict(title=TITLE, product_type="website_template", price=SALE,
                          currency="USD", active=False, owner_id=owner, metadata=wanted)
            if "factory_managed" in fields:
                kwargs["factory_managed"] = False
            p = Product(**kwargs)
            p.full_clean()
            p.save(force_insert=True)
            state = "new_inactive_draft_created"
        product_id = p.pk
    v = Product.objects.get(pk=product_id)
    if v.active or v.price != SALE or v.currency != "USD":
        raise RuntimeError("Native draft verification failed")
    print("ATELIER_NATIVE_COMMERCE_DRAFT=" + json.dumps({
        "id": product_id, "sku": SKU, "state": state,
        "price_usd": str(v.price), "regular_usd": str(REGULAR),
        "discount_percent": 60, "private_sha_verified": True,
        "checkout_enabled": False, "payment_live": False,
        "public_sales_enabled": False, "live_site_templates_changed": False,
    }, sort_keys=True))


def selftest():
    m = intended_metadata()
    assert SALE == REGULAR * Decimal("0.40")
    assert m["owner_approved_inactive_registration"] == "2026-10-21"
    assert m["mpw_commerce"]["enabled"] is False
    assert m["checkout_enabled"] is False and m["payment_live"] is False
    assert m["license_verified"] is False
    assert SHA256 == m["sha256"]
    print("ATELIER_INACTIVE_DRAFT_SELFTEST=PASS")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit(2)
