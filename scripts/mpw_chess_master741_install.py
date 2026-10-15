#!/usr/bin/env python3
"""Strictly private, SHA-256-pinned handoff for the 741-page MojPlayWin chess manuscript.

Never publishes the product, enables payment or changes third-party sites.
The source must already exist in cPanel's PRIVATE uploads directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

ROOT = Path("/home/zomorod2")
SOURCE = ROOT / "MojPlayWin_Private_Uploads" / "MojPlayWin_Chess_Master_Editorial_Working.pdf"
PRIVATE_ROOT = ROOT / "MojPlayWin_Private_Assets"
RELATIVE = Path("store/chess-improvement/MojPlayWin_Chess_Master_Editorial_Working_741p.pdf")
TARGET = PRIVATE_ROOT / RELATIVE
EXPECTED_SIZE = 5_285_095
EXPECTED_SHA256 = "fbe687e6ef947b827bf524fe32c3a23cae6618424134ac4ac3f1c3d094290cfb"


def verify(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("PRIVATE_PDF_MISSING_OR_SYMLINK")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != EXPECTED_SIZE:
        raise ValueError("PRIVATE_PDF_SIZE_OR_TYPE_MISMATCH")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("INVALID_PDF_MAGIC")
        stream.seek(0)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != EXPECTED_SHA256:
        raise ValueError("PRIVATE_PDF_SHA256_MISMATCH")
    return digest.hexdigest()


def _secure_parents():
    if PRIVATE_ROOT.is_symlink() or not PRIVATE_ROOT.is_dir():
        raise ValueError("PRIVATE_ASSET_ROOT_UNSAFE")
    for part in (PRIVATE_ROOT / "store", PRIVATE_ROOT / "store/chess-improvement"):
        if part.is_symlink():
            raise ValueError("PRIVATE_ASSET_PARENT_SYMLINK")
        part.mkdir(mode=0o700, exist_ok=True)
        if not part.is_dir() or part.is_symlink():
            raise ValueError("PRIVATE_ASSET_PARENT_INVALID")


def install_file():
    verified = verify(SOURCE)
    _secure_parents()
    if TARGET.exists() or TARGET.is_symlink():
        if verify(TARGET) == verified:
            print("MPW_MASTER741_PRIVATE_ALREADY_PRESENT=YES")
            return verified
        raise ValueError("REFUSE_TO_OVERWRITE_PRIVATE_BOOK")
    fd, temporary = tempfile.mkstemp(prefix=".master741-", dir=str(TARGET.parent))
    try:
        with SOURCE.open("rb") as src, os.fdopen(fd, "wb") as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        os.chmod(temporary, 0o600)
        if verify(Path(temporary)) != verified:
            raise ValueError("PRIVATE_COPIED_SHA256_MISMATCH")
        os.replace(temporary, TARGET)
        print("MPW_MASTER741_PRIVATE_ASSET_INSTALLED=YES")
        return verified
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def bind_unpublished_draft(digest):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    from django.apps import apps
    from django.conf import settings
    from django.db import transaction
    django.setup()
    if settings.DEBUG is not False:
        raise RuntimeError("PRODUCTION_DJANGO_REQUIRED")
    for flag in ("MPW_COMMERCE_RELEASE_READY", "MPW_COMMERCE_INVOICING_ENABLED",
                 "MPW_COMMERCE_SETTLEMENT_ENABLED", "MPW_COMMERCE_DOWNLOADS_ENABLED"):
        if getattr(settings, flag, False) is True:
            raise RuntimeError("PUBLIC_COMMERCE_MUST_BE_DISABLED")
    Product = apps.get_model("core", "Product")
    with transaction.atomic():
        product = Product.objects.select_for_update().select_related("knowledge_article").get(pk=72)
        if product.active or product.owner_id is None or product.knowledge_article_id is None:
            raise RuntimeError("PRODUCT_72_DRAFT_OWNER_AND_ARTICLE_REQUIRED")
        if product.knowledge_article.published:
            raise RuntimeError("PRODUCT_ARTICLE_MUST_REMAIN_PRIVATE")
        if str(product.price) != "7.50" or product.currency != "USD" or product.product_type != "digital_book":
            raise RuntimeError("PRODUCT_IDENTITY_PRICE_CHANGED")
        metadata = dict(product.metadata) if isinstance(product.metadata, dict) else {}
        config = dict(metadata.get("mpw_commerce", {}))
        if config.get("enabled") is True:
            raise RuntimeError("PUBLIC_PURCHASE_ALREADY_ENABLED")
        prior = config.get("private_file")
        valid_prior = ("store/chess-improvement/MojPlayWin_Chess_Grandmaster_Final_Covered_2026.pdf",
                       str(RELATIVE))
        if prior not in valid_prior:
            raise RuntimeError("UNKNOWN_OR_CONFLICTING_PRODUCT_ASSET_REFERENCE")
        # Preserve prior book in its private directory: this is an additive versioned import.
        config.update({"enabled": False, "fulfillment": "digital",
                       "private_file": str(RELATIVE)})
        metadata.update({
            "mpw_commerce": config,
            "asset_verified": True,
            "asset_sha256": digest,
            "asset_size_bytes": EXPECTED_SIZE,
            "manuscript_page_count": 741,
            "quality_approved": False,
            "license_verified": False,
            "factory_publication_permission": False,
            "mpw_book72_release_hold": "independent_chess_engine_editorial_and_mainnet_sale_evidence_required",
        })
        if product.metadata != metadata:
            backup_dir = ROOT / ".mpw-book72-private-rollback"
            if backup_dir.is_symlink():
                raise RuntimeError("BACKUP_DIRECTORY_SYMLINK")
            backup_dir.mkdir(mode=0o700, exist_ok=True)
            fd, backup_tmp = tempfile.mkstemp(prefix="741-prebind-", suffix=".json", dir=str(backup_dir))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump({"product_id": product.pk, "metadata": product.metadata,
                               "active": product.active, "owner_id": product.owner_id,
                               "knowledge_id": product.knowledge_article_id}, handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(backup_tmp, 0o600)
            except BaseException:
                if os.path.exists(backup_tmp): os.unlink(backup_tmp)
                raise
            product.metadata = metadata
            product.full_clean()
            product.save(update_fields=["metadata", "updated_at"])
        assert product.active is False and product.metadata["mpw_commerce"]["enabled"] is False
        assert product.knowledge_article.published is False
    print("MPW_MASTER741_PRIVATE_DRAFT_BOUND=YES")
    print("MPW_MASTER741_PUBLIC_SALES_ENABLED=NO")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.status == args.install:
        parser.error("Choose exactly one of --status and --install")
    if args.status:
        print("MPW_MASTER741_INCOMING_PRESENT=" + ("YES" if SOURCE.is_file() and not SOURCE.is_symlink() else "NO"))
        print("MPW_MASTER741_PRIVATE_INSTALLED=" + ("YES" if TARGET.is_file() and not TARGET.is_symlink() else "NO"))
        return
    if os.getuid() != 0 and os.environ.get("USER", "") != "zomorod2":
        raise RuntimeError("EXPECTED_CPANEL_ACCOUNT_REQUIRED")
    digest = install_file()
    bind_unpublished_draft(digest)


if __name__ == "__main__":
    main()
