#!/usr/bin/env python3
"""Execute real bounded technical rework on MojPlayWin's returned stock.

Checks every immutable source stock receipt and original ZIP; attempts to build
the absent, usable, source-bound consumer bundle with the existing genuine
packager; independently verifies the result with the site's courier contract.
Each case is written to a durable private per-version repair record.

This NEVER forges reviewer, rights, license, price or owner authorization.
A commercial-review-only rejection remains rejected even if packaging succeeds.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent
ROOT=Path.home()/"factory-runtime/private/autonomous-product-cycle"
SCHEMA="mpw.factory.stage1-executed-technical-repair.v1"
NAME=re.compile(r"^[a-z][a-z0-9_]{1,63}-[a-f0-9]{64}\.json$")
MAX=50

def load(name):
    path=HERE/(name+".py")
    if not path.is_file() or path.is_symlink():raise ValueError("REPAIR_TRUSTED_MODULE_MISSING")
    spec=importlib.util.spec_from_file_location("repair_scope_"+name,str(path))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

def private(path):
    path=Path(path)
    if path.is_symlink():raise ValueError("REPAIR_UNSAFE_PRIVATE_DIR")
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not path.is_dir() or path.is_symlink():raise ValueError("REPAIR_BAD_PRIVATE_DIR")
    os.chmod(path,0o700)
    return path

def save(path,obj):
    target=Path(path)
    private(target.parent)
    if target.is_symlink():raise ValueError("REPAIR_OUTPUT_SYMLINK")
    raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    if target.is_file() and target.read_bytes()==raw:return False
    fd,temp=tempfile.mkstemp(prefix=".rework-",dir=str(target.parent))
    try:
        with os.fdopen(fd,"wb") as file:
            file.write(raw);file.flush();os.fsync(file.fileno())
        os.chmod(temp,0o600)
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return True

def stage1(root,courier):
    loc=root/"design-intake/mojplaywin-stage1-quality-returns"
    if not loc.is_dir() or loc.is_symlink():raise ValueError("REPAIR_STAGE1_MISSING")
    entries=sorted(loc.iterdir())
    if len(entries)>MAX:raise ValueError("REPAIR_TOO_MANY_RETURNS")
    if any(not p.is_file() or p.is_symlink() or not NAME.fullmatch(p.name) for p in entries):
        raise ValueError("REPAIR_UNSAFE_STAGE1_ENTRIES")
    return [(p,courier.json_file(p,100000)) for p in entries]

def validate_original(root,filename,row,courier):
    if (row.get("schema")!=courier.RETURN_SCHEMA or row.get("tenant")!=courier.TENANT or
        row.get("stage")!=1 or row.get("status")!="return_for_qa_completion" or
        row.get("issues")!=list(courier.ISSUES) or
        row.get("factory_original_must_be_preserved") is not True or
        row.get("published") is not False):
        raise ValueError("REPAIR_INVALID_STAGE1_SOURCE")
    product=row.get("product_id");version=row.get("source_sha256")
    if (not isinstance(product,str) or not courier.RECIPE.fullmatch(product) or
        not isinstance(version,str) or not courier.SHA.fullmatch(version) or
        filename!=product+"-"+version+".json"):
        raise ValueError("REPAIR_IDENTITY_MISMATCH")
    stock=root/"production-warehouse/finished"/product/version
    if stock.is_symlink() or not stock.is_dir():raise ValueError("REPAIR_FACTORY_STOCK_MISSING")
    manifest=courier.json_file(stock/"warehouse_manifest.json",100000)
    blob=stock/"product.zip"
    if not blob.is_file() or blob.is_symlink() or not 0<blob.stat().st_size<=courier.MAX_ZIP:
        raise ValueError("REPAIR_ORIGINAL_ZIP_MISSING")
    raw=blob.read_bytes()
    courier.verify_stock(manifest,product,version,raw)
    if row["artifact_sha256"]!=manifest["artifact_sha256"]:
        raise ValueError("REPAIR_SOURCE_RETURN_SHA_DRIFT")
    return product,version,manifest,raw

def once(root,courier,packager,native,filename,row,do_pack):
    """Returns honest per-source result. No mutation of original production ZIP."""
    item={"schema":SCHEMA,
      "tenant":courier.TENANT,
      "source_receipt_sha256":courier.digest(courier.json_blob(row)),
      "product_id":row.get("product_id"),"source_sha256":row.get("source_sha256"),
      "source_archive_sha256":row.get("artifact_sha256"),
      "source_unchanged":False,"technical_zip_integrity_passed":False,
      "consumer_bundle_status":"not_examined",
      "consumer_package_sha256":None,
      "new_customer_bundle_rebuilt":False,
      "new_native_private_preview_created":False,
      "rebuild_of_factory_source_performed":False,
      "commercial_review_complete":False,
      "content_expert_signed":False,
      "all_rights_license_signed":False,
      "owner_publication_approved":False,
      "public_sale_allowed":False,
      "return_work_closed":False,
      "still_blocked_for_human_review":True,
      "remaining_issue_codes":list(courier.ISSUES),
      "blocking_reason":None}
    try:
        product,version,manifest,raw=validate_original(root,filename,row,courier)
        item["source_unchanged"]=True
        item["technical_zip_integrity_passed"]=True
        companion=courier.customer_companion(root,product,version,manifest["artifact_sha256"])
        if companion:
            report,payload=companion
            item["consumer_bundle_status"]=("preexisting_native_private_preview_verified"
                if report.get("schema")==courier.NATIVE_PREVIEW_SCHEMA else
                "preexisting_independently_verified")
            item["consumer_package_sha256"]=report["package_sha256"]
        else:
            item["consumer_bundle_status"]="absent"
            if not do_pack:
                item["blocking_reason"]="REPAIR_BUDGET_DEFERS_TECHNICAL_PACKAGE"
            else:
                # Keep real calculator smoke tests for synthesizer products;
                # other source-native families receive static private previews.
                if packager.RECIPE.fullmatch(product):
                    rec=root/"digital-products"/product/"manufacturing_manifest.json"
                    details=packager.read(rec)
                    if (details.get("source_sha256")!=version or
                        details.get("artifact_sha256")!=manifest["artifact_sha256"]):
                        raise ValueError("REPAIR_LATEST_MANUFACTURED_VERSION_DIFFERENT")
                    packer=packager.pack(root,product)
                    status="new_independently_verified"
                    item["new_customer_bundle_rebuilt"]=bool(packer["new"])
                else:
                    packer=native.pack(root,product,version,manifest,raw,courier)
                    status="new_native_structure_verified_private_review"
                    item["new_native_private_preview_created"]=bool(packer["new"])
                companion=courier.customer_companion(root,product,version,manifest["artifact_sha256"])
                if not companion or companion[0]["package_sha256"]!=packer["package_sha256"]:
                    raise ValueError("REPAIR_INDEPENDENT_BUYER_PACKAGE_VERIFICATION_FAILED")
                item["consumer_bundle_status"]=status
                item["consumer_package_sha256"]=packer["package_sha256"]
    except (OSError,ValueError,RuntimeError,KeyError,TypeError,TimeoutError) as error:
        item["consumer_bundle_status"]="held_for_rework"
        item["blocking_reason"]=(type(error).__name__+":"+str(error))[:220]
    return item

def run(root=ROOT,max_new=43):
    root=Path(root)
    if not root.is_dir() or root.is_symlink():raise ValueError("REPAIR_PRIVATE_FACTORY_NOT_FOUND")
    if type(max_new) is not int or not 0<=max_new<=43:raise ValueError("REPAIR_BAD_BUDGET")
    courier=load("mpw_vps_warehouse_courier")
    packager=load("factory_customer_packager")
    native=load("factory_native_customer_packager")
    entries=stage1(root,courier)
    # Fair scheduled rotation: a few permanent blockers must not starve
    # the remaining private source versions when max_new is only three.
    if entries and max_new:
        shift=(int(datetime.now(timezone.utc).timestamp()//300)*max_new)%len(entries)
        entries=entries[shift:]+entries[:shift]
    parent=private(root/"design-state/mojplaywin-actual-technical-repair")
    lock=parent/".repair.lock"
    if lock.is_symlink():raise ValueError("REPAIR_LOCK_SYMLINK")
    descriptor=os.open(str(lock),os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX)
        repaired=checked=blocked=already=missing=native_new=native_existing=attempted=0
        rows=[]
        for p,row in entries:
            filename=p.name
            # Inspect and authenticate the complete immutable source first.
            # Do not spend the limited packaging budget on forged returns,
            # corrupt stock, or existing native previews. The old path-only
            # check could repeatedly spend all three slots on those cases.
            preliminary=once(root,courier,packager,native,filename,row,False)
            eligible=(preliminary["technical_zip_integrity_passed"] is True and
                      preliminary["consumer_bundle_status"]=="absent")
            if eligible and attempted<max_new:
                attempted+=1
                result=once(root,courier,packager,native,filename,row,True)
            else:
                result=preliminary
            if result["technical_zip_integrity_passed"]:checked+=1
            if result["new_customer_bundle_rebuilt"]:repaired+=1
            if result["new_native_private_preview_created"]:native_new+=1
            if result["consumer_bundle_status"]=="preexisting_native_private_preview_verified":native_existing+=1
            if result["consumer_bundle_status"]=="preexisting_independently_verified":already+=1
            if result["consumer_bundle_status"] in ("held_for_rework","absent"):
                if result.get("blocking_reason")=="REPAIR_BUDGET_DEFERS_TECHNICAL_PACKAGE":missing+=1
                else:blocked+=1
            save(parent/filename,result)
            rows.append({"product_id":result["product_id"],
                "source_sha256":result["source_sha256"],
                "technical_integrity":result["technical_zip_integrity_passed"],
                "consumer_bundle_status":result["consumer_bundle_status"],
                "consumer_package_sha256":result["consumer_package_sha256"],
                "reason":result["blocking_reason"],"human_release_pending":True})
        status={"schema":SCHEMA,"tenant":courier.TENANT,
          "updated_at_utc":datetime.now(timezone.utc).isoformat(),
          "returned_products_inspected":len(entries),
          "original_stock_zips_verified":checked,
          "new_customer_bundles_technically_repaired":repaired,
           "new_native_private_previews_statically_validated":native_new,
           "existing_native_private_previews_revalidated":native_existing,
          "existing_customer_bundles_verified":already,
          "technical_package_attempts_blocked":blocked,
          "technical_package_deferred_by_budget":missing,
          "technical_package_attempts_consumed":attempted,
          "independent_content_rights_review_still_required":len(entries),
          "source_product_rebuilds_verified":0,
          "commercially_approved_returns":0,
          "stage1_returns_remaining_open":len(entries),
          "public_store_products_modified":0,"site_sales_enabled":False,
          "no_cross_tenant_modification":True,
          "results":rows}
        save(parent/"execution-status.json",status)
        print("MPW_STAGE1_REAL_TECHNICAL_REPAIR="+json.dumps({
          k:status[k] for k in (
            "returned_products_inspected","original_stock_zips_verified",
            "new_customer_bundles_technically_repaired","existing_customer_bundles_verified",
             "new_native_private_previews_statically_validated",
             "existing_native_private_previews_revalidated",
            "technical_package_attempts_blocked","technical_package_deferred_by_budget",
            "independent_content_rights_review_still_required","source_product_rebuilds_verified",
            "stage1_returns_remaining_open","commercially_approved_returns")},
          sort_keys=True))
        return status
    finally:
        os.close(descriptor)
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--factory-private",required=True)
    ap.add_argument("--max-new",type=int,default=43)
    args=ap.parse_args()
    run(args.factory_private,args.max_new)
