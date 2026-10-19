#!/usr/bin/env python3
"""Isolated free Zomorod product release; never touches payments or other sites."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys

SCHEMA = "saeit.zomorod.original-wheat-free-v1"
SKU = "wheat_seed_rate_v1"
URL = "/store/free-products/wheat-seed-rate-planner-v1/index.html"
HEX = re.compile(r"^[a-f0-9]{64}$")

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(131072), b""):
            h.update(part)
    return h.hexdigest()

def verify_file(path, expected):
    if not path.is_file() or path.is_symlink() or sha(path) != expected:
        raise RuntimeError("RELEASE_FILE_HASH_OR_TYPE_MISMATCH:" + path.name)

def atomic_copy(src, dst, mode=0o644):
    if dst.is_symlink():
        raise RuntimeError("SYMLINK_DESTINATION_FORBIDDEN")
    temporary = dst.with_name("." + dst.name + ".free-stage")
    if temporary.exists() or temporary.is_symlink():
        raise RuntimeError("UNOWNED_STAGED_FILE")
    try:
        shutil.copyfile(src, temporary)
        os.chmod(temporary, mode)
        os.replace(temporary, dst)
    finally:
        if temporary.exists():
            temporary.unlink()

def release(home, stage, runid, old_lib, old_index, new_lib, new_index, product_sha):
    if not re.fullmatch(r"[0-9]{5,20}", runid):
        raise ValueError("INVALID_ACTIONS_RUN_ID")
    for item in (old_lib, old_index, new_lib, new_index, product_sha):
        if not HEX.fullmatch(item):
            raise ValueError("INVALID_DIGEST")
    root = Path(home)
    if root != Path("/home/zomorod2") or root.is_symlink():
        raise RuntimeError("WRONG_SITE_OWNER")
    private = root / ".private/zomorod-business"
    webroot = root / "public_html/store"
    dbfile = private / "site_store.sqlite3"
    lib = private / "site_store.php"
    index = webroot / "index.php"
    stage = Path(stage)
    incoming = (stage / "site_store.php", stage / "store_index.php", stage / "product.html")
    for p in (root, private, webroot, stage, dbfile, lib, index, *incoming):
        if p.is_symlink():
            raise RuntimeError("UNSAFE_SYMLINK:" + p.name)
    if not all(x.is_dir() for x in (root, private, webroot, stage)):
        raise RuntimeError("SITE_ROOT_NOT_PROVEN")
    if not all(x.is_file() for x in (dbfile, lib, index, *incoming)):
        raise RuntimeError("STORE_SOURCE_MISSING")
    for source, expected in zip(incoming, (new_lib, new_index, product_sha)):
        verify_file(source, expected)
    for file in incoming[:2]:
        subprocess.run(["php", "-l", str(file)], check=True, capture_output=True, timeout=10)
    for existing, old, new in ((lib, old_lib, new_lib), (index, old_index, new_index)):
        if sha(existing) not in (old, new):
            raise RuntimeError("ACTIVE_NATIVE_STORE_BASELINE_CHANGED:" + existing.name)
    free_root = webroot / "free-products"
    dest = free_root / "wheat-seed-rate-planner-v1"
    marker = dest / ".zomorod-product-owner"
    product = dest / "index.html"
    for p in (free_root, dest, marker, product):
        if p.is_symlink():
            raise RuntimeError("UNOWNED_FREE_PRODUCT_TARGET")
    was_present = dest.exists()
    if was_present and (
        not marker.is_file() or marker.read_text().strip() != SCHEMA
        or not product.is_file() or sha(product) != product_sha
    ):
        raise RuntimeError("EXISTING_FREE_PRODUCT_OWNERSHIP_MISMATCH")
    backup = root / ".backups" / ("zomorod-free-wheat-" + runid)
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("RELEASE_BACKUP_COLLISION")
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup, 0o700)
    shutil.copy2(lib, backup / "site_store.php")
    shutil.copy2(index, backup / "index.php")
    with sqlite3.connect("file:" + str(dbfile) + "?mode=ro", uri=True) as db:
        with sqlite3.connect(str(backup / "store.sqlite3")) as snap:
            db.backup(snap)
            assert snap.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    previous = None
    with sqlite3.connect(str(dbfile), timeout=20) as db:
        present = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='free_digital_products'").fetchone()
        if present:
            previous = db.execute("SELECT artifact_sha256,download_path,enabled FROM free_digital_products WHERE sku=?", (SKU,)).fetchone()
            if previous and previous[:2] != (product_sha, URL):
                raise RuntimeError("FREE_SKU_OWNERSHIP_COLLISION")
    try:
        if sha(lib) != new_lib:
            atomic_copy(incoming[0], lib, 0o600)
        if sha(index) != new_index:
            atomic_copy(incoming[1], index, 0o644)
        free_root.mkdir(mode=0o755, exist_ok=True)
        if not was_present:
            dest.mkdir(mode=0o755)
            marker.write_text(SCHEMA + "\n", encoding="utf-8")
            os.chmod(marker, 0o644)
            atomic_copy(incoming[2], product)
        verify_file(product, product_sha)
        with sqlite3.connect(str(dbfile), timeout=20) as db:
            db.execute("PRAGMA busy_timeout=15000")
            db.execute("""CREATE TABLE IF NOT EXISTS free_digital_products (
                id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
                description TEXT NOT NULL, download_path TEXT NOT NULL UNIQUE,
                artifact_sha256 TEXT NOT NULL, license_text TEXT NOT NULL,
                price_irr INTEGER NOT NULL DEFAULT 0 CHECK(price_irr=0),
                enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("BEGIN IMMEDIATE")
            if previous:
                db.execute("UPDATE free_digital_products SET enabled=1 WHERE sku=?", (SKU,))
            else:
                db.execute("""INSERT INTO free_digital_products
                    (sku,title,description,download_path,artifact_sha256,license_text,price_irr,enabled)
                    VALUES(?,?,?,?,?,?,0,1)""",
                    (SKU, "محاسبه‌گر علمی بذر گندم",
                     "ابزار آفلاین محاسبه بذر گندم با تراکم هدف، وزن هزار دانه، قوه نامیه و استقرار مزرعه‌ای؛ محصول رایگان آموزشی.",
                     URL, product_sha, "Free personal and educational use"))
            result = db.execute("SELECT price_irr,enabled,artifact_sha256 FROM free_digital_products WHERE sku=?", (SKU,)).fetchone()
            if result != (0,1,product_sha):
                raise RuntimeError("FREE_PRODUCT_DB_ACTIVATION_NOT_VERIFIED")
            paid = db.execute("SELECT sql FROM sqlite_master WHERE name='products'").fetchone()
            if paid is None or "CHECK(price_irr>0)" not in paid[0]:
                raise RuntimeError("PAID_STORE_SCHEMA_REGRESSION")
        verify_file(lib, new_lib)
        verify_file(index, new_index)
        print("ZOMOROD_FREE_WHEAT_NATIVE_STORE_RECORD=PASS")
        print("ZOMOROD_FREE_WHEAT_STATIC_DOWNLOAD_SHA256=" + product_sha)
        print("ZOMOROD_PAID_PAYMENT_TABLE_UNCHANGED=PASS")
        print("ZOMOROD_RESTORABLE_BACKUP=" + str(backup))
    except BaseException:
        atomic_copy(backup / "site_store.php", lib, 0o600)
        atomic_copy(backup / "index.php", index, 0o644)
        with sqlite3.connect(str(dbfile), timeout=15) as db:
            if db.execute("SELECT name FROM sqlite_master WHERE name='free_digital_products'").fetchone():
                if previous:
                    db.execute("UPDATE free_digital_products SET enabled=? WHERE sku=?", (previous[2], SKU))
                else:
                    db.execute("DELETE FROM free_digital_products WHERE sku=? AND artifact_sha256=?", (SKU, product_sha))
        if not was_present and marker.is_file() and marker.read_text().strip() == SCHEMA:
            product.unlink(missing_ok=True)
            marker.unlink(missing_ok=True)
            dest.rmdir()
        print("ZOMOROD_FREE_WHEAT_ROLLBACK=ATTEMPTED", file=sys.stderr)
        raise

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--old-lib", required=True)
    p.add_argument("--old-index", required=True)
    p.add_argument("--new-lib", required=True)
    p.add_argument("--new-index", required=True)
    p.add_argument("--product-sha", required=True)
    a = p.parse_args()
    release("/home/zomorod2", a.stage, a.run, a.old_lib, a.old_index,
            a.new_lib, a.new_index, a.product_sha)
