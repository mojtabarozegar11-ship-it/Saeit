#!/usr/bin/env python3
"""Recover exact lost factory-owned original recipe bytes from verified private QA ZIPs.

No synthesis, guesswork, permission change, store publication, replacement of
existing source or modification of goods. Source SHA must match canonical
manifest digest over exact archived contents, and QA workorder must bind to the
current immutable technical assessment. Python 3.8+, stdlib only.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile
def active_product_allowlist(path):
    """Read the factory's authoritative five active slots; fail closed."""
    state_path = Path(path)
    if state_path.is_symlink() or not state_path.is_file() or state_path.stat().st_size > 2000000:
        raise ValueError("ACTIVE_PRODUCT_SLOTS_REQUIRED")
    state = json.loads(state_path.read_text(encoding="utf8"))
    active = state.get("active") if isinstance(state, dict) else None
    if (state.get("schema") != "saeit.factory.product-slots.v1"
            or state.get("capacity") != 5 or not isinstance(active, list)
            or len(active) != 5):
        raise ValueError("EXACTLY_FIVE_ACTIVE_FACTORY_PRODUCTS_REQUIRED")
    recipes = [item.get("recipe") if isinstance(item, dict) else None for item in active]
    if (len(set(recipes)) != 5 or any(not isinstance(recipe, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{1,65}", recipe) for recipe in recipes)):
        raise ValueError("ACTIVE_PRODUCT_SLOT_ENTRIES_INVALID")
    return set(recipes)


SKU=re.compile(r"^[a-z][a-z0-9_]{1,65}$")
HASH=re.compile(r"^[0-9a-f]{64}$")
MAX_ZIP=25*1024*1024
MAX_EXPAND=100*1024*1024

def digest(b):return hashlib.sha256(b).hexdigest()

def document(path):
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=2_000_000:
        raise ValueError("RECOVERY_DOCUMENT_UNTRUSTED")
    value=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(value,dict):raise ValueError("RECOVERY_DOCUMENT_INVALID")
    return value

def member_name(recipe,name):
    if not isinstance(name,str) or len(name)>240 or "\\" in name:
        raise ValueError("RECOVERY_MEMBER_NAME_INVALID")
    target=PurePosixPath(name)
    if not name or name.startswith("/") or any(p in ("",".","..") or p.startswith(".") for p in name.split("/")):
        raise ValueError("RECOVERY_MEMBER_TRAVERSAL")
    if str(target)!=name or name.endswith("/"):
        raise ValueError("RECOVERY_MEMBER_CANONICAL_NAME_REQUIRED")
    return recipe+"/"+name

def source_from_zip(recipe,zip_path,manifest):
    expected=manifest.get("source_sha256")
    zipped=manifest.get("artifact_sha256")
    names=manifest.get("files")
    if (not isinstance(expected,str) or not HASH.fullmatch(expected)
        or not isinstance(zipped,str) or not HASH.fullmatch(zipped)
        or not isinstance(names,list) or not 1<=len(names)<=256
        or not all(isinstance(s,str) for s in names) or len(set(names))!=len(names)
        or "README.md" not in names
        or not any(x.startswith("test_") and x.endswith(".py") or "/test_" in x and x.endswith(".py") for x in names)):
        raise ValueError("RECOVERY_MANIFEST_NOT_VERIFIABLE_SOURCE")
    desired={member_name(recipe,n):n for n in names}
    if zip_path.is_symlink() or not zip_path.is_file() or not 0<zip_path.stat().st_size<=MAX_ZIP:
        raise ValueError("RECOVERY_ZIP_UNSAFE")
    if digest(zip_path.read_bytes())!=zipped:raise ValueError("RECOVERY_ARCHIVE_HASH_MISMATCH")
    source_bytes={}
    with zipfile.ZipFile(str(zip_path)) as archive:
        entries=archive.infolist()
        if (len(entries)!=len(desired)
            or {entry.filename for entry in entries}!=set(desired)
            or len({entry.filename for entry in entries})!=len(entries)
            or sum(e.file_size for e in entries)>MAX_EXPAND
            or archive.testzip() is not None):
            raise ValueError("RECOVERY_SOURCE_MEMBERS_INVALID")
        for entry in entries:
            mode=(entry.external_attr>>16)&0o170000
            if entry.is_dir() or mode==0o120000:
                raise ValueError("RECOVERY_LINK_OR_DIR_FORBIDDEN")
            name=desired[entry.filename]
            if entry.file_size > MAX_ZIP:
                raise ValueError("RECOVERY_SINGLE_FILE_TOO_LARGE")
            data=archive.read(entry)
            if len(data)!=entry.file_size:raise ValueError("RECOVERY_SIZE_MISMATCH")
            source_bytes[name]=data
    check=hashlib.sha256()
    for name in sorted(source_bytes):
        check.update(name.encode("utf8")+b"\0")
        check.update(source_bytes[name])
    if check.hexdigest()!=expected:
        raise ValueError("RECOVERY_SOURCE_HASH_MISMATCH")
    return source_bytes,expected,zipped

def original_source(root,recipe):
    for folder in (root/"digital-products",root/"product-lifecycle"/"digital-products"):
        if folder.is_symlink():raise ValueError("RECOVERY_UNSAFE_STOCK_ROOT")
        product=folder/recipe
        if product.is_symlink():raise ValueError("RECOVERY_STOCK_SYMLINK")
        if (product/"manufacturing_manifest.json").is_file() and not (product/"manufacturing_manifest.json").is_symlink():
            yield product

def verify_previous_recovery(root, result_root, recipe, order, order_path, target):
    """Fail closed on stale, incomplete or altered private recovered source.

    A folder alone is never evidence of a successful prior recovery.
    Verify the original immutable archive, exact target bytes and bound
    private receipt before reporting idempotent success.
    """
    proof = result_root / (".recovery-" + recipe + ".json")
    receipt = document(proof)
    products = list(original_source(root, recipe))
    if len(products) != 1:
        raise ValueError("RECOVERY_PREVIOUS_STOCK_UNVERIFIABLE")
    product = products[0]
    meta = document(product / "manufacturing_manifest.json")
    if (meta.get("recipe") != recipe or meta.get("qa_status") != "passed"
        or meta.get("commercial_status") != "private_internal_qa_pass_not_published"
        or meta.get("public_listing_enabled") is not False
        or meta.get("owner_publication_approval") is not False
        or meta.get("artifact_sha256") != order.get("artifact_sha256")):
        raise ValueError("RECOVERY_PREVIOUS_STOCK_UNVERIFIABLE")
    files, source_sha, archive_sha = source_from_zip(
        recipe, product / (recipe + "-internal-qa.zip"), meta)
    if (receipt.get("schema") != "saeit.factory.exact-source-recovery.v1"
        or receipt.get("recipe") != recipe
        or receipt.get("source_sha256") != source_sha
        or receipt.get("internal_artifact_sha256") != archive_sha
        or receipt.get("quality_workorder_sha256") != digest(order_path.read_bytes())
        or receipt.get("source_hash_verified_against_original_manifest") is not True
        or receipt.get("old_product_mutated") is not False
        or receipt.get("technical_qa_retested") is not False
        or receipt.get("professional_quality_1000_approved") is not False
        or receipt.get("commercial_release_allowed") is not False):
        raise ValueError("RECOVERY_PREVIOUS_PROOF_MISMATCH")
    observed = set()
    for node in target.rglob("*"):
        if node.is_symlink() or (not node.is_file() and not node.is_dir()):
            raise ValueError("RECOVERY_PREVIOUS_FILES_UNTRUSTED")
        if not node.is_file():
            continue
        name = node.relative_to(target).as_posix()
        if (name not in files or node.stat().st_size != len(files[name])
            or node.read_bytes() != files[name]):
            raise ValueError("RECOVERY_PREVIOUS_FILES_MISMATCH")
        observed.add(name)
        if len(observed) > 256:
            raise ValueError("RECOVERY_PREVIOUS_FILES_UNTRUSTED")
    if observed != set(files):
        raise ValueError("RECOVERY_PREVIOUS_FILES_MISMATCH")


def recover(root,*,limit=3,other_roots=(),products_file=None):
    root=Path(root)
    active_products=active_product_allowlist(products_file) if products_file else None
    if root.is_symlink() or not root.is_dir():raise ValueError("RECOVERY_PRIVATE_ROOT_UNSAFE")
    if type(limit)is not int or not 1<=limit<=3:raise ValueError("RECOVERY_CAPACITY_INVALID")
    if len(other_roots)>3:raise ValueError("RECOVERY_SOURCE_ROOT_LIMIT")
    other=[Path(p) for p in other_roots]
    if any(p.is_symlink() for p in other):raise ValueError("RECOVERY_OTHER_SOURCE_SYMLINK")
    orders=root/"quality-excellence"/"production-workorders"
    if orders.is_symlink() or not orders.is_dir():raise ValueError("RECOVERY_WORKORDERS_MISSING")
    result_root=root/"recovered-original-product-recipes"
    if result_root.is_symlink():raise ValueError("RECOVERY_TARGET_SYMLINK")
    result_root.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(result_root,0o700)
    stats=Counter()
    results=[]
    for order_folder in sorted(orders.iterdir()):
        if not order_folder.is_dir() or order_folder.is_symlink() or not SKU.fullmatch(order_folder.name):continue
        recipe=order_folder.name
        if active_products is not None and recipe not in active_products:continue
        stats["orders_examined"]+=1
        try:
            order_path=order_folder/"current.json"
            order=document(order_path)
            qa=root/"quality-excellence"/"rework"/recipe/"current.json"
            quality=document(qa)
            if (order.get("schema")!="saeit.factory.production-rework-order.v1"
                or order.get("recipe")!=recipe
                or order.get("source_quality_receipt_sha256")!=digest(qa.read_bytes())
                or order.get("artifact_sha256")!=quality.get("artifact_sha256")):
                raise ValueError("RECOVERY_UNBOUND_QUALITY_WORKORDER")
            # Never compete with an existing good source, especially not an
            # independently edited source requiring a specialist merge.
            target=result_root/recipe
            if target.is_symlink():raise ValueError("RECOVERY_DESTINATION_SYMLINK")
            if any((base/recipe).exists() or (base/recipe).is_symlink() for base in other):
                stats["existing_original_source"]+=1
                continue
            if target.is_dir():
                verify_previous_recovery(root,result_root,recipe,order,order_path,target)
                stats["previously_recovered"]+=1
                continue
            if stats["restored"]>=limit:
                stats["deferred_by_capacity"]+=1
                continue
            products=list(original_source(root,recipe))
            if len(products)!=1:
                raise ValueError("RECOVERY_AMBIGUOUS_OR_MISSING_STOCK")
            product=products[0]
            meta=document(product/"manufacturing_manifest.json")
            if (meta.get("recipe")!=recipe or meta.get("qa_status")!="passed"
                or meta.get("artifact_sha256")!=order.get("artifact_sha256")
                or meta.get("commercial_status")!="private_internal_qa_pass_not_published"
                or meta.get("public_listing_enabled") is not False
                or meta.get("owner_publication_approval") is not False):
                raise ValueError("RECOVERY_UNSAFE_STOCK_MANIFEST")
            source,source_sha,artifact_sha=source_from_zip(
                recipe,product/(recipe+"-internal-qa.zip"),meta)
            staging=Path(tempfile.mkdtemp(prefix=".restore-"+recipe+"-",dir=str(result_root)))
            try:
                for name,b in source.items():
                    p=staging/name
                    p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                    with p.open("xb") as f:
                        f.write(b)
                        f.flush()
                        os.fsync(f.fileno())
                    os.chmod(p,0o600)
                # Run independent SHA reinspection of recovered bytes.
                check=hashlib.sha256()
                for name in sorted(source):
                    check.update(name.encode()+b"\0")
                    check.update((staging/name).read_bytes())
                if check.hexdigest()!=source_sha:raise ValueError("RECOVERY_POST_WRITE_SOURCE_HASH_INVALID")
                if target.exists() or target.is_symlink():raise ValueError("RECOVERY_CONCURRENT_SOURCE_EXISTS")
                staging.rename(target)
            finally:
                if staging.exists():shutil.rmtree(staging)
            receipt={
                "schema":"saeit.factory.exact-source-recovery.v1","recipe":recipe,
                "source_sha256":source_sha,"internal_artifact_sha256":artifact_sha,
                "quality_workorder_sha256":digest(order_path.read_bytes()),
                "source_hash_verified_against_original_manifest":True,
                "old_product_mutated":False,"technical_qa_retested":False,
                "professional_quality_1000_approved":False,
                "commercial_release_allowed":False
            }
            # Immutable private evidence receipt; no overwrite existing evidence.
            proof=result_root/(".recovery-"+recipe+".json")
            record=(json.dumps(receipt,sort_keys=True,ensure_ascii=False)+"\n").encode()
            if proof.is_symlink():raise ValueError("RECOVERY_RECEIPT_SYMLINK")
            if proof.exists():
                if proof.read_bytes()!=record:raise ValueError("RECOVERY_RECEIPT_CONFLICT")
            else:
                with proof.open("xb") as f:
                    f.write(record);f.flush();os.fsync(f.fileno())
                os.chmod(proof,0o600)
            stats["restored"]+=1
            results.append({"recipe":recipe,"source_sha256":source_sha})
        except (OSError,ValueError,TypeError,json.JSONDecodeError,zipfile.BadZipFile) as exc:
            stats["unrecoverable_with_current_provenance"]+=1
            # Exact aggregate remediation reasons; never log confidential
            # paths, arbitrary exceptions, source text or customer metadata.
            allowed={
                "RECOVERY_DOCUMENT_UNTRUSTED","RECOVERY_DOCUMENT_INVALID",
                "RECOVERY_UNBOUND_QUALITY_WORKORDER",
                "RECOVERY_AMBIGUOUS_OR_MISSING_STOCK",
                "RECOVERY_UNSAFE_STOCK_MANIFEST",
                "RECOVERY_MANIFEST_NOT_VERIFIABLE_SOURCE",
                "RECOVERY_ZIP_UNSAFE","RECOVERY_ARCHIVE_HASH_MISMATCH",
                "RECOVERY_SOURCE_MEMBERS_INVALID","RECOVERY_MEMBER_TRAVERSAL",
                "RECOVERY_MEMBER_NAME_INVALID","RECOVERY_MEMBER_CANONICAL_NAME_REQUIRED",
                "RECOVERY_SOURCE_HASH_MISMATCH","RECOVERY_SINGLE_FILE_TOO_LARGE",
                "RECOVERY_POST_WRITE_SOURCE_HASH_INVALID",
                "RECOVERY_CONCURRENT_SOURCE_EXISTS","RECOVERY_DESTINATION_SYMLINK",
                "RECOVERY_STOCK_SYMLINK","RECOVERY_UNSAFE_STOCK_ROOT",
                "RECOVERY_LINK_OR_DIR_FORBIDDEN",
                "RECOVERY_PREVIOUS_STOCK_UNVERIFIABLE",
                "RECOVERY_PREVIOUS_PROOF_MISMATCH",
                "RECOVERY_PREVIOUS_FILES_UNTRUSTED",
                "RECOVERY_PREVIOUS_FILES_MISMATCH",
            }
            detail=str(exc) if type(exc) is ValueError else ""
            reason=detail if detail in allowed else (
                "RECOVERY_UNREADABLE_ZIP" if isinstance(exc,zipfile.BadZipFile)
                else "RECOVERY_METADATA_OR_IO_NOT_VERIFIABLE")
            stats["remediation_"+reason]+=1
    summary={"schema":"saeit.factory.exact-source-recovery-summary.v1",
        "totals":dict(sorted(stats.items())),"recovered_receipts":results,
        "no_source_synthesis":True,"original_stock_mutated":False,
        "commercial_release_authorized":False,
        "independent_professional_quality_passed":False}
    print("FACTORY_EXACT_ORIGINAL_SOURCE_RECOVERY="+json.dumps(summary,sort_keys=True))
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--private-root",required=True)
    parser.add_argument("--limit",type=int,default=3)
    parser.add_argument("--other-source-root",action="append",default=[])
    parser.add_argument("--products-file",default=None)
    args=parser.parse_args()
    recover(args.private_root,limit=args.limit,other_roots=args.other_source_root,products_file=args.products_file)
if __name__=="__main__":main()
