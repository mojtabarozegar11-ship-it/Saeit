#!/usr/bin/env python3
"""Authentic private 40-family commerce preparation and measured release holds.

Creates reviewable SKU proposals from live registry and BUILD50 receipts.
It cannot write a store, charge a customer, forge a license, or grant approvals.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

SCHEMA="saeit.factory.commerce40-readiness.v1"
HEX=re.compile(r"^[0-9a-f]{64}$")
RECIPE=re.compile(r"^[a-z][a-z0-9_-]{1,90}$")
PRICES={
 "books":(19,69),"education":(19,89),"software":(29,149),
 "design":(15,99),"media":(12,79),"data":(29,199),"other":(19,99)}
# Proposed illustrative bands in USD only. No market/price acceptance claimed.
def segment(n):
    if n in (1,2,3,4,5,6):return "books"
    if n in (7,8,9,10,11):return "education"
    if n in (12,13,14,16,17,18,19,20,21,22,23,24,28):return "software"
    if n in (25,26):return "data"
    if n in (27,29,30,31,32,33,34,35,36):return "design"
    if n in (15,37,38,39,40):return "media"
    return "other"
def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(65536),b""):h.update(part)
    return h.hexdigest()
def read(path,limit=2_000_000):
    p=Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size>limit:
        raise ValueError("COMMERCE_UNTRUSTED_FILE")
    v=json.loads(p.read_text("utf8"))
    if not isinstance(v,dict):raise ValueError("COMMERCE_EXPECTED_OBJECT")
    return v
def loader(directory,name):
    source=Path(directory)/(name+".py")
    if not source.is_file() or source.is_symlink():raise ValueError("COMMERCE_BAD_TRUSTED_MODULE")
    spec=importlib.util.spec_from_file_location("commerce_40_"+name,str(source))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def private(path):
    p=Path(path)
    if p.is_symlink():raise ValueError("COMMERCE_SYMLINK_DIR")
    p.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not p.is_dir() or p.is_symlink():raise ValueError("COMMERCE_NOT_PRIVATE_DIR")
    os.chmod(p,0o700)
    return p
def save(path,obj):
    path=Path(path);private(path.parent)
    if path.is_symlink():raise ValueError("COMMERCE_SYMLINK_DEST")
    raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf8")
    if path.is_file() and path.read_bytes()==raw:return False
    fd,temp=tempfile.mkstemp(dir=str(path.parent),prefix=".commerce-")
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.chmod(temp,0o600);os.replace(temp,str(path))
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return True
def archive_check(path,recipe,expected_sha):
    """Real bounded CRC+member inspection; safely supports 48x3 game assets."""
    p=Path(path)
    if (not RECIPE.fullmatch(recipe) or not isinstance(expected_sha,str)
            or not HEX.fullmatch(expected_sha)
            or not p.is_file() or p.is_symlink()
            or not 100<=p.stat().st_size<=25*1024*1024):
        raise ValueError("COMMERCE_ARCHIVE_UNTRUSTED")
    actual=sha(p)
    if actual!=expected_sha:raise ValueError("COMMERCE_ARCHIVE_SHA_MISMATCH")
    with zipfile.ZipFile(str(p)) as z:
        members=z.infolist()
        if not 1<=len(members)<=300 or sum(x.file_size for x in members)>250*1024*1024:
            raise ValueError("COMMERCE_ARCHIVE_RESOURCE_LIMIT")
        names=[]
        for item in members:
            name=item.filename
            if (item.is_dir() or item.flag_bits&1 or
                len(name)>512 or len(name.split("/"))<2 or
                not name.startswith(recipe+"/") or
                any(part in ("",".","..") or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",part)
                    for part in name.split("/"))
                or (item.external_attr>>16)&0o170000==0o120000):
                raise ValueError("COMMERCE_ARCHIVE_UNSAFE_MEMBER")
            names.append(name)
        if len(names)!=len(set(names)) or z.testzip() is not None:
            raise ValueError("COMMERCE_ARCHIVE_CRC_OR_DUPLICATE")
    return {"archive_sha256":actual,"members":len(members),
            "compressed_bytes":p.stat().st_size,"structural_integrity":True}
def product_proof(root,record):
    """Require actual source-bound 50 receipts PLUS real physical ZIP."""
    if record.get("verified") is not True or record.get("completed_stages")!=50:
        return {"technical_ok":False,"blockers":["NO_VALID_BUILD50_PROOF"]}
    recipe=record.get("product_id");family=record.get("family_id")
    if not isinstance(recipe,str) or not RECIPE.fullmatch(recipe):
        return {"technical_ok":False,"blockers":["UNSAFE_RECIPE_ID"]}
    folder=Path(root)/"digital-products"/recipe
    if folder.is_symlink():
        return {"technical_ok":False,"blockers":["UNSAFE_PRODUCT_PATH"]}
    manifest=folder/"manufacturing_manifest.json"
    try:
        m=read(manifest,100000)
        if (m.get("family_id")!=family or m.get("qa_status")!="passed"
                or m.get("public_listing_enabled") is not False
                or m.get("owner_publication_approval") is not False
                or m.get("recipe")!=recipe):
            raise ValueError("MANIFEST_FIELDS_INCONSISTENT")
        pack=archive_check(folder/(recipe+"-internal-qa.zip"),recipe,m.get("artifact_sha256"))
        return {"technical_ok":True,"blockers":[],"archive":pack,
                 "manifest_sha256":sha(manifest),
                 "manufacturer_release_authorized":False}
    except (ValueError,KeyError,TypeError,OSError,zipfile.BadZipFile):
        return {"technical_ok":False,"blockers":["MANIFEST_OR_ARCHIVE_NOT_STRICTLY_VALID"]}
def offer(profile,proofs,now):
    fid=profile["id"];num=int(fid[1:])
    tier=segment(num);low,high=PRICES[tier]
    genuine=[x for x in proofs if x.get("technical_ok")]
    problems=set()
    if not genuine:problems.add("TECHNICAL_MANUFACTURING_EVIDENCE_OR_PACKAGE_MISSING")
    if not proofs:problems.add("NO_50_STAGE_PRODUCT")
    if any(not x.get("technical_ok") for x in proofs):
        problems.add("AT_LEAST_ONE_TECHNICAL_PACKAGE_REQUIRES_REWORK")
    # Each of these is a real admission requirement. Do not invent their pass.
    problems.update((
      "INDEPENDENT_SPECIALIST_OR_HUMAN_CONTENT_ACCEPTANCE_MISSING",
      "LICENSE_AND_PROVENANCE_RIGHTS_SIGNOFF_MISSING",
      "OWNER_APPROVED_PRODUCT_PRICE_AND_SCOPE_MISSING",
      "REFUND_TAX_AND_CUSTOMER_TERMS_NOT_VERIFIED",
      "PAYMENT_WEBHOOK_AND_FULFILLMENT_E2E_NOT_VERIFIED",
      "LIVE_STORE_RELEASE_GATE_NOT_VERIFIED"))
    sku="SM-"+fid+"-"+profile["slug"].upper().replace("_","-")
    return {"schema":"saeit.factory.internal-commercial-offer.v1",
      "family_id":fid,"family_name":profile["name_fa"],"sku":sku,
      "offer_status":"commercial_preparation_private_only",
      "source_adapter":profile["producer_adapter"],
      "output_formats_expected":profile["formats"],
      "audiences":profile["audiences"],
      "language_options":profile["languages"],
      "suggested_usd_range":{"lower":low,"upper":high,
          "kind":"hypothesis_not_live_price","market_validation":False},
      "monetization_candidates":["one_time_digital_license","business_multi_seat_license"],
      "license_terms":"requires_owner_drafted_rights_clearance_and_specific_product_license",
      "technical_products_with_verified_archive":len(genuine),
      "technical_products_attempted":len(proofs),
      "technical_sources":[{"product_id":x["product_id"],
          "technical_ok":x["technical_ok"],
          "archive_sha256":x.get("archive",{}).get("archive_sha256"),
          "archive_members":x.get("archive",{}).get("members"),
          "blockers":x.get("blockers",[])} for x in proofs],
      "commercial_blockers":sorted(problems),
      "specialist_tests_required":profile["specialist_tests"],
      "requested_owner_actions":[
          "Record verified ownership/license documents for the exact product and assets",
          "Obtain appropriate independent domain specialist and human acceptance",
          "Choose actual SKU retail price, locale, tax and refund policy",
          "Prove end-to-end checkout/webhook, receipt and authorized downloadable delivery",
          "Independently verify production site release gate and explicitly approve publication"],
      "owner_explicit_goal":"commercialize_all_40_families",
      "per_product_owner_release_signed":False,
      "store_ready":False,"public_sale_allowed":False,"payment_enabled":False,
      "published":False,"orders_created":0}
def run(root,registry,module_dir):
    root=Path(root);module_dir=Path(module_dir)
    if root.is_symlink() or not root.is_dir() or module_dir.is_symlink():
        raise ValueError("COMMERCE_UNSAFE_ROOT")
    bridge=loader(module_dir,"factory_build50_family_bridge")
    protocol=loader(module_dir,"factory_build_50")
    master=loader(module_dir,"factory_40_family_master")
    profiles=master.registry_valid(read(registry))
    evidence=bridge.inventory(root,registry,protocol,master)
    rows_by_family={p["id"]:[] for p in profiles}
    for record in evidence["products"]:
        family=record.get("family_id")
        if family in rows_by_family:
            result=product_proof(root,record)
            rows_by_family[family].append({"product_id":record["product_id"],**result})
    place=private(root/"commercial40")
    records=[];stats=Counter()
    for profile in profiles:
        fid=profile["id"]
        row=offer(profile,rows_by_family[fid],None)
        save(place/"offers"/(fid+".json"),row)
        records.append({"family_id":fid,"sku":row["sku"],"technical_products_verified":
          row["technical_products_with_verified_archive"],
          "blocked_reasons":row["commercial_blockers"],"status":row["offer_status"],
          "commercial_release":False})
        stats["families_created"]+=1
        stats["technical_families_with_eligible_archives"]+=int(
            row["technical_products_with_verified_archive"]>0)
        stats["family_with_missing_technical_proof"]+=int(
            row["technical_products_with_verified_archive"]==0)
        stats["product_archives_technically_verified"]+=row["technical_products_with_verified_archive"]
    report={"schema":SCHEMA,"observed_utc":datetime.now(timezone.utc).isoformat(),
      "registry_profiles":len(profiles),"private_commercial_sku_proposals":len(records),
      "genuine_verified_product_families":stats["technical_families_with_eligible_archives"],
      "families_without_trusted_package":stats["family_with_missing_technical_proof"],
      "strict_archives_verified":stats["product_archives_technically_verified"],
      "commercially_approved_families":0,"live_products_published_by_this_engine":0,
      "sales_or_payments_processed":0,"sites_contacted":0,
      "owner_approval_is_not_implied_by_global_commercialization_request":True,
      "pricing_status":"internal_USD_price_hypotheses_not_customer_charges",
      "rows":records}
    if len(records)!=40 or len({r["sku"] for r in records})!=40:
        raise RuntimeError("COMMERCE_REGISTRY_INCOMPLETE")
    save(place/"dashboard.json",report)
    print("FACTORY_COMMERCE40_REAL_READINESS="+json.dumps({k:report[k] for k in (
      "private_commercial_sku_proposals","genuine_verified_product_families",
      "families_without_trusted_package","strict_archives_verified",
      "commercially_approved_families","live_products_published_by_this_engine")},sort_keys=True))
    return report
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--registry",required=True)
    p.add_argument("--module-dir",required=True)
    a=p.parse_args()
    run(a.factory_private,a.registry,a.module_dir)
if __name__=="__main__":
    try:main()
    except (ValueError,OSError,KeyError,RuntimeError,TypeError,zipfile.BadZipFile) as exc:
        print("FACTORY_COMMERCE40_ERROR="+type(exc).__name__+":"+str(exc)[:190])
        raise SystemExit(1)
