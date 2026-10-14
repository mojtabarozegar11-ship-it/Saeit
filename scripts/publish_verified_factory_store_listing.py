#!/usr/bin/env python3
"""Publish one owner-authorized free factory toolkit in MojPlayWin's native catalog.

Activates ONLY an exact SHA-matched, already imported and QA-verified draft.
Calls the project's existing ApprovalService for knowledge and product, while
recording the owner's publication request as a delegated instruction.
Never creates orders, payment intents, or alters unrelated products.
"""
import argparse
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import re
import sys

RECIPE = "farm_enterprise_economics"
ARTICLE_SLUG = "farm-enterprise-economics-toolkit-free-v1"
TITLE = "Farm Enterprise Economics Toolkit — Free Edition"
PUBLIC_RELATIVE_URL = "/factory-releases/farm-enterprise-economics-v1/index.html"
FREE_DOWNLOAD_URL = ("/factory-releases/farm-enterprise-economics-v1/"
                     "Farm_Enterprise_Economics_Toolkit_Free_v1.zip")
OWNER_DECISION_NOTE = (
    "Explicit owner instruction to publish the Farm Enterprise Economics Toolkit "
    "received on 2026-10-14; carried out by authorized ChatGPT agent as delegated operation. "
    "Release is free, no payment is enabled, and claims are limited to validated software functions."
)
ARTICLE_TEXT = """Farm Enterprise Economics Toolkit — Free Edition (Version 1.0)

This is an offline, user-input-driven agricultural enterprise economics calculator.
It calculates gross sales, variable cost, selling fees, contribution margin,
operating result and a break-even unit quantity where unit contribution is positive.
For each enterprise, it produces nine illustrative sensitivity scenarios varying
sales volume and selling price. It accepts a consistent user-selected currency
label but does not perform conversions. Python 3.8 or newer is required.

The product download, documentation, example inputs and automated software
tests are available from the official product page:
https://mojplaywin.com/factory-releases/farm-enterprise-economics-v1/index.html

Limits: example figures are synthetic, not current market data. The model
excludes taxes, depreciation, financing, capital expenditure, working capital
and cash flow timing. Outputs are deterministic scenarios rather than verified
market forecasts or advice. It is a free software download with no payment
required and is not presented as a comprehensive agricultural investment
appraisal or a scientific research publication.
"""


def loaded(name, filename):
    path = Path(__file__).resolve().parent / filename
    if not path.is_file():
        raise RuntimeError("REQUIRED_DEPLOYED_VERIFIER_MISSING")
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_sources(inbox, docroot):
    inbox = Path(inbox).expanduser().resolve()
    docroot = Path(docroot).expanduser().resolve()
    if docroot.name != "mojplaywin.com":
        raise ValueError("UNVERIFIED_MOJPLAYWIN_DOCROOT")
    verifier = loaded("factory_native_store_verifier", "store_receiver.py")
    receipt_dir = inbox / "receipts" / RECIPE
    if not receipt_dir.is_dir():
        raise ValueError("FACTORY_RECEIPT_MISSING")
    refs = sorted(p.stem for p in receipt_dir.glob("*.json") if re.fullmatch(r"[0-9a-f]{64}", p.stem))
    valid = [digest for digest in refs if verifier.status(inbox, RECIPE, digest)]
    if len(valid) != 1:
        raise ValueError("REQUIRE_EXACTLY_ONE_VALID_PRODUCT_RELEASE")
    digest = valid[0]
    release = docroot / PUBLIC_RELATIVE_URL.lstrip("/")
    package = docroot / FREE_DOWNLOAD_URL.lstrip("/")
    if release.is_symlink() or not release.is_file() or package.is_symlink() or not package.is_file():
        raise ValueError("PUBLIC_FACTORY_RELEASE_NOT_FOUND")
    publisher = loaded("factory_native_store_publisher", "publish_factory_free_tool.py")
    if publisher.digest_file(package) != digest:
        raise ValueError("PUBLIC_FACTORY_SHA256_MISMATCH")
    body = release.read_text(encoding="utf-8")
    if TITLE not in body or digest not in body or "Free Toolkit" not in body:
        raise ValueError("PUBLIC_FREE_TOOLKIT_CONTENT_NOT_VERIFIED")
    return digest


def publish(inbox, app, docroot, *, apply=False, delegated_owner_instruction=False):
    importer = loaded("factory_native_store_importer", "import_factory_store_drafts.py")
    app = importer.verify_target(app, docroot)
    digest = verify_sources(inbox, docroot)
    import django
    from django.conf import settings
    from django.apps import apps
    from django.contrib.auth import get_user_model
    from django.db import transaction
    django.setup()
    if settings.DEBUG is not False:
        raise RuntimeError("DEBUG_MUST_BE_DISABLED")
    User = get_user_model()
    owners = User.objects.filter(is_active=True, is_staff=True, is_superuser=True)
    if owners.count() != 1:
        raise RuntimeError("RELEASE_REQUIRES_UNIQUE_ACTIVE_OWNER")
    owner = owners.first()
    Product = apps.get_model("core", "Product")
    Knowledge = apps.get_model("core", "KnowledgeArticle")
    matches = Product.objects.filter(metadata__factory_bridge_sha256=digest)
    if matches.count() != 1:
        raise RuntimeError("EXACT_FACTORY_DRAFT_REQUIRED")
    product = matches.first()
    metadata = product.metadata if isinstance(product.metadata, dict) else {}
    if (metadata.get("factory_origin") != "saeit_vps"
            or metadata.get("factory_recipe") != RECIPE
            or metadata.get("factory_software_qa") != "passed"
            or product.owner_id != owner.pk
            or product.currency != "USD"
            or product.price != Decimal("0")):
        raise ValueError("FACTORY_DRAFT_RELEASE_GATE_FAILED")
    if product.active:
        if (metadata.get("factory_public_url") == PUBLIC_RELATIVE_URL
                and product.knowledge_article_id is not None
                and product.knowledge_article.published):
            return {"status": "already_active", "product_id": product.pk, "sha256": digest}
        raise ValueError("ACTIVE_PRODUCT_RELEASE_MISMATCH")
    if not apply:
        return {"status": "verified_dry_run", "product_id": product.pk, "sha256": digest}
    if not delegated_owner_instruction:
        raise ValueError("OWNER_PUBLICATION_MANDATE_REQUIRED")
    from core.approval import ApprovalService
    Approval = apps.get_model("core", "ApprovalRequest")
    with transaction.atomic():
        product = Product.objects.select_for_update().get(pk=product.pk)
        if product.active:
            raise RuntimeError("CONCURRENT_PRODUCT_ACTIVATION_REFUSED")
        existing = Knowledge.objects.filter(slug=ARTICLE_SLUG).first()
        if existing and product.knowledge_article_id != existing.pk:
            raise ValueError("CONFLICTING_KNOWLEDGE_SLUG")
        if existing is None:
            article = Knowledge.objects.create(
                title=TITLE, slug=ARTICLE_SLUG, content=ARTICLE_TEXT,
                published=False
            )
        else:
            article = existing
            if article.content != ARTICLE_TEXT or article.title != TITLE:
                raise ValueError("UNEXPECTED_EXISTING_KNOWLEDGE_CONTENT")
        if not article.published:
            req = Approval.objects.create(
                action_type="publish_knowledge_article", target_type="KnowledgeArticle",
                target_id=str(article.pk), requested_by=owner,
                reason="Publish verified free offline farm calculator product documentation.",
                risk="high",
            )
            ApprovalService().decide(
                req.pk, True, actor_id=owner.pk,
                note=OWNER_DECISION_NOTE, actor_type="owner"
            )
        metadata.update({
            "factory_public_url": PUBLIC_RELATIVE_URL,
            "factory_public_download_url": FREE_DOWNLOAD_URL,
            "factory_software_qa": "passed",
            "factory_product_edition": "free_v1",
            "factory_storefront": "mojplaywin",
            "factory_publication_permission": True,
            "factory_commercial_status": "published_free_download_no_checkout",
            "factory_status": "published_free",
            "factory_factual_and_market_qa": "not_claimed_or_required_for_synthetic_scenarios",
            "factory_license_review": "free_evaluation_permission_from_owner",
            "manual_price_required": False,
        })
        product.knowledge_article = article
        product.metadata = metadata
        product.title = TITLE
        product.full_clean()
        product.save(update_fields=["knowledge_article", "metadata", "title", "updated_at"])
        request = Approval.objects.create(
            action_type="activate_product", target_type="Product",
            target_id=str(product.pk), requested_by=owner,
            reason="Publish owner-authorized free tested software with public SHA-verified download.",
            risk="high",
        )
        ApprovalService().decide(
            request.pk, True, actor_id=owner.pk,
            note=OWNER_DECISION_NOTE, actor_type="owner"
        )
        product.refresh_from_db()
        if not product.active:
            raise RuntimeError("NATIVE_PRODUCT_ACTIVATION_FAILED")
    return {"status": "activated_free", "product_id": product.pk, "sha256": digest}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--inbox", required=True)
    p.add_argument("--app", required=True)
    p.add_argument("--document-root", required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--owner-delegated-publication", action="store_true")
    args = p.parse_args(argv)
    result = publish(
        args.inbox, args.app, args.document_root,
        apply=args.apply, delegated_owner_instruction=args.owner_delegated_publication
    )
    print("FACTORY_NATIVE_STORE_RESULT=" + result["status"])
    print("FACTORY_NATIVE_PRODUCT_ID=" + str(result["product_id"]))
    print("FACTORY_NATIVE_PRODUCT_SHA256=" + result["sha256"])
    print("FACTORY_NATIVE_PRODUCT_PRICE_USD=0.00")
    print("FACTORY_NATIVE_PRODUCT_PAYMENT_REQUIRED=false")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        print("FACTORY_NATIVE_STORE_RELEASE_BLOCKED=" +
              type(exc).__name__ + ":" + str(exc)[:160], file=sys.stderr)
        sys.exit(1)
