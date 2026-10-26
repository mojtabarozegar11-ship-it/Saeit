#!/usr/bin/env python3
"""Real-inventory global-product-quality triage with immutable rework receipts.

Technical PASS and commercial quality are separate. Inspects manufacturing
artifacts and evidence in a non-public VPS directory. Never sells, publishes,
charges, changes a product manifest, or simulates reviewer credentials.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
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


SCHEMA="saeit.factory.quality-triage.v2"
REWORK="saeit.factory.quality-rework.v2"
SKU=re.compile(r"^[a-z][a-z0-9_]{1,65}$")
HEX=re.compile(r"^[a-f0-9]{64}$")
AUDIT_PENDING={"P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED",
               "P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED"}
QUARANTINE={"P0_ARTIFACT_UNVERIFIED","P0_BUILD_HASH_NOT_MATCHING_MANIFEST",
            "P0_SOURCE_PROVENANCE_HASH_MISSING_OR_INVALID",
            "P0_TECHNICAL_QA_NOT_PASSED","P0_UNSAFE_COMMERCIAL_STATE"}
QUALITY_CATEGORIES={
    "P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING":"REWORK_COMPETITIVE_COMPARISON",
    "P0_MEASURED_SUPERIORITY_UNVERIFIED":"REWORK_MEASURABLE_ADVANTAGE",
    "P0_ORIGINAL_INNOVATIONS_UNPROVEN":"REWORK_NOVELTY",
    "P0_UNMAPPED_PRODUCT_FAMILY":"REWORK_FAMILY_CLASSIFICATION",
    "P0_SOURCE_PROVENANCE_HASH_MISSING_OR_INVALID":"RECONSTRUCT_OR_AUTHENTICATE_ORIGINAL_SOURCE_PROVENANCE",
}
def sha(data):
    return hashlib.sha256(data).hexdigest()

def atomic_json(path, doc):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    assert not path.is_symlink()
    raw=(json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    fd,tmp=tempfile.mkstemp(prefix=".quality-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(raw);out.flush();os.fsync(out.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    assert path.read_bytes()==raw
    return sha(raw)

def load_module(path):
    spec=importlib.util.spec_from_file_location("global_premium_gate",str(path))
    if not spec or not spec.loader:raise RuntimeError("QUALITY_GATE_MISSING")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def classify(result):
    codes=[x["code"] for x in result["blockers"]]
    actual=[c for c in codes if c not in AUDIT_PENDING]
    if any(c in QUARANTINE for c in actual):
        status="QUARANTINE_TECHNICAL_OR_INTEGRITY"
    elif any(c=="P0_UNMAPPED_PRODUCT_FAMILY" for c in actual):
        status="RETURN_TO_PRODUCTION_CLASSIFICATION"
    elif actual:
        status="RETURN_TO_PRODUCTION_QUALITY"
    else:
        status="AWAITING_AUTHENTICATED_INDEPENDENT_REVIEW"
    if not actual:
        assert result["public_release_allowed"] is False
    return status,actual,[c for c in codes if c in AUDIT_PENDING]

def plan(code):
    if code in QUALITY_CATEGORIES:return QUALITY_CATEGORIES[code]
    if code.startswith("P0_PROOF_MISSING:"):return "PRODUCE_AUTHENTIC_"+code.split(":",1)[1].upper()
    if code.startswith("P0_DOMAIN_SPECIALIST_PROOF_MISSING:"):
        return "RUN_INDEPENDENT_FAMILY_SPECIALIST_TEST"
    if code in QUARANTINE:return "RESTORE_CORRECT_ARTIFACT_AND_RETEST"
    return "INVESTIGATE_WITH_ACCOUNTABLE_SPECIALIST"

def independent_zip_q068_fallback(folder,recipe,archive,manifest):
    """Bounded real ZIP measurement when newer reusable probe is not deployed.

    Never score a ZIP by merely trusting metadata. Does not assert originality,
    scientific validity, or human review.
    """
    import zipfile
    from pathlib import PurePosixPath
    target=Path(archive)
    desired=manifest.get("artifact_sha256")
    if (not isinstance(desired,str) or not HEX.fullmatch(desired)
        or not target.is_file() or target.is_symlink()
        or not 0<target.stat().st_size<=65*1024*1024):
        return None
    if sha(target.read_bytes())!=desired:return None
    try:
        count=0;total=0;member_checks=[]
        with zipfile.ZipFile(target) as bundle:
            files=bundle.infolist()
            if not 1<=len(files)<=2500:return None
            seen=set()
            for item in files:
                rel=item.filename
                parts=PurePosixPath(rel)
                if (rel in seen or rel.startswith("/") or "\\" in rel or
                    ".." in parts.parts or not rel.startswith(recipe+"/") or
                    item.is_dir() or ((item.external_attr>>16)&0o170000)==0o120000 or
                    item.file_size>40*1024*1024):
                    return None
                seen.add(rel)
                total+=item.file_size
                if total>150*1024*1024:return None
                data=bundle.read(item)
                if len(data)!=item.file_size:return None
                member_checks.append([rel,sha(data),len(data)])
                count+=1
    except (zipfile.BadZipFile,ValueError,OSError,EOFError,RuntimeError,NotImplementedError):
        return None
    report={"schema":"saeit.factory.measured-zip-integrity-q068.v1",
            "criterion":"Q068",
            "scope":"cryptographic_identity_zip_safety_crc_member_integrity_only",
            "recipe":recipe,"artifact_sha256":desired,
            "archive_bytes":target.stat().st_size,
            "actual_members_tested":count,
            "actual_uncompressed_bytes_tested":total,
            "members_sha256":member_checks,
            "all_crc_and_path_safety_tests_passed":True,
            "excludes":"scientific_veracity_game_originality_human_review_global_quality",
            "professional_quality_1000_approved":False}
    blob=(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
    out=Path(folder)/".quality-measurements"
    if out.is_symlink():raise ValueError("QUALITY_MEASUREMENTS_UNSAFE")
    out.mkdir(mode=0o700,exist_ok=True)
    evidence=out/("q068-"+desired+".json")
    if evidence.is_symlink():raise ValueError("QUALITY_MEASUREMENTS_UNSAFE")
    if evidence.exists():
        if evidence.read_bytes()!=blob:raise ValueError("QUALITY_MEASUREMENT_CHANGED")
    else:
        with evidence.open("xb") as receipt:
            receipt.write(blob);receipt.flush();os.fsync(receipt.fileno())
        evidence.chmod(0o600)
    return {"path":evidence.relative_to(folder).as_posix(),"sha256":sha(blob)}


def triage_inventory(private_root,policy,registry,run_reference="manual",limit=250,scorecard_file=None,products_file=None):
    root=Path(private_root)
    active_products=active_product_allowlist(products_file) if products_file else None
    assert root.is_dir() and not root.is_symlink()
    module=load_module(Path(policy))
    score_module=load_module(Path(scorecard_file) if scorecard_file else Path(__file__).with_name("factory_quality_1000_v2.py"))
    integrity_file=Path(__file__).with_name("factory_measured_zip_evidence_v1.py")
    integrity_module=load_module(integrity_file) if integrity_file.is_file() and not integrity_file.is_symlink() else None
    profiles=module.load_registry(Path(registry))
    assert len(profiles)==40
    out=root/"quality-excellence"/"rework"
    assert not out.is_symlink()
    out.mkdir(parents=True,exist_ok=True,mode=0o700)
    records=[]
    edition_stock=root/"quality-excellence"/"document-edition-private-stock"
    if edition_stock.is_symlink():
        raise ValueError("QA_EDITION_STOCK_SYMLINK_UNSAFE")
    sources=(root/"digital-products", root/"product-lifecycle"/"digital-products",
             edition_stock)
    # Refuse a superficially green report covering only the first N products.
    # Never silently omit eligible manifest-bearing inventory after a budget cap.
    eligible_total=0
    for base in sources:
        if base.is_dir() and not base.is_symlink():
            eligible_total+=sum(
                1 for folder in base.iterdir()
                if folder.is_dir() and not folder.is_symlink() and SKU.fullmatch(folder.name)
                and (active_products is None or folder.name in active_products)
                and (folder/"manufacturing_manifest.json").is_file()
                and not (folder/"manufacturing_manifest.json").is_symlink()
            )
    if eligible_total>limit:
        raise ValueError("QUALITY_INVENTORY_LIMIT_EXCEEDED:"+str(eligible_total))
    encountered=set()
    for base in sources:
        if not base.is_dir() or base.is_symlink():continue
        for folder in sorted(base.iterdir()):
            if len(records)>=limit:break
            if folder.is_symlink() or not folder.is_dir() or not SKU.fullmatch(folder.name):continue
            manifest_path=folder/"manufacturing_manifest.json"
            if not manifest_path.is_file() or manifest_path.is_symlink():continue
            name=folder.name
            if active_products is not None and name not in active_products:continue
            assert name not in encountered,"DUPLICATE_RECIPE_DIRECTORY:"+name
            encountered.add(name)
            try:
                doc=json.loads(manifest_path.read_text(encoding="utf8"))
                if not isinstance(doc,dict) or doc.get("recipe")!=name:
                    raise ValueError("MANUFACTURING_RECEIPT_IDENTITY")
                zipfile=folder/(name+"-internal-qa.zip")
                manifest_sha=doc.get("artifact_sha256")
                existing_hash=sha(zipfile.read_bytes()) if zipfile.is_file() and not zipfile.is_symlink() else None
                candidate_file=folder/"global_quality_candidate.json"
                if candidate_file.is_file() and not candidate_file.is_symlink() and candidate_file.stat().st_size<100000:
                    candidate=json.loads(candidate_file.read_text(encoding="utf8"))
                    if not isinstance(candidate,dict):raise ValueError("INVALID_CANDIDATE_OBJECT")
                else:
                    candidate={}
                family=doc.get("family_id") or candidate.get("family_id")
                if doc.get("family_id") and candidate.get("family_id") not in (None,doc["family_id"]):
                    raise ValueError("FAMILY_ID_CONFLICT")
                candidate=dict(candidate,family_id=family,artifact={
                    "path":zipfile.name,"sha256":existing_hash or ""})
                # Independently *measure* criterion Q068 from the actual ZIP bytes;
                # never accept an arbitrary text dossier as proof of ZIP integrity.
                measured=(integrity_module.measured_zip_evidence(folder,name,zipfile,doc)
                          if integrity_module is not None else
                          independent_zip_q068_fallback(folder,name,zipfile,doc))
                dossier=candidate.get("criteria_evidence")
                dossier=dict(dossier) if isinstance(dossier,dict) else {}
                dossier.pop("Q068",None)
                if measured:
                    dossier["Q068"]=measured
                verdict=module.inspect(candidate,folder,profiles,doc)
                status,actual,pending=classify(verdict)
                card=score_module.grade(verdict,exact_build_sha256=existing_hash,
                                        criteria_evidence=dossier,
                                        evidence_root=folder)
                score_module.require_no_false_certification(card)
                if not isinstance(manifest_sha,str) or not HEX.fullmatch(manifest_sha):
                    status="QUARANTINE_TECHNICAL_OR_INTEGRITY"
                    actual.append("P0_INVALID_MANIFEST_SHA256")
                source_sha=doc.get("source_sha256")
                provenance_ok=isinstance(source_sha,str) and bool(HEX.fullmatch(source_sha))
                if not provenance_ok:
                    status="QUARANTINE_TECHNICAL_OR_INTEGRITY"
                    actual.append("P0_SOURCE_PROVENANCE_HASH_MISSING_OR_INVALID")
                record={
                    "schema":REWORK, "recipe":name,"family_id":family,
                    "inventory_origin":("private_document_edition" if base==edition_stock
                                        else "existing_manufacturer_stock"),
                    "artifact_sha256":manifest_sha,
                    "actual_sha256":existing_hash,
                    "technical_qa_status":doc.get("qa_status"),
                    "source_provenance_sha256":source_sha if provenance_ok else None,
                    "source_provenance_hash_present":provenance_ok,
                    "verified_artifact_integrity":bool(
                        isinstance(manifest_sha,str) and HEX.fullmatch(manifest_sha)
                        and existing_hash==manifest_sha),
                    "measured_zip_integrity_Q068":measured,
                    "quality_1000_scorecard":card,
                    "quality_group_count":100,
                    "quality_points_per_group":10,
                    "required_quality_points":1000,
                    "quality_points_verified":None,
                    "documentary_evidence_points":card["documentary_evidence_points"],
                    "quality_status":status,
                    "premium_quality_approved":False,
                    "commercial_release_allowed":False,
                    "defects":sorted(set(actual)),
                    "external_audit_pending":sorted(set(pending)),
                    "rework_actions":sorted(set(plan(c) for c in actual)),
                    "candidate_evidence_dossier_sha256":(sha(candidate_file.read_bytes())
                        if candidate_file.is_file() and not candidate_file.is_symlink() else None),
                    "source_manifest_sha256":sha(manifest_path.read_bytes()),
                    "policy_sha256":sha(Path(policy).read_bytes()),
                    "registry_sha256":sha(Path(registry).read_bytes())
                }
            except (OSError,ValueError,KeyError,TypeError,AssertionError) as error:
                record={"schema":REWORK,"recipe":name,"quality_status":"QUARANTINE_AUDIT_ERROR",
                        "defects":["P0_AUDIT_ERROR_"+type(error).__name__],
                        "rework_actions":["INVESTIGATE_WITH_ACCOUNTABLE_SPECIALIST"],
                        "required_quality_points":1000,"quality_points_verified":None,
                        "documentary_evidence_points":0,
                        "premium_quality_approved":False,"commercial_release_allowed":False}
            folder_out=out/name
            assert not folder_out.is_symlink()
            folder_out.mkdir(parents=True,exist_ok=True,mode=0o700)
            os.chmod(folder_out,0o700)
            # Version/evidence-bound progress proof: never close an issue just
            # because the scoring policy or file label changed. A repaired
            # source or changed evidence dossier must pass a fresh rerun.
            old_file=folder_out/"current.json"
            try:
                previous=json.loads(old_file.read_text(encoding="utf8")) if old_file.is_file() and not old_file.is_symlink() else {}
            except (ValueError,OSError,TypeError):
                previous={}
            valid_previous=(isinstance(previous,dict) and previous.get("schema")==REWORK
                            and previous.get("recipe")==name)
            prior_codes=set(previous.get("defects",[])) if valid_previous else set()
            actual_codes=set(record.get("defects",[]))
            source_changed=(valid_previous and
                previous.get("source_manifest_sha256")!=record.get("source_manifest_sha256"))
            evidence_changed=(valid_previous and
                previous.get("candidate_evidence_dossier_sha256")!=record.get("candidate_evidence_dossier_sha256"))
            versioned_change=bool(source_changed or evidence_changed)
            closed=sorted(prior_codes-actual_codes) if versioned_change else []
            if prior_codes-actual_codes and not versioned_change:
                record["unverified_criterion_drops"]=sorted(prior_codes-actual_codes)
                record["commercial_release_allowed"]=False
            record["verified_against_new_version_or_dossier"]=versioned_change
            record["detected_defect_rechecks_after_change"]=closed
            record["closed_by_independent_expert"]=False
            record["rework_closeout_status"]="INDEPENDENT_SIGNOFF_STILL_REQUIRED"
            immutable_blob=(json.dumps(record,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode()
            key=sha(immutable_blob)
            receipt=folder_out/("rework-"+key[:24]+".json")
            if receipt.exists():
                assert not receipt.is_symlink() and receipt.read_bytes()==immutable_blob
            else:
                with receipt.open("xb") as fp:
                    fp.write(immutable_blob);fp.flush();os.fsync(fp.fileno())
                os.chmod(receipt,0o600)
            atomic_json(folder_out/"current.json",record)
            records.append(record)
    statuses=Counter(x["quality_status"] for x in records)
    defects=Counter(c for x in records for c in x["defects"])
    summary={
        "schema":SCHEMA,"run_reference":str(run_reference)[:80],
        "total_products":len(records),"inventory_eligible_total":eligible_total,
        "all_eligible_inventory_scanned":len(records)==eligible_total,
        "registered_families":len(profiles),
        "technical_passed":sum(x.get("technical_qa_status")=="passed"
                                and x.get("verified_artifact_integrity") is True
                                and x.get("source_provenance_hash_present") is True
                                for x in records),
        "new_document_editions_reentered_qa":sum(
            x.get("inventory_origin")=="private_document_edition" for x in records),
        "source_provenance_missing_or_invalid":sum(
            x.get("source_provenance_hash_present") is False for x in records),
        "quality_certified":0,"public_release_authorized":False,
        "required_quality_points":1000,
        "quality_group_count":100,
        "quality_points_per_group":10,
        "quality_score_units":"100_independent_groups_x_10",
        "actual_quality_verified_product_count":0,
        "documentary_evidence_points_sum":sum(x.get("documentary_evidence_points",0) for x in records),
        "status_counts":dict(sorted(statuses.items())),
        "top_stop_ship_defects":defects.most_common(20),
        "product_quality_scores": [{"recipe":x["recipe"],"required":1000,
             "documentary_evidence_points":x.get("documentary_evidence_points",0),
             "verified_quality_points":None,
             "eligible_for_sales":False} for x in records],
        "product_receipts":[{"recipe":x["recipe"],
                             "quality_status":x["quality_status"],
                             "defect_count":len(x["defects"])} for x in records]
    }
    summary_root=root/"quality-excellence"/"audit-receipts"
    assert not summary_root.is_symlink()
    summary_root.mkdir(parents=True,exist_ok=True,mode=0o700)
    filename="audit-"+re.sub(r"[^a-zA-Z0-9_-]","_",str(run_reference))[:72]+".json"
    signature=atomic_json(summary_root/filename,summary)
    print("FACTORY_ALL_40_GLOBAL_QA_TRIAGE=PASS")
    print("FACTORY_REAL_PRODUCTS_IN_REWORK_QUEUE="+str(len(records)))
    print("FACTORY_TECHNICAL_PASS_NOT_PREMIUM="+str(summary["technical_passed"]))
    print("FACTORY_PRIVATE_DOCUMENT_EDITIONS_IN_STRICT_QA="+
          str(summary["new_document_editions_reentered_qa"]))
    print("FACTORY_REAL_REWORK_CLASSIFICATION="+json.dumps(dict(statuses),sort_keys=True))
    print("FACTORY_TOP_STOP_SHIP_DEFECTS="+json.dumps(defects.most_common(8)))
    print("FACTORY_QUARANTINE_ROOT_CAUSES="+json.dumps(
        Counter(code for x in records if x["quality_status"].startswith("QUARANTINE")
                for code in x["defects"] if code.startswith(("P0_SOURCE_","P0_BUILD_","P0_ARTIFACT_","P0_TECHNICAL_","P0_UNSAFE_","P0_INVALID_","P0_AUDIT_"))).most_common(15)))
    print("FACTORY_QUALITY_GROUP_COUNT=100")
    print("FACTORY_QUALITY_POINTS_PER_GROUP=10")
    print("FACTORY_QUALITY_CRITERIA_COUNT=100")
    print("FACTORY_QUALITY_POINTS_PER_CRITERION=10")
    print("FACTORY_QUALITY_MINIMUM_REQUIRED=1000/1000")
    print("FACTORY_QUALITY_1000_INDEPENDENTLY_VERIFIED=0")
    print("FACTORY_WORLD_EXCELLENCE_APPROVED=0")
    print("FACTORY_REWORK_RECEIPT_SHA256="+signature)
    return summary

def main():
    p=argparse.ArgumentParser()
    for name in ("private-root","policy","registry"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--run-reference",default="manual")
    p.add_argument("--scorecard",default=None)
    p.add_argument("--products-file",default=None)
    args=p.parse_args()
    triage_inventory(args.private_root,args.policy,args.registry,args.run_reference,scorecard_file=args.scorecard,products_file=args.products_file)
if __name__=="__main__":main()
