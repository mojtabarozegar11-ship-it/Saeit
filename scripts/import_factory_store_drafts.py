#!/usr/bin/env python3
"""Import verified private cPanel factory receipts as INACTIVE Django draft products.

The importer is strictly opt-in and idempotent. It never makes products
purchasable, publishes knowledge, creates orders, changes payments or touches
an existing non-factory product. Reject wrong storefront/owner identity.
"""
import argparse
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

HEX = re.compile(r"^[0-9a-f]{64}$")
NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def receiver_module():
    path = Path(__file__).resolve().parent / "store_receiver.py"
    if not path.is_file():
        raise RuntimeError("PRIVATE_RECEIVER_MISSING")
    spec = importlib.util.spec_from_file_location("saeit_verified_store_receiver", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def catalog_receipts(root, *, max_count=20):
    receipts = root / "receipts"
    if not receipts.is_dir():
        return []
    candidate = []
    for folder in sorted(receipts.iterdir()):
        if not folder.is_dir() or folder.is_symlink() or not NAME.fullmatch(folder.name):
            continue
        for item in sorted(folder.glob("*.json")):
            if item.is_symlink() or not HEX.fullmatch(item.stem):
                continue
            candidate.append((folder.name, item.stem))
            if len(candidate) >= max_count:
                return candidate
    return candidate


def verify_target(app, document_root):
    app = Path(app).expanduser().resolve()
    document_root = Path(document_root).expanduser().resolve()
    if not app.is_dir() or not (app / "manage.py").is_file():
        raise RuntimeError("DJANGO_APP_NOT_VERIFIED")
    wsgi = document_root / "passenger_wsgi.py"
    if not wsgi.is_file() or wsgi.is_symlink():
        raise RuntimeError("STOREFRONT_PASSENGER_NOT_VERIFIED")
    # Passenger mapping is currently established only for MojPlayWin.
    if "Saeit-staging" not in wsgi.read_text(encoding="utf-8"):
        raise RuntimeError("STOREFRONT_TARGET_MISMATCH")
    return app


def import_receipts(root, app, document_root, owner_username=None, *, apply=False, sole_owner=False):
    root = Path(root).expanduser().resolve()
    app = verify_target(app, document_root)
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError("PRIVATE_INBOX_NOT_VERIFIED")
    if not owner_username and not sole_owner:
        raise RuntimeError("OWNER_IDENTITY_REQUIRED")
    import django
    from django.conf import settings
    django.setup()
    if settings.DEBUG is not False:
        raise RuntimeError("PRODUCTION_DEBUG_MUST_BE_FALSE")
    from django.contrib.auth import get_user_model
    from django.apps import apps
    from django.db import transaction
    User = get_user_model()
    eligible = User.objects.filter(is_active=True, is_staff=True, is_superuser=True)
    if owner_username:
        owner = eligible.filter(**{User.USERNAME_FIELD: owner_username}).first()
    else:
        if eligible.count() != 1:
            raise RuntimeError("SOLE_ACTIVE_SUPERUSER_NOT_UNIQUE")
        owner = eligible.first()
    if owner is None:
        raise RuntimeError("IDENTIFIED_STORE_OWNER_NOT_PRESENT")
    Product = apps.get_model("core", "Product")
    verifier = receiver_module()
    quality_path = Path(__file__).resolve().with_name(
        "factory_commercial_quality_release_guard_v1.py"
    )
    if quality_path.is_symlink() or not quality_path.is_file():
        raise RuntimeError("STORE_FINAL_QUALITY_REVIEW_GUARD_MISSING")
    quality_spec = importlib.util.spec_from_file_location(
        "factory_store_final_quality_guard", str(quality_path)
    )
    if quality_spec is None or quality_spec.loader is None:
        raise RuntimeError("STORE_FINAL_QUALITY_REVIEW_GUARD_UNAVAILABLE")
    quality_guard = importlib.util.module_from_spec(quality_spec)
    quality_spec.loader.exec_module(quality_guard)
    created, unchanged, examined = 0, 0, 0
    for recipe, digest in catalog_receipts(root):
        if not verifier.status(root, recipe, digest):
            raise RuntimeError("STOREFRONT_RECEIPT_INTEGRITY_FAILED")
        manifest_path = root / "packages" / recipe / (digest + ".json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        package_path = root / "packages" / recipe / (digest + ".zip")
        clearance = quality_guard.require_quality_clearance(
            root, recipe, digest, manifest, package_path
        )
        if (clearance.get("status") != "VERIFIED_SIGNED_PREMIUM_1000"
                or clearance.get("1000_quality_verified") is not True
                or clearance.get("chatgpt_final_review") != "CHATGPT_FINAL_REVIEW_VERIFIED"):
            raise RuntimeError("STORE_BLOCKED_UNTIL_CHATGPT_AND_QC1000_APPROVE")
        title = str(manifest.get("name") or "").strip()
        if not title or len(title) > 300:
            raise RuntimeError("PRODUCT_TITLE_INVALID")
        if not HEX.fullmatch(digest) or not NAME.fullmatch(recipe):
            raise RuntimeError("PRODUCT_REFERENCE_INVALID")
        examined += 1
        # Portable JSONField lookup in modern Django/MySQL and supported SQLite.
        already = Product.objects.filter(metadata__factory_bridge_sha256=digest).first()
        if already:
            unchanged += 1
            continue
        if not apply:
            continue
        with transaction.atomic():
            already = Product.objects.select_for_update().filter(
                metadata__factory_bridge_sha256=digest
            ).first()
            if already:
                unchanged += 1
                continue
            metadata = {
                "factory_origin": "saeit_vps",
                "factory_bridge_sha256": digest,
                "factory_recipe": recipe,
                "factory_archive_private": True,
                "factory_storefront": "mojplaywin",
                "factory_status": "needs_editorial_pricing_and_owner_approval",
                "factory_software_qa": "passed",
                "factory_quality_1000_verified": True,
                "factory_chatgpt_final_review": "approved_for_store",
                "factory_chatgpt_reviewer": "ChatGPT (Codex)",
                "factory_chatgpt_review_receipt": (
                    "quality-clearance/" + recipe + "/" + digest
                    + "/chatgpt-final-review.json"
                ),
                "factory_factual_and_market_qa": "pending",
                "factory_license_review": "pending",
                "factory_publication_permission": False,
                "factory_inbox_relative_ref": "packages/" + recipe + "/" + digest + ".zip",
                "manual_price_required": True,
                "source_type": "offline_software_package",
            }
            args = {
                "title": title, "product_type": "digital", "price": Decimal("0"),
                "currency": "USD", "active": False, "owner": owner,
                "knowledge_article": None, "metadata": metadata
            }
            if any(field.name == "factory_managed" for field in Product._meta.fields):
                args["factory_managed"] = True
            obj = Product(**args)
            obj.full_clean()
            obj.save()
            created += 1
    return {"examined": examined, "created": created, "already_present": unchanged,
            "dry_run": not apply, "publications": 0}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--inbox", required=True)
    p.add_argument("--app", required=True)
    p.add_argument("--document-root", required=True)
    p.add_argument("--owner-username")
    p.add_argument("--sole-active-superuser", action="store_true")
    p.add_argument("--apply", action="store_true")
    options = p.parse_args(argv)
    result = import_receipts(
        options.inbox, options.app, options.document_root,
        options.owner_username, apply=options.apply,
        sole_owner=options.sole_active_superuser
    )
    for key, value in result.items():
        print("STORE_DRAFT_" + key.upper() + "=" + str(value))
    print("STORE_DRAFT_PRODUCTS_PUBLIC=false")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        print("STORE_DRAFT_IMPORT_BLOCKED=" + type(exc).__name__ + ":" + str(exc)[:150],
              file=sys.stderr)
        sys.exit(1)
