#!/usr/bin/env python3
"""MojPlayWin-only courier inbox -> inactive Django factory draft catalog.

Never opens checkout, writes public files, or activates products. Imported private
drafts provide a real admin review path; a separately verified product-specific
QA + authorized owner release are still required for public publication.
"""
from __future__ import annotations
import argparse
from decimal import Decimal
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sys
import zipfile

TENANT="mojplaywin-main"
SOURCE_SCHEMA="saeit.factory.production-warehouse.v1"
QA_SCHEMA="mpw.factory.warehouse-courier.v1"
PRODUCT=re.compile(r"^[a-z][a-z0-9_]{1,63}$")
VERSION=re.compile(r"^[a-f0-9]{64}$")
MAX_PRODUCTS=10000

def checked_json(path, max_bytes=100000):
    if (not path.is_file() or path.is_symlink() or
            not 0<path.stat().st_size<=max_bytes):
        raise RuntimeError("MPW_DRAFT_UNSAFE_JSON")
    obj=json.loads(path.read_bytes())
    if not isinstance(obj,dict):
        raise RuntimeError("MPW_DRAFT_JSON_OBJECT_REQUIRED")
    return obj

def scan(root):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("MPW_DRAFT_INBOX_MISSING")
    received=root/"received"
    if not received.is_dir() or received.is_symlink():
        raise RuntimeError("MPW_DRAFT_RECEIVED_MISSING")
    rows=[]
    for product in sorted(received.iterdir()):
        if product.is_symlink() or not product.is_dir() or not PRODUCT.fullmatch(product.name):
            raise RuntimeError("MPW_DRAFT_UNSAFE_PRODUCT_DIR")
        for version in sorted(product.iterdir()):
            if version.is_symlink() or not version.is_dir() or not VERSION.fullmatch(version.name):
                raise RuntimeError("MPW_DRAFT_UNSAFE_VERSION_DIR")
            manifest=checked_json(version/"warehouse_manifest.json")
            artifact=version/"product.zip"
            if (not artifact.is_file() or artifact.is_symlink() or
                    not 0<artifact.stat().st_size<=25*1024*1024):
                raise RuntimeError("MPW_DRAFT_PRIVATE_ARTIFACT_MISSING")
            sha=hashlib.sha256(artifact.read_bytes()).hexdigest()
            if (manifest.get("schema")!=SOURCE_SCHEMA
                    or manifest.get("product_id")!=product.name
                    or manifest.get("source_sha256")!=version.name
                    or manifest.get("artifact_sha256")!=sha
                    or manifest.get("bytes")!=artifact.stat().st_size
                    or manifest.get("manufacturing_qc")!="passed"
                    or manifest.get("commercial_release") is not False):
                raise RuntimeError("MPW_DRAFT_SOURCE_MANIFEST_MISMATCH")
            try:
                with zipfile.ZipFile(artifact) as z:
                    if not z.infolist() or z.testzip() is not None:
                        raise RuntimeError("MPW_DRAFT_BAD_ZIP")
            except zipfile.BadZipFile as err:
                raise RuntimeError("MPW_DRAFT_ZIP_INVALID") from err
            qa=checked_json(version/"site_qa.json")
            if (qa.get("schema")!=QA_SCHEMA or qa.get("tenant")!=TENANT or
                    qa.get("product_id")!=product.name or
                    qa.get("version")!=version.name or
                    qa.get("artifact_sha256")!=sha or
                    qa.get("technical_zip_verified") is not True or
                    qa.get("public_listing") is not False or
                    qa.get("payment_enabled") is not False):
                raise RuntimeError("MPW_DRAFT_QA_OR_TENANT_MISMATCH")
            # The site-review report is not itself an owner publication grant.
            passed=qa.get("qa_state")=="independent_qa_passed_awaiting_owner_release"
            if passed:
                reviews=root/"independent_qa"
                doc=checked_json(reviews/product.name/(version.name+".json"))
                secret=reviews/"reviewer_hmac.key"
                if (secret.is_symlink() or not secret.is_file() or
                        secret.stat().st_mode & 0o077 or not 32<=secret.stat().st_size<=1024):
                    raise RuntimeError("MPW_DRAFT_REVIEW_KEY_REQUIRED")
                signed={k:v for k,v in doc.items() if k!="signature"}
                canonical=json.dumps(signed,sort_keys=True,ensure_ascii=False,
                                     separators=(",",":")).encode()
                signature=hmac.new(secret.read_bytes(),canonical,hashlib.sha256).hexdigest()
                if (not isinstance(doc.get("signature"),str)
                        or not hmac.compare_digest(doc["signature"],signature)
                        or doc.get("artifact_sha256")!=sha
                        or doc.get("source_sha256")!=version.name
                        or doc.get("product_id")!=product.name
                        or doc.get("tenant")!=TENANT):
                    raise RuntimeError("MPW_DRAFT_REVIEW_SIGNATURE_MISMATCH")
            identity=hashlib.sha256((TENANT+"/"+product.name+"/"+version.name).encode()).hexdigest()
            title=manifest.get("product_name") or product.name.replace("_"," ").title()
            if not isinstance(title,str) or not 1<=len(title)<=300:
                raise RuntimeError("MPW_DRAFT_PRODUCT_TITLE_INVALID")
            rows.append({"product_id":product.name,"version":version.name,
                         "artifact_sha256":sha,"identity":identity,
                         "title":title,"qa_passed":passed})
            if len(rows)>MAX_PRODUCTS:
                raise RuntimeError("MPW_DRAFT_TOO_MANY_PRODUCTS")
    return rows

def target(app,docroot):
    app=Path(app).expanduser().resolve()
    docroot=Path(docroot).expanduser().resolve()
    if (docroot.name!="mojplaywin.com" or
            not app.is_dir() or app.name!="Saeit-staging" or
            not (app/"manage.py").is_file()):
        raise RuntimeError("MPW_DRAFT_WRONG_SITE_ROOT")
    wsgi=docroot/"passenger_wsgi.py"
    if not wsgi.is_file() or wsgi.is_symlink() or "Saeit-staging" not in wsgi.read_text(errors="replace"):
        raise RuntimeError("MPW_DRAFT_WRONG_PASSENGER_MAPPING")
    return app

def import_drafts(root,app,docroot,*,apply=False):
    rows=scan(root)
    result={"tenant":TENANT,"versions_examined":len(rows),
            "quality_reviewed":sum(x["qa_passed"] for x in rows),
            "quality_pending":sum(not x["qa_passed"] for x in rows),
            "created_inactive_drafts":0,"already_existing":0,
            "publicly_activated":0,"payments_enabled":0,
            "status":"preview" if not apply else "applied"}
    if not rows:
        return result
    app=target(app,docroot)
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django
    django.setup()
    from django.conf import settings
    from django.apps import apps
    from django.contrib.auth import get_user_model
    from django.db import transaction
    if settings.DEBUG is not False:
        raise RuntimeError("MPW_DRAFT_PRODUCTION_DEBUG_UNSAFE")
    User=get_user_model()
    owners=User.objects.filter(is_active=True,is_staff=True,is_superuser=True)
    if owners.count()!=1:
        raise RuntimeError("MPW_DRAFT_UNAMBIGUOUS_OWNER_REQUIRED")
    owner=owners.first()
    ProductModel=apps.get_model("core","Product")
    for item in rows:
        match=ProductModel.objects.filter(metadata__factory_courier_identity=item["identity"])
        if match.count()>1:
            raise RuntimeError("MPW_DRAFT_DUPLICATE_IDENTITY")
        if match.exists():
            old=match.first()
            m=old.metadata if isinstance(old.metadata,dict) else {}
            if m.get("factory_source_sha256")!=item["version"] or old.owner_id!=owner.pk:
                raise RuntimeError("MPW_DRAFT_EXISTING_PRODUCT_CONFLICT")
            result["already_existing"]+=1
            continue
        if not apply:
            continue
        with transaction.atomic():
            if ProductModel.objects.select_for_update().filter(
                    metadata__factory_courier_identity=item["identity"]).exists():
                result["already_existing"]+=1
                continue
            metadata={
                "factory_origin":"saeit_vps_warehouse_courier",
                "factory_storefront":"mojplaywin",
                "factory_courier_identity":item["identity"],
                "factory_recipe":item["product_id"],
                "factory_source_sha256":item["version"],
                "factory_bridge_sha256":item["artifact_sha256"],
                "factory_archive_private":True,
                "factory_publication_permission":False,
                "factory_factual_and_market_qa":"passed" if item["qa_passed"] else "pending",
                "factory_license_review":"reviewed" if item["qa_passed"] else "pending",
                "factory_status":"owner_publication_review_required" if item["qa_passed"] else "independent_review_required",
                "factory_delivery_ready":False,
                "checkout_enabled":False,
                "manual_price_required":True,
                "factory_private_relative_ref":"received/"+item["product_id"]+"/"+item["version"]+"/product.zip",
            }
            p=ProductModel(title=item["title"],product_type="digital",price=Decimal("0"),
                           currency="USD",active=False,owner=owner,
                           knowledge_article=None,metadata=metadata)
            if any(f.name=="factory_managed" for f in ProductModel._meta.fields):
                p.factory_managed=True
            p.full_clean()
            p.save()
            result["created_inactive_drafts"]+=1
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--inbox",required=True)
    p.add_argument("--app",required=True)
    p.add_argument("--document-root",required=True)
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    result=import_drafts(args.inbox,args.app,args.document_root,apply=args.apply)
    print("MPW_COURIER_STORE_DRAFT_RESULT="+json.dumps(result,sort_keys=True))

if __name__=="__main__":
    main()
