#!/usr/bin/env python3
"""Import only four SHA-matched Astra private ZIPs as inactive MojPlayWin drafts.

Authorized by owner's instruction to commercialize. No checkout, payments,
site asset publication, automatic entitlement, or changes to other products.
Runs on the bound Saeit-staging Django app only; can safely dry-run first.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

EXPECTED_SKUS={
    "ASTRA-ORCHARD-01","ASTRA-PROCURE-01",
    "ASTRA-WATER-01","ASTRA-CIRCUIT-01",
}
SHA=re.compile(r"[a-f0-9]{64}\Z")
SKU=re.compile(r"ASTRA-[A-Z]+-[0-9]{2}\Z")


def _sha(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(256*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def verify_store_bundle(catalog_file, package_root):
    cat=Path(catalog_file)
    folder=Path(package_root)
    if cat.is_symlink() or not cat.is_file() or cat.stat().st_size>100000:
        raise ValueError("unsafe commercial catalog")
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("unsafe private package folder")
    doc=json.loads(cat.read_text(encoding="utf-8"))
    if (doc.get("mode")!="commercial_preparation_not_store_activation" or
            doc.get("owner_exclusive_rights_declared_for_four_products") is not True or
            doc.get("storefront_target")!="mojplaywin.com" or
            doc.get("publications")!=0 or
            doc.get("real_checkout_transactions")!=0 or
            not isinstance(doc.get("items"),list) or len(doc["items"])!=4):
        raise ValueError("unrecognized four-product owner-attested catalog")
    records=[]
    for item in doc["items"]:
        sku=item.get("sku")
        proof=item.get("source_proof") or {}
        digest=proof.get("artifact_sha256")
        if (not isinstance(sku,str) or not SKU.fullmatch(sku) or
                sku not in EXPECTED_SKUS or
                not isinstance(digest,str) or not SHA.fullmatch(digest) or
                item.get("status")!="PRIVATE_COMMERCIAL_CANDIDATE_NOT_FOR_SALE" or
                item.get("owner_exclusive_rights_declared") is not True or
                item.get("checkout_authorized") is not False or
                item.get("public_listing_authorized") is not False or
                item.get("quality_score") is not None):
            raise ValueError("product release attestations not matched")
        price=Decimal(str(item["suggested_discounted_price_usd"]))
        list_price=Decimal(str(item["suggested_list_price_usd"]))
        if (not Decimal("0.01")<=price<=Decimal("1000.00") or
                price!=(list_price*Decimal("0.10")).quantize(Decimal("0.01"))):
            raise ValueError("unexpected 90 percent discount")
        archive=folder/(sku+"-"+digest+".zip")
        if (archive.is_symlink() or not archive.is_file() or
                not 0<archive.stat().st_size<25_000_000 or _sha(archive)!=digest):
            raise ValueError("private archive or sha not verified: "+sku)
        title=str(item["title"])
        if not 10<=len(title)<=250:
            raise ValueError("bad item title")
        records.append({
            "sku":sku,"builder":item["builder"],"title":title,
            "list_usd":str(list_price),"sale_usd":str(price),
            "sha256":digest,"archive_name":archive.name,
            "summary":str(item["verified_technical_function"])[:300],
            "limits":str(item["important_limits"])[:500],
        })
    if {x["sku"] for x in records}!=EXPECTED_SKUS:
        raise ValueError("must have four distinct SKUs")
    return sorted(records,key=lambda x:x["sku"])


def import_drafts(catalog_file, package_root, *, app_root, document_root, apply=False):
    root=Path(app_root)
    docroot=Path(document_root)
    if (root.is_symlink() or not (root/"manage.py").is_file() or
            root.name!="Saeit-staging" or
            docroot.is_symlink() or docroot.name!="mojplaywin.com" or
            not (docroot/"passenger_wsgi.py").is_file() or
            "Saeit-staging" not in (docroot/"passenger_wsgi.py").read_text(encoding="utf-8")):
        raise ValueError("actual bound MojPlayWin application is not verified")
    entries=verify_store_bundle(catalog_file,package_root)
    import django
    from django.apps import apps
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.db import transaction
    django.setup()
    if settings.DEBUG is not False:
        raise RuntimeError("public settings must have DEBUG=False")
    User=get_user_model()
    owners=User.objects.filter(is_active=True,is_superuser=True,is_staff=True)
    if owners.count()!=1:
        raise RuntimeError("exactly one active designated owner required")
    owner=owners.first()
    Product=apps.get_model("core","Product")
    created,unchanged=0,0
    for item in entries:
        prior=Product.objects.filter(metadata__astra_sku=item["sku"])
        if prior.count()>1:
            raise ValueError("duplicate factory product SKU")
        if prior.exists():
            existing=prior.get()
            metadata=existing.metadata if isinstance(existing.metadata,dict) else {}
            if (existing.owner_id!=owner.pk or
                    metadata.get("astra_archive_sha256")!=item["sha256"] or
                    existing.active or existing.currency!="USD" or
                    existing.price!=Decimal(item["sale_usd"])):
                raise ValueError("conflicting or already public SKU; refuse mutation")
            unchanged+=1
            continue
        if not apply:
            continue
        with transaction.atomic():
            if Product.objects.select_for_update().filter(metadata__astra_sku=item["sku"]).exists():
                raise RuntimeError("concurrent product creation; retry audited import")
            metadata={
                "factory_origin":"saeit_vps",
                "factory_builder":item["builder"],
                "astra_sku":item["sku"],
                "astra_archive_sha256":item["sha256"],
                "factory_inbox_relative_ref":item["archive_name"],
                "factory_archive_private":True,
                "factory_status":"commercial_draft_pending_checkout_and_public_release",
                "factory_software_qa":"passed",
                "factory_publication_permission":False,
                "owner_exclusive_rights_declared":True,
                "third_party_license_audit":"pending",
                "factory_list_price_usd":item["list_usd"],
                "factory_discount_percent":90,
                "summary":item["summary"],
                "limitations":item["limits"],
            }
            obj=Product(
                title=item["title"],product_type="digital",
                price=Decimal(item["sale_usd"]),currency="USD",
                active=False,owner=owner,knowledge_article=None,metadata=metadata,
            )
            if any(f.name=="factory_managed" for f in Product._meta.fields):
                obj.factory_managed=True
            obj.full_clean()
            obj.save()
            created+=1
    return {"examined":len(entries),"created":created,"unchanged":unchanged,
            "publications":0,"orders":0,"payments":0,"dry_run":not apply}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog",required=True)
    p.add_argument("--packages",required=True)
    p.add_argument("--app",required=True)
    p.add_argument("--document-root",required=True)
    p.add_argument("--apply",action="store_true")
    a=p.parse_args(argv)
    result=import_drafts(a.catalog,a.packages,app_root=a.app,
                         document_root=a.document_root,apply=a.apply)
    for key,value in sorted(result.items()):
        print("ASTRA_STORE_"+key.upper()+"="+str(value))
    print("ASTRA_STORE_PUBLIC_RELEASED=0")


if __name__=="__main__":
    main()
