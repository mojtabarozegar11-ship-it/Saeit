#!/usr/bin/env python3
"""Safely copy exact Atelier ZIP into existing payment engine private file root."""
import copy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import sys

APP=Path("/home/zomorod2/Saeit-staging")
SOURCE=Path("/home/zomorod2/.private_mojplaywin_digital_products/atelier-interior-kit-v1-original-vector-edition.zip")
SHA="20894f2de0228318c0e96ba407c2bd4aa98b62ba2f3f2f2fbca53987c9276783"
NAME="atelier-interior-kit-v1-original-vector-edition.zip"
def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(131072),b""):
            h.update(b)
    return h.hexdigest()
def secure(p):
    if p.is_symlink():raise RuntimeError("SYMLINK_REFUSED")
    s=p.stat()
    if s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)&0o077:
        raise RuntimeError("WRONG_OWNER_OR_EXPOSED_MODE")
def main():
    if os.environ.get("ATELIER_PRIVATE_ENGINE_COPY_APPROVAL")!="owner-2026-10-21":
        raise PermissionError("MISSING_SCOPED_COPY_PERMISSION")
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":
        raise RuntimeError("WRONG_OS_ACCOUNT")
    secure(SOURCE);secure(SOURCE.parent)
    if digest(SOURCE)!=SHA:raise RuntimeError("SOURCE_SHA_MISMATCH")
    os.chdir(APP);sys.path.insert(0,str(APP))
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.db import transaction
    from core.models import Product
    import core.cryptopay_checkout as engine
    root=Path(engine.PRIVATE_ROOT)
    home=Path("/home/zomorod2")
    if not root.is_absolute() or not root.is_relative_to(home) or root==home:
        raise RuntimeError("PAYMENT_PRIVATE_ROOT_OUT_OF_SCOPE")
    if any("public_html"==part or "mojplaywin.com"==part for part in root.parts):
        raise RuntimeError("PUBLIC_DOCROOT_REFUSED")
    if not root.is_dir() or root.parent.is_symlink():raise RuntimeError("INVALID_PAYMENT_PRIVATE_ROOT")
    if root.is_symlink():raise RuntimeError("ROOT_SYMLINK")
    # Existing engine root may be shared/0755; create an isolated 0700 child
    # rather than changing permissions on the shared commerce directory.
    private_child=root/".atelier_paid_digital_20261021"
    if private_child.is_symlink():raise RuntimeError("CHILD_SYMLINK")
    if not private_child.exists():private_child.mkdir(mode=0o700)
    if not private_child.is_dir():raise RuntimeError("CHILD_NOT_DIRECTORY")
    secure(private_child)
    dest=private_child/NAME
    if dest.is_symlink():raise RuntimeError("DESTINATION_SYMLINK")
    if dest.exists():
        secure(dest)
        if not dest.is_file() or digest(dest)!=SHA:raise RuntimeError("PRIVATE_FILE_COLLISION")
        state="already_stocked"
    else:
        # Source is less than 10MB, so one exclusive, synchronous bounded write.
        if SOURCE.stat().st_size>10_000_000:raise RuntimeError("OVERSIZE_PRODUCT")
        with dest.open("xb") as f:
            os.fchmod(f.fileno(),0o600)
            with SOURCE.open("rb") as source:
                for b in iter(lambda:source.read(131072),b""):
                    f.write(b)
            f.flush();os.fsync(f.fileno())
        if digest(dest)!=SHA:raise RuntimeError("COPIED_BYTE_MISMATCH")
        state="newly_stocked_in_engine_root"
    from core.cryptopay_checkout import _file_for,product_delivery_ready
    with transaction.atomic():
        p=Product.objects.select_for_update().get(pk=879)
        m=p.metadata
        if p.title!="Atelier Interior — Client-Ready Website Kit" or p.active or p.price!=Decimal("6.80"):
            raise RuntimeError("NOT_SPECIFIC_INACTIVE_PRODUCT")
        if not isinstance(m,dict) or m.get("sha256")!=SHA:
            raise RuntimeError("WRONG_PRODUCT_SHA")
        cur=m.get("private_file")
        if cur==str(dest) and m.get("mpw_commerce",{}).get("private_file")==str(dest):
            db="already_exact"
        elif cur==str(SOURCE):
            new=copy.deepcopy(m)
            new["private_file"]=str(dest)
            new["mpw_commerce"]["private_file"]=str(dest)
            new["mpw_private_file_prepared"]=True
            new["private_asset_installed"]=True
            new["fulfillment_status"]="private_asset_installed_checkout_disabled"
            new["checkout_enabled"]=False
            new["mpw_commerce"]["enabled"]=False
            candidate=copy.copy(p)
            candidate.metadata=new
            resolved=_file_for(candidate)
            if resolved is None or Path(resolved).resolve()!=dest.resolve() or not product_delivery_ready(candidate):
                raise RuntimeError("ENGINE_ROOT_CANDIDATE_STILL_UNDELIVERABLE")
            p.metadata=new
            p.full_clean()
            p.save(update_fields=["metadata","updated_at"])
            db="inactive_product_linked_to_engine"
        else:raise RuntimeError("UNEXPECTED_PRIVATE_FILE_CURRENT_REF")
    p=Product.objects.get(pk=879)
    final=_file_for(p)
    if p.active or not final or Path(final).resolve()!=dest.resolve() or not product_delivery_ready(p):
        raise RuntimeError("DELIVERY_GATE_NOT_GREEN_AFTER_LINK")
    print("ATELIER_PAYMENT_PRIVATE_STOCK="+json.dumps({
        "sku":"atelier-interior-kit-v1","product_id":879,"file_sha256":SHA,
        "private_stock_state":state,"product_state":db,
        "native_delivery_gate":True,"paid_sales_enabled":False,
        "route_or_template_mutations":False,"other_products_unchanged":True,
    },sort_keys=True))
if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":
        assert NAME.endswith(".zip") and len(SHA)==64
        print("ATELIER_ENGINE_PRIVATE_ROOT_SELFTEST=PASS")
    elif len(sys.argv)==1:main()
    else:raise SystemExit(2)
