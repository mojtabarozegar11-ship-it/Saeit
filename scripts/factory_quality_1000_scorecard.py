#!/usr/bin/env python3
"""Noncompensatory 1000/1000 quality standard for every registered product family.

Numbers quantify only HASH-CHECKED DOCUMENTATION COVERAGE; an uploaded text
or score never validates its scientific truth, human author, actual customer
value or originality. A professional 1000/1000 certificate is unassessed until
an independent and authenticated examiner judges the exact build version.

No score can auto-enable sales, remove a P0, or declare #1 in the world.
"""
from pathlib import Path

SCHEMA="saeit.factory.quality-1000.v1"
TARGET=1000
# Explicit weighting, invariant across 40 families.
WEIGHTS={
 "global_comparative_advantage":120,
 "originality_and_non_derivativeness":100,
 "verified_innovation":120,
 "technology_and_technical_excellence":100,
 "domain_depth_and_accuracy":100,
 "user_customer_value":100,
 "independent_expert_review":80,
 "real_world_performance_accessibility":70,
 "security_ethics_regulatory_safety":70,
 "legal_rights_and_provenance":50,
 "distribution_support_reliability":40,
 "independent_adversarial_testing":50,
}
assert sum(WEIGHTS.values())==TARGET
PENDING_CODES={
 "P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED",
 "P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED",
}
EXTRA_REQUIREMENTS={
 "global_comparative_advantage":{
   "P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING",
   "P0_MEASURED_SUPERIORITY_UNVERIFIED"},
 "originality_and_non_derivativeness":{"P0_ORIGINAL_INNOVATIONS_UNPROVEN"},
 "verified_innovation":{"P0_ORIGINAL_INNOVATIONS_UNPROVEN"},
}

def grade(result, *, exact_build_sha256=None, reviewer_verified=False):
    """Grade a real result from global premium gate; no metadata self-attests.

    reviewer_verified is informational only. Even True cannot stand in for an
    authorized cryptographic and independently confirmed signed assessment.
    """
    if not isinstance(result,dict):
        raise TypeError("QUALITY_REPORT_REQUIRED")
    reasons=result.get("blockers")
    if not isinstance(reasons,list) or any(not isinstance(x,dict) for x in reasons):
        raise ValueError("QUALITY_REPORT_BLOCKERS_INVALID")
    present={x.get("code") for x in reasons}
    marks={}
    for pillar,maximum in WEIGHTS.items():
        required_evidence="P0_PROOF_MISSING:"+pillar
        supplementary=EXTRA_REQUIREMENTS.get(pillar,set())
        eligible=required_evidence not in present and not (supplementary & present)
        marks[pillar]={
            "maximum_points":maximum,
            "documentary_points":maximum if eligible else 0,
            "documentary_evidence_status":"HASH_CHECKED_NOT_EXPERT_VERIFIED" if eligible else "INSUFFICIENT",
            "professionally_validated_points":None,
            "noncompensatory":True,
        }
    documents=sum(item["documentary_points"] for item in marks.values())
    actual_defects=sorted(str(c) for c in present if c not in PENDING_CODES)
    specialist_missing=sorted(str(c) for c in present if isinstance(c,str)
                                  and c.startswith("P0_DOMAIN_SPECIALIST_PROOF_MISSING:"))
    genuine_sha=(isinstance(exact_build_sha256,str) and len(exact_build_sha256)==64
                 and all(c in "0123456789abcdef" for c in exact_build_sha256))
    return {
      "schema":SCHEMA,
      "family_id":result.get("family_id"),
      "required_points":TARGET,
      "pillars":marks,
      "documentary_evidence_points":documents,
      "documentary_evidence_gap":TARGET-documents,
      "product_quality_points":None,
      "quality_points_status":"NOT_INDEPENDENTLY_EVALUATED",
      "world_leading_quality_certified":False,
      "professional_quality_1000_passed":False,
      "all_pillars_must_pass":True,
      "critical_defects_must_equal_zero":True,
      "critical_defect_count":len(actual_defects),
      "specialist_gates_missing":specialist_missing,
      "technical_qa_is_separate":True,
      "artifact_sha256":exact_build_sha256 if genuine_sha else None,
      "exact_artifact_hash_verified":bool(genuine_sha and "P0_ARTIFACT_UNVERIFIED" not in present
                                          and "P0_BUILD_HASH_NOT_MATCHING_MANIFEST" not in present),
      "independent_reviewer_authentication":False,
      "self_attested_review_cannot_override_quality":True,
      "release_allowed":False,
      "release_gate_policy":"Score=1000/1000 from independently authenticated domain reviewers AND zero P0 AND all family-specific gates AND actual owner authorization; otherwise BLOCKED.",
      "disposition":("NEEDS_INDEPENDENT_EXPERT_ASSESSMENT" if documents==TARGET and not actual_defects
                     else "RETURN_TO_PRODUCTION_REWORK"),
    }

def require_no_false_certification(card):
    if (card.get("required_points")!=TARGET
            or set(card.get("pillars",{}))!=set(WEIGHTS)
            or sum(p["maximum_points"] for p in card["pillars"].values())!=TARGET
            or card.get("release_allowed") is not False
            or card.get("professional_quality_1000_passed") is not False):
        raise RuntimeError("QUALITY_1000_FAIL_CLOSED_POLICY_VIOLATION")
    earned=sum(p["documentary_points"] for p in card["pillars"].values())
    if earned!=card["documentary_evidence_points"] or earned>TARGET or earned<0:
        raise RuntimeError("QUALITY_1000_SCORE_INTEGRITY")
    if card.get("product_quality_points") is not None:
        raise RuntimeError("UNAUTHENTICATED_PRODUCT_QUALITY_SCORE")
    return True
