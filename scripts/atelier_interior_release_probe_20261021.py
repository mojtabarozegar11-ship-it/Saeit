#!/usr/bin/env python3
"""Read-only evidence probe for the exact existing Atelier Interior commercial ZIP.

Runs via the owner-approved GitHub Actions -> VPS relay -> cPanel connection.
No database, site, private file, checkout, or payment mutations are performed.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

SKU = "atelier-interior-kit-v1"
TITLE = "Atelier Interior — Client-Ready Website Kit"
SHA256 = "98bffad4ccf36f84c7924ca77e4a8b473b42f33a8fce4d85cefe2367afc097aa"
SALE_PRICE = "6.80"
REGULAR_PRICE = "17.00"
ARCHIVE_NAME = "atelier-interior-kit-v1-repacked.zip"
ROOT = Path("/home/zomorod2")
APP = ROOT / "Saeit-staging"
SITE = ROOT / "mojplaywin.com"
# Only explicitly limited private directories: no home-wide scans or public hosting paths.
PRIVATE_FOLDERS = (
    ROOT / ".private_mojplaywin_main_agents",
    ROOT / ".private_mojplaywin_digital_products",
    ROOT / ".private_mojplaywin_products",
    APP / ".private_products",
)
REQUIRED = frozenset(("index.html", "styles.css", "app.js", "config.js", "README.md"))


def safe_zip(raw):
    """Reject traversal, symlinks, duplicate ZIP members and ZIP bombs."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members = z.infolist()
            if not 5 <= len(members) <= 200:
                return False
            names = set()
            total = 0
            for entry in members:
                name = entry.filename
                path = PurePosixPath(name)
                if not name or name.startswith("/") or "\\" in name or ":" in name:
                    return False
                if ".." in path.parts or "." in path.parts:
                    return False
                if name in names:
                    return False
                names.add(name)
                if (entry.external_attr >> 16) & 0o170000 == stat.S_IFLNK:
                    return False
                if entry.flag_bits & 1:
                    return False
                total += entry.file_size
                if entry.file_size > 12_000_000 or total > 60_000_000:
                    return False
                if entry.compress_size and entry.file_size > 150 * max(1, entry.compress_size):
                    return False
            if not REQUIRED.issubset(names):
                return False
            if not any(n.startswith("assets/") and n.lower().endswith((".jpg", ".png", ".webp")) for n in names):
                return False
            if z.testzip() is not None:
                return False
            html = z.read("index.html")
            js = z.read("app.js")
            cfg = z.read("config.js")
            return (b'whatsapp' in (html + js).lower()
                    and b'ATELIER_CONFIG' in cfg
                    and (b'gallery' in (html + js).lower() or b'project-grid' in html.lower()))
    except (zipfile.BadZipFile, OSError, ValueError, RuntimeError, KeyError):
        return False


def archive_candidates():
    """Never follow symlinked private directory or archive."""
    for parent in PRIVATE_FOLDERS:
        if parent.is_symlink() or not parent.is_dir() or parent.parent.is_symlink():
            continue
        candidate = parent / ARCHIVE_NAME
        if candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            size = candidate.stat().st_size
            if 1_000 <= size <= 15_000_000:
                yield candidate
        except OSError:
            continue


def inspect_archive():
    matched = []
    for candidate in archive_candidates():
        try:
            raw = candidate.read_bytes()
            if hashlib.sha256(raw).hexdigest() == SHA256 and safe_zip(raw):
                matched.append(candidate)
        except OSError:
            pass
    return len(matched) == 1, len(matched)


def main():
    checks = {
        "main_app_wiring": False,
        "private_exact_sha_zip": False,
        "zip_complete_and_safe": False,
        "one_native_product": False,
        "owner_selected_sale_price": False,
        "native_paid_delivery_flags": False,
        "exact_private_download_resolves": False,
        "isolated_checkout_route": False,
    }
    try:
        wsgi = SITE / "passenger_wsgi.py"
        if (APP.is_dir() and not APP.is_symlink() and SITE.is_dir()
                and not SITE.is_symlink() and wsgi.is_file()
                and not wsgi.is_symlink()):
            checks["main_app_wiring"] = "APP='/home/zomorod2/Saeit-staging'" in wsgi.read_text("utf-8", "replace")
    except OSError:
        pass
    exact_archive, count = inspect_archive()
    checks["private_exact_sha_zip"] = exact_archive
    checks["zip_complete_and_safe"] = exact_archive
    details = {"private_matching_archives": count, "product_id": None}
    if checks["main_app_wiring"]:
        try:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
            os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
            os.chdir(str(APP))
            sys.path.insert(0, str(APP))
            import django
            django.setup()
            from core.models import Product
            from django.urls import resolve
            # Exactly the SKU+title is eligible; no arbitrary product mutation.
            matches = [
                product for product in Product.objects.filter(title=TITLE)[:3]
                if isinstance(product.metadata, dict) and product.metadata.get("sku") == SKU
            ]
            checks["one_native_product"] = len(matches) == 1
            if len(matches) == 1:
                product = matches[0]
                details["product_id"] = product.pk
                meta = product.metadata
                cfg = meta.get("mpw_commerce")
                checks["owner_selected_sale_price"] = (
                    product.currency == "USD" and str(product.price) in ("6.80", "6.8")
                )
                checks["native_paid_delivery_flags"] = (
                    product.active is True
                    and all(meta.get(flag) is True for flag in (
                        "asset_verified", "license_verified", "quality_approved",
                        "factory_publication_permission"
                    ))
                    and isinstance(cfg, dict)
                    and cfg.get("enabled") is True
                    and cfg.get("fulfillment") == "digital"
                )
                try:
                    from mpw_commerce.fulfillment import _private_file
                    from types import SimpleNamespace
                    p = _private_file(SimpleNamespace(product=product))
                    if isinstance(p, Path) and p.is_file() and not p.is_symlink():
                        checks["exact_private_download_resolves"] = (
                            hashlib.sha256(p.read_bytes()).hexdigest() == SHA256
                        )
                except (ImportError, ValueError, OSError, TypeError, AttributeError):
                    pass
                try:
                    route = resolve("/store/product/{}/checkout/".format(product.pk))
                    checks["isolated_checkout_route"] = route is not None
                except Exception:
                    pass
        except Exception as exc:
            details["runtime_probe_error_type"] = type(exc).__name__
    ready = all(checks.values())
    print("ATELIER_INTERIOR_REAL_READONLY_EVIDENCE=" + json.dumps({
        "sku": SKU, "release_ready": ready, "checks": checks, "details": details,
        "customer_payment_and_download_tested": False,
        "live_site_mutations": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        good = io.BytesIO()
        with zipfile.ZipFile(good, "w") as z:
            for name in sorted(REQUIRED | {"assets/hero.jpg"}):
                z.writestr(name, b"whatsapp project-grid ATELIER_CONFIG")
        assert safe_zip(good.getvalue())
        bad = io.BytesIO()
        with zipfile.ZipFile(bad, "w") as z:
            for name in sorted(REQUIRED | {"assets/hero.jpg", "../escape.html"}):
                z.writestr(name, b"whatsapp project-grid ATELIER_CONFIG")
        assert not safe_zip(bad.getvalue())
        print("ATELIER_INTERIOR_READONLY_SELFTEST=PASS")
    else:
        raise SystemExit(main())
