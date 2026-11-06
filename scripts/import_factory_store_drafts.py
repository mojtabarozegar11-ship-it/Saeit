#!/usr/bin/env python3
"""Import ONE verified private factory receipt as an INACTIVE Django draft.

Technical acceptance lets an owner prepare a private listing. It is NOT a
commercial-quality approval. Only the separately guarded publisher may
authorize a public listing. This importer never publishes, creates orders,
changes payments or modifies non-factory products.
"""
import argparse
from decimal import Decimal
import importlib.util
import json
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


def selected_receipt(root, recipe, digest):
    """Require a conscious, exact-version selection; never import a backlog."""
    if not isinstance(recipe, str) or not NAME.fullmatch(recipe):
        raise RuntimeError("EXACT_FACTORY_RECIPE_REQUIRED")
    if not isinstance(digest, str) or not HEX.fullmatch(digest):
        raise RuntimeError("EXACT_FACTORY_SHA256_REQUIRED")
    directory = root / "receipts" / recipe
    receipt = directory / (digest + ".json")
    if directory.is_symlink() or not directory.is_dir() or receipt.is_symlink() or not receipt.is_file():
        raise RuntimeError("SELECTED_PRIVATE_RECEIPT_NOT_FOUND")
    return recipe, digest


def verify_target(app, document_root):
    app = Path(app).expanduser()
    document_root = Path(document_root).expanduser()
    if app.is_symlink() or document_root.is_symlink():
        raise RuntimeError("STOREFRONT_PATH_SYMLINK_REJECTED")
    app = app.resolve()
    document_root = document_root.resolve()
    if not app.is_dir() or not (app / "manage.py").is_file():
        raise RuntimeError("DJANGO_APP_NOT_VERIFIED")
    if document_root.name != "mojplaywin.com":
        raise RuntimeError("UNVERIFIED_MOJPLAYWIN_DOCROOT")
    wsgi = document_root / "passenger_wsgi.py"
    if not wsgi.is_file() or wsgi.is_symlink():
        raise RuntimeError("STOREFRONT_PASSENGER_NOT_VERIFIED")
    # Passenger mapping is currently established only for MojPlayWin.
    if "Saeit-staging" not in wsgi.read_text(encoding="utf-8"):
        raise RuntimeError("STOREFRONT_TARGET_MISMATCH")
    return app


def import_receipts(root, app, document_root, owner_username=None, *, apply=False,
                    sole_owner=False, recipe=None, digest=None):
    root = Path(root).expanduser()
    if root.is_symlink():
        raise RuntimeError("PRIVATE_INBOX_SYMLINK_REJECTED")
    root = root.resolve()
    app = verify_target(app, document_root)
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError("PRIVATE_INBOX_NOT_VERIFIED")
    if not owner_username and not sole_owner:
        raise RuntimeError("OWNER_IDENTITY_REQUIRED")
    recipe, digest = selected_receipt(root, recipe, digest)
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
    created, unchanged, examined = 0, 0, 0
    for recipe, digest in [(recipe, digest)]:
        if not verifier.status(root, recipe, digest):
            raise RuntimeError("STOREFRONT_RECEIPT_INTEGRITY_FAILED")
        manifest_path = root / "packages" / recipe / (digest + ".json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        title = str(manifest.get("name") or "").strip()
        if not title or len(title) > 300:
            raise RuntimeError("PRODUCT_TITLE_INVALID")
        if not HEX.fullmatch(digest) or not NAME.fullmatch(recipe):
            raise RuntimeError("PRODUCT_REFERENCE_INVALID")
        examined += 1
        # Portable JSONField lookup in modern Django/MySQL and supported SQLite.
        already = Product.objects.filter(metadata__factory_bridge_sha256=digest).first()
        if already:
            existing_meta = already.metadata if isinstance(already.metadata, dict) else {}
            if (existing_meta.get("factory_origin") != "saeit_vps"
                    or existing_meta.get("factory_recipe") != recipe
                    or already.owner_id != owner.pk):
                raise RuntimeError("FACTORY_SHA_ALREADY_OWNED_BY_DIFFERENT_PRODUCT")
            unchanged += 1
            continue
        if not apply:
            continue
        with transaction.atomic():
            already = Product.objects.select_for_update().filter(
                metadata__factory_bridge_sha256=digest
            ).first()
            if already:
                existing_meta = already.metadata if isinstance(already.metadata, dict) else {}
                if (existing_meta.get("factory_origin") != "saeit_vps"
                        or existing_meta.get("factory_recipe") != recipe
                        or already.owner_id != owner.pk):
                    raise RuntimeError("FACTORY_SHA_ALREADY_OWNED_BY_DIFFERENT_PRODUCT")
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
                "factory_software_qa_scope": "private_archive_integrity_only",
                "factory_quality_1000_verified": False,
                "factory_chatgpt_final_review": "pending_independent_review",
                "factory_factual_and_market_qa": "pending",
                "factory_license_review": "pending",
                "factory_publication_permission": False,
                "factory_commercial_release": False,
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
            "dry_run": not apply, "publications": 0,
            "commercial_quality_approved": False}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--inbox", required=True)
    p.add_argument("--app", required=True)
    p.add_argument("--document-root", required=True)
    p.add_argument("--owner-username")
    p.add_argument("--sole-active-superuser", action="store_true")
    p.add_argument("--recipe", required=True, help="One exact, private factory recipe")
    p.add_argument("--sha256", required=True, help="Exact SHA-256 of its private ZIP")
    p.add_argument("--apply", action="store_true")
    options = p.parse_args(argv)
    result = import_receipts(
        options.inbox, options.app, options.document_root,
        options.owner_username, apply=options.apply,
        sole_owner=options.sole_active_superuser,
        recipe=options.recipe, digest=options.sha256
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
