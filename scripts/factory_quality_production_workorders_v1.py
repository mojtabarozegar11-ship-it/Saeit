#!/usr/bin/env python3
"""Produce REAL data collection work-orders from private QA, never fake 1000 pts.

Each product has 100 separate criterion obligations plus domain-specific work.
This is an operational queue for specialists and engineering, not AI-written
evidence: criterion points stay zero unless measured, peer reviewed and signed.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
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

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):
    spec=importlib.util.spec_from_file_location("factory_100_criteria_gate",str(path))
    assert spec is not None and spec.loader is not None
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
EXTERNAL_SIGNATURE_ROLES = (
    "domain_specialist", "independent_quality_auditor", "rights_reviewer"
)
EXTERNAL_ONLY_DEFECTS = {
    "P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED",
    "P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED",
    "P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING",
    "P0_MEASURED_SUPERIORITY_UNVERIFIED",
}
EXTERNAL_PROOF_AREAS = {
    "global_comparative_advantage", "domain_depth_and_accuracy",
    "user_customer_value", "independent_expert_review",
    "legal_rights_and_provenance", "originality_and_non_derivativeness",
}
ENGINEERING_AREAS = {
    "technology_and_technical_excellence", "distribution_support_reliability",
    "real_world_performance_accessibility", "independent_adversarial_testing",
    "security_ethics_regulatory_safety",
}

def external_only_defect(code):
    return (code in EXTERNAL_ONLY_DEFECTS or
            code.startswith("P0_PROOF_MISSING:") and
            code.partition(":")[2] in EXTERNAL_PROOF_AREAS)

def workstream(group_id, policy):
    dimensions=policy.get("quality_dimensions",[])
    if (group_id in ("Q068","Q092") or
            any(x in ENGINEERING_AREAS for x in dimensions)):
        return "engineering_evidence"
    return "external_evidence_acquisition"



def write_private_lane(base, lane, product, document, run_id):
    """Durable private queues, never an electronic expert or owner signature."""
    parent = base / "quality-excellence" / lane
    if parent.is_symlink():
        raise RuntimeError("UNSAFE_QUALITY_LANE_PARENT")
    parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    target = parent / product
    if target.is_symlink():
        raise RuntimeError("UNSAFE_QUALITY_LANE_TARGET")
    target.mkdir(mode=0o700, exist_ok=True)
    body = (json.dumps(document, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf8")
    digest = hashlib.sha256(body).hexdigest()
    receipt = target / ("order-" + digest[:24] + ".json")
    if receipt.is_symlink():
        raise RuntimeError("UNSAFE_QUALITY_LANE_RECEIPT")
    if receipt.exists():
        if receipt.read_bytes() != body:
            raise RuntimeError("QUALITY_LANE_RECEIPT_COLLISION")
    else:
        with receipt.open("xb") as stream:
            stream.write(body)
            stream.flush()
        receipt.chmod(0o600)
    current = target / "current.json"
    if current.is_symlink():
        raise RuntimeError("UNSAFE_QUALITY_LANE_CURRENT")
    tmp = target / (".next-" + re.sub(r"[^0-9A-Za-z]", "", str(run_id))[:20])
    if tmp.is_symlink():
        raise RuntimeError("UNSAFE_QUALITY_LANE_TEMP")
    with tmp.open("wb") as stream:
        stream.write(body)
        stream.flush()
    tmp.chmod(0o600)
    tmp.replace(current)
    if current.read_bytes() != body:
        raise RuntimeError("QUALITY_LANE_READBACK_FAILED")
    return digest


def separate_lanes(snapshot, findings, defects, source_receipt_sha256):
    """Human certification must not globally block private technical work."""
    external_pending = sorted(set(snapshot.get("external_audit_pending") or []))
    engineering_defects = sorted(x for x in set(defects) if not external_only_defect(x))
    external_defects = sorted(x for x in set(defects) if external_only_defect(x))
    technical_findings = [x for x in findings if x["workstream"]=="engineering_evidence"]
    external_findings = [x for x in findings if x["workstream"]=="external_evidence_acquisition"]
    technical_precheck = (
        snapshot.get("technical_qa_status") == "passed"
        and snapshot.get("verified_artifact_integrity") is True
        and snapshot.get("source_provenance_hash_present") is True
    )
    engineering_status = (
        "TECHNICAL_REPAIR_REQUIRED"
        if engineering_defects or not technical_precheck
        else "PRIVATE_TECHNICAL_PRECHECK_PASSED"
    )
    shared = {
        "recipe": snapshot.get("recipe"),
        "source_quality_receipt_sha256": source_receipt_sha256,
        "artifact_sha256": snapshot.get("artifact_sha256"),
        "human_signature_forged": False,
        "quality_1000_certified": False,
        "commercial_release_allowed": False,
    }
    engineering = {
        **shared,
        "schema": "saeit.factory.engineering-quality-lane.v1",
        "status": engineering_status,
        "mechanical_precheck_verified": technical_precheck,
        "unresolved_engineering_defects": engineering_defects,
        "technical_evidence_work_pending": technical_findings,
        "technical_evidence_gap_count": len(technical_findings),
        "external_only_defects_not_sent_to_engineering": external_defects,
        "nontechnical_evidence_gaps_not_sent_to_engineering": len(external_findings),
        "next_action": (
            "RUN_SOURCE_BACKED_REPAIR_AND_RETEST"
            if engineering_status == "TECHNICAL_REPAIR_REQUIRED"
            else "CONTINUE_MEASURABLE_ENGINEERING_IMPROVEMENTS"
        ),
        "independent_specialist_signature_required_to_continue_engineering": False,
        "independent_expert_certification_obtained": False,
    }
    certification = {
        **shared,
        "schema": "saeit.factory.independent-certification-lane.v1",
        "status": "AWAITING_VERIFIED_EXTERNAL_SPECIALISTS",
        "pending_roles": list(EXTERNAL_SIGNATURE_ROLES),
        "pending_external_audit_findings": external_pending,
        "pending_nonengineering_defects": external_defects,
        "external_evidence_work_pending": external_findings,
        "external_evidence_gap_count": len(external_findings),
        "quality_criteria_requiring_independent_validation": [
            entry["group_id"] for entry in findings
        ],
        "verified_external_signatures": 0,
        "independent_certification_claimed": False,
        "blocks_private_engineering": False,
        "blocks_professional_1000_certification": True,
        "blocks_new_commercial_release": True,
    }
    return engineering, certification


def work_orders(root,quality_file,catalog_file,run_id,limit=300,products_file=None):
    base=Path(root)
    active_products=active_product_allowlist(products_file) if products_file else None
    source=base/"quality-excellence"/"rework"
    assert base.is_dir() and source.is_dir() and not source.is_symlink()
    module=load(quality_file)
    catalog=module.catalog()
    assert len(catalog)==100
    # Bind --catalog to the exact policy used for the 100 orders.
    policy_path=Path(catalog_file)
    if (policy_path.is_symlink() or not policy_path.is_file()
            or not 0<policy_path.stat().st_size<=200_000):
        raise ValueError("QUALITY_CATALOG_FILE_MISSING_OR_UNSAFE")
    policy_doc=json.loads(policy_path.read_text(encoding="utf8"))
    if (not isinstance(policy_doc,dict)
            or policy_doc.get("schema")!="saeit.factory.quality-100-groups.v2"
            or policy_doc.get("groups")!=catalog):
        raise ValueError("QUALITY_CATALOG_ARGUMENT_MISMATCH")
    catalog_sha256=sha(policy_path)
    output=base/"quality-excellence"/"production-workorders"
    assert not output.is_symlink()
    output.mkdir(parents=True,mode=0o700,exist_ok=True)
    jobs=[]
    for folder in sorted(source.iterdir()):
        if len(jobs)>=limit:break
        if active_products is not None and folder.name not in active_products:continue
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r"[a-z][a-z0-9_]{1,65}",folder.name):
            continue
        current=folder/"current.json"
        if not current.is_file() or current.is_symlink():continue
        snapshot=json.loads(current.read_text(encoding="utf8"))
        score=snapshot.get("quality_1000_scorecard",{})
        rows=score.get("criteria",{})
        findings=[]
        for number,policy in catalog.items():
            item=rows.get(number,{})
            status=item.get("evidence_status")
            if item.get("documentary_points")==10:continue
            findings.append({
                "group_id":number,
                "criterion":policy["name"],
                "max_points":10,
                "quality_dimensions":list(policy["quality_dimensions"]),
                "workstream":workstream(number,policy),
                "observed_evidence_status":status or "NO_EVIDENCE",
                "state":"AWAITING_REAL_MEASUREMENT_AND_REVIEW",
                "action":"Produce reproducible test or specialist assessment, attach original source bytes with SHA256, and request independent fact/quality review.",
            })
        rest=sorted(set(snapshot.get("defects",[])))
        content={
          "schema":"saeit.factory.production-rework-order.v1",
          "recipe":folder.name,
          "source_quality_receipt_sha256":sha(current),
          "quality_catalog_sha256":catalog_sha256,
          "artifact_sha256":snapshot.get("artifact_sha256"),
          "quality_score_required":1000,
          "group_count":100,"points_per_group":10,
          "status":"NEEDS_REWORK" if findings or rest else "WAITING_SIGNED_INDEPENDENT_APPROVAL",
          "missing_documentary_group_count":len(findings),
          "unresolved_technical_or_domain_defects":rest,
          "rework_actions":snapshot.get("rework_actions",[]),
          "required_criterion_work":findings,
          "never_auto_sign_off":True,
          "signed_external_quality_approval_required":True,
          "owner_release_approval_required":True,
          "commercial_publish_allowed":False,
        }
        dest=output/folder.name
        assert not dest.is_symlink()
        dest.mkdir(parents=True,exist_ok=True,mode=0o700)
        bytes_=json.dumps(content,ensure_ascii=False,sort_keys=True,indent=2).encode()+b"\n"
        key=hashlib.sha256(bytes_).hexdigest()
        persistent=dest/("order-"+key[:20]+".json")
        if persistent.exists():
            assert not persistent.is_symlink() and persistent.read_bytes()==bytes_
        else:
            with persistent.open("xb") as out:
                out.write(bytes_);out.flush()
            persistent.chmod(0o600)
        current_order=dest/"current.json"
        tmp=dest/(".stage-"+re.sub(r"[^0-9A-Za-z]","",str(run_id))[:20])
        with tmp.open("wb") as out:out.write(bytes_)
        tmp.chmod(0o600);tmp.replace(current_order)
        engineering, certification = separate_lanes(snapshot, findings, rest, sha(current))
        engineering["recipe"] = folder.name
        certification["recipe"] = folder.name
        engineering_digest = write_private_lane(
            base, "engineering-workorders", folder.name, engineering, run_id)
        certification_digest = write_private_lane(
            base, "independent-certification-queue", folder.name, certification, run_id)
        jobs.append({"recipe":folder.name,"groups_pending":len(findings),
                     "unresolved_defect_count":len(rest),
                     "engineering_lane_status":engineering["status"],
                     "external_certification_status":certification["status"],
                     "engineering_order_sha256":engineering_digest,
                     "certification_order_sha256":certification_digest,
                     "source_receipt_sha256":sha(current),
                     "engineering_evidence_gaps":engineering["technical_evidence_gap_count"],
                     "external_evidence_gaps":certification["external_evidence_gap_count"],
                     "workorder_sha256":key})
    overview={"schema":"saeit.factory.workorder-index.v1",
              "products":len(jobs),"pending_groups_total":sum(x["groups_pending"] for x in jobs),
              "workorder_count":len(jobs),
              "quality_catalog_sha256":catalog_sha256,
              "engineering_evidence_gaps_total":sum(x["engineering_evidence_gaps"] for x in jobs),
              "external_evidence_gaps_total":sum(x["external_evidence_gaps"] for x in jobs),
              "commercially_approved":0,
               "private_engineering_prechecks_passed":sum(
                   item["engineering_lane_status"]=="PRIVATE_TECHNICAL_PRECHECK_PASSED"
                   for item in jobs),
               "external_certifications":0,
               "independent_certification_pending":len(jobs),
               "generated_by":"measured_evidence_intake_only",
              "items":jobs}
    manifest=output/("index-"+re.sub(r"[^0-9A-Za-z]","",str(run_id))[:40]+".json")
    if manifest.exists():assert json.loads(manifest.read_text())==overview
    else:
        with manifest.open("x",encoding="utf8") as f:
            json.dump(overview,f,ensure_ascii=False,sort_keys=True,indent=2);f.write("\n")
        manifest.chmod(0o600)
    print("FACTORY_PRODUCTION_WORKORDERS_WRITTEN="+str(len(jobs)))
    print("FACTORY_MISSING_VERIFIABLE_QUALITY_GROUPS="+str(overview["pending_groups_total"]))
    print("FACTORY_COMMERCIAL_APPROVALS_CREATED=0")
    return overview
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("private-root","quality-module","catalog","run-id"):
        p.add_argument("--"+key,required=True)
    p.add_argument("--products-file",default=None)
    a=p.parse_args()
    work_orders(a.private_root,Path(a.quality_module),Path(a.catalog),a.run_id,products_file=a.products_file)
