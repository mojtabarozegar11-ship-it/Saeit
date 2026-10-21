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

SCHEMA="saeit.factory.quality-triage.v2"
REWORK="saeit.factory.quality-rework.v2"
SKU=re.compile(r"^[a-z][a-z0-9_]{1,65}$")
HEX=re.compile(r"^[a-f0-9]{64}$")
AUDIT_PENDING={"P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED",
               "P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED"}
QUARANTINE={"P0_ARTIFACT_UNVERIFIED","P0_BUILD_HASH_NOT_MATCHING_MANIFEST",
            "P0_TECHNICAL_QA_NOT_PASSED","P0_UNSAFE_COMMERCIAL_STATE"}
QUALITY_CATEGORIES={
    "P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING":"REWORK_COMPETITIVE_COMPARISON",
    "P0_MEASURED_SUPERIORITY_UNVERIFIED":"REWORK_MEASURABLE_ADVANTAGE",
    "P0_ORIGINAL_INNOVATIONS_UNPROVEN":"REWORK_NOVELTY",
    "P0_UNMAPPED_PRODUCT_FAMILY":"REWORK_FAMILY_CLASSIFICATION",
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

def triage_inventory(private_root,policy,registry,run_reference="manual",limit=250,scorecard_file=None):
    root=Path(private_root)
    assert root.is_dir() and not root.is_symlink()
    module=load_module(Path(policy))
    score_module=load_module(Path(scorecard_file) if scorecard_file else Path(__file__).with_name("factory_quality_1000_scorecard.py"))
    profiles=module.load_registry(Path(registry))
    assert len(profiles)==40
    out=root/"quality-excellence"/"rework"
    assert not out.is_symlink()
    out.mkdir(parents=True,exist_ok=True,mode=0o700)
    records=[]
    sources=(root/"digital-products", root/"product-lifecycle"/"digital-products")
    encountered=set()
    for base in sources:
        if not base.is_dir() or base.is_symlink():continue
        for folder in sorted(base.iterdir()):
            if len(records)>=limit:break
            if folder.is_symlink() or not folder.is_dir() or not SKU.fullmatch(folder.name):continue
            manifest_path=folder/"manufacturing_manifest.json"
            if not manifest_path.is_file() or manifest_path.is_symlink():continue
            name=folder.name
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
                verdict=module.inspect(candidate,folder,profiles,doc)
                status,actual,pending=classify(verdict)
                card=score_module.grade(verdict,exact_build_sha256=existing_hash)
                score_module.require_no_false_certification(card)
                if not isinstance(manifest_sha,str) or not HEX.fullmatch(manifest_sha):
                    status="QUARANTINE_TECHNICAL_OR_INTEGRITY"
                    actual.append("P0_INVALID_MANIFEST_SHA256")
                record={
                    "schema":REWORK, "recipe":name,"family_id":family,
                    "artifact_sha256":manifest_sha,
                    "actual_sha256":existing_hash,
                    "technical_qa_status":doc.get("qa_status"),
                    "quality_1000_scorecard":card,
                    "required_quality_points":1000,
                    "quality_points_verified":None,
                    "documentary_evidence_points":card["documentary_evidence_points"],
                    "quality_status":status,
                    "premium_quality_approved":False,
                    "commercial_release_allowed":False,
                    "defects":sorted(set(actual)),
                    "external_audit_pending":sorted(set(pending)),
                    "rework_actions":sorted(set(plan(c) for c in actual)),
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
        "total_products":len(records),"registered_families":len(profiles),
        "technical_passed":sum(x.get("technical_qa_status")=="passed" for x in records),
        "quality_certified":0,"public_release_authorized":False,
        "required_quality_points":1000,
        "quality_score_units":"noncompensatory_12_pillar_thousand",
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
    print("FACTORY_REAL_REWORK_CLASSIFICATION="+json.dumps(dict(statuses),sort_keys=True))
    print("FACTORY_TOP_STOP_SHIP_DEFECTS="+json.dumps(defects.most_common(8)))
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
    args=p.parse_args()
    triage_inventory(args.private_root,args.policy,args.registry,args.run_reference,scorecard_file=args.scorecard)
if __name__=="__main__":main()
