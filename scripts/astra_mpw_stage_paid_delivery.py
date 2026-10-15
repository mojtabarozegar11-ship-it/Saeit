#!/usr/bin/env python3
"""Stage four checksum-pinned Astra ZIP assets for PAID delivery; no sales enabled.

Moves verified COPIES from the private handoff inbox to MPW_COMMERCE_PRIVATE_ASSET_ROOT
(outside all document roots), then binds each INACTIVE Product to a disabled
server-controlled mpw_commerce/private_file. Does not enable any checkout
switch, publish an article or product, set license/quality flags, or create
orders. Reruns are idempotent and fail closed on conflicts.
"""
import argparse
from decimal import Decimal
import hashlib
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

from astra_mpw_four_draft_import import verify_store_bundle

def _sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for piece in iter(lambda:f.read(256*1024),b""):
            h.update(piece)
    return h.hexdigest()

def validate_roots(root,doc):
    asset=Path(root)
    public=Path(doc)
    if not asset.is_absolute() or asset.is_symlink() or not asset.is_dir():
        raise ValueError("configured private asset root missing or unsafe")
    if not public.is_absolute() or public.is_symlink() or not public.is_dir() or public.name!="mojplaywin.com":
        raise ValueError("unexpected MojPlayWin public document root")
    a=asset.resolve(strict=True)
    p=public.resolve(strict=True)
    if a==p or p in a.parents or a in p.parents:
        raise ValueError("private asset root cannot overlap public document root")
    return asset

def copy_assets(entries,inbox,asset_root, *, apply=False):
    source=Path(inbox)
    if not source.is_dir() or source.is_symlink():
        raise ValueError("invalid owner-private source inbox")
    dest=Path(asset_root)/"astra-four-specialist-v1"
    if dest.is_symlink() or (dest.exists() and not dest.is_dir()):
        raise ValueError("unsafe private target")
    outputs=[]
    # Validate ALL archives and existing destination integrity before writing ANY.
    for item in entries:
        filename=item["sku"]+"-"+item["sha256"]+".zip"
        origin=source/filename
        target=dest/filename
        if (origin.is_symlink() or not origin.is_file()
                or origin.stat().st_size>25_000_000
                or _sha(origin)!=item["sha256"]):
            raise ValueError("SHA mismatch or unsafe private source "+item["sku"])
        if target.is_symlink() or (target.exists() and
                (not target.is_file() or _sha(target)!=item["sha256"])):
            raise ValueError("conflicting existing delivery archive "+item["sku"])
        outputs.append((item,origin,target))
    if apply:
        dest.mkdir(mode=0o700,exist_ok=True)
        os.chmod(dest,0o700)
        for item,origin,target in outputs:
            if target.exists():
                continue
            temp=dest/("."+target.name+".staging")
            if temp.is_symlink() or temp.exists():
                raise ValueError("stale partial staging file")
            try:
                fd=os.open(str(temp),os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,"wb") as output, origin.open("rb") as stream:
                    shutil.copyfileobj(stream,output,length=256*1024)
                    output.flush()
                    os.fsync(output.fileno())
                if _sha(temp)!=item["sha256"]:
                    raise ValueError("temporary copy SHA failed")
                os.rename(temp,target)
            finally:
                if temp.exists():
                    temp.unlink()
    return [
        {"sku":item["sku"],"relative_file":"astra-four-specialist-v1/"+target.name,
         "sha256":item["sha256"],"exists":target.exists()}
        for item,_,target in outputs
    ]

def attach_to_inactive_products(entries,files, *, apply=False):
    from django.apps import apps
    from django.conf import settings
    from django.db import transaction
    from mpw_commerce.downloads import _private_file
    Product=apps.get_model("core","Product")
    keyed={x["sku"]:x for x in files}
    prepared=[]
    for item in entries:
        sku=item["sku"]
        matches=Product.objects.filter(metadata__astra_sku=sku)
        if matches.count()!=1:
            raise ValueError("SKU absent or duplicated "+sku)
        product=matches.get()
        metadata=product.metadata
        if (product.active or product.currency!="USD"
                or product.price!=Decimal(item["sale_usd"])
                or not product.factory_managed
                or not isinstance(metadata,dict)
                or metadata.get("factory_publication_permission") is not False
                or metadata.get("astra_archive_sha256")!=item["sha256"]):
            raise ValueError("active or untrusted product record "+sku)
        existing=metadata.get("mpw_commerce")
        expected={"enabled":False,"fulfillment":"digital",
                  "private_file":keyed[sku]["relative_file"]}
        if existing not in (None,expected):
            raise ValueError("existing commerce configuration conflicts "+sku)
        prepared.append((product,metadata,expected))
    if apply:
        with transaction.atomic():
            for p,meta,expected in prepared:
                current=Product.objects.select_for_update().get(pk=p.pk)
                if current.active or current.metadata!=meta:
                    raise ValueError("product modified during asset staging")
                copied=dict(meta)
                copied["mpw_commerce"]=expected
                current.metadata=copied
                current.save(update_fields=["metadata"])
                actual=_private_file(SimpleNamespace(product=current))
                if _sha(actual)!=copied["astra_archive_sha256"]:
                    raise ValueError("private download SHA mismatch: "+str(current.pk))
    return len(prepared)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog",required=True)
    parser.add_argument("--inbox",required=True)
    parser.add_argument("--app",required=True)
    parser.add_argument("--document-root",required=True)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args(argv)
    app=Path(args.app)
    if (not app.is_absolute() or app.is_symlink() or app.name!="Saeit-staging"
            or not (app/"manage.py").is_file()
            or not (app/"core/models.py").is_file()):
        raise ValueError("Saeit Django app identity mismatch")
    import django
    from django.conf import settings
    django.setup()
    if settings.DEBUG is not False:
        raise ValueError("live production Django DEBUG must be off")
    root=validate_roots(getattr(settings,"MPW_COMMERCE_PRIVATE_ASSET_ROOT",""),
                        args.document_root)
    items=verify_store_bundle(args.catalog,args.inbox)
    output=copy_assets(items,args.inbox,root,apply=args.apply)
    count=attach_to_inactive_products(items,output,apply=args.apply)
    print("ASTRA_DELIVERY_PRIVATE_FILES_VERIFIED="+str(count))
    print("ASTRA_DELIVERY_PREVIEW_ONLY="+str(not args.apply))
    print("ASTRA_DELIVERY_FILES_STAGED="+str(sum(x["exists"] for x in output)))
    print("ASTRA_DELIVERY_PUBLIC_PRODUCT_ACTIVATIONS=0")
    print("ASTRA_DELIVERY_CHECKOUT_SWITCH_MUTATIONS=0")
    print("ASTRA_DELIVERY_REVENUE_TRANSACTIONS=0")

if __name__=="__main__":
    main()
