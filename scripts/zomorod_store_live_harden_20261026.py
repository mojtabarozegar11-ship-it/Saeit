#!/usr/bin/env python3
"""Zomorod-only, fail-closed in-place public storefront hardening.

No commerce DB, payment state, other site, or shared site configuration is touched.
Run only as the authorized cPanel user with a verified pinned SSH hop.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

HOME = Path("/home/zomorod2")
STORE = HOME / "public_html/store/index.php"
PRIVATE = HOME / ".private/zomorod-business"
MARK = "ZM_STORE_HARDENING_20261026"

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def swap_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError("ANCHOR_NOT_UNIQUE_OR_ABSENT:" + old[:55])
    return source.replace(old, new, 1)

def prepare(original: str) -> str:
    if MARK in original:
        raise RuntimeError("ALREADY_PATCHED")
    if not original.startswith("<?php") or "zmStoreDb($private)" not in original:
        raise RuntimeError("UNKNOWN_ZOMOROD_STOREFRONT")
    if "free_digital_products WHERE enabled=1" not in original:
        raise RuntimeError("FREE_PRODUCTS_CONTRACT_MISSING")
    if "پرداخت بانک شهر" not in original:
        raise RuntimeError("BANK_SH AHR_NOTICE_MISSING".replace(" ", ""))
    result = swap_once(original,
        "header('X-Content-Type-Options: nosniff');",
        "header('X-Content-Type-Options: nosniff');\n"
        "// "+MARK+": owned public store hardening, no payment change.\n"
        "header('X-Frame-Options: DENY');\n"
        "header('Referrer-Policy: strict-origin-when-cross-origin');\n"
        "header('Permissions-Policy: camera=(), microphone=(), geolocation=()');\n"
        "header(\\"Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'\\");")
    result = swap_once(result,
        '<link rel="icon" href="/favicon.ico">',
        '<link rel="icon" href="/favicon.ico"><link rel="canonical" href="https://zomorodmelal.ir/store/"><meta property="og:type" content="website"><meta property="og:locale" content="fa_IR"><meta property="og:url" content="https://zomorodmelal.ir/store/">')
    result = swap_once(result,
        "header img{width:50px;height:50px;vertical-align:middle}",
        "header img{width:50px;height:50px;vertical-align:middle}.skip-link{position:absolute;top:-60px;right:1rem;padding:12px;background:#172e1c;z-index:2}.skip-link:focus{top:0}a:focus-visible{outline:3px solid #ffdf8c;outline-offset:4px}")
    result = swap_once(result,
        '</style></head><body><header>',
        '</style></head><body><a class="skip-link" href="#main-content">رفتن به محتوای اصلی</a><header>')
    result = swap_once(result,
        '</header><main><h1>فروشگاه محصولات زمرد ملل',
        '</header><main id="main-content"><h1>فروشگاه محصولات زمرد ملل')
    return result

def file_guard(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("UNSAFE_FILE:" + str(path))

def apply(expected: str, run: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or not re.fullmatch(r"[0-9]{5,20}", run):
        raise ValueError("INVALID_HASH_OR_RUN")
    if Path.home() != HOME:
        raise RuntimeError("WRONG_CPANEL_ACCOUNT")
    for directory in (HOME, PRIVATE, STORE.parent):
        if directory.is_symlink() or not directory.is_dir():
            raise RuntimeError("UNSAFE_DIRECTORY")
    for path in (STORE, PRIVATE / "site_store.php"):
        file_guard(path)
    lock = PRIVATE / ".store-hardening.lock"
    if lock.is_symlink(): raise RuntimeError("UNSAFE_LOCK")
    with lock.open("a+b") as lockfp:
        os.chmod(lock, 0o600)
        fcntl.flock(lockfp, fcntl.LOCK_EX)
        before = STORE.read_bytes()
        if sha(before) != expected:
            raise RuntimeError("LIVE_CHANGED_AFTER_PREFLIGHT")
        candidate = prepare(before.decode("utf-8")).encode("utf-8")
        private_sha = sha((PRIVATE / "site_store.php").read_bytes())
        product = STORE.parent / "free-products/wheat-seed-rate-planner-v1/index.html"
        file_guard(product)
        product_sha = sha(product.read_bytes())
        backupdir = PRIVATE / (".store-hardening-backup-" + run)
        if backupdir.exists() or backupdir.is_symlink():
            raise RuntimeError("BACKUP_COLLISION")
        backupdir.mkdir(mode=0o700)
        backup = backupdir / "index.before.php"
        backup.write_bytes(before)
        os.chmod(backup, 0o600)
        if sha(backup.read_bytes()) != expected:
            raise RuntimeError("BACKUP_CORRUPT")
        temp = STORE.parent / (".store-harden-" + run + ".php")
        if temp.exists() or temp.is_symlink():
            raise RuntimeError("STAGING_COLLISION")
        try:
            with temp.open("xb") as f:
                f.write(candidate); f.flush(); os.fsync(f.fileno())
            os.chmod(temp, STORE.stat().st_mode & 0o777)
            cmd = subprocess.run(["php", "-l", str(temp)], capture_output=True, text=True, timeout=15)
            if cmd.returncode != 0:
                raise RuntimeError("PHP_SYNTAX:" + (cmd.stderr + cmd.stdout)[:200])
            if sha(STORE.read_bytes()) != expected:
                raise RuntimeError("CONCURRENT_EDIT")
            os.replace(temp, STORE)
            try:
                url = "https://zomorodmelal.ir/store/?security_release=" + run
                with urllib.request.urlopen(url, timeout=20) as response:
                    body = response.read(512000).decode("utf-8", "replace")
                    heads = response.headers
                    if response.status != 200 or MARK in body:
                        raise RuntimeError("HTTP_INVALID")
                    if "فروشگاه محصولات زمرد ملل" not in body or "free-products" not in body:
                        raise RuntimeError("PUBLIC_CATALOG_REGRESSION")
                    if "frame-ancestors" not in heads.get("Content-Security-Policy", ""):
                        raise RuntimeError("SECURITY_HEADER_NOT_SERVING")
                if sha(product.read_bytes()) != product_sha or sha((PRIVATE / "site_store.php").read_bytes()) != private_sha:
                    raise RuntimeError("OTHER_STORE_FILES_CHANGED")
                print("ZM_STORE_ONLY_HARDENING_LIVE=PASS")
                print("ZM_STORE_BACKUP=" + str(backup))
                print("ZM_STORE_SOURCE_SHA256=" + sha(candidate))
            except BaseException:
                with tempfile.NamedTemporaryFile(dir=STORE.parent, prefix=".zm-rollback-", delete=False) as f:
                    f.write(before); f.flush(); os.fsync(f.fileno())
                    restore = Path(f.name)
                os.chmod(restore, 0o644)
                if sha(STORE.read_bytes()) == sha(candidate):
                    os.replace(restore, STORE)
                    print("ZM_STORE_ROLLBACK=RESTORED")
                else:
                    print("ZM_STORE_ROLLBACK=REFUSED_CONCURRENT_EDIT")
                if restore.exists(): restore.unlink()
                raise
        finally:
            if temp.exists(): temp.unlink()

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--expected-sha256",required=True)
    p.add_argument("--run",required=True)
    a=p.parse_args()
    apply(a.expected_sha256,a.run)
