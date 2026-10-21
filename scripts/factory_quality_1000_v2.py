#!/usr/bin/env python3
"""Actual 100 distinct quality criteria, ten points each; no auto-approval."""
import hashlib,json,re
from pathlib import Path
SCHEMA="saeit.factory.quality-1000.v2"
TARGET=1000
def catalog():
    here=Path(__file__).resolve()
    one=here.with_name("quality_100_criteria.json")
    two=here.parents[1]/"factory_config"/"quality_100_criteria.json"
    d=json.loads((one if one.is_file() else two).read_text(encoding="utf8"))
    if d.get("schema")!="saeit.factory.quality-100-criteria.v1" or d.get("required_points")!=1000 or d.get("points_per_criterion")!=10:
        raise RuntimeError("QUALITY_CATALOG_WRONG_SCHEMA")
    if len(d["groups"])!=10 or any(len(x)!=10 for x in d["groups"].values()):
        raise RuntimeError("QUALITY_CATALOG_NOT_100_ITEMS")
    items={"Q%03d"%(i*10+j+1):{"name":name,"group":group}
           for i,(group,values) in enumerate(d["groups"].items())
           for j,name in enumerate(values)}
    if len(items)!=100 or len({x["name"] for x in items.values()})!=100:
        raise RuntimeError("QUALITY_CATALOG_DUPLICATES")
    return items
CRITERIA=catalog()
LINK={
"global_competition":["global_comparative_advantage"],
"originality_innovation":["originality_and_non_derivativeness","verified_innovation"],
"advanced_technology":["technology_and_technical_excellence"],
"domain_scientific_depth":["domain_depth_and_accuracy"],
"customer_value":["user_customer_value"],
"design_user_experience":["real_world_performance_accessibility"],
"reliability_testing":["independent_adversarial_testing"],
"safety_security_rights":["security_ethics_regulatory_safety","legal_rights_and_provenance"],
"commercial_delivery":["distribution_support_reliability"],
"independent_validation":["independent_expert_review"]}
assert {c["group"] for c in CRITERIA.values()}==set(LINK)
SPECIAL={
"Q002":"P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING",
"Q006":"P0_MEASURED_SUPERIORITY_UNVERIFIED",
"Q013":"P0_ORIGINAL_INNOVATIONS_UNPROVEN",
"Q014":"P0_ORIGINAL_INNOVATIONS_UNPROVEN"}
PENDING={"P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED",
         "P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED"}
def file_matches(base,value):
    if not isinstance(value,dict) or base is None:return False
    p,h=value.get("path"),value.get("sha256")
    if not isinstance(p,str) or not isinstance(h,str) or not re.fullmatch("[a-f0-9]{64}",h) or len(p)>240:return False
    path=Path(p)
    if path.is_absolute() or ".." in path.parts:return False
    try:
        root=Path(base).resolve(strict=True)
        actual=(root/path).resolve(strict=True)
        return (root in actual.parents and actual.is_file() and
                64<=actual.stat().st_size<=5_000_000 and
                hashlib.sha256(actual.read_bytes()).hexdigest()==h)
    except (OSError,ValueError,RuntimeError):return False
def grade(result,*,exact_build_sha256=None,reviewer_verified=False,
          criteria_evidence=None,evidence_root=None):
    if not isinstance(result,dict) or not isinstance(result.get("blockers"),list):
        raise ValueError("QUALITY_REPORT_MISSING")
    if any(not isinstance(x,dict) or not isinstance(x.get("code"),str) for x in result["blockers"]):
        raise ValueError("QUALITY_BLOCKER_INVALID")
    codes={x["code"] for x in result["blockers"]}
    evidence=criteria_evidence if isinstance(criteria_evidence,dict) else {}
    items={}
    for key,c in CRITERIA.items():
        has=file_matches(evidence_root,evidence.get(key))
        conflict=(any("P0_PROOF_MISSING:"+p in codes for p in LINK[c["group"]])
                  or SPECIAL.get(key) in codes)
        pts=10 if has and not conflict else 0
        items[key]={"criterion":c["name"],"group":c["group"],"maximum_points":10,
                    "documentary_points":pts,"independent_quality_points":None,
                    "evidence_status":"HASH_CHECK_ONLY" if pts else "MISSING_OR_BLOCKED"}
    earned=sum(x["documentary_points"] for x in items.values())
    outstanding=sorted(codes-PENDING)
    valid_hash=bool(isinstance(exact_build_sha256,str) and re.fullmatch("[a-f0-9]{64}",exact_build_sha256))
    result_card={
      "schema":SCHEMA,"family_id":result.get("family_id"),"required_points":1000,
      "criteria_count":100,"points_per_criterion":10,"criteria":items,
      "documentary_evidence_points":earned,"documentary_evidence_gap":1000-earned,
      "product_quality_points":None,"professionally_validated_criteria":0,
      "quality_points_status":"NOT_INDEPENDENTLY_EVALUATED",
      "critical_defect_count":len(outstanding),
      "specialist_gates_missing":[c for c in outstanding if c.startswith("P0_DOMAIN_SPECIALIST_PROOF_MISSING:")],
      "all_100_criteria_required":True,"critical_defects_must_equal_zero":True,
      "artifact_sha256":exact_build_sha256 if valid_hash else None,
      "independent_reviewer_authentication":False,"technical_qa_is_separate":True,
      "professional_quality_1000_passed":False,"world_leading_quality_certified":False,
      "release_allowed":False,
      "disposition":"NEEDS_INDEPENDENT_EXPERT_ASSESSMENT" if earned==1000 and not outstanding else "RETURN_TO_PRODUCTION_REWORK"}
    require_no_false_certification(result_card)
    return result_card
def require_no_false_certification(c):
    if (c.get("schema")!=SCHEMA or c.get("required_points")!=1000 or
        c.get("criteria_count")!=100 or c.get("points_per_criterion")!=10 or
        set(c.get("criteria",{}))!=set(CRITERIA) or
        c.get("product_quality_points") is not None or
        c.get("professional_quality_1000_passed") is not False or
        c.get("release_allowed") is not False or
        c.get("independent_reviewer_authentication") is not False):
        raise RuntimeError("INVALID_1000_QUALITY_SCORE")
    pts=0
    for id,item in c["criteria"].items():
        if (item.get("maximum_points")!=10 or item.get("documentary_points") not in (0,10)
            or item.get("independent_quality_points") is not None
            or item.get("criterion")!=CRITERIA[id]["name"]):
            raise RuntimeError("INVALID_10_POINT_CRITERION")
        pts+=item["documentary_points"]
    if pts!=c.get("documentary_evidence_points") or c.get("documentary_evidence_gap")!=1000-pts:
        raise RuntimeError("SCORE_ADDITION_MISMATCH")
    return True
