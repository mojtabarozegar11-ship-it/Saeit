#!/usr/bin/env python3
"""Private product receipt adapter for Mojtaba Roozegar Django V17.

Copies QA-verified factory artifacts from the shared cPanel inbound warehouse
to a strictly private, app-owned import queue. Does not modify Django, DB,
routing, orders, payment or any public website file.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

SLUG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def store_receiver():
    path = Path(__file__).resolve().parent / "store_receiver.py"
    if not path.is_file():
        raise RuntimeError("VERIFIER_NOT_INSTALLED")
    spec = importlib.util.spec_from_file_location("personal_bridge_verifier", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def private_directory(path):
    if path.is_symlink():
        raise ValueError("PRIVATE_DIRECTORY_SYMLINK")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("PRIVATE_DIRECTORY_INVALID")
    os.chmod(str(path), 0o700)


def atomic_json(path, data):
    private_directory(path.parent)
    handle, pending = tempfile.mkstemp(prefix=".catalog-", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(pending, 0o600)
        os.replace(pending, str(path))
    finally:
        if os.path.exists(pending):
            os.unlink(pending)


def atomic_copy(src, dest, expected):
    if src.is_symlink() or not src.is_file() or not DIGEST.fullmatch(expected):
        raise ValueError("INBOUND_PACKAGE_INVALID")
    private_directory(dest.parent)
    if dest.is_symlink():
        raise ValueError("DESTINATION_SYMLINK")
    if dest.is_file() and digest_file(dest) == expected:
        return False
    fd, pending = tempfile.mkstemp(prefix=".product-", dir=str(dest.parent))
    try:
        with os.fdopen(fd, "wb") as out, src.open("rb") as incoming:
            shutil.copyfileobj(incoming, out, length=1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        if digest_file(Path(pending)) != expected:
            raise ValueError("PRODUCT_COPY_HASH_MISMATCH")
        os.chmod(pending, 0o600)
        os.replace(pending, str(dest))
    finally:
        if os.path.exists(pending):
            os.unlink(pending)
    return True


def verify_application(app, public_base, target):
    app = Path(app).expanduser().resolve()
    public_base = Path(public_base).expanduser().resolve()
    target = Path(target).expanduser().absolute()
    if not (app / "manage.py").is_file() or not (app / "passenger_wsgi.py").is_file():
        raise RuntimeError("INDEPENDENT_V17_DJANGO_APP_MISSING")
    if not (public_base / ".htaccess").is_file():
        raise RuntimeError("PERSONAL_PASSENGER_CONFIG_MISSING")
    conf = (public_base / ".htaccess").read_text(encoding="utf-8", errors="replace")
    directives = {}
    for row in conf.splitlines():
        row = row.strip()
        if row and not row.startswith("#"):
            parts = row.split(None, 1)
            if len(parts) == 2:
                directives[parts[0].lower()] = parts[1].strip()
    configured = Path(directives.get("passengerapproot", "/nonexistent")).expanduser().resolve()
    if configured != app:
        raise RuntimeError("PERSONAL_PASSENGER_APP_MISMATCH")
    if not str(target).startswith(str(app) + os.sep):
        raise RuntimeError("PRIVATE_TARGET_OUTSIDE_APP")
    if target.is_symlink() or public_base == target or str(target).startswith(str(public_base) + os.sep):
        raise RuntimeError("PUBLIC_OR_SYMLINK_TARGET")
    return app


def stage(source, app, public_base, target, *, limit=20):
    if not 1 <= limit <= 50:
        raise ValueError("INVALID_BATCH_LIMIT")
    app = verify_application(app, public_base, target)
    source = Path(source).expanduser().resolve()
    target = Path(target).expanduser().absolute()
    if not source.is_dir() or source.is_symlink():
        raise RuntimeError("SHARED_CPANEL_WAREHOUSE_UNAVAILABLE")
    verifier = store_receiver()
    receipt_root = source / "receipts"
    if not receipt_root.is_dir():
        return {"examined": 0, "updated": 0, "unchanged": 0}
    products = []
    for folder in sorted(receipt_root.iterdir()):
        if folder.is_dir() and not folder.is_symlink() and SLUG.fullmatch(folder.name):
            for receipt in sorted(folder.glob("*.json")):
                if receipt.is_file() and not receipt.is_symlink() and DIGEST.fullmatch(receipt.stem):
                    products.append((folder.name, receipt.stem))
    products = products[:limit]
    private_directory(target)
    records = []
    updated = unchanged = 0
    for recipe, sha in products:
        if not verifier.status(source, recipe, sha):
            raise RuntimeError("SOURCE_RECEIPT_VERIFICATION_FAILED")
        origin = source / "packages" / recipe / (sha + ".zip")
        manifest = json.loads((source / "packages" / recipe / (sha + ".json")).read_text(encoding="utf-8"))
        out = target / "packages" / recipe / (sha + ".zip")
        copied = atomic_copy(origin, out, sha)
        updated += int(copied)
        unchanged += int(not copied)
        records.append({
            "recipe": recipe,
            "name": str(manifest.get("name") or ""),
            "sha256": sha,
            "private_relative_archive": str(Path("packages") / recipe / (sha + ".zip")),
            "status": "awaiting_product_editorial_review",
            "software_qa": "passed",
            "publication_authorized": False,
            "storefront_listing_created": False,
            "price_set": False,
            "independent_of_orders": True,
        })
    payload = {"schema": 1, "target": "mojtaba_roozegar_personal_v17",
               "items": records, "public_products": 0,
               "requires_explicit_qa_and_owner_approval": True}
    catalog = target / "private_catalog.json"
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    if not catalog.is_file() or catalog.read_text(encoding="utf-8") != canonical:
        atomic_json(catalog, payload)
    return {"examined": len(records), "updated": updated, "unchanged": unchanged}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--app", required=True)
    p.add_argument("--public-base", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max-products", type=int, default=20)
    opts = p.parse_args(argv)
    result = stage(opts.source, opts.app, opts.public_base, opts.out, limit=opts.max_products)
    for key, value in result.items():
        print("PERSONAL_FACTORY_"+key.upper()+"="+str(value))
    print("PERSONAL_FACTORY_DELIVERY_PRIVATE_ONLY=true")
    print("PERSONAL_FACTORY_PUBLIC_LISTING=false")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        print("PERSONAL_FACTORY_ADAPTER_ERROR="+type(exc).__name__, file=sys.stderr)
        sys.exit(1)
