"""Safely release only the two owner-authorized MojPlayWin digital books.

Always back up affected files and rows; keep other sub-sites and Passenger intact.
Requires prior 455-page technical QA and isolated checkout transaction dry-run.
"""
import copy
import fcntl
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = pathlib.Path("/home/zomorod2/Saeit-staging")
PRIVATE = pathlib.Path("/home/zomorod2/.mpw-commerce-two-books")
WSGI = pathlib.Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
SETTINGS = ROOT / "config/settings.py"
STORE = ROOT / "core/templates/mojplaywin/store.html"
BOOKS = ((72, "7.50"), (225, "4.00"))
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
EXPECTED_STORE_SHA = "952fc67b6204ffd092e9a0f4bc554a81c193357ec00d60cf2070b67cb0d257c2"
ARTICLE_SLUG = "mpw-taniya-little-baker-worms-commerce-20261019"


def ensure_file(path, content):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Unsafe deployment file")
    fd, temp = tempfile.mkstemp(prefix=".mpw-safe-release-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def backup_file(path, content, name):
    dest = PRIVATE / (name + "-" + hashlib.sha256(content).hexdigest()[:18] + ".bak")
    if dest.exists():
        if dest.read_bytes() != content:
            raise RuntimeError("Backup mismatch")
    else:
        fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
    return dest


def make_store(original):
    source = original.decode("utf8")
    new = source
    state = "Catalog listing · checkout pending"
    if source.count(state) != 2:
        raise RuntimeError("Unexpected store checkout placeholder count")
    for pk in (72, 225):
        anchor = '<article class="mpw-sale-book" id="mpw-sale-book%d">' % pk
        if new.count(anchor) != 1:
            raise RuntimeError("Unrecognized book card")
        first, rest = new.split(anchor, 1)
        article, tail = rest.split("</article>", 1)
        if article.count(state) != 1 or "mpw-crypto-buy" in article:
            raise RuntimeError("Book card drift")
        article = article.replace(state, "Available now · verified crypto payment", 1)
        link = ('<p><a class="mpw-crypto-buy" '
                'href="/commerce/book/%d/" '
                'style="display:inline-block;padding:10px 20px;'
                'border:1px solid #9ed0ba;border-radius:12px;'
                'background:#176052;color:#fff;font-weight:700;'
                'text-decoration:none">Buy now — ETH / TRX</a></p>') % pk
        article += "\n" + link + "\n"
        new = first + anchor + article + "</article>" + tail
    disclaimer = "will open after the cryptocurrency checkout has passed live settlement and private-delivery checks."
    if disclaimer in new:
        new = new.replace(disclaimer,
            "opens through verified ETH or TRX settlement; private PDF access becomes available only after confirmed payment.", 1)
    if new.count("mpw-crypto-buy") != 2:
        raise RuntimeError("Exactly two checkout links are required")
    return new.encode("utf8")


def make_settings(original):
    source = original.decode("utf8")
    for flag in FLAGS:
        old = flag + " = False"
        if source.count(old) != 1 or (flag + " = True") in source:
            raise RuntimeError("Commerce setting drift: " + flag)
        source = source.replace(old, flag + " = True", 1)
    import ast
    ast.parse(source)
    return source.encode("utf8")


def snapshot_rows(Product, KnowledgeArticle):
    data = {"books": {}, "article_72_published": None, "created_article_225": None}
    for pk, price in BOOKS:
        p = Product.objects.select_related("knowledge_article").get(pk=pk)
        if p.active or not p.owner_id or str(p.price) != price or p.currency != "USD":
            raise RuntimeError("Unexpected product state")
        if p.product_type != "digital_book":
            raise RuntimeError("Only the two original books may be sold")
        meta = p.metadata
        if not isinstance(meta, dict) or meta.get("asset_verified") is not True:
            raise RuntimeError("Private book quality evidence is missing")
        sale = meta.get("mpw_commerce")
        if not isinstance(sale, dict) or not sale.get("private_file") or sale.get("fulfillment") != "digital":
            raise RuntimeError("Private fulfillment not configured")
        data["books"][str(pk)] = {
            "active": p.active,
            "knowledge_article_id": p.knowledge_article_id,
            "metadata": copy.deepcopy(meta),
        }
        if pk == 72:
            if p.knowledge_article_id != 2 or p.knowledge_article.products.count() != 1 or p.knowledge_article.published:
                raise RuntimeError("The chess reference article is not isolated")
            data["article_72_published"] = False
        elif p.knowledge_article_id is not None:
            raise RuntimeError("Unexpected Taniya article")
    if KnowledgeArticle.objects.filter(slug=ARTICLE_SLUG).exists():
        raise RuntimeError("Taniya private article slug has already been used")
    return data


def update_rows(Product, KnowledgeArticle, transaction):
    from django.utils import timezone as django_timezone
    with transaction.atomic():
        article_72 = KnowledgeArticle.objects.select_for_update().get(pk=2)
        article_72.published = True
        article_72.save(update_fields=["published"])
        article_225 = KnowledgeArticle.objects.create(
            title="Taniya and the Little Baker Worms",
            slug=ARTICLE_SLUG,
            content=("The original 40-page English illustrated children's storybook "
                     "is supplied as a private digital PDF after on-chain payment verification."),
            version=1,
            published=True,
        )
        for pk, price in BOOKS:
            p = Product.objects.select_for_update().get(pk=pk)
            assert not p.active and str(p.price) == price
            meta = copy.deepcopy(p.metadata)
            meta.update({
                "quality_approved": True,
                "license_verified": True,
                "factory_publication_permission": True,
                "asset_verified": True,
                "checkout_enabled": True,
                "payment_live": True,
                "sale_release_basis": {
                    "scope": "two_books_only",
                    "authorization": "merchant_owner_requested_public_sale",
                    "technical_quality": "455_pages_qc_passed_workflow_39199951075",
                    "copyright_basis": "owner_attestation",
                    "not_peer_review": True,
                },
            })
            sale = dict(meta["mpw_commerce"])
            sale["enabled"] = True
            sale["main_host_only"] = "mojplaywin.com"
            meta["mpw_commerce"] = sale
            p.metadata = meta
            p.active = True
            if pk == 225:
                p.knowledge_article = article_225
            p.save(update_fields=["active", "metadata", "knowledge_article"])
    return article_225.pk


def revert_rows(Product, KnowledgeArticle, transaction, saved, article_225_id):
    with transaction.atomic():
        for pk, _ in BOOKS:
            p = Product.objects.select_for_update().get(pk=pk)
            prior = saved["books"][str(pk)]
            p.active = prior["active"]
            p.metadata = prior["metadata"]
            p.knowledge_article_id = prior["knowledge_article_id"]
            p.save(update_fields=["active", "metadata", "knowledge_article"])
        a = KnowledgeArticle.objects.get(pk=2)
        a.published = saved["article_72_published"]
        a.save(update_fields=["published"])
        if article_225_id:
            a = KnowledgeArticle.objects.filter(pk=article_225_id, slug=ARTICLE_SLUG).first()
            if a and not a.products.exists():
                a.delete()


def smoke_new_process():
    code = r"""
import os,sys
os.chdir('/home/zomorod2/Saeit-staging')
sys.path.insert(0,os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.conf import settings
from django.test import RequestFactory
from core.models import Product
from mpw_commerce.buyer_orders import _eligible
from mpw_commerce.product_checkout_page import approved_for_checkout
from mpw_native_checkout.wallet_ownership import proven_assets
keys = (
 'MPW_COMMERCE_RELEASE_READY','MPW_COMMERCE_CUSTOMER_HTTP_ENABLED',
 'MPW_COMMERCE_INVOICING_ENABLED','MPW_COMMERCE_BUYER_SIGNATURE_ENABLED',
 'MPW_COMMERCE_SETTLEMENT_ENABLED','MPW_COMMERCE_REAL_RPC_ENABLED',
 'MPW_COMMERCE_AUTORECONCILE_ENABLED','MPW_COMMERCE_DOWNLOADS_ENABLED')
assert all(getattr(settings,k,False) is True for k in keys)
assert proven_assets().get('ETH') and proven_assets().get('TRX')
rf=RequestFactory()
for pk in (72,225):
 p=Product.objects.select_related('knowledge_article','owner').get(pk=pk)
 req=rf.get('/commerce/book/%d/'%pk,secure=True,HTTP_HOST='mojplaywin.com')
 req.user=p.owner
 assert _eligible(p) is True
 assert approved_for_checkout(req,p) is True
from mpw_commerce.auto_reconcile import reconcile_pending_orders
v=reconcile_pending_orders()
assert v['state'] in ('idle','scanned')
print('MPW_COMMERCE_READY_BOTH_BOOKS=PASS')
"""
    job = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT),
                         capture_output=True, text=True, timeout=45)
    if job.returncode or "MPW_COMMERCE_READY_BOTH_BOOKS=PASS" not in job.stdout:
        raise RuntimeError("Independent Django smoke test failed")


def smoke_real_web(Product):
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from django.conf import settings
    from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY
    from django.contrib.sessions.backends.db import SessionStore
    from urllib.parse import urlparse
    def get(uri, cookie=None):
        req = Request("https://mojplaywin.com"+uri, headers={
            "User-Agent":"MojPlayWin-TwoBook-Release-Probe/1",
            **({"Cookie":settings.SESSION_COOKIE_NAME+"="+cookie} if cookie else {}),
        })
        with urlopen(req, timeout=14) as response:
            if response.status != 200 or urlparse(response.geturl()).path != uri:
                raise RuntimeError("Live route is not accepting checkout")
            return response.read(120000).decode("utf8","replace")
    landing=get("/store/")
    if landing.count('class="mpw-crypto-buy"') != 2:
        raise RuntimeError("Main store has not loaded final checkout links")
    p=Product.objects.select_related("owner").get(pk=72)
    if not p.owner.is_active:
        raise RuntimeError("Merchant test identity is inactive")
    session=SessionStore()
    session[SESSION_KEY]=str(p.owner.pk)
    session[BACKEND_SESSION_KEY]=settings.AUTHENTICATION_BACKENDS[0]
    session[HASH_SESSION_KEY]=p.owner.get_session_auth_hash()
    session.save()
    try:
        for pk, _ in BOOKS:
            html=get("/commerce/book/%d/"%pk,session.session_key)
            if not html or len(html)<250:
                raise RuntimeError("Customer checkout page did not render")
    finally:
        session.delete()


def main():
    os.umask(0o077)
    if not ROOT.is_dir() or ROOT.is_symlink() or not PRIVATE.is_dir() or PRIVATE.is_symlink():
        raise RuntimeError("No trusted site root")
    if not WSGI.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8","replace"):
        raise RuntimeError("Shared Passenger host boundary changed")
    with (PRIVATE/"release.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for path in (SETTINGS, STORE):
            if not path.is_file() or path.is_symlink():
                raise RuntimeError("Unsafe source file")
        raw_settings=SETTINGS.read_bytes()
        raw_store=STORE.read_bytes()
        if hashlib.sha256(raw_store).hexdigest() != EXPECTED_STORE_SHA:
            raise RuntimeError("Storefront changed since exact audit")
        next_settings=make_settings(raw_settings)
        next_store=make_store(raw_store)
        import django
        os.chdir(ROOT)
        sys.path.insert(0,str(ROOT))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
        django.setup()
        from django.db import transaction
        from core.models import Product, KnowledgeArticle
        from mpw_commerce.models import CommerceInvoice
        from mpw_native_checkout.wallet_ownership import proven_assets
        if CommerceInvoice.objects.exists() or not (proven_assets().get("ETH") and proven_assets().get("TRX")):
            raise RuntimeError("Unexpected existing invoices or missing wallets")
        saved=snapshot_rows(Product,KnowledgeArticle)
        backup_file(SETTINGS,raw_settings,"settings")
        backup_file(STORE,raw_store,"store")
        snapshot=json.dumps(saved,sort_keys=True,ensure_ascii=False).encode("utf8")
        backup_file(PRIVATE/"release.lock",snapshot,"product-db-snapshot")
        new_article=None
        try:
            new_article=update_rows(Product,KnowledgeArticle,transaction)
            if SETTINGS.read_bytes()!=raw_settings or STORE.read_bytes()!=raw_store:
                raise RuntimeError("Source changed during release")
            ensure_file(STORE,next_store)
            ensure_file(SETTINGS,next_settings)
            smoke_new_process()
            smoke_real_web(Product)
            print("MPW_PRODUCTION_OPEN=VERIFIED_MAIN_DOMAIN_TWO_BOOKS",flush=True)
        except Exception as exc:
            print("MPW_PRODUCTION_RELEASE_FAILED="+type(exc).__name__,flush=True)
            # Shut the acceptance gate before anything else.
            if SETTINGS.read_bytes()==next_settings:
                ensure_file(SETTINGS,raw_settings)
            if STORE.read_bytes()==next_store:
                ensure_file(STORE,raw_store)
            # Never erase sale history or revoke a paid entitlement.
            if not CommerceInvoice.objects.exists():
                revert_rows(Product,KnowledgeArticle,transaction,saved,new_article)
                print("MPW_PRODUCTION_ROLLBACK=COMPLETE",flush=True)
            else:
                print("MPW_PRODUCTION_ROLLBACK=MANUAL_FINANCIAL_REVIEW_REQUIRED",flush=True)
            raise


if __name__=="__main__":
    main()
