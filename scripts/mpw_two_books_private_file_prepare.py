#!/usr/bin/env python3
"""Safely connect only two existing MojPlayWin PDFs to private Django delivery.

This is NOT a checkout-activation command. It never changes active, checkout,
payment flags, prices, customer data, sender wallets, or any other host/site.
Source files remain untouched. Run on the authorised cPanel app only.
"""
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
WSGI = DOCROOT / "passenger_wsgi.py"
PILOTS = {
    72: {
        "key": "mojplaywin-chess-improvement-2026",
        "price": "7.50",
        "src": HOME / "MojPlayWin_Private_Assets/store/chess-improvement/MojPlayWin_Chess_Grandmaster_Final_Covered_2026.pdf",
        "sha": "3837fc3cb21ed1a2e7c33e0db8f8e10d158583309b02b97d4d674d25a147207a",
    },
    225: {
        "key": "mojplaywin-taniya-little-baker-worms",
        "price": "4.00",
        "src": HOME / "MojPlayWin_Private_Assets/taniya-little-baker-worms/Taniya_and_the_Little_Baker_Worms.pdf",
        "sha": "2f6dace4e5bc09ffe5f8d7a677ddff4980fe00de94b7c2ea5b286d1303901d48",
    },
}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1048576), b""):
            h.update(data)
    return h.hexdigest()


def verify_pdf(path, expected):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Missing, unsafe, or linked book source")
    if not 1000 < path.stat().st_size < 30000000:
        raise RuntimeError("Unexpected book file size")
    with path.open("rb") as stream:
        if not stream.read(5) == b"%PDF-":
            raise RuntimeError("Book lacks PDF signature")
    if sha256(path) != expected:
        raise RuntimeError("Book hash mismatch")


def guarded_root(root):
    """Only private writable locations can hold paid goods."""
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise RuntimeError("Private download root missing/unsafe")
    resolved = root.resolve(strict=True)
    if HOME not in resolved.parents or resolved == HOME:
        raise RuntimeError("Private root outside approved home or overly broad")
    if DOCROOT.resolve(strict=True) == resolved or DOCROOT.resolve(strict=True) in resolved.parents:
        raise RuntimeError("Private root resides in public document root")
    if stat.S_IMODE(resolved.stat().st_mode) & 0o022:
        raise RuntimeError("Private root writable by group or others")
    return resolved


def copy_verified(source, dest, digest):
    """Create one private immutable copy, preserving original and failing on conflicts."""
    if dest.is_symlink():
        raise RuntimeError("Private destination is a symlink")
    if dest.exists():
        verify_pdf(dest, digest)
        return False
    parent = dest.parent
    if parent.exists():
        if parent.is_symlink() or not parent.is_dir():
            raise RuntimeError("Untrusted private subfolder")
    else:
        parent.mkdir(mode=0o700)  # Only one known, owned book-specific folder.
    fd, temp = tempfile.mkstemp(prefix=".mpw-book-", dir=parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as out, source.open("rb") as src:
            while True:
                chunk = src.read(1048576)
                if not chunk:
                    break
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        verify_pdf(Path(temp), digest)
        if dest.exists() or dest.is_symlink():
            raise RuntimeError("Concurrent book destination modification")
        os.link(temp, dest)  # Exclusive create: never overwrite an existing asset.
        verify_pdf(dest, digest)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return True


def setup_django():
    if not APP.is_dir() or APP.is_symlink() or not WSGI.is_file() or WSGI.is_symlink():
        raise RuntimeError("App topology changed; stop")
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8", "replace"):
        raise RuntimeError("Actual Passenger root changed; stop")
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from core.cryptopay_checkout import PRIVATE_ROOT, product_delivery_ready
    from core.models import Product
    return Product, guarded_root(Path(PRIVATE_ROOT)), product_delivery_ready


def check_product(product, p_id, spec):
    meta = product.metadata if isinstance(product.metadata, dict) else {}
    if meta.get("product_id") != spec["key"] or product.active is not False:
        raise RuntimeError("Unexpected product identity or already on sale")
    if product.currency != "USD" or str(product.price) != spec["price"]:
        raise RuntimeError("Unexpected price or currency")
    if meta.get("checkout_enabled") is not False:
        raise RuntimeError("Checkout flag not safely disabled")
    if meta.get("payment_live") is True or meta.get("factory_publication_permission") is True:
        raise RuntimeError("Payment/publication flags changed; refuse")
    return meta


def prepare():
    """Do not turn on payment; install only vetted deliverables and metadata links."""
    Product, root, ready = setup_django()
    for id_, data in PILOTS.items():
        verify_pdf(data["src"], data["sha"])
        check_product(Product.objects.get(pk=id_), id_, data)
    directory = root / "mpw-two-books-2026"
    if directory.is_symlink():
        raise RuntimeError("Unsafe staging location")
    if directory.exists() and not directory.is_dir():
        raise RuntimeError("Destination is not a directory")
    directory.mkdir(mode=0o700, exist_ok=True)
    if stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise RuntimeError("Private book folder not protected")
    from django.db import transaction
    # Make private copies first. DB changes are atomic and tightly scoped.
    mappings = {}
    for id_, data in PILOTS.items():
        dest = directory / ("%d.pdf" % id_)
        copy_verified(data["src"], dest, data["sha"])
        mappings[id_] = (dest, str(dest.relative_to(root)))
    # Store original metadata backup BEFORE DB mutation. Never replace a backup.
    backup = directory / "original-django-product-metadata.json"
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Prior backup exists; do not overwrite")
    prev = {}
    with transaction.atomic():
        for id_, data in PILOTS.items():
            p = Product.objects.select_for_update().get(pk=id_)
            meta = check_product(p, id_, data)
            prev[str(id_)] = meta
        fd, temp = tempfile.mkstemp(prefix=".mpw-metadata-", dir=directory)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf8") as stream:
                json.dump(prev, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temp, backup)  # Exclusive creation; preserve any concurrent backup.
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        for id_, data in PILOTS.items():
            p = Product.objects.get(pk=id_)
            updated = dict(p.metadata)
            updated.update({
                "private_file": mappings[id_][1],
                "sha256": data["sha"],
                "mpw_private_file_prepared": True,
            })
            p.metadata = updated
            if not ready(p):
                raise RuntimeError("Real checkout delivery verifier rejected prepared book")
            p.save(update_fields=["metadata", "updated_at"])
    print("MPW_TWO_BOOKS_PREPARED="+json.dumps({
        "ids":sorted(PILOTS), "delivery_checks_passed":True, "originals_untouched":True,
        "active_products_changed":0,"payment_flags_changed":0,"passenger_restarted":False,
        "seller_status":"DISABLED_PENDING_LIVE_PAYMENT_VERIFICATION"}))


def preflight():
    Product, root, ready = setup_django()
    results = []
    for id_, data in PILOTS.items():
        verify_pdf(data["src"], data["sha"])
        p = Product.objects.get(pk=id_)
        meta = check_product(p, id_, data)
        dest = root / "mpw-two-books-2026" / ("%d.pdf" % id_)
        results.append({"id":id_, "source_verified":True,"dest_present":dest.is_file(),
                        "ready_before":bool(ready(p)),"price":str(p.price),
                        "existing_metadata_keys":sorted(meta)})
    print("MPW_TWO_BOOKS_PREFLIGHT="+json.dumps(results, ensure_ascii=False))


def rollback():
    """Undo only our own metadata keys; refuse if a sale was ever enabled."""
    Product, root, ready = setup_django()
    directory = root / "mpw-two-books-2026"
    backup = directory / "original-django-product-metadata.json"
    if backup.is_symlink() or not backup.is_file():
        raise RuntimeError("Missing protected rollback metadata")
    original = json.loads(backup.read_text("utf8"))
    if set(original) != {"72", "225"}:
        raise RuntimeError("Unexpected backup product set")
    from django.db import transaction
    with transaction.atomic():
        rows = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=PILOTS)}
        if len(rows) != 2:
            raise RuntimeError("One or more product records disappeared")
        for id_, spec in PILOTS.items():
            p = rows[id_]
            check_product(p, id_, spec)
            md = dict(p.metadata or {})
            expected_rel = "mpw-two-books-2026/%d.pdf" % id_
            if (md.get("private_file") != expected_rel or
                    md.get("sha256") != spec["sha"] or
                    md.get("mpw_private_file_prepared") is not True):
                raise RuntimeError("Concurrent product metadata modification: rollback refused")
            old = original[str(id_)]
            for k, v in md.items():
                if k not in ("private_file", "sha256", "mpw_private_file_prepared") and old.get(k) != v:
                    raise RuntimeError("Other product fields changed: rollback refused")
            p.metadata = old
            p.save(update_fields=["metadata", "updated_at"])
    # Keep harmless private PDFs and backup as evidence; never touch originals.
    print("MPW_TWO_BOOKS_METADATA_ROLLED_BACK="+json.dumps({
        "ids":sorted(PILOTS),"payment_flags_changed":0,"original_assets_untouched":True
    }))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("preflight", "prepare", "rollback"):
        raise SystemExit("Usage: script.py preflight | prepare | rollback")
    if sys.argv[1] == "preflight":
        preflight()
    elif sys.argv[1] == "prepare":
        prepare()
    else:
        rollback()
