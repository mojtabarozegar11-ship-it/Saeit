#!/usr/bin/env python3
"""One-time, isolated MojPlayWin native TRX micro-priced PDF product release.

Creates one private one-page PDF, one published KnowledgeArticle and one active
Product in the actual Django application. Does not create, alter or fake
orders, invoices, payments, receipts or blockchain transactions.
"""
import hashlib
import json
import os
import pwd
import stat
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
WSGI = Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
MARKER = "mpw-native-trx-micro-trial-20261020-v1"
SLUG = "mpw-native-trx-micro-trial-20261020"
FILE_NAME = "mpw-native-trx-micro-trial-20261020.pdf"
PRICE = Decimal("0.03")
TITLE = "MojPlayWin Secure TRX Purchase — One-Page Digital PDF Trial"
SOURCE_PK = 72
SIBLING_PK = 225

def report(k, obj):
    print(k + "=" + json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str), flush=True)

def pdf_bytes():
    lines = [
        "MojPlayWin - Secure TRX Purchase Trial",
        "One-page digital book sample | USD 0.03",
        "",
        "Introduction",
        "This original short guide is a sample product for a real digital sale.",
        "Its goal is to verify the full checkout and private file delivery process.",
        "",
        "Lesson 1: Verify the network",
        "TRX is the native coin on TRON mainnet. Check the network before paying.",
        "Never send tokens to an address merely displayed in a preview or chat.",
        "",
        "Lesson 2: Match the invoice exactly",
        "Start checkout from the official store and wait for the signed wallet step.",
        "Use the unique amount and receiving address shown in that specific invoice.",
        "Different invoices can require slightly different TRX micro-amounts.",
        "",
        "Lesson 3: Wait for final settlement",
        "A transaction hash or screenshot alone is not proof of completed payment.",
        "The merchant verifies the on-chain transfer before granting access.",
        "",
        "Lesson 4: Check your entitlement",
        "Once payment is confirmed, open the authenticated purchased-download page.",
        "If settlement is delayed, do not send a duplicate transfer.",
        "",
        "MojPlayWin | Trial edition | No full-price book content is included.",
    ]
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    commands = ["BT", "/F1 11 Tf", "44 754 Td", "15 TL"]
    for i, line in enumerate(lines):
        if i: commands.append("T*")
        commands.append("(" + esc(line) + ") Tj")
    commands.append("ET")
    stream = ("\n".join(commands) + "\n").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        (b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    blob = bytearray(b"%PDF-1.4\n%Trial\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(blob))
        blob.extend(str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n")
    start = len(blob)
    blob.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        blob.extend(("%010d 00000 n \n" % offset).encode())
    blob.extend(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n")
    blob.extend(str(start).encode() + b"\n%%EOF\n")
    return bytes(blob)

def selftest():
    data = pdf_bytes()
    assert data.startswith(b"%PDF-1.4") and data.endswith(b"%%EOF\n")
    assert b"/Count 1" in data and b"Lesson 4" in data and len(data) > 1000
    assert Decimal("0") < PRICE < Decimal("1.00")
    print("MPW_MICRO_LOCAL_SELFTEST=PASS")

def setup():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Refuse: not the dedicated cPanel account")
    if ROOT.is_symlink() or not ROOT.is_dir() or not WSGI.is_file() or WSGI.is_symlink():
        raise RuntimeError("Unexpected production app routing")
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8", "replace"):
        raise RuntimeError("Passenger app mismatch")
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.conf import settings
    from core.models import Product, KnowledgeArticle, OrderItem
    from mpw_commerce.buyer_orders import _eligible, _private_file
    from mpw_commerce.product_checkout_page import approved_for_checkout
    from types import SimpleNamespace
    source = Product.objects.select_related("knowledge_article", "owner").get(pk=SOURCE_PK)
    sibling = Product.objects.get(pk=SIBLING_PK)
    if (not source.active or source.currency != "USD" or source.owner_id is None
        or source.owner.is_active is not True or not source.knowledge_article_id
        or not source.knowledge_article.published or not _eligible(source)):
        raise RuntimeError("Source product not an approved native checkout product")
    raw = source.metadata["mpw_commerce"].get("private_file")
    root_setting = getattr(settings, "MPW_COMMERCE_PRIVATE_ASSET_ROOT", None)
    if not isinstance(root_setting, str) or not root_setting.startswith("/"):
        raise RuntimeError("Private assets root not configured")
    private_root = Path(root_setting)
    if private_root.is_symlink() or not private_root.is_dir():
        raise RuntimeError("Private assets root untrusted")
    rel = Path(raw) if isinstance(raw, str) else Path("INVALID")
    if rel.is_absolute() or ".." in rel.parts or rel.name == "":
        raise RuntimeError("Source private file reference unsafe")
    original = _private_file(SimpleNamespace(product=source))
    target_rel = rel.parent / FILE_NAME
    target = private_root / target_rel
    if target.parent.resolve(strict=True) != original.parent.resolve(strict=True):
        raise RuntimeError("Private sample not isolated alongside vetted source")
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise RuntimeError("Unsafe sample file target")
    if stat.S_IMODE(target.parent.stat().st_mode) & 0o077:
        raise RuntimeError("Sample parent directory is not private")
    if not os.access(target.parent, os.W_OK):
        raise RuntimeError("Private sample directory not writable")
    assert source.price == Decimal("7.50") and sibling.price == Decimal("4.00")
    assert source.pk != sibling.pk
    return dict(Product=Product, KnowledgeArticle=KnowledgeArticle, OrderItem=OrderItem,
                source=source, sibling=sibling, target=target, target_rel=target_rel,
                private_file=_private_file, eligible=_eligible, approved=approved_for_checkout)

def existing_product(ctx):
    Product, KnowledgeArticle = ctx["Product"], ctx["KnowledgeArticle"]
    article = KnowledgeArticle.objects.filter(slug=SLUG).first()
    if article is None:
        return None
    products = list(Product.objects.filter(knowledge_article=article))
    if len(products) != 1 or products[0].metadata.get("mpw_micro_trial") != MARKER:
        raise RuntimeError("Existing article/product collision: no replacement allowed")
    return products[0]

def check(ctx, product):
    from django.test import RequestFactory, Client
    from types import SimpleNamespace
    if (product.price != PRICE or product.currency != "USD" or not product.active
        or product.owner_id != ctx["source"].owner_id
        or product.metadata.get("mpw_micro_trial") != MARKER
        or not product.knowledge_article.published):
        raise RuntimeError("Trial product integrity check failed")
    actual = ctx["private_file"](SimpleNamespace(product=product))
    if actual != ctx["target"].resolve(strict=True) or actual.stat().st_size != len(pdf_bytes()):
        raise RuntimeError("Private PDF entitlement failed")
    if hashlib.sha256(actual.read_bytes()).digest() != hashlib.sha256(pdf_bytes()).digest():
        raise RuntimeError("Private PDF content mismatch")
    if not ctx["eligible"](product):
        raise RuntimeError("Native commerce buyer order disallows sample")
    request = RequestFactory().get("/commerce/book/%s/" % product.pk,
                                    secure=True, HTTP_HOST="mojplaywin.com")
    request.user = ctx["source"].owner
    if not ctx["approved"](request, product):
        raise RuntimeError("Native product checkout is not approved")
    resp = Client(raise_request_exception=True).get(
        "/store/product/%s/" % product.pk, secure=True, HTTP_HOST="mojplaywin.com")
    if resp.status_code != 200:
        raise RuntimeError("Trial store detail route is not HTTP 200: " + str(resp.status_code))
    if ctx["source"].refresh_from_db() is not None:
        pass
    ctx["sibling"].refresh_from_db()
    if ctx["source"].price != Decimal("7.50") or ctx["sibling"].price != Decimal("4.00"):
        raise RuntimeError("Original product prices changed")

def preview():
    ctx = setup()
    old = existing_product(ctx)
    if old:
        report("MPW_MICRO_PREVIEW", {"already_exists": True, "product_id": old.pk})
    else:
        if ctx["target"].exists():
            raise RuntimeError("Existing untracked file; no overwrite allowed")
        report("MPW_MICRO_PREVIEW", {"new_private_pdf": True, "source_id": SOURCE_PK,
                "price_usd": str(PRICE), "original_prices_unchanged": True,
                "requires_buyer_wallet_signature": True, "no_payment_created": True})
    print("MPW_MICRO_PREVIEW=PASS")

def publish():
    ctx = setup()
    old = existing_product(ctx)
    if old:
        check(ctx, old)
        report("MPW_MICRO_PUBLISHED", {"product_id": old.pk, "reused": True,
                "price_usd": str(PRICE), "url": "https://mojplaywin.com/store/product/%s/" % old.pk})
        return
    if ctx["target"].exists():
        raise RuntimeError("Sample file already exists: refusing overwrite")
    data = pdf_bytes()
    descriptor = os.open(str(ctx["target"]), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        ctx["target"].unlink(missing_ok=True)
        raise
    from django.db import transaction
    try:
        with transaction.atomic():
            article = ctx["KnowledgeArticle"].objects.create(
                slug=SLUG, title=TITLE, published=True,
                content=("A private, one-page English educational PDF created for the MojPlayWin "
                         "native TRX checkout test. It explains invoice-specific amounts, "
                         "TRON finality and verified paid downloads. This is a trial edition, "
                         "not a discounted copy of either full-price book."),
            )
            meta = {
                "factory_publication_permission": True, "asset_verified": True,
                "quality_approved": True, "license_verified": True,
                "rights_cleared": True, "checkout_enabled": True, "payment_live": True,
                "mpw_micro_trial": MARKER,
                "mpw_commerce": {"enabled": True, "fulfillment": "digital",
                    "main_host_only": "mojplaywin.com",
                    "private_file": ctx["target_rel"].as_posix(),
                    "filename": FILE_NAME,
                    "sha256": hashlib.sha256(data).hexdigest()},
            }
            product = ctx["Product"].objects.create(
                title=TITLE, product_type="digital_book", price=PRICE,
                currency="USD", active=True, factory_managed=False,
                owner=ctx["source"].owner, knowledge_article=article,
                metadata=meta,
            )
            check(ctx, product)
        report("MPW_MICRO_PUBLISHED", {"product_id": product.pk, "reused": False,
              "price_usd": str(PRICE), "url": "https://mojplaywin.com/store/product/%s/" % product.pk,
              "pdf_bytes": len(data), "real_payment_sent": False})
    except BaseException:
        ctx["target"].unlink(missing_ok=True)
        raise

def verify():
    ctx = setup()
    obj = existing_product(ctx)
    if obj is None:
        raise RuntimeError("Trial was not published")
    check(ctx, obj)
    report("MPW_MICRO_VERIFIED", {"product_id": obj.pk,
         "price_usd": str(PRICE), "link": "https://mojplaywin.com/store/product/%s/" % obj.pk,
         "main_only": True, "payment_and_receipt_not_faked": True})

def rollback():
    ctx = setup()
    obj = existing_product(ctx)
    if obj is None:
        print("MPW_MICRO_ROLLBACK=NO_PRODUCT")
        return
    if ctx["OrderItem"].objects.filter(product=obj).exists():
        raise RuntimeError("Trial has customer orders, refuse rollback")
    from django.db import transaction
    with transaction.atomic():
        obj.active = False
        obj.save(update_fields=["active"])
        obj.knowledge_article.published = False
        obj.knowledge_article.save(update_fields=["published"])
    report("MPW_MICRO_ROLLBACK", {"deactivated": obj.pk, "private_asset_retained": True})

if __name__ == "__main__":
    modes = {"selftest": selftest, "preview": preview, "publish": publish,
             "verify": verify, "rollback": rollback}
    if len(sys.argv) != 2 or sys.argv[1] not in modes:
        raise SystemExit("Usage: selftest|preview|publish|verify|rollback")
    modes[sys.argv[1]]()
