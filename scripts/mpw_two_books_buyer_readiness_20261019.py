#!/usr/bin/env python3
"""Add safe buyer information to the two live MojPlayWin book cards.

Never changes database rows, wallet addresses, payment flags, checkout code,
other templates, Passenger, or sibling sub-sites. Fails closed on layout drift.
"""
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path("/home/zomorod2")
APP = ROOT / "Saeit-staging"
TARGET = APP / "core/templates/mojplaywin/store.html"
WSGI = ROOT / "mojplaywin.com/passenger_wsgi.py"
BEGIN = "<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_START -->"
END = "<!-- MPW_TWO_BOOKS_PUBLIC_CATALOG_V1_END -->"
MARKER_BEGIN = "<!-- MPW_TWO_BOOK_BUYER_READINESS_20261019_START -->"
MARKER_END = "<!-- MPW_TWO_BOOK_BUYER_READINESS_20261019_END -->"

DETAILS = """<!-- MPW_TWO_BOOK_BUYER_READINESS_20261019_START -->
<style>
#mpw-book-buyer-details{margin:25px 0 16px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
#mpw-book-buyer-details .mpw-buyer-panel{min-width:0;border:1px solid rgba(240,207,130,.38);border-radius:18px;padding:clamp(16px,2.2vw,26px);background:linear-gradient(135deg,rgba(19,19,18,.95),rgba(40,35,23,.65))}
#mpw-book-buyer-details h3{font-size:1.12rem;color:#f4d99b;margin:6px 0 12px;line-height:1.4}
#mpw-book-buyer-details p,#mpw-book-buyer-details li{line-height:1.7;color:#e0e7f2;font-size:.92rem}
#mpw-book-buyer-details ul{padding-left:20px;margin:9px 0}
#mpw-book-buyer-details a{display:inline-block;padding:9px 14px;border:1px solid #dfb860;border-radius:9px;margin-top:8px;color:#f9dfa3;text-decoration:none;font-weight:700}
#mpw-book-buyer-details a:focus-visible{outline:3px solid #dfb860;outline-offset:3px}
#mpw-book-buyer-details .mpw-checkout-alert{border-left:3px solid #dfb860;padding:10px 13px;background:#302717;color:#f8eed8}
@media(max-width:750px){#mpw-book-buyer-details{grid-template-columns:1fr}}
</style>
<div id="mpw-book-buyer-details" aria-label="Book details and purchase availability">
<section class="mpw-buyer-panel" aria-labelledby="mpw-buyer-chess-title">
<span class="mw-kicker">BOOK DETAILS · DIGITAL PDF</span>
<h3 id="mpw-buyer-chess-title">The Science and Practice of Chess Improvement</h3>
<p>For chess enthusiasts who want a structured approach to better decisions, analysis and deliberate practice.</p>
<ul><li>Language: English</li><li>Format: PDF digital book</li><li>Length: 415 pages (2026 edition)</li><li>Topics: chess decision-making, strategy, game analysis and practice exercises</li><li>Listed price: US $7.50</li></ul>
<p class="mpw-checkout-alert">Checkout is not open. No payment should be sent without a verified order-specific invoice and confirmed digital delivery.</p>
<a href="/support/" aria-label="Questions about the chess book">Ask about this book ↗</a>
</section>
<section class="mpw-buyer-panel" aria-labelledby="mpw-buyer-taniya-title">
<span class="mw-kicker">BOOK DETAILS · ILLUSTRATED PDF</span>
<h3 id="mpw-buyer-taniya-title">Taniya and the Little Baker Worms</h3>
<p>An original illustrated story for family reading with young children.</p>
<ul><li>Language: English</li><li>Format: illustrated landscape PDF</li><li>Length: 40 pages</li><li>Suggested readers: ages 3–8, with adult guidance as appropriate</li><li>Listed price: US $4.00</li></ul>
<p class="mpw-checkout-alert">Checkout is not open. No payment should be sent without a verified order-specific invoice and confirmed digital delivery.</p>
<a href="/support/" aria-label="Questions about Taniya and the Little Baker Worms">Ask about this book ↗</a>
</section>
</div>
<!-- MPW_TWO_BOOK_BUYER_READINESS_20261019_END -->"""

def digest(b):
    return hashlib.sha256(b).hexdigest()

def verify_scope():
    if APP.is_symlink() or TARGET.is_symlink() or WSGI.is_symlink():
        raise RuntimeError("Symlink in protected application path")
    if not TARGET.is_file() or not WSGI.is_file() or not (APP / "manage.py").is_file():
        raise RuntimeError("Exact live application path not present")
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8", "replace"):
        raise RuntimeError("Passenger pin does not match audited main site")

def replace_exact(current):
    text = current.decode("utf-8")
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise RuntimeError("Book catalog boundaries changed")
    if MARKER_BEGIN in text or MARKER_END in text:
        raise RuntimeError("Buyer details already installed")
    start = text.index(BEGIN)
    stop = text.index(END)
    fragment = text[start:stop]
    required = ('id="mpw-sale-book72"', 'id="mpw-sale-book225"',
                'US $7.50', 'US $4.00',
                "Payment is not open for these books yet.")
    if any(fragment.count(token) != 1 for token in required):
        raise RuntimeError("Live book IDs, prices, or checkout notice changed")
    needle = '<p class="mpw-book-pay-note">'
    if fragment.count(needle) != 1:
        raise RuntimeError("Expected book note not found exactly once")
    modified = fragment.replace(needle, DETAILS + "\n" + needle, 1)
    newer = text[:start] + modified + text[stop:]
    assert newer.replace(DETAILS + "\n", "", 1) == text
    if any(term in DETAILS.lower() for term in ("<form", "<script", "wallet-address", "eth_receive_address", "checkout/crypto", "<iframe")):
        raise RuntimeError("Unexpected payment or active-form control")
    return newer.encode("utf8")

def backup_path(run):
    return ROOT / (".mpw-two-book-buyer-readiness-" + run + ".backup")

def atomic_replace(path, content, mode):
    fd, tmp = tempfile.mkstemp(prefix=".mpw-book-ready-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def publish(run):
    verify_scope()
    original = TARGET.read_bytes()
    proposed = replace_exact(original)
    saved = backup_path(run)
    if saved.exists() or saved.is_symlink():
        raise RuntimeError("Refusing existing backup path")
    with saved.open("xb") as f:
        os.chmod(saved, 0o600)
        f.write(original)
        f.flush()
        os.fsync(f.fileno())
    atomic_replace(TARGET, proposed, stat.S_IMODE(TARGET.stat().st_mode))
    if TARGET.read_bytes() != proposed:
        raise RuntimeError("Installed bytes differ")
    print("MPW_BOOK_BUYER_DETAILS=" + json.dumps({
        "installed": True, "only_store_template_modified": True,
        "payment_activated": False, "other_sites_modified": False,
        "old_sha256": digest(original), "new_sha256": digest(proposed)
    }))

def rollback(run):
    verify_scope()
    saved = backup_path(run)
    if saved.is_symlink() or not saved.is_file():
        raise RuntimeError("No original backup")
    original = saved.read_bytes()
    current = TARGET.read_bytes()
    if replace_exact(original) != current:
        raise RuntimeError("Store has other edits: rollback blocked for safety")
    atomic_replace(TARGET, original, stat.S_IMODE(TARGET.stat().st_mode))
    print("MPW_BOOK_BUYER_DETAILS_ROLLBACK=original-restored")

def audit():
    """A safe proof snapshot; never emits private paths, addresses or customer data."""
    verify_scope()
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.conf import settings
    from core.models import Product
    flags = ("MPW_COMMERCE_RELEASE_READY", "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
             "MPW_COMMERCE_INVOICING_ENABLED", "MPW_COMMERCE_SETTLEMENT_ENABLED",
             "MPW_COMMERCE_REAL_RPC_ENABLED", "MPW_COMMERCE_AUTORECONCILE_ENABLED",
             "MPW_COMMERCE_DOWNLOADS_ENABLED")
    found = {p.pk: p for p in Product.objects.filter(pk__in=(72, 225))}
    result = []
    for pk in (72, 225):
        p = found.get(pk)
        if p is None:
            result.append({"id": pk, "exists": False, "sale_ready": False})
            continue
        m = p.metadata if isinstance(p.metadata, dict) else {}
        record = {
            "id": pk, "exists": True, "active": p.active,
            "checkout_enabled": m.get("checkout_enabled") is True,
            "payment_live": m.get("payment_live") is True,
            "delivery_metadata_set": bool(m.get("private_file")),
            "price_matches_catalog": str(p.price) in (("7.50",) if pk == 72 else ("4.00",)),
            "currency_usd": p.currency == "USD",
        }
        record["sale_ready"] = (
            record["active"] and record["checkout_enabled"] and record["payment_live"]
            and record["price_matches_catalog"] and record["currency_usd"]
            and all(getattr(settings, key, False) is True for key in flags)
        )
        result.append(record)
    print("MPW_TWO_BOOK_COMMERCE_AUDIT=" + json.dumps({
        "books": result,
        "gateway_flags": {k: getattr(settings, k, False) is True for k in flags},
        "live_settlement_test_confirmed": False,
        "payment_activation_attempted": False
    }))

def selftest():
    synthetic = ('before' + BEGIN + '<article id="mpw-sale-book72">US $7.50</article>'
                 + '<article id="mpw-sale-book225">US $4.00</article>'
                 + '<p class="mpw-book-pay-note">Payment is not open for these books yet.</p>'
                 + END + 'after').encode("utf8")
    revised = replace_exact(synthetic)
    assert revised.count(MARKER_BEGIN.encode()) == 1
    assert revised.count(MARKER_END.encode()) == 1
    assert revised.count(b'checkout is not open') == 0  # Case-preserving, intentional.
    assert revised.count(b'Checkout is not open') == 2
    assert revised.replace((DETAILS + "\n").encode(), b"", 1) == synthetic
    try:
        replace_exact(revised)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Repeated publication was allowed")
    print("MPW_TWO_BOOK_BUYER_DETAILS_SELFTEST=PASS")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 2 and sys.argv[1] == "audit":
        audit()
    elif len(sys.argv) == 3 and sys.argv[1] in ("publish", "rollback") and re.fullmatch(r"[0-9]{8,20}", sys.argv[2]):
        (publish if sys.argv[1] == "publish" else rollback)(sys.argv[2])
    else:
        raise SystemExit("Usage: script.py selftest|audit|publish RUN_ID|rollback RUN_ID")
