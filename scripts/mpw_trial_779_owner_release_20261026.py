#!/usr/bin/env python3
"""Owner-authorized, isolated re-release of the existing USD 0.03 trial SKU 779.

Changes only the MojPlayWin product-detail canary exception, public TRX
allowlist, and store listing. Preserves all orders, customer data, product
records, payment logic, other sites, and the original three store assets.
"""
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

APP = Path("/home/zomorod2/Saeit-staging")
WSGI = Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
BACKUP_ROOT = Path("/home/zomorod2/.mpw-trial-779-owner-release-20261026")
FILES = {
    "view": APP / "core/brand_views.py",
    "settings": APP / "config/settings.py",
    "store": APP / "core/templates/mojplaywin/store.html",
    "detail": APP / "core/templates/brands/mojplaywin/product.html",
}
TRIAL_MARKER = "mpw-native-trx-micro-trial-20261020-v1"
OLD_VIEW = "    if product.pk in canary_ids or not _eligible(product): raise Http404"
NEW_VIEW = (
    "    owner_approved_micro_trial = (\n"
    "        product.pk == 779 and product.currency == 'USD'\n"
    "        and str(product.price) == '0.03'\n"
    "        and isinstance(product.metadata, dict)\n"
    "        and product.metadata.get('mpw_micro_trial') == 'mpw-native-trx-micro-trial-20261020-v1'\n"
    "        and product.metadata.get('asset_verified') is True\n"
    "        and product.metadata.get('rights_cleared') is True\n"
    "        and product.metadata.get('checkout_enabled') is True\n"
    "    )\n"
    "    if (product.pk in canary_ids and not owner_approved_micro_trial) or not _eligible(product): raise Http404\n"
    "    if owner_approved_micro_trial:\n"
    "        product.metadata = dict(product.metadata)\n"
    "        product.metadata['summary'] = 'Original one-page educational PDF on the secure TRX checkout process.'\n"
    "        product.metadata['seo_description'] = 'Three-cent MojPlayWin TRX digital PDF trial: invoice, safe payment and private download.'"
)
OLD_SETTINGS = "MPW_TRX_PUBLIC_PRODUCT_IDS = (72, 225, 879)"
NEW_SETTINGS = "MPW_TRX_PUBLIC_PRODUCT_IDS = (72, 225, 879, 779)"
ANCHOR = "<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_START -->"
CARD_MARKER = 'id="mpw-trx-micro-trial-779-20261026"'
DETAIL_ANCHOR = "{% elif product.pk == 72 or product.pk == 225 %}"
DETAIL_MARKER = 'id="mpw-trial-779-buy"'
DETAIL_BLOCK = """{% elif product.pk == 779 %}
<p>This one-page original PDF costs USD 0.03. Sign in to request the native TRX invoice. Network fees are extra, and private delivery follows verified payment.</p>
<a class="primary" id="mpw-trial-779-buy" href="/commerce/book/779/">Buy USD 0.03 PDF with TRX</a>
<a href="/accounts/register/?next=/commerce/book/779/">New customer? Create an account</a>
"""
CARD = """<section class="mpw-store-section" id="mpw-trx-micro-trial-779-20261026" aria-labelledby="mpw-trial-779-title" style="border:1px solid rgba(212,175,55,.65);border-radius:18px;padding:clamp(18px,3vw,34px);background:linear-gradient(125deg,#172025,#121512);margin-top:28px">
<span class="mpw-store-label">LOW-COST DIGITAL PDF · NATIVE TRX</span>
<h2 id="mpw-trial-779-title">MojPlayWin Secure TRX Purchase — One-Page Digital PDF Trial</h2>
<p style="max-width:760px;color:#d7d0c2;line-height:1.75">An original one-page educational PDF on secure TRON-network payments, order-specific invoices and verified private downloads. This is a small checkout trial, not a full-length book.</p>
<p style="font-weight:800;font-size:1.4rem;color:#f0d98f">US $0.03 <span style="font-size:.85rem;font-weight:500;color:#c5bdab">· Digital PDF · Network transaction fees are extra</span></p>
<a class="mpw-store-button" href="/store/product/779/" aria-label="View and purchase the three-cent secure TRX trial PDF">View 3-cent PDF &amp; secure checkout →</a>
<p class="mpw-store-note" style="font-size:.84rem">An invoice and private download depend on actual buyer eligibility and independently verified payment. Never send funds without a valid order-specific invoice.</p>
</section>
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def report(name, payload):
    print(name + "=" + json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def safe_root():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("DEDICATED_CPANEL_ACCOUNT_REQUIRED")
    if APP.is_symlink() or not APP.is_dir() or WSGI.is_symlink() or not WSGI.is_file():
        raise RuntimeError("UNEXPECTED_APP_OR_WSGI_ROOT")
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text(errors="replace"):
        raise RuntimeError("PRODUCTION_PASSENGER_ROOT_NOT_VERIFIED")
    for name, path in FILES.items():
        if path.is_symlink() or not path.is_file() or path.parent.is_symlink():
            raise RuntimeError("UNTRUSTED_LIVE_FILE:" + name)
        if path.stat().st_size < 1000 or path.stat().st_size > 400000:
            raise RuntimeError("LIVE_FILE_SIZE_OUT_OF_BOUNDS:" + name)


def verify_product():
    import django
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    from core.models import Product
    from mpw_commerce.buyer_orders import _eligible, _private_file
    from types import SimpleNamespace
    obj = Product.objects.select_related("knowledge_article", "owner").get(pk=779)
    if (obj.price != Decimal("0.03") or obj.currency != "USD"
            or obj.active is not True or not obj.knowledge_article_id
            or obj.knowledge_article.published is not True
            or obj.owner_id is None or obj.owner.is_active is not True
            or not isinstance(obj.metadata, dict)
            or obj.metadata.get("mpw_micro_trial") != TRIAL_MARKER
            or not all(obj.metadata.get(k) is True for k in
                       ("asset_verified", "rights_cleared", "quality_approved", "checkout_enabled"))
            or not _eligible(obj)):
        raise RuntimeError("TRIAL_779_METADATA_OR_RIGHTS_NOT_APPROVED")
    f = _private_file(SimpleNamespace(product=obj))
    if f.is_symlink() or not f.is_file() or f.stat().st_size < 1000:
        raise RuntimeError("PRIVATE_TRIAL_PDF_MISSING")
    expected = obj.metadata.get("mpw_commerce", {}).get("sha256")
    if not isinstance(expected, str) or sha(f.read_bytes()) != expected:
        raise RuntimeError("TRIAL_779_PRIVATE_PDF_HASH_MISMATCH")
    for pk, price in ((72, Decimal("7.50")), (225, Decimal("4.00")), (879, Decimal("6.80"))):
        p = Product.objects.filter(pk=pk, active=True).first()
        if p is None or p.price != price:
            raise RuntimeError("PROTECTED_STORE_PRODUCT_CHANGED:" + str(pk))
    report("MPW_TRIAL_779_SOURCE_VERIFIED", {
        "pk": 779, "price_usd": "0.03", "original_skus_preserved": [72, 225, 879],
        "private_pdf_sha256": expected, "payment_or_order_writes": 0})


def proposed(current):
    view = current["view"].decode("utf-8")
    settings = current["settings"].decode("utf-8")
    store = current["store"].decode("utf-8")
    detail = current["detail"].decode("utf-8")
    if all((NEW_VIEW in view, NEW_SETTINGS in settings, CARD_MARKER in store,
            DETAIL_MARKER in detail)):
        return current, "already_installed"
    if (view.count(OLD_VIEW) != 1 or settings.count(OLD_SETTINGS) != 1
            or store.count(ANCHOR) != 1 or CARD_MARKER in store
            or detail.count(DETAIL_ANCHOR) != 1 or DETAIL_MARKER in detail
            or NEW_VIEW in view or NEW_SETTINGS in settings):
        raise RuntimeError("LIVE_SOURCE_DRIFT_OR_PARTIAL_RELEASE")
    for key in ('id="catalog"', 'id="mpw-original-books"', '/store/product/72/',
                '/store/product/225/', 'id="mpw-atelier-discovery-20261025"'):
        if key not in store:
            raise RuntimeError("PROTECTED_STORE_SECTION_MISSING:" + key)
    output = {
        "view": view.replace(OLD_VIEW, NEW_VIEW, 1).encode(),
        "settings": settings.replace(OLD_SETTINGS, NEW_SETTINGS, 1).encode(),
        "store": store.replace(ANCHOR, CARD + ANCHOR, 1).encode(),
        "detail": detail.replace(DETAIL_ANCHOR, DETAIL_BLOCK + DETAIL_ANCHOR, 1).encode(),
    }
    for name in ("view", "settings"):
        compile(output[name], str(FILES[name]), "exec")
    if output["store"].count(CARD_MARKER.encode()) != 1 or output["detail"].count(DETAIL_MARKER.encode()) != 1:
        raise RuntimeError("TRIAL_CARD_OR_CHECKOUT_CTA_PATCH_INVALID")
    return output, "new_install"

def atomic_write(path, data):
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, name = tempfile.mkstemp(prefix=".mpw-micro-779-", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def manifest_paths(run_id):
    if not re.fullmatch(r"[0-9]{6,20}", run_id):
        raise RuntimeError("INVALID_ACTION_RUN_ID")
    root = BACKUP_ROOT / run_id
    if root.is_symlink():
        raise RuntimeError("BACKUP_SYMLINK_REFUSED")
    return root


def do_restart():
    folder = APP / "tmp"
    if folder.is_symlink():
        raise RuntimeError("PASSENGER_RESTART_PATH_UNSAFE")
    folder.mkdir(mode=0o700, exist_ok=True)
    flag = folder / "restart.txt"
    if flag.is_symlink():
        raise RuntimeError("PASSENGER_RESTART_FLAG_UNSAFE")
    fd = os.open(str(flag), os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    os.utime(flag, None)


def restore(root):
    if not root.is_dir():
        raise RuntimeError("ROLLBACK_RECEIPT_MISSING")
    m = json.loads((root / "manifest.json").read_text())
    for key, path in FILES.items():
        before = (root / (key + ".bak")).read_bytes()
        current = path.read_bytes()
        if sha(before) != m["before"][key]:
            raise RuntimeError("ROLLBACK_RECEIPT_CORRUPT:" + key)
        if sha(current) not in (m["before"][key], m["after"][key]):
            raise RuntimeError("ROLLBACK_CONCURRENT_MODIFICATION:" + key)
    for key, path in FILES.items():
        before = (root / (key + ".bak")).read_bytes()
        if sha(path.read_bytes()) == m["after"][key]:
            atomic_write(path, before)
    do_restart()
    report("MPW_TRIAL_779_SAFE_ROLLBACK", {"restored": sorted(FILES), "payment_records_changed": 0})


def apply(run_id):
    safe_root()
    verify_product()
    before = {key: path.read_bytes() for key, path in FILES.items()}
    after, state = proposed(before)
    if state == "already_installed":
        report("MPW_TRIAL_779_RELEASE", {"state": "already_installed"})
        return
    root = manifest_paths(run_id)
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    for key, blob in before.items():
        p = root / (key + ".bak")
        fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as target:
            target.write(blob)
            target.flush()
            os.fsync(target.fileno())
    m = {"run_id": run_id, "before": {k: sha(v) for k, v in before.items()},
         "after": {k: sha(v) for k, v in after.items()},
         "state": "prepared", "scope": "SKU779_only_three_code_files"}
    (root / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    try:
        for key, path in FILES.items():
            if path.read_bytes() != before[key]:
                raise RuntimeError("CONCURRENT_LIVE_EDIT:" + key)
            atomic_write(path, after[key])
        do_restart()
        m["state"] = "installed"
        (root / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        report("MPW_TRIAL_779_RELEASE", {"state": "installed", "run": run_id,
               "changed": sorted(FILES), "originals": [72, 225, 879],
               "orders_invoices_payments_mutated": 0})
    except BaseException:
        restore(root)
        raise


def verify():
    safe_root()
    verify_product()
    current = {key: path.read_bytes() for key, path in FILES.items()}
    _, state = proposed(current)
    if state != "already_installed":
        raise RuntimeError("TRIAL_779_PATCH_NOT_INSTALLED")
    from django.test import Client
    client = Client(raise_request_exception=False)
    checks = {}
    for pk in (72, 225, 779, 879):
        status = client.get("/store/product/%s/" % pk, secure=True,
                            HTTP_HOST="mojplaywin.com").status_code
        checks[str(pk)] = status
        if status != 200:
            raise RuntimeError("STORE_PRODUCT_ROUTE_BAD:" + str(pk))
    detail_response = client.get("/store/product/779/", secure=True, HTTP_HOST="mojplaywin.com")
    from django.template.loader import get_template
    selected_template = get_template("brands/mojplaywin/product.html")
    report("MPW_TRIAL_779_TEMPLATE_ORIGIN", {"origin": selected_template.origin.name,
        "edited": str(FILES["detail"]), "is_same_file": selected_template.origin.name == str(FILES["detail"]),
        "rendered_buy_id": DETAIL_MARKER.encode() in detail_response.content,
        "rendered_checkout_link": b'/commerce/book/779/' in detail_response.content,
        "rendered_tail": detail_response.content[-400:].decode("utf-8", "replace")})
    if b'Buy USD 0.03 PDF with TRX' not in detail_response.content or b'/commerce/book/779/' not in detail_response.content:
        raise RuntimeError("TRIAL_779_PURCHASE_BUTTON_MISSING")
    store = client.get("/store/", secure=True, HTTP_HOST="mojplaywin.com")
    if store.status_code != 200 or b'/store/product/779/' not in store.content:
        raise RuntimeError("TRIAL_MISSING_FROM_STORE_LISTING")
    checkout = client.get("/commerce/book/779/", secure=True,
                          HTTP_HOST="mojplaywin.com")
    if checkout.status_code not in (200, 302):
        raise RuntimeError("TRIAL_CHECKOUT_ROUTE_UNAVAILABLE")
    from django.conf import settings
    if tuple(settings.MPW_TRX_PUBLIC_PRODUCT_IDS) != (72, 225, 879, 779):
        raise RuntimeError("TRIAL_PAYMENT_ALLOWLIST_WRONG")
    report("MPW_TRIAL_779_OWNER_RELEASE_VERIFIED", {"store_product_http": checks,
        "store_listing_http": 200, "checkout_guest_status": checkout.status_code,
        "product_id": 779, "price_usd": "0.03", "paid_order_created": False})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: script.py apply RUN_ID | verify | rollback RUN_ID")
    action = sys.argv[1]
    if action == "apply" and len(sys.argv) == 3:
        apply(sys.argv[2])
    elif action == "verify" and len(sys.argv) == 2:
        verify()
    elif action == "rollback" and len(sys.argv) == 3:
        safe_root()
        restore(manifest_paths(sys.argv[2]))
    else:
        raise SystemExit("invalid arguments")
