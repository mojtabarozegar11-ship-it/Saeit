"""Read-only preflight for the single Grandmaster chess PDF product #72.

This command cannot approve rights, enable products, issue invoices, run a
blockchain transfer, or change payment settings. It gives explicit blockers
based on the live database, exact private deliverable and Django settings.
"""
import hashlib
import json
from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from core.models import Product
from mpw_commerce.downloads import _private_file

PRODUCT_ID = 72
PRODUCT_KEY = "mojplaywin-chess-improvement-2026"
EXPECTED_RELATIVE_PATH = "store/chess-improvement/MojPlayWin_Chess_Grandmaster_Final_Covered_2026.pdf"
EXPECTED_BYTES = 3631972
EXPECTED_SHA256 = "3837fc3cb21ed1a2e7c33e0db8f8e10d158583309b02b97d4d674d25a147207a"
FLAGS = (
    "MPW_COMMERCE_RELEASE_READY",
    "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
    "MPW_COMMERCE_INVOICING_ENABLED",
    "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED",
    "MPW_COMMERCE_SETTLEMENT_ENABLED",
    "MPW_COMMERCE_REAL_RPC_ENABLED",
    "MPW_COMMERCE_AUTORECONCILE_ENABLED",
    "MPW_COMMERCE_DOWNLOADS_ENABLED",
)
PRODUCT_FLAGS = (
    "factory_publication_permission",
    "asset_verified",
    "quality_approved",
    "license_verified",
)


def _verified_file(product):
    try:
        file = _private_file(SimpleNamespace(product=product))
        if file.name != EXPECTED_RELATIVE_PATH.split("/")[-1] or file.stat().st_size != EXPECTED_BYTES:
            return False
        with file.open("rb") as source:
            digest = hashlib.sha256()
            for chunk in iter(lambda: source.read(262144), b""):
                digest.update(chunk)
        return digest.hexdigest() == EXPECTED_SHA256
    except (OSError, ValueError, TypeError):
        return False


def audit():
    """Return safe booleans only: no addresses, buyer IDs or private paths."""
    try:
        product = Product.objects.select_related("knowledge_article").filter(pk=PRODUCT_ID).first()
    except Exception:
        raise  # DB errors are not silently downgraded to a false 'healthy' status.

    meta = product.metadata if product and isinstance(product.metadata, dict) else {}
    commerce = meta.get("mpw_commerce", {})
    if not isinstance(commerce, dict):
        commerce = {}
    checks = {
        "product_exists": product is not None,
        "product_id_matches": meta.get("product_id") == PRODUCT_KEY,
        "product_is_public": bool(product and product.active is True),
        "author_linked": bool(product and product.owner_id is not None),
        "article_published": bool(product and product.knowledge_article_id and
                                  product.knowledge_article.published is True),
        "price_exactly_usd_7_50": bool(product and product.currency == "USD"
                                     and product.price == Decimal("7.50")),
        "owner_rights_self_attested_in_database": meta.get("rights_owner_attested") is True,
        "digital_fulfillment_enabled": commerce.get("enabled") is True
                                        and commerce.get("fulfillment") == "digital",
        "correct_private_asset_mapping": commerce.get("private_file") == EXPECTED_RELATIVE_PATH,
    }
    for flag in PRODUCT_FLAGS:
        checks["product_"+flag] = meta.get(flag) is True
    checks["private_pdf_matches_exact_sha256"] = bool(product and _verified_file(product))

    try:
        checks["checkout_page_route_installed"] = (
            reverse("mpw_commerce:book", kwargs={"product_id":PRODUCT_ID})
            == "/commerce/book/72/"
        )
    except (NoReverseMatch, ImportError):
        checks["checkout_page_route_installed"] = False

    try:
        from mpw_native_checkout.wallet_ownership import proven_assets
        proofs = proven_assets()
    except (ImportError, ValueError, OSError):
        proofs = {}
    for asset in ("ETH", "TRX"):
        checks["merchant_"+asset.lower()+"_proof_verified"] = proofs.get(asset) is True
    for flag in FLAGS:
        checks["setting_"+flag] = getattr(settings, flag, False) is True

    # A passing code/DB audit is not evidence of actual, final mainnet
    # receipts or the uptime of a separately operated reconciliation worker.
    all_technical_checks = all(checks.values())
    return {
        "audit": "mojplaywin_product_72_readonly_go_nogo",
        "product_id": PRODUCT_ID,
        "timestamp_utc": timezone.now().isoformat(),
        "checks": checks,
        "technical_preflight_passed": all_technical_checks,
        "live_mainnet_end_to_end_sale_verified": False,
        "independent_editorial_and_service_terms_review_verified": False,
        "public_paid_sales_go": False,
        "required_before_go": [
            "Resolve every false check with independently verifiable evidence",
            "Confirm live settlement/reconciliation worker and RPC availability",
            "Verify customer login and support/refund terms",
            "Run an explicitly authorized, separately funded real mainnet purchase and buyer-only PDF download",
            "Only then make a separate, reviewed live-payment release decision",
        ],
    }


class Command(BaseCommand):
    help = "Read-only JSON status for MojPlayWin chess book #72; never activates payment."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true",
                            help="Exit nonzero if technical checks are not all green")

    def handle(self, *args, **options):
        data = audit()
        self.stdout.write(json.dumps(data, sort_keys=True, ensure_ascii=False))
        if options["strict"] and not data["technical_preflight_passed"]:
            from django.core.management.base import CommandError
            raise CommandError("MojPlayWin paid product 72 is not technically release-ready")
