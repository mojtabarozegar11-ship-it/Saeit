#!/usr/bin/env python3
"""Prepare a truthful, versioned commercial catalog for four private Astra QA ZIPs.

THIS DOES NOT activate checkout or grant product rights. Uses a read-only
private SQLite queue, and SHA-verified, isolated product archives. Prevents
misrepresenting technical QA as independent market or legal validation.
Python 3.8+, standard library. No network or website API required.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import zipfile

HEX64 = re.compile(r"[a-f0-9]{64}\Z")
CATALOG = {
    "orchard_decision_audit_v2": {
        "sku":"ASTRA-ORCHARD-01",
        "name":"Orchard Investment Decision Audit",
        "use":"Compare orchard investment scenarios using your own assumptions.",
        "limitations":"Not a verified orchard yield, regional crop forecast, or financial advice.",
        "list_usd":"19.00",
        "customer":"Growers and farm-economics advisers needing a local decision worksheet.",
        "benchmark":"https://farmplenty.com/crop-planner/",
    },
    "farm_procurement_audit_v1": {
        "sku":"ASTRA-PROCURE-01",
        "name":"Farm Input Procurement Quote Audit",
        "use":"Audit arithmetic of supplier quotes, freight and wastage.",
        "limitations":"Does not supply live vendor quotes or independently check suppliers.",
        "list_usd":"19.00",
        "customer":"Farm procurement teams comparing their own supplier estimates.",
        "benchmark":"https://templatesprime.com/product/farm-bookkeeping-template-agriculture-income-expense-tracker/",
    },
    "farm_water_land_margin_audit_v1": {
        "sku":"ASTRA-WATER-01",
        "name":"Farm Water and Land Margin Audit",
        "use":"Explore land, water and operating-margin sensitivity scenarios.",
        "limitations":"Not a verified hydrological model, crop suitability forecast or professional advice.",
        "list_usd":"29.00",
        "customer":"Farm operators modelling the economics of land and water constraints.",
        "benchmark":"https://www.agshared.ag/reports/budget",
    },
    "circuit_courier_v1": {
        "sku":"ASTRA-CIRCUIT-01",
        "name":"Circuit Courier — 36-Stage Offline Puzzle",
        "use":"Play 36 reproducibly tested offline logic-puzzle levels.",
        "limitations":"No independently verified player experience, difficulty or commercial demand.",
        "list_usd":"4.99",
        "customer":"Desktop-browser players interested in self-contained logic games.",
        "benchmark":"https://mcfatty9000.itch.io/rlink",
    },
}
REQUIRED_QUALITY = (
    "INDEPENDENT_USABILITY_TEST",
    "ACCESSIBILITY_AND_CONTENT_REVIEW",
    "ORIGINALITY_AND_DISTRIBUTION_RIGHTS",
    "REAL_BUYER_AND_COMPETITOR_VALIDATION",
    "DOWNLOAD_AND_DEVICE_SUPPORT_REVIEW",
    "PAYMENT_PROVIDER_AND_CONFIRMATION_LIVE_PROOF",
    "ORDER_LINKED_LICENSE_AND_FULFILMENT_PROOF",
    "APPLICABLE_TAX_REFUND_AND_CONSUMER_TERMS",
)


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda:f.read(262144), b""):
            h.update(part)
    return h.hexdigest()


def verify_dir(path, *, make=False):
    p = Path(path).expanduser()
    if not p.is_absolute() or p.is_symlink():
        raise ValueError("private root must be absolute, without symlink")
    if make:
        p.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(str(p), 0o700)
    if not p.is_dir() or p.is_symlink():
        raise ValueError("private directory unavailable")
    return p


def read_manifest(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>200000:
        raise ValueError("unsafe QA manifest")
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict):
        raise ValueError("invalid QA manifest")
    return data


def verify_candidate(root, builder, artifact_sha):
    if builder not in CATALOG or not isinstance(artifact_sha,str) or not HEX64.fullmatch(artifact_sha):
        raise ValueError("unexpected builder or SHA")
    matches=[]
    for manifest_path in root.glob("qa-*.json"):
        if manifest_path.is_symlink():
            raise ValueError("symlink QA record")
        row=read_manifest(manifest_path)
        if row.get("source_builder")==builder and row.get("artifact_sha256")==artifact_sha:
            matches.append((manifest_path,row))
    if len(matches)!=1:
        raise ValueError("missing or duplicated verified QA proof: "+builder)
    path,row=matches[0]
    revision=row.get("source_digest")
    if not isinstance(revision,str) or not HEX64.fullmatch(revision):
        raise ValueError("invalid source digest")
    if path.name != "qa-"+revision+".json":
        raise ValueError("wrong manifest identity")
    expected={
        "technical_regression":"PASSED", "integrity_check":"PASSED",
        "development_scope":"private_reference_prototype",
        "commercial_product":False, "sale_ready":False,
        "public_deployment_allowed":False, "real_payment_allowed":False,
    }
    if any(row.get(key)!=value for key,value in expected.items()):
        raise ValueError("cannot bypass old private QA gates")
    product=root/("artifact-"+revision+".zip")
    if product.is_symlink() or not product.is_file() or product.stat().st_size>25_000_000:
        raise ValueError("artifact missing/unsafe")
    if sha256_file(product)!=artifact_sha:
        raise ValueError("artifact digest mismatch")
    with zipfile.ZipFile(product) as z:
        names=z.namelist()
        if (z.testzip() is not None or not 3<=len(names)<=30
                or len(set(names))!=len(names)
                or any("/" not in n or n.startswith("/") or ".." in n.split("/")
                       or "\\" in n or n.endswith("/") for n in names)):
            raise ValueError("unsafe ZIP entries")
        prefix={n.split("/",1)[0] for n in names}
        if prefix != {row.get("product_slug")}:
            raise ValueError("wrong product content folder")
        if len(names)!=len(row.get("included_files", [])):
            raise ValueError("manifest inventory mismatch")
        if set(n.split("/",1)[1] for n in names)!=set(row["included_files"]):
            raise ValueError("manifest file list mismatch")
        if sum(z.getinfo(n).file_size for n in names)>7_000_000:
            raise ValueError("uncompressed payload excessive")
    return {"artifact_sha256":artifact_sha,"qa_sha256":sha256_file(path),
            "source_digest":revision,"archive_name":product.name}


def private_catalog(factory_root, now=None):
    root=verify_dir(factory_root)
    sqlite=root/"queue.sqlite3"
    if sqlite.is_symlink() or not sqlite.is_file():
        raise ValueError("verified private queue is required")
    uri=sqlite.resolve().as_uri()+"?mode=ro"
    with sqlite3.connect(uri,uri=True,timeout=5) as conn:
        conn.execute("PRAGMA query_only=ON")
        results=conn.execute(
            "SELECT builder,artifact_sha FROM jobs "
            "WHERE stage='PRIVATE_QA_PASSED' ORDER BY id DESC").fetchall()
    source_by_builder={}
    for builder,digest in results:
        if builder in CATALOG and builder not in source_by_builder:
            source_by_builder[builder]=digest
    if set(source_by_builder)!=set(CATALOG):
        raise ValueError("not all four independent build families have QA passes")
    products=[]
    for builder in sorted(CATALOG):
        details=CATALOG[builder]
        proof=verify_candidate(root,builder,source_by_builder[builder])
        normal=Decimal(details["list_usd"])
        price=(normal*Decimal("0.10")).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
        products.append({
            "builder":builder, "sku":details["sku"],"title":details["name"],
            "audience_hypothesis":details["customer"],
            "verified_technical_function":details["use"],
            "important_limits":details["limitations"],
            "market_reference":details["benchmark"],
            "suggested_list_price_usd":format(normal,".2f"),
            "suggested_discount_percent":90,
            "suggested_discounted_price_usd":format(price,".2f"),
            "suggestions_not_verified_fair_value":True,
            "quality_score":None, "rights_verified":False,
            "buyer_willingness_to_pay_verified":False,
            "public_listing_authorized":False,
            "checkout_authorized":False,
            "automated_delivery_authorized":False,
            "release_blockers":list(REQUIRED_QUALITY),
            "source_proof":proof,
            "status":"PRIVATE_COMMERCIAL_CANDIDATE_NOT_FOR_SALE",
        })
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("aware UTC time required")
    return {
        "schema":1,"generated_utc":now.astimezone(timezone.utc).isoformat(),
        "mode":"commercial_preparation_not_store_activation",
        "storefront_target":"mojplaywin.com",
        "payment_assets_requested":["TRX","ETH"],
        "real_payment_engine_live_verified":False,
        "sales_verified":0,
        "publications":0,"real_checkout_transactions":0,
        "factory_main_queue_mutated":False,
        "discount_formula":"suggested_list_price_USD × (1 - 0.90); no price approved",
        "items":products
    }


def _write_new(path,data):
    if path.is_symlink():
        raise ValueError("symlink output forbidden")
    fd=os.open(str(path),os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def store_private_catalog(report, directory):
    out=verify_dir(directory,make=True)
    fixed=dict(report)
    fixed.pop("generated_utc",None)
    dig=hashlib.sha256(json.dumps(fixed,sort_keys=True).encode()).hexdigest()[:20]
    full=out/("commercial-catalog-"+dig+".json")
    data=(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+"\n").encode()
    if full.exists() or full.is_symlink():
        if full.is_symlink() or not full.is_file():
            raise ValueError("unsafe existing catalog")
        existing=json.loads(full.read_text(encoding="utf-8"))
        if {k:v for k,v in existing.items() if k!="generated_utc"}!=fixed:
            raise ValueError("immutable commercial candidate mismatch")
        return {"status":"UNCHANGED","name":full.name,"products":len(report["items"])}
    _write_new(full,data)
    return {"status":"PRIVATE_CANDIDATE_CREATED","name":full.name,
            "products":len(report["items"])}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--factory-root",required=True)
    p.add_argument("--output-root",required=True)
    args=p.parse_args(argv)
    report=private_catalog(args.factory_root)
    result=store_private_catalog(report,args.output_root)
    for key,v in sorted(result.items()):
        print("ASTRA_COMMERCE_"+key.upper()+"="+str(v))
    print("ASTRA_COMMERCE_PAID_CHECKOUT_ACTIVE=false")
    print("ASTRA_COMMERCE_PUBLIC_PRODUCTS_ACTIVATED=0")


if __name__=="__main__":
    main()
