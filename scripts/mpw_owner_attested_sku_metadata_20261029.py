#!/usr/bin/env python3
"""Private, reversible MojPlayWin owner-attestation metadata migration."""
from __future__ import annotations
import fcntl, hashlib, json, os, stat, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

HOME=Path("/home/zomorod2")
APP=HOME/"Saeit-staging"
BACKUPS=HOME/".local/share/mpw-owner-rights-release-20261029"
SKUS=(72,225,879)
# Stable digest for the owner's explicit declaration in this session. The
# declaration text is not copied to public logs or product-facing pages.
OWNER_STATEMENT_SHA256="6ad2a44037ef778ff149e0cd05a22abee89a3dc439d5b2fe7704ed54aee02f20"

def digest_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def setup():
    if APP.is_symlink() or not APP.is_dir(): raise RuntimeError("APP_ROOT_UNSAFE")
    os.chdir(APP)
    sys.path.insert(0,str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django
    django.setup()
    from core.models import Product
    from mpw_commerce.downloads import _private_file
    from mpw_commerce.buyer_orders import _eligible
    return Product,_private_file,_eligible

def inspect():
    Product,private_file,eligible=setup()
    rows={}
    for sku in SKUS:
        p=Product.objects.filter(pk=sku).first()
        if p is None or p.active is not True or not eligible(p):
            raise RuntimeError("SKU_NOT_ACTIVE_AND_ELIGIBLE:"+str(sku))
        meta=p.metadata
        if type(meta) is not dict: raise RuntimeError("SKU_METADATA_INVALID:"+str(sku))
        asset=private_file(SimpleNamespace(product=p))
        if asset.is_symlink() or not asset.is_file() or asset.stat().st_size<=0:
            raise RuntimeError("SKU_PRIVATE_ASSET_UNSAFE:"+str(sku))
        actual=digest_file(asset)
        catalog=[meta.get(k) for k in ("sha256","asset_sha256","final_pdf_sha256","pdf_sha256")]
        if actual not in catalog:
            raise RuntimeError("CATALOG_ASSET_HASH_MISMATCH:"+str(sku))
        rows[sku]={"product":p,"metadata":meta,"asset_sha256":actual}
    return rows

def safe_dir():
    BACKUPS.mkdir(mode=0o700,parents=True,exist_ok=True)
    if BACKUPS.is_symlink() or stat.S_IMODE(BACKUPS.stat().st_mode)&0o077:
        raise RuntimeError("OWNER_RIGHTS_BACKUP_NOT_PRIVATE")

def record_path(run):
    if not run.isdigit() or not (8<=len(run)<=20): raise RuntimeError("RUN_ID_INVALID")
    return BACKUPS/(run+".json")

def save_backup(run,rows):
    safe_dir()
    path=record_path(run)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    payload={"run_id":run,"owner_statement_sha256":OWNER_STATEMENT_SHA256,
             "products":{str(sku):{"metadata":row["metadata"],
               "asset_sha256":row["asset_sha256"]} for sku,row in rows.items()}}
    with os.fdopen(fd,"w",encoding="utf8") as f:
        json.dump(payload,f,ensure_ascii=False,sort_keys=True)
        f.flush();os.fsync(f.fileno())
    dfd=os.open(BACKUPS,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
    try: os.fsync(dfd)
    finally: os.close(dfd)
    return path

def check():
    rows=inspect()
    print("MPW_OWNER_RIGHTS_PREFLIGHT="+json.dumps({
      "read_only":True,"orders_created":0,"payments_created":0,
      "skus":{str(k):{"active":True,"eligible":True,
       "asset_sha256_prefix":v["asset_sha256"][:16]} for k,v in rows.items()}},sort_keys=True))

def apply(run):
    rows=inspect()
    safe_dir()
    with (BACKUPS/"release.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        backup=save_backup(run,rows)
        from django.db import transaction
        try:
            with transaction.atomic():
                for sku,row in rows.items():
                    p=row["product"]
                    meta=dict(row["metadata"])
                    meta.update({
                      "rights_cleared":True,
                      "publication_approved":True,
                      "rights_asset_sha256":row["asset_sha256"],
                      "rights_document_sha256":OWNER_STATEMENT_SHA256,
                      "rights_evidence_type":"owner_attestation",
                      "rights_basis":"factory_product_owner_declaration",
                      "rights_attestation_run_id":run,
                      "rights_attestation_received_at":datetime.now(timezone.utc).isoformat(),
                    })
                    p.metadata=meta
                    p.save(update_fields=["metadata"])
        except BaseException:
            # The enclosing database transaction restores every row atomically.
            raise
    print("MPW_OWNER_RIGHTS_METADATA=APPLIED_PRIVATE_ATTESTATION; SKUS=72,225,879; ORDERS=0; PAYMENTS=0; BACKUP="+str(backup))

def verify(run):
    rows=inspect()
    for sku,row in rows.items():
        m=row["metadata"]
        if not (m.get("rights_cleared") is True and m.get("publication_approved") is True
          and m.get("rights_asset_sha256")==row["asset_sha256"]
          and m.get("rights_document_sha256")==OWNER_STATEMENT_SHA256
          and m.get("rights_evidence_type")=="owner_attestation"
          and m.get("rights_attestation_run_id")==run):
            raise RuntimeError("OWNER_RIGHTS_METADATA_VERIFY_FAILED:"+str(sku))
    print("MPW_OWNER_RIGHTS_METADATA=VERIFIED; SKUS=72,225,879")

def rollback(run):
    path=record_path(run)
    if path.is_symlink() or not path.is_file(): raise RuntimeError("OWNER_RIGHTS_BACKUP_MISSING")
    snapshot=json.loads(path.read_text("utf8"))
    if snapshot.get("run_id")!=run or snapshot.get("owner_statement_sha256")!=OWNER_STATEMENT_SHA256:
        raise RuntimeError("OWNER_RIGHTS_BACKUP_INVALID")
    Product,_,_=setup()
    from django.db import transaction
    with transaction.atomic():
        for sku in SKUS:
            p=Product.objects.select_for_update().get(pk=sku)
            meta=p.metadata if type(p.metadata) is dict else {}
            if meta.get("rights_attestation_run_id")!=run:
                raise RuntimeError("OWNER_RIGHTS_NEWER_METADATA_OR_WRONG_RUN:"+str(sku))
            expected=snapshot["products"][str(sku)]["asset_sha256"]
            if meta.get("rights_asset_sha256")!=expected:
                raise RuntimeError("OWNER_RIGHTS_ASSET_CHANGED:"+str(sku))
        for sku in SKUS:
            p=Product.objects.select_for_update().get(pk=sku)
            p.metadata=snapshot["products"][str(sku)]["metadata"]
            p.save(update_fields=["metadata"])
    print("MPW_OWNER_RIGHTS_METADATA=ROLLED_BACK_EXACT_SNAPSHOT; SKUS=72,225,879")


def restart_passenger():
    from pathlib import Path
    for root in (HOME/"Saeit-staging",HOME/"mojplaywin.com"):
        if root.is_symlink() or not root.is_dir():
            raise RuntimeError("UNSAFE_PASSENGER_ROOT")
        wsgi=root/"passenger_wsgi.py"
        if root.name=="mojplaywin.com":
            if wsgi.is_symlink() or not wsgi.is_file() or "Saeit-staging" not in wsgi.read_text("utf8","replace"):
                raise RuntimeError("PASSENGER_MAPPING_CHANGED")
        tmp=root/"tmp"
        if tmp.is_symlink() or not tmp.is_dir():
            raise RuntimeError("UNSAFE_RESTART_DIRECTORY")
        marker=tmp/"restart.txt"
        if marker.is_symlink() or (marker.exists() and not marker.is_file()):
            raise RuntimeError("UNSAFE_RESTART_MARKER")
        marker.touch()
    print("MPW_PASSENGER_RESTART_MARKERS=TOUCHED; ORDERS=0; PAYMENTS=0")

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="check": check()
    elif len(sys.argv)==3 and sys.argv[1]=="apply": apply(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="verify": verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback": rollback(sys.argv[2])
    elif len(sys.argv)==2 and sys.argv[1]=="restart": restart_passenger()
    else: raise SystemExit("Usage: check | apply RUN_ID | verify RUN_ID | rollback RUN_ID")
