"""Idempotent draft pricing for verified Saeit factory receipts.

Applies only to exact, unique, inactive MojPlayWin product drafts after checking
a published valuation policy, private sha256-backed receipts and unique owner.
Never activates sales, changes payment configuration or exposes private archives.
A fresh private row-level snapshot is written before the database transaction.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import sys

from factory_fair_90pct_pricing import assess

ROOT = Path("/home/zomorod2")
WAREHOUSE = ROOT / ".saeit-factory-inbox"
BASE_POLICY = Path(__file__).resolve().parent.parent / "pricing/factory_2026-10-14_valuation.json"


def check_receipt(recipe):
    p=WAREHOUSE/"bin/store_receiver.py"
    if not p.is_file() or p.is_symlink():
        raise RuntimeError("PRIVATE_RECEIVER_UNAVAILABLE")
    spec=importlib.util.spec_from_file_location("factory_policy_receiver",p)
    reader=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    receipts=WAREHOUSE/"receipts"/recipe
    files=list(receipts.glob("*.json")) if receipts.is_dir() and not receipts.is_symlink() else []
    digests=[x.stem for x in files if not x.is_symlink() and reader.status(WAREHOUSE,recipe,x.stem)]
    if len(digests)!=1:
        raise RuntimeError("EXACT_PRIVATE_RECEIPT_REQUIRED")
    return digests[0]


def plan_quotes():
    assert BASE_POLICY.is_file() and not BASE_POLICY.is_symlink()
    original=json.loads(BASE_POLICY.read_text("utf-8"))
    return original, assess(original)


def update(*, apply=False):
    from django.conf import settings
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import transaction,connection
    from core.models import Product
    if settings.DEBUG is not False or connection.vendor != "mysql":
        raise RuntimeError("PRODUCTION_DB_VERIFICATION_FAILED")
    if ROOT != Path.home() or not WAREHOUSE.is_dir() or WAREHOUSE.is_symlink():
        raise RuntimeError("WRONG_HOST_CONTEXT")
    owner=get_user_model().objects.filter(is_active=True,is_staff=True,is_superuser=True)
    if owner.count()!=1:
        raise RuntimeError("SINGLE_AUTHORIZED_OWNER_REQUIRED")
    owner_pk=owner.first().pk
    source,rows=plan_quotes()
    refs={p["recipe"]:p for p in source["assessments"]}
    targets=[]
    for data in rows:
        recipe=data["recipe"]
        ref=refs[recipe]
        digest=check_receipt(recipe)
        if recipe=="farm_enterprise_economics" and digest!=ref["verified_public_sha256"]:
            raise RuntimeError("FREE_PRODUCT_SHA_NOT_MATCHED")
        if recipe=="water_budget_economics" and not digest.startswith(ref["private_archive_receipt_sha256_prefix"]):
            raise RuntimeError("WATER_PACKAGE_SHA_NOT_MATCHED")
        candidates=Product.objects.filter(metadata__factory_bridge_sha256=digest)
        if candidates.count()!=1:
            raise RuntimeError("EXACT_CATALOG_ITEM_REQUIRED")
        product=candidates.first()
        if (product.owner_id != owner_pk or product.active
            or product.currency!="USD" or product.product_type!="digital"
            or product.metadata.get("factory_origin")!="saeit_vps"
            or product.metadata.get("factory_recipe")!=recipe
            or product.metadata.get("factory_software_qa")!="passed"):
            raise RuntimeError("PRODUCT_PROVENANCE_OR_RELEASE_STATUS_INVALID")
        target=Decimal(data["launch_quote"])
        if product.price not in (Decimal("0.00"),target):
            raise RuntimeError("EXISTING_PRICE_CONFLICT")
        targets.append((product.pk,recipe,digest,target,ref,data))
    print("FACTORY_PRICING_VERIFIED_CANDIDATES="+str(len(targets)))
    for product_id,recipe,digest,target,ref,data in targets:
        print("FACTORY_PRICING_QUOTED_"+recipe.upper()+"="+str(target)+"_USD")
    if not apply:
        print("FACTORY_PRICING_DRY_RUN=True")
        return
    # The user has approved a 90% assessed-value launch pricing policy; this
    # is NOT evidence of a historic regular selling price.
    backup_root=ROOT/".mpw-factory-pricing-backups"
    if backup_root.is_symlink():
        raise RuntimeError("BACKUP_PARENT_SYMLINK")
    backup_root.mkdir(mode=0o700,exist_ok=True)
    backup_root.chmod(0o700)
    folder=backup_root/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+secrets.token_hex(4))
    folder.mkdir(mode=0o700)
    snapshot=[]
    for product_id,recipe,sha,price,ref,data in targets:
        p=Product.objects.get(pk=product_id)
        snapshot.append({"id":p.pk,"recipe":recipe,"price":str(p.price),
                         "currency":p.currency,"active":p.active,"metadata":p.metadata})
    path=folder/"product_preimage.json"
    path.write_text(json.dumps(snapshot,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    path.chmod(0o600)
    assert stat.S_IMODE(path.stat().st_mode)==0o600 and json.loads(path.read_text())==snapshot
    print("FACTORY_PRICING_PRIVATE_PREIMAGE_SNAPSHOT_VERIFIED=True")
    with transaction.atomic():
        for product_id,recipe,sha,target,ref,data in targets:
            p=Product.objects.select_for_update().get(pk=product_id)
            if p.active or p.owner_id!=owner_pk or p.metadata.get("factory_bridge_sha256")!=sha:
                raise RuntimeError("CONCURRENT_CATALOG_CHANGE_REFUSED")
            if p.price not in (Decimal("0.00"),target):
                raise RuntimeError("CONCURRENT_PRICE_CHANGE_REFUSED")
            metadata=dict(p.metadata)
            metadata.update({
                "factory_pricing_policy_version":"2026-10-14-v1",
                "factory_price_evaluation_status":"provisional_fair_value_verified_for_exact_package",
                "factory_assessed_reference_usd":ref["fair_normal_price_usd"],
                "factory_launch_reduction_percent":"90" if target>0 else "not_applicable_free",
                "factory_price_reference_is_historical_regular_price":False,
                "factory_marketing_can_claim_former_price":False,
                "factory_market_review_required_before_live_promotion":True,
                "factory_paid_checkout_ready":False,
                "factory_price_original_source":"manual_market_benchmark_2026-10-14",
            })
            if recipe=="water_budget_economics":
                metadata["factory_status"]="priced_pending_commercial_release_gate"
                metadata["factory_publication_permission"]=False
                metadata["factory_support_review"]="pending"
                metadata["factory_license_review"]="pending"
            p.price=target
            p.metadata=metadata
            p.full_clean()
            p.save(update_fields=["price","metadata","updated_at"])
        for product_id,recipe,sha,target,_,_ in targets:
            verify=Product.objects.get(pk=product_id)
            assert verify.price==target and not verify.active
    print("FACTORY_PRICING_PRIVATE_DRAFT_PRICES_APPLIED=True")
    print("FACTORY_PRICING_PAID_PURCHASES_NOT_ENABLED=True")
    print("FACTORY_PRICING_PUBLIC_PROMOTIONS_NOT_ENABLED=True")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    update(apply=args.apply)


if __name__=="__main__":
    main()
