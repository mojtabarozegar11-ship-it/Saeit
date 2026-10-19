#!/usr/bin/env python3
"""Add ONE QA-tested free wheat tool to the existing Zomorod native store.

Fail closed on any unexpected live source revision. Never replace private store
PHP, change paid products, payments, Django or another site's documents.
"""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile

LIVE_INDEX_SHA = "ed8889b108ebf229d7682d77208104d0367032026a34e70c31cf7f3b5dbd91ff"
LIVE_LIB_SHA = "9336beef43d99f41dfcfbca924c3689781f78645098e2168805d185a10c0ad36"
SKU = "wheat_seed_rate_v1"
DOWNLOAD = "/store/free-products/wheat-seed-rate-planner-v1/index.html"
MARK = "zm_free_wheat_v1_additive_release"
PAYLOAD_SHA = re.compile(r"[0-9a-f]{64}")
NO_ITEMS = "if(!$items) echo"
PAID_CARD = "foreach($items as $p){echo"
QUERY = '''$free=$db->query("SELECT sku,title,description,download_path,artifact_sha256,license_text FROM free_digital_products WHERE enabled=1 ORDER BY id DESC LIMIT 100")->fetchAll();
'''
FREE_CARD = r'''/* zm_free_wheat_v1_additive_release : bounded free-only catalog extension */
foreach($free as $p){
 $url=(string)$p['download_path'];
 $digest=(string)$p['artifact_sha256'];
 if(!preg_match('#^/store/free-products/[a-z0-9-]+/index\.html$#D',$url) || !preg_match('/^[a-f0-9]{64}$/D',$digest))continue;
 echo '<article><h2>'.storeEsc((string)$p['title']).'</h2><p>'.nl2br(storeEsc((string)$p['description'])).'</p><strong>رایگان — بدون پرداخت</strong><p><a href="'.storeEsc($url).'" download>دریافت نسخه آفلاین</a> | <a href="'.storeEsc($url).'">اجرای آنلاین ابزار</a></p><p class="muted">کد محصول: '.storeEsc((string)$p['sku']).' — مجوز: '.storeEsc((string)$p['license_text']).'</p><small class="muted">SHA-256: '.storeEsc($digest).'</small></article>';
}
'''

def digest(path):
    obj=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(131072),b''):obj.update(block)
    return obj.hexdigest()

def check_file(p):
    if p.is_symlink() or not p.is_file():
        raise RuntimeError("FILE_MISSING_OR_SYMLINK:"+str(p))

def build_candidate(before):
    if MARK in before or "free_digital_products" in before:
        raise RuntimeError("FREE_CATALOG_ALREADY_EDITED")
    if before.count(NO_ITEMS)!=1 or before.count(PAID_CARD)!=1 or before.count("function storeEsc(")!=1:
        raise RuntimeError("UNKNOWN_PUBLIC_STORE_TEMPLATE")
    # Query executes before the old empty-state decision; original paid loop remains unchanged.
    candidate=before.replace(NO_ITEMS,QUERY+"if(!$items && !$free) echo",1)
    candidate=candidate.replace(PAID_CARD,FREE_CARD+PAID_CARD,1)
    if candidate.count(MARK)!=1 or candidate.count(PAID_CARD)!=1:
        raise RuntimeError("CANDIDATE_RENDER_CONTRACT")
    return candidate

def copy_atomic(src,dst,mode):
    if dst.is_symlink():raise RuntimeError("ATOMIC_DEST_SYMLINK")
    handle,tmp=tempfile.mkstemp(prefix=".zm-wheat-",dir=str(dst.parent))
    try:
        with os.fdopen(handle,"wb") as out,src.open("rb") as inp:
            shutil.copyfileobj(inp,out)
            out.flush();os.fsync(out.fileno())
        os.chmod(tmp,mode)
        os.replace(tmp,dst)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def apply(home,stage,run,expected):
    if not re.fullmatch(r"[0-9]{5,20}",run) or not PAYLOAD_SHA.fullmatch(expected):
        raise ValueError("INVALID_RUN_OR_ARTIFACT_SHA")
    home=Path(home);stage=Path(stage)
    if home!=Path("/home/zomorod2"):raise RuntimeError("WRONG_CPANEL_USER")
    private=home/".private/zomorod-business"
    store=home/"public_html/store"
    index=store/"index.php"
    lib=private/"site_store.php"
    dbfile=private/"site_store.sqlite3"
    source=stage/"index.html"
    for part in (home,private,store,stage):
        if part.is_symlink() or not part.is_dir():raise RuntimeError("UNSAFE_SITE_ROOT")
    for path in (index,lib,dbfile,source):
        check_file(path)
    if digest(source)!=expected:raise RuntimeError("QA_ARTIFACT_MISMATCH")
    if digest(lib)!=LIVE_LIB_SHA:raise RuntimeError("PRIVATE_STORE_CHANGED_REFUSING_RELEASE")
    free_root=store/"free-products"
    dest=free_root/"wheat-seed-rate-planner-v1"
    mark=dest/".zm-owner"
    file=dest/"index.html"
    for p in (free_root,dest,mark,file):
        if p.is_symlink():raise RuntimeError("DESTINATION_SYMLINK")
    if dest.exists():raise RuntimeError("PRODUCT_LOCATION_ALREADY_USED")
    before=index.read_bytes()
    if hashlib.sha256(before).hexdigest()!=LIVE_INDEX_SHA:
        raise RuntimeError("PUBLIC_STORE_CHANGED_REFUSING_RELEASE")
    candidate=build_candidate(before.decode("utf8"))
    tmp=stage/"store-index.php"
    if tmp.exists() or tmp.is_symlink():raise RuntimeError("UNOWNED_CANDIDATE")
    tmp.write_text(candidate,encoding="utf8")
    os.chmod(tmp,0o600)
    result=subprocess.run(["php","-l",str(tmp)],capture_output=True,text=True,timeout=15)
    if result.returncode:raise RuntimeError("PHP_LINT_FAIL:"+result.stderr[:300])
    # Advisory lock serializes this release. Earlier baseline guards protect other writers.
    lock=private/".zm-free-wheat-release.lock"
    if lock.is_symlink():raise RuntimeError("LOCK_SYMLINK")
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(),0o600)
        fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
        if digest(lib)!=LIVE_LIB_SHA or digest(index)!=LIVE_INDEX_SHA:
            raise RuntimeError("CONCURRENT_SITE_EDIT_DETECTED")
        backup=home/".backups"/("zomorod-wheat-"+run)
        if backup.exists() or backup.is_symlink():raise RuntimeError("BACKUP_PATH_COLLISION")
        backup.mkdir(parents=True,mode=0o700)
        os.chmod(backup,0o700)
        (backup/"store-index.php").write_bytes(before)
        os.chmod(backup/"store-index.php",0o600)
        with sqlite3.connect("file:"+str(dbfile)+"?mode=ro",uri=True) as src:
            with sqlite3.connect(str(backup/"store.sqlite3")) as copy:
                src.backup(copy)
                if copy.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                    raise RuntimeError("DB_BACKUP_INTEGRITY_FAIL")
        os.chmod(backup/"store.sqlite3",0o600)
        print("ZM_FREE_PREDEPLOY_BACKUP_VERIFIED="+str(backup),flush=True)
        made_dir=False;inserted=False;patched=False
        try:
            with sqlite3.connect(dbfile,timeout=20) as db:
                # Never modify the existing paid products or payment_state tables.
                paid=db.execute("SELECT sql FROM sqlite_master WHERE name='products'").fetchone()
                payment=db.execute("SELECT 1 FROM sqlite_master WHERE name='payment_state'").fetchone()
                if not paid or not payment or "CHECK(price_irr>0)" not in paid[0]:
                    raise RuntimeError("PAID_CATALOG_CONTRACT_MISMATCH")
                db.execute("""CREATE TABLE IF NOT EXISTS free_digital_products(
                    id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
                    description TEXT NOT NULL, download_path TEXT NOT NULL UNIQUE,
                    artifact_sha256 TEXT NOT NULL, license_text TEXT NOT NULL,
                    price_irr INTEGER NOT NULL DEFAULT 0 CHECK(price_irr=0),
                    enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
                if db.execute("SELECT 1 FROM free_digital_products WHERE sku=?",(SKU,)).fetchone():
                    raise RuntimeError("FREE_SKU_COLLISION")
                db.execute("""INSERT INTO free_digital_products
                 (sku,title,description,download_path,artifact_sha256,license_text,price_irr,enabled)
                 VALUES (?,?,?,?,?,?,0,0)""",(SKU,"محاسبه‌گر علمی بذر گندم",
                 "محاسبه‌گر آفلاین رایگان بذر گندم بر پایه تراکم هدف، وزن هزار دانه، قوه نامیه و سبزشدن مزرعه‌ای؛ نسخه ۱.",
                 DOWNLOAD,expected,"Free personal and educational use"))
                inserted=True
            free_root.mkdir(exist_ok=True,mode=0o755)
            dest.mkdir(mode=0o755)
            made_dir=True
            mark.write_text("saeit.zomorod.wheat.v1\n",encoding="utf8")
            os.chmod(mark,0o644)
            copy_atomic(source,file,0o644)
            if digest(file)!=expected:raise RuntimeError("PUBLISHED_FILE_SHA_MISMATCH")
            copy_atomic(tmp,index,0o644)
            patched=True
            if digest(index)!=digest(tmp):raise RuntimeError("PUBLIC_STORE_INSTALL_HASH_MISMATCH")
            with sqlite3.connect(dbfile,timeout=20) as db:
                db.execute("UPDATE free_digital_products SET enabled=1 WHERE sku=? AND artifact_sha256=?",(SKU,expected))
                status=db.execute("SELECT price_irr,enabled FROM free_digital_products WHERE sku=?",(SKU,)).fetchone()
                if status!=(0,1):raise RuntimeError("FREE_CATALOG_ACTIVATION_FAILED")
            print("ZM_FREE_WHEAT_NATIVE_CATALOG=ENABLED",flush=True)
            print("ZM_FREE_WHEAT_PRODUCT_SHA256="+expected,flush=True)
            print("ZM_FREE_WHEAT_PAID_STORE_PRESERVED=true",flush=True)
        except BaseException:
            if patched and digest(index)==digest(tmp):
                copy_atomic(backup/"store-index.php",index,0o644)
            with sqlite3.connect(dbfile,timeout=15) as db:
                if inserted and db.execute("SELECT 1 FROM sqlite_master WHERE name='free_digital_products'").fetchone():
                    db.execute("DELETE FROM free_digital_products WHERE sku=? AND artifact_sha256=?",(SKU,expected))
            if made_dir and mark.exists() and mark.read_text(encoding="utf8")=="saeit.zomorod.wheat.v1\n":
                file.unlink(missing_ok=True)
                mark.unlink(missing_ok=True)
                dest.rmdir()
            raise

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage",required=True)
    parser.add_argument("--run",required=True)
    parser.add_argument("--sha256",required=True)
    opts=parser.parse_args()
    apply("/home/zomorod2",opts.stage,opts.run,opts.sha256)
