#!/usr/bin/env python3
"""Read-only PLT product 879 commercial chain audit on the existing cPanel Django app.

Never create orders/invoices, query raw transaction IDs, disclose customer data,
trigger chain settlement, enable payment, or change production files/DB.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

APP = Path("/home/zomorod2/Saeit-staging")
SITE = Path("/home/zomorod2/mojplaywin.com")
ARTIFACT = Path("/home/zomorod2/.private_mojplaywin_digital_products/atelier-interior-kit-v1-repacked.zip")
EXPECTED_SHA = "98bffad4ccf36f84c7924ca77e4a8b473b42f33a8fce4d85cefe2367afc097aa"
EXPECTED_TITLE = "Atelier Interior — Client-Ready Website Kit"
EXPECTED_SKU = "atelier-interior-kit-v1"
PRODUCT_ID = 879

def scoped():
    wsgi = SITE / "passenger_wsgi.py"
    try:
        return (APP.is_dir() and not APP.is_symlink()
                and SITE.is_dir() and not SITE.is_symlink()
                and wsgi.is_file() and not wsgi.is_symlink()
                and "APP='/home/zomorod2/Saeit-staging'" in wsgi.read_text("utf-8", "replace"))
    except OSError:
        return False

def archive_verified():
    try:
        if (not ARTIFACT.is_file() or ARTIFACT.is_symlink()
                or ARTIFACT.parent.is_symlink()
                or not 1000 <= ARTIFACT.stat().st_size <= 15_000_000):
            return False
        digest = hashlib.sha256()
        with ARTIFACT.open("rb") as source:
            for block in iter(lambda: source.read(131072), b""):
                digest.update(block)
        return digest.hexdigest() == EXPECTED_SHA
    except OSError:
        return False

def route_resolves(path):
    from django.urls import resolve
    try:
        return resolve(path).func is not None
    except Exception:
        return False

def worker_exists():
    worker = Path("/home/zomorod2/.private_mojplaywin_main_agents/mpw_commerce_live_inbound_reconciler.py")
    return worker.is_file() and not worker.is_symlink() and not worker.parent.is_symlink()

def scheduler_present():
    try:
        out = subprocess.run(["crontab", "-l"], timeout=7, capture_output=True, text=True, check=False)
        if out.returncode:
            return False
        marker = "# MPW_TWO_BOOKS_INBOUND_RECONCILER_20261019"
        entries = [line for line in out.stdout.splitlines() if marker in line]
        return len(entries) == 1 and entries[0].lstrip().startswith("* * * * * ") and "flock -n " in entries[0]
    except (OSError, subprocess.TimeoutExpired):
        return False

def main():
    flags = {
        "verified_main_tenant": scoped(),
        "private_zip_integrity": False,
        "exact_product_879": False,
        "sale_price_6_80_usd": False,
        "approved_native_product": False,
        "buyer_checkout_route": False,
        "commerce_invoice_models": False,
        "status_and_download_routes": False,
        "incoming_chain_reconciler_command": False,
        "incoming_chain_reconciler_installed": False,
        "incoming_chain_reconciler_scheduled": False,
        "receiver_enabled": False,
        "verified_live_tx_settlement_and_download": False,
        "verified_full_backup_restore": False,
    }
    if flags["verified_main_tenant"]:
        flags["private_zip_integrity"] = archive_verified()
        flags["incoming_chain_reconciler_installed"] = worker_exists()
        flags["incoming_chain_reconciler_scheduled"] = scheduler_present()
        try:
            os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
            os.chdir(APP)
            sys.path.insert(0, str(APP))
            import django
            django.setup()
            from django.conf import settings
            from django.apps import apps
            from django.core.management import get_commands
            from core.models import Product
            products = list(Product.objects.filter(pk=PRODUCT_ID)[:2])
            if len(products) == 1:
                product = products[0]
                meta = product.metadata if isinstance(product.metadata, dict) else {}
                cfg = meta.get("mpw_commerce") if isinstance(meta.get("mpw_commerce"), dict) else {}
                flags["exact_product_879"] = (product.title == EXPECTED_TITLE and meta.get("sku") == EXPECTED_SKU)
                flags["sale_price_6_80_usd"] = (product.currency == "USD" and str(product.price) in ("6.8", "6.80"))
                flags["approved_native_product"] = bool(
                    product.active and cfg.get("enabled") is True
                    and cfg.get("fulfillment") == "digital"
                    and all(meta.get(k) is True for k in (
                        "asset_verified", "license_verified", "quality_approved",
                        "factory_publication_permission"))
                )
            flags["buyer_checkout_route"] = route_resolves(f"/store/product/{PRODUCT_ID}/checkout/")
            flags["status_and_download_routes"] = all(route_resolves(path) for path in (
                "/commerce/checkout/status/1/", "/commerce/download/1/"))
            # A native invoice can point to core.Order rather than a separate
            # CommerceOrder class. Validate the actual Django relation.
            try:
                invoice_cls = apps.get_model("mpw_commerce", "CommerceInvoice")
                order_field = invoice_cls._meta.get_field("order")
                flags["commerce_invoice_models"] = bool(
                    (order_field.many_to_one or order_field.one_to_one)
                    and order_field.related_model is not None
                    and hasattr(order_field.related_model, "_meta")
                )
            except (LookupError, AttributeError, ValueError):
                flags["commerce_invoice_models"] = False
            flags["incoming_chain_reconciler_command"] = "mpw_commerce_reconcile" in get_commands()
            flags["receiver_enabled"] = (
                getattr(settings, "MOJ_COMMERCE_RECEIVER_ENABLED", False) is True
            )
        except Exception as exc:
            # Only exception class; never disclose DB credentials, paths or buyer details.
            flags["django_probe_completed"] = False
            flags["django_error_class"] = type(exc).__name__
        else:
            flags["django_probe_completed"] = True
    # Verified mainnet payment and isolated FULL restore require independent receipts.
    # Neither may be inferred from model flags, mock transactions, or this read-only probe.
    mandatory = [k for k in flags if k not in (
        "verified_live_tx_settlement_and_download", "verified_full_backup_restore",
        "receiver_enabled", "django_error_class", "django_probe_completed")]
    passed = all(flags.get(k) is True for k in mandatory)
    result = {
        "classification": "PLT_879_COMMERCIAL_CHAIN_READ_ONLY",
        "product_id": PRODUCT_ID,
        "checks": flags,
        "source_contract_ready": passed,
        "release_authorized": False,
        "live_payment_and_delivery_certified": False,
        "missing_gates": [name for name in mandatory if flags.get(name) is not True],
        "writes": 0,
        "real_payment_sent": False,
    }
    print("PLT_879_CHAIN_AUDIT=" + json.dumps(result, sort_keys=True))
    return 0

def selftest():
    assert PRODUCT_ID == 879
    assert EXPECTED_SHA == "98bffad4ccf36f84c7924ca77e4a8b473b42f33a8fce4d85cefe2367afc097aa"
    assert "/home/zomorod2/.private_mojplaywin_digital_products" in str(ARTIFACT)
    print("PLT_879_CHAIN_AUDIT_SELFTEST=PASS")

if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        selftest()
    elif not sys.argv[1:]:
        raise SystemExit(main())
    else:
        raise SystemExit("use selftest or no arguments")
