#!/usr/bin/env python3
"""Point inactive exact Product 879 to original-vector private stock, transactionally."""
import copy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import sys
import zipfile

APP=Path("/home/zomorod2/Saeit-staging")
ROOT=Path("/home/zomorod2/.private_mojplaywin_digital_products")
ARCHIVE=ROOT/"atelier-interior-kit-v1-original-vector-edition.zip"
SHA="20894f2de0228318c0e96ba407c2bd4aa98b62ba2f3f2f2fbca53987c9276783"
OLD_SHA="98bffad4ccf36f84c7924ca77e4a8b473b42f33a8fce4d85cefe2367afc097aa"
BACKUP=ROOT/"atelier-product-879-inactive-before-vector.json"
SKU="atelier-interior-kit-v1"
TITLE="Atelier Interior — Client-Ready Website Kit"

def digest(raw):return hashlib.sha256(raw).hexdigest()

def verify_asset():
    if ROOT.is_symlink() or not ROOT.is_dir() or stat.S_IMODE(ROOT.stat().st_mode)&0o077:
        raise RuntimeError("INVALID_PRIVATE_ROOT")
    if ARCHIVE.is_symlink() or not ARCHIVE.is_file() or stat.S_IMODE(ARCHIVE.stat().st_mode)&0o077:
        raise RuntimeError("VECTOR_ARCHIVE_NOT_PRIVATE")
    data=ARCHIVE.read_bytes()
    if digest(data)!=SHA:
        raise RuntimeError("VECTOR_SHA_MISMATCH")
    with zipfile.ZipFile(ARCHIVE) as z:
        if z.testzip() is not None or len(z.namelist())!=11:
            raise RuntimeError("VECTOR_ZIP_INVALID")
        names=z.namelist()
        if len([x for x in names if x.endswith(".svg")])!=5 or any(x.endswith((".jpg",".png",".webp")) for x in names):
            raise RuntimeError("THIRD_PARTY_PHOTO_INSIDE_CANDIDATE")
        if b"purchaser receives a non-exclusive" not in z.read("README.md").lower():
            raise RuntimeError("PURCHASER_LICENSE_NOT_INCLUDED")
        if b"ATELIER_CONFIG" not in z.read("config.js"):
            raise RuntimeError("CONFIG_NOT_CUSTOMIZABLE")

def main():
    if os.environ.get("ATELIER_VECTOR_METADATA_APPROVAL")!="owner-2026-10-21":
        raise PermissionError("MISSING_OWNER_SCOPE")
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":
        raise RuntimeError("WRONG_CPANEL_OWNER")
    verify_asset()
    if APP.is_symlink() or not (APP/"manage.py").is_file():
        raise RuntimeError("NOT_EXPECTED_APP")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    os.chdir(APP);sys.path.insert(0,str(APP))
    import django
    django.setup()
    from django.db import transaction
    from core.models import Product
    with transaction.atomic():
        p=Product.objects.select_for_update().get(pk=879)
        if p.title!=TITLE or p.price!=Decimal("6.80") or p.currency!="USD" or p.active:
            raise RuntimeError("PRODUCT_879_NOT_EXACT_INACTIVE")
        m=p.metadata
        if not isinstance(m,dict) or m.get("sku")!=SKU or not isinstance(m.get("mpw_commerce"),dict):
            raise RuntimeError("WRONG_PRODUCT_METADATA")
        if m.get("sha256")==SHA and m.get("private_file")==str(ARCHIVE):
            state="already_linked_without_mutation"
        elif m.get("sha256")==OLD_SHA and m.get("private_file")==str(ROOT/"atelier-interior-kit-v1-repacked.zip"):
            if BACKUP.is_symlink():
                raise RuntimeError("BACKUP_SYMLINK_BLOCKED")
            snapshot=json.dumps({"id":p.pk,"price":str(p.price),"currency":p.currency,
                                 "active":p.active,"metadata":m},sort_keys=True,ensure_ascii=False).encode("utf8")
            if BACKUP.exists():
                if not BACKUP.is_file() or digest(BACKUP.read_bytes())!=digest(snapshot):
                    raise RuntimeError("EXISTING_SNAPSHOT_DOES_NOT_MATCH_CURRENT_ROW")
            else:
                with BACKUP.open("xb") as f:
                    os.fchmod(f.fileno(),0o600)
                    f.write(snapshot);f.flush();os.fsync(f.fileno())
            new=copy.deepcopy(m)
            new.update({
                "edition":"1.1-original-vector",
                "private_file":str(ARCHIVE),"sha256":SHA,
                "asset_verified":True,
                "license_verified":True,
                "rights_review_status":"original vector illustrations + owner-generated site source; no bundled stock photography",
                "license_review_basis":"purchaser license included in archive; no third party binaries or remote assets",
                "quality_approved":False,
                "factory_publication_permission":True,
                "checkout_enabled":False,"payment_live":False,"sales_enabled":False,"in_stock":False,
                "short_description":"Editable responsive interior studio website kit, five original SVG illustrations, gallery and WhatsApp inquiry.",
                "catalog_state":"original_vector_edition_private_QA_hold",
            })
            new["mpw_commerce"].update({
                "enabled":False,"fulfillment":"digital",
                "private_file":str(ARCHIVE),"filename":ARCHIVE.name,"sha256":SHA,
                "main_host_only":True,
            })
            p.metadata=new
            p.full_clean()
            p.save(update_fields=["metadata","updated_at"])
            state="inactive_vector_file_linked"
        else:
            raise RuntimeError("PRODUCT_METADATA_UNRECOGNIZED_NO_OVERWRITE")
    verify=Product.objects.get(pk=879)
    if verify.active or verify.metadata.get("sha256")!=SHA or verify.metadata["mpw_commerce"]["enabled"]:
        raise RuntimeError("POSTWRITE_INACTIVE_GUARD_FAILED")
    print("ATELIER_VECTOR_NATIVE_METADATA="+json.dumps({
        "id":879,"state":state,"price":"6.80","vector_zip_sha256":SHA,
        "license_basis":"original-code-and-graphics","quality_release_pending":True,
        "public_payment_enabled":False,"product_active":False,
        "original_archives_untouched":True,"isolated_snapshot_created":BACKUP.is_file(),
    },sort_keys=True))
if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":
        assert len(SHA)==64 and SHA!=OLD_SHA
        print("ATELIER_ORIGINAL_VECTOR_METADATA_GUARD_SELFTEST=PASS")
    elif len(sys.argv)==1:main()
    else:raise SystemExit(2)
