#!/usr/bin/env python3
"""Verify actual evolved private products become fresh, hash-matched tested ZIPs.

Never exports packages to a storefront and never treats unit tests as
independent scientific, owner, rights or 1000-point quality acceptance.
The caller MUST hold the factory source and production-cycle locks.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile

RECIPE=re.compile(r"^(?:synth|sheet)_[a-f0-9]{24}$")
HEX=re.compile(r"^[a-f0-9]{64}$")


def import_maker(scripts):
    path=Path(scripts)/"factory_product_maker.py"
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("EVOLUTION_MANUFACTURER_MODULE_UNAVAILABLE")
    spec=importlib.util.spec_from_file_location("factory_evolution_package_maker",str(path))
    maker=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maker)
    return maker


def load_object(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2_000_000:
        raise RuntimeError("EVOLUTION_RECEIPT_OR_MANIFEST_UNTRUSTED")
    obj=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(obj,dict):
        raise RuntimeError("EVOLUTION_DOCUMENT_OBJECT_REQUIRED")
    return obj


def digest_file(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda:stream.read(1024*1024),b""):
            h.update(part)
    return h.hexdigest()


def ensure_tree_regular(root):
    if root.is_symlink():
        raise RuntimeError("EVOLUTION_PRODUCT_DIRECTORY_SYMLINK")
    if root.exists() and not root.is_dir():
        raise RuntimeError("EVOLUTION_PRODUCT_DIRECTORY_UNSAFE")
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise RuntimeError("EVOLUTION_PRODUCT_TREE_UNSAFE")


def current_package_state(product,name,maker):
    manifest=product/"manufacturing_manifest.json"
    zip_path=product/(name+"-internal-qa.zip")
    if not manifest.exists() or not zip_path.exists():
        return None
    try:
        row=load_object(manifest)
        if zip_path.is_symlink() or not zip_path.is_file():
            return None
        digest=digest_file(zip_path)
        if (row.get("artifact_sha256")!=digest or
                not isinstance(row.get("source_sha256"),str) or
                not HEX.fullmatch(row["source_sha256"]) or
                row.get("qa_status")!="passed"):
            return None
        return {"manifest":row,"archive_sha256":digest}
    except (OSError,RuntimeError,ValueError,json.JSONDecodeError):
        return None


def run(root,scripts,limit=3,maker=None):
    """Rebuild at most a bounded number of stale compiler-owned product ZIPs."""
    if type(limit) is not int or not 1<=limit<=10:
        raise ValueError("EVOLUTION_REBUILD_LIMIT_INVALID")
    root=Path(root).expanduser()
    scripts=Path(scripts).expanduser()
    if root.is_symlink() or not root.is_dir() or scripts.is_symlink() or not scripts.is_dir():
        raise ValueError("EVOLUTION_REBUILD_ROOT_UNSAFE")
    source_root=root/"generated-product-recipes"
    private_products=root/"digital-products"
    if source_root.is_symlink() or not source_root.is_dir():
        return {"schema":"saeit.factory.evolved-product-packages.v1",
                "source_count":0,"stale_products_examined":0,
                "actually_rebuilt":0,"products":[],"failures":[],
                "commercial_release":False,"publicly_published":False}
    if private_products.is_symlink():
        raise RuntimeError("EVOLUTION_PRIVATE_PRODUCTS_SYMLINK")
    maker=maker or import_maker(scripts)
    outcomes=[]; failures=[]; examined=0; sources=0
    for source in sorted(source_root.iterdir()):
        if not RECIPE.fullmatch(source.name) or not source.is_dir() or source.is_symlink():
            continue
        sources+=1
        name=source.name
        try:
            receipt=load_object(source/"design_receipt.json")
            request=load_object(source/"design_request.json")
            if (receipt.get("schema")!="saeit.factory.synthesis-receipt.v1"
                    or receipt.get("generator_capability_revision")!="verified-batch-v2"
                    or receipt.get("recipe")!=name
                    or receipt.get("family_id") not in ("F27","F28")
                    or request.get("family_id")!=receipt.get("family_id")):
                continue
            # Authentication includes the complete original request and current
            # validated source. The newer capability must be present in code.
            canonical=hashlib.sha256(json.dumps(
                request,sort_keys=True,ensure_ascii=False,separators=(",",":")
            ).encode()).hexdigest()
            if canonical!=receipt.get("request_sha256"):
                raise RuntimeError("EVOLUTION_SOURCE_PROVENANCE_MISMATCH")
            calculator=source/"calculator.py"
            if calculator.is_symlink() or not calculator.is_file() or calculator.stat().st_size>200000:
                raise RuntimeError("EVOLUTION_CALCULATOR_UNTRUSTED")
            if "# BATCH_API_V2_START" not in calculator.read_text(encoding="utf8"):
                raise RuntimeError("EVOLUTION_BATCH_CAPABILITY_UNVERIFIED")
            _,files=maker.inspect_recipe(source)
            fresh_source_sha=maker.source_digest(source,files)
            product=private_products/name
            ensure_tree_regular(product)
            old=current_package_state(product,name,maker)
            if old and old["manifest"].get("source_sha256")==fresh_source_sha:
                continue
            if examined>=limit:
                continue
            examined+=1
            # Protect *entire* previous product folder (ZIP, manifest, passport,
            # release-stop and any other private sidecars) before rebuilding.
            prior_exists=product.is_dir()
            backups=root/"evolution-package-backups"
            if backups.is_symlink():
                raise RuntimeError("EVOLUTION_BACKUP_ROOT_SYMLINK")
            backups.mkdir(parents=True,exist_ok=True,mode=0o700)
            os.chmod(str(backups),0o700)
            backup=Path(tempfile.mkdtemp(prefix=name+"-",dir=str(backups)))
            backup_was_populated=False
            if prior_exists:
                for candidate in product.iterdir():
                    if candidate.is_dir():
                        shutil.copytree(str(candidate),str(backup/candidate.name),symlinks=False)
                    elif candidate.is_file() and not candidate.is_symlink():
                        shutil.copy2(str(candidate),str(backup/candidate.name))
                    else:
                        raise RuntimeError("EVOLUTION_BACKUP_UNSAFE_FILE")
                backup_was_populated=True
            try:
                made=maker.manufacture(name,source_root,private_products)
                after=current_package_state(product,name,maker)
                if after is None or after["manifest"].get("source_sha256")!=fresh_source_sha:
                    raise RuntimeError("EVOLUTION_REBUILD_MANIFEST_MISMATCH")
                measured=after["manifest"].get("qa_measurements") or {}
                passed=measured.get("successful_tests")
                if (made.get("qa_status")!="passed" or type(passed) is not int or passed<5
                        or after["manifest"].get("professional_quality_approved") is not False
                        or after["manifest"].get("public_listing_enabled") is not False
                        or after["manifest"].get("owner_publication_approval") is not False):
                    raise RuntimeError("EVOLUTION_REBUILD_QA_OR_PUBLICATION_GATE_FAILED")
                zip_path=product/(name+"-internal-qa.zip")
                with zipfile.ZipFile(zip_path) as archive:
                    if not archive.namelist() or archive.testzip() is not None:
                        raise RuntimeError("EVOLUTION_REBUILD_ZIP_INTEGRITY_FAILED")
                if old is not None and old["archive_sha256"]==after["archive_sha256"]:
                    raise RuntimeError("EVOLUTION_REBUILD_SOURCE_CHANGED_BUT_ARCHIVE_UNCHANGED")
                row={"recipe":name,"source_sha256":fresh_source_sha,
                     "prior_artifact_sha256":old["archive_sha256"] if old else None,
                     "new_artifact_sha256":after["archive_sha256"],
                     "verified_customer_bundle":False,"technical_tests_passed":passed,
                     "retained_prior_product":bool(prior_exists),
                     "commercially_approved":False,"publicly_published":False}
                # A complete private receipt is essential, not merely a print.
                receipt_dir=root/"evolution-rebuild-receipts"
                if receipt_dir.is_symlink():
                    raise RuntimeError("EVOLUTION_RECEIPT_DIRECTORY_UNSAFE")
                receipt_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
                receipt_file=receipt_dir/(name+"-"+after["archive_sha256"][:16]+".json")
                maker.atomic_text(receipt_file,json.dumps({
                    "schema":"saeit.factory.evolution-rebuilt-product.v1",
                    "recorded_utc":datetime.now(timezone.utc).isoformat(),
                    **row},sort_keys=True,indent=2)+"\n")
                outcomes.append(row)
            except (RuntimeError,ValueError,OSError,ArithmeticError,zipfile.BadZipFile) as error:
                # Fail closed and restore the original immutable customer-bound
                # bytes, not just the old manifest or the prior source tree.
                if product.is_dir():
                    shutil.rmtree(str(product))
                if prior_exists and backup_was_populated:
                    shutil.copytree(str(backup),str(product),symlinks=False)
                failures.append({"recipe":name,"error_type":type(error).__name__,
                                 "technical_candidate_released":False})
                continue
        except (RuntimeError,ValueError,OSError,ArithmeticError,json.JSONDecodeError) as error:
            failures.append({"recipe":name,"error_type":type(error).__name__,
                             "technical_candidate_released":False})
    result={"schema":"saeit.factory.evolved-product-packages.v1",
            "source_count":sources,"stale_products_examined":examined,
            "actually_rebuilt":len(outcomes),"products":outcomes,
            "failures":failures,"commercial_release":False,
            "publicly_published":False}
    return result


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--scripts",required=True)
    p.add_argument("--limit",type=int,default=3)
    opts=p.parse_args(argv)
    result=run(opts.root,opts.scripts,opts.limit)
    print("FACTORY_EVOLVED_PACKAGES_REBUILT="+str(result["actually_rebuilt"]))
    print("FACTORY_EVOLVED_PACKAGES_UNRESOLVED="+str(len(result["failures"])))
    print("FACTORY_EVOLVED_PACKAGE_REAL_RECEIPT="+json.dumps(result,sort_keys=True))
    print("FACTORY_EVOLVED_PACKAGES_COMMERCIAL_RELEASE=false")
    return 0 if not result["failures"] else 2


if __name__=="__main__":
    sys.exit(main())
