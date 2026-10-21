#!/usr/bin/env python3
"""Bounded QA-to-native-rebuild bridge. No authorizations, sales or false QA closeout.

Consumes REAL VPS 1000-point private workorders. Where a factory-owned source
has changed, or an archived ZIP is mechanically broken, rebuilds a fresh private
candidate with the existing tested manufacturer. Never edits original warehouse.
Nonmechanical quality findings remain open for verifiable work by specialists.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

RECIPE=re.compile(r"^[a-z][a-z0-9_]{1,65}$")
HEX=re.compile(r"^[0-9a-f]{64}$")
MECHANICAL=("P0_BUILD_", "P0_ARTIFACT_", "P0_TECHNICAL_")
SCHEMA="saeit.factory.qa-native-rebuild-bridge.v1"

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def load_maker(path):
    if path.is_symlink() or not path.is_file():raise ValueError("PINNED_MAKER_NOT_PRESENT")
    spec=importlib.util.spec_from_file_location("saeit_qa_rebuild_pinned_maker",str(path))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def checked_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2_000_000:
        raise ValueError("UNSAFE_SOURCE_EVIDENCE")
    doc=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(doc,dict):raise ValueError("INVALID_EVIDENCE_DOCUMENT")
    return doc

def atomic_receipt(path,doc):
    blob=(json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
    digest=sha(blob)
    dest=path/("repair-"+digest[:24]+".json")
    if dest.is_symlink():raise ValueError("REPAIR_RECEIPT_SYMLINK")
    if dest.exists():
        if dest.read_bytes()!=blob:raise ValueError("REPAIR_RECEIPT_CONFLICT")
    else:
        path.mkdir(parents=True,mode=0o700,exist_ok=True)
        with dest.open("xb") as f:
            f.write(blob);f.flush();os.fsync(f.fileno())
        os.chmod(dest,0o600)
    return digest

def recover_source_from_archive(root,recipe,order,maker,recovered_root):
    """Recover source only from the original artifact bound to its QA receipt."""
    product=root/"digital-products"/recipe
    manifest=product/"manufacturing_manifest.json"
    archive=product/(recipe+"-internal-qa.zip")
    if not product.exists():return False,None
    if product.is_symlink():return False,"unsafe_archive_path"
    if not archive.is_file():return False,None
    if archive.is_symlink() or (manifest.exists() and manifest.is_symlink()):
        return False,"unsafe_archive_path"
    try:
        expected_artifact=order.get("artifact_sha256")
        receipt=root/"quality-excellence"/"rework"/recipe/"current.json"
        if (not isinstance(expected_artifact,str) or not HEX.fullmatch(expected_artifact)
                or not receipt.is_file() or receipt.is_symlink()
                or sha(receipt.read_bytes())!=order.get("source_quality_receipt_sha256")
                or checked_json(receipt).get("artifact_sha256")!=expected_artifact):
            return False,"triage_receipt_mismatch"
        try:meta=checked_json(manifest) if manifest.is_file() else {}
        except (ValueError,OSError,UnicodeError):meta={}
        files=meta.get("files") if meta.get("recipe")==recipe else None
        source_expected=meta.get("source_sha256")
        if not isinstance(source_expected,str) or not HEX.fullmatch(source_expected):source_expected=None
        if (not isinstance(files,list) or not files or len(files)>256
                or any(not isinstance(name,str) or "\\" in name for name in files)):
            files=None
        raw=archive.read_bytes()
        if len(raw)>64*1024*1024:return False,"archive_too_large"
        if sha(raw)!=expected_artifact:return False,"archive_hash_mismatch"
        if recovered_root.parent.is_symlink():return False,"unsafe_recovered_root"
        recovered_root.mkdir(parents=True,mode=0o700,exist_ok=True)
        if recovered_root.is_symlink():return False,"unsafe_recovered_root"
        target=recovered_root/recipe
        if target.exists() or target.is_symlink():return False,"recovered_target_conflict"
        stage=Path(tempfile.mkdtemp(prefix="."+recipe+"-",dir=str(recovered_root)))
        try:
            payload=stage/recipe
            payload.mkdir(mode=0o700)
            with zipfile.ZipFile(archive,"r") as zf:
                infos=zf.infolist()
                if not infos or len(infos)>256 or zf.testzip() is not None or sum(i.file_size for i in infos)>64*1024*1024:
                    return False,"archive_members_invalid"
                archive_names=[]
                for info in infos:
                    if info.is_dir():return False,"archive_members_invalid"
                    name=info.filename
                    rel=PurePosixPath(name)
                    if not name or "\\" in name or rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
                        return False,"archive_members_invalid"
                    archive_names.append(rel.as_posix())
                if len(set(archive_names))!=len(archive_names):return False,"archive_members_invalid"
                if all(name.startswith(recipe+"/") for name in archive_names):
                    names=[name[len(recipe)+1:] for name in archive_names]
                elif all("/" not in name for name in archive_names):
                    names=list(archive_names)
                else:
                    top={name.split("/",1)[0] for name in archive_names}
                    if len(top)!=1 or any("/" not in name for name in archive_names):
                        return False,"archive_members_invalid"
                    wrapper=next(iter(top))
                    names=[name[len(wrapper)+1:] for name in archive_names]
                normalized=sorted(files) if files is not None else sorted(names)
                if sorted(names)!=normalized:return False,"archive_members_invalid"
                for info,name in zip(infos,names):
                    if stat.S_ISLNK(info.external_attr>>16):return False,"archive_symlink_member"
                    dest=payload/name
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(zf.read(info));os.chmod(dest,0o600)
            _,checked_files=maker.inspect_recipe(payload)
            source_hash=maker.source_digest(payload,checked_files)
            if tuple(checked_files)!=tuple(normalized) or (source_expected and source_hash!=source_expected):
                return False,"source_hash_mismatch"
            os.chmod(payload,0o700);os.replace(payload,target)
            return True,None
        finally:
            if stage.exists():shutil.rmtree(stage)
    except zipfile.BadZipFile:return False,"archive_invalid_zip"
    except (OSError,ValueError,RuntimeError,UnicodeError,KeyError):
        return False,"archive_recovery_error"

def execute(root,source_root,maker_path,*,limit=2,additional_source_roots=()):
    """Rebuild from either verified generated or installed native recipe roots."""
    root=Path(root);source_root=Path(source_root);maker_path=Path(maker_path)
    if not root.is_dir() or root.is_symlink():raise ValueError("PRIVATE_FACTORY_ROOT_INVALID")
    if not source_root.is_dir() or source_root.is_symlink():raise ValueError("PRIVATE_SOURCE_ROOT_INVALID")
    if not isinstance(additional_source_roots,(list,tuple)) or len(additional_source_roots)>2:
        raise ValueError("BOUNDED_SOURCE_ROOTS_REQUIRED")
    # Installed factory sources are stored outside private generated recipes.
    # Discover only the canonical sibling under the same factory-runtime root.
    # Preserve the explicit override for isolated CI fixtures and operators.
    canonical=root.parent.parent/"operations"/"autonomous-product-runtime"/"product_recipes"
    if not additional_source_roots and canonical.is_dir():
        if canonical.is_symlink():
            raise ValueError("CANONICAL_PRODUCT_RECIPES_SYMLINK_UNSAFE")
        additional_source_roots=[canonical]
    roots=[source_root]
    for extra in additional_source_roots:
        candidate=Path(extra)
        if candidate.is_symlink() or not candidate.is_dir():
            raise ValueError("ADDITIONAL_RECIPE_ROOT_UNSAFE_OR_MISSING")
        if candidate.resolve() in (item.resolve() for item in roots):
            raise ValueError("DUPLICATE_SOURCE_ROOT")
        roots.append(candidate)
    recovered_root=root/"quality-excellence"/"recovered-verified-sources"
    if recovered_root.exists() or recovered_root.is_symlink():
        if recovered_root.is_symlink() or not recovered_root.is_dir():
            raise ValueError("RECOVERED_SOURCE_ROOT_UNSAFE")
        if recovered_root.resolve() in (item.resolve() for item in roots):
            raise ValueError("DUPLICATE_SOURCE_ROOT")
        roots.append(recovered_root)
    if type(limit) is not int or not 1<=limit<=3:raise ValueError("BOUNDED_CAP_REQUIRED")
    maker=load_maker(maker_path)
    workorders=root/"quality-excellence"/"production-workorders"
    if not workorders.is_dir() or workorders.is_symlink():
        raise ValueError("ACTUAL_QA_WORKORDERS_NOT_PRESENT")
    output=root/"quality-excellence"/"rebuilt-technical-candidates"
    output.mkdir(parents=True,mode=0o700,exist_ok=True)
    if output.is_symlink():raise ValueError("UNSAFE_REBUILD_DESTINATION")
    receipts=root/"quality-excellence"/"native-rebuild-receipts"
    if receipts.is_symlink():raise ValueError("UNSAFE_REPAIR_RECEIPT_ROOT")
    totals={"orders_seen":0,"sources_available":0,"source_changed":0,
            "rebuild_attempted":0,"technical_candidates_verified":0,
            "unchanged_or_human_only":0,"missing_source":0,"failed":0,
            "archive_sources_recovered":0,"archive_recovery_rejected":0,
            "archive_recovery_rejection_reasons":{},
            "verified_source_roots":len(roots),
            "source_root_hits":[0 for _ in roots],
            "duplicate_recipe_roots_blocked":0}
    orders=[]
    for folder in sorted(workorders.iterdir()):
        if folder.is_symlink() or not folder.is_dir() or not RECIPE.fullmatch(folder.name):
            continue
        current=folder/"current.json"
        if not current.is_file() or current.is_symlink():continue
        order=checked_json(current)
        if order.get("schema")!="saeit.factory.production-rework-order.v1" or order.get("recipe")!=folder.name:
            continue
        if not isinstance(order.get("source_quality_receipt_sha256"),str) or not HEX.fullmatch(order["source_quality_receipt_sha256"]):
            continue
        if not isinstance(order.get("unresolved_technical_or_domain_defects",[]),list):
            continue
        orders.append((folder.name,order))
    for recipe,order in orders:
        totals["orders_seen"]+=1
        locations=[(index,parent,parent/recipe)
                   for index,parent in enumerate(roots)
                   if (parent/recipe).is_dir() and not (parent/recipe).is_symlink()]
        if not locations:
            restored,rejection=recover_source_from_archive(root,recipe,order,maker,recovered_root)
            if rejection:
                totals["archive_recovery_rejected"]+=1
                reasons=totals["archive_recovery_rejection_reasons"]
                reasons[rejection]=reasons.get(rejection,0)+1
            if restored:
                totals["archive_sources_recovered"]+=1
                if recovered_root.resolve() not in (item.resolve() for item in roots):
                    roots.append(recovered_root);totals["source_root_hits"].append(0)
                    totals["verified_source_roots"]=len(roots)
                index=next(i for i,item in enumerate(roots)
                           if item.resolve()==recovered_root.resolve())
                locations=[(index,recovered_root,recovered_root/recipe)]
            else:
                totals["missing_source"]+=1
                continue
        # Never make an arbitrary selection if two roots own the same recipe.
        # A genuine source collision needs operator provenance resolution.
        if len(locations)>1:
            totals["duplicate_recipe_roots_blocked"]+=1
            continue
        index,active_root,source=locations[0]
        try:
            _,files=maker.inspect_recipe(source)
            source_hash=maker.source_digest(source,files)
        except (OSError,ValueError,RuntimeError,UnicodeError):
            totals["missing_source"]+=1
            continue
        totals["sources_available"]+=1
        totals["source_root_hits"][index]+=1
        original=root/"digital-products"/recipe/"manufacturing_manifest.json"
        prior=checked_json(original) if original.is_file() else {}
        changed=prior.get("source_sha256")!=source_hash
        mechanical=any(isinstance(code,str) and code.startswith(MECHANICAL)
                       for code in order.get("unresolved_technical_or_domain_defects",[]))
        if not changed and not mechanical:
            totals["unchanged_or_human_only"]+=1
            continue
        if changed:totals["source_changed"]+=1
        receipt_folder=receipts/recipe
        if receipt_folder.is_symlink():raise ValueError("UNSAFE_RECIPE_RECEIPT")
        # Per exact source + QA order. A repeated failed build may be retried on
        # the next authorized run; successful immutable receipts are idempotent.
        basis=sha((recipe+source_hash+order["source_quality_receipt_sha256"]).encode())
        proof=receipt_folder/("source-"+basis[:24]+".json")
        if proof.is_file() and not proof.is_symlink():
            prior_proof=checked_json(proof)
            if prior_proof.get("status")=="technical_candidate_verified":
                continue
        if totals["rebuild_attempted"]>=limit:continue
        totals["rebuild_attempted"]+=1
        try:
            result=maker.manufacture(recipe,active_root,output)
            target=output/recipe
            meta=checked_json(target/"manufacturing_manifest.json")
            package=target/(recipe+"-internal-qa.zip")
            if (meta.get("qa_status")!="passed" or meta.get("source_sha256")!=source_hash
                or not package.is_file() or package.is_symlink()
                or maker.sha256_file(package)!=meta.get("artifact_sha256")
                or result.get("qa_status")!="passed"):
                raise ValueError("REBUILD_TECHNICAL_QA_NOT_VERIFIED")
            record={"schema":SCHEMA,"recipe":recipe,"source_sha256":source_hash,
                    "source_root_slot":index,
                    "source_order_sha256":order["source_quality_receipt_sha256"],
                    "artifact_sha256":meta["artifact_sha256"],
                    "source_changed":changed,
                    "status":"technical_candidate_verified",
                    "independent_quality_1000_passed":False,
                    "commercial_release_authorized":False,
                    "original_stock_mutated":False}
            atomic_receipt(receipt_folder,record)
            receipt_folder.mkdir(parents=True,mode=0o700,exist_ok=True)
            if proof.is_symlink():raise ValueError("UNSAFE_SUCCESS_MARKER")
            if proof.is_file():
                if checked_json(proof)!=record:raise ValueError("CONFLICTING_SUCCESS_MARKER")
            else:
                with proof.open("x",encoding="utf8") as f:
                    json.dump(record,f,ensure_ascii=False,sort_keys=True)
                    f.write("\n")
                    f.flush();os.fsync(f.fileno())
                os.chmod(proof,0o600)
            totals["technical_candidates_verified"]+=1
        except (ValueError,OSError,RuntimeError,AssertionError,KeyError,TypeError):
            totals["failed"]+=1
    totals.update({"schema":SCHEMA,"commercial_release_authorized":False,
                   "professional_quality_1000_verified":False,
                   "all_40_native_executors_proven":False})
    print("FACTORY_REAL_NATIVE_REBUILD="+json.dumps(totals,sort_keys=True))
    return totals

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--private-root",required=True)
    p.add_argument("--source-root",required=True)
    p.add_argument("--additional-source-root",action="append",default=[])
    p.add_argument("--maker",required=True)
    p.add_argument("--limit",type=int,default=2)
    a=p.parse_args()
    execute(a.private_root,a.source_root,a.maker,limit=a.limit,
            additional_source_roots=a.additional_source_root)

if __name__=="__main__":main()

