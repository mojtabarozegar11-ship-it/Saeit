#!/usr/bin/env python3
"""World-class product excellence **REJECTION** gate for ALL 40 factory families.

Scope: reliable detection of missing/unverifiable world-class quality evidence.
Not capable of proving a product is #1 worldwide; cryptographic file hashes
prove identity, not reviewer independence, truth, creativity, or market impact.
Never grants a sales permit. Existing technical unit-test 'PASS' is not
commercial / scholarly / artistic / premium product acceptance.
"""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "saeit.factory.global-premium-quality.v1"
REGISTRY_SCHEMA = "saeit.factory.family-registry.v1"
MAX_EVIDENCE = 5_000_000
SHA = re.compile(r"^[a-f0-9]{64}$")
# Individually mandatory, not averaged; a beautiful but unoriginal product fails.
DIMENSIONS = (
    "global_comparative_advantage",
    "originality_and_non_derivativeness",
    "verified_innovation",
    "technology_and_technical_excellence",
    "domain_depth_and_accuracy",
    "user_customer_value",
    "independent_expert_review",
    "real_world_performance_accessibility",
    "security_ethics_regulatory_safety",
    "legal_rights_and_provenance",
    "distribution_support_reliability",
    "independent_adversarial_testing",
)
MIN_CURRENT_COMPARATORS = 5
MAX_BENCHMARK_AGE_DAYS = 540
REQUIRED_INNOVATIONS = 2
NEEDS_HUMAN = ("real_competitor_comparison", "expert_reviews", "real_users",
               "innovation_prototypes", "factual_validity", "rights_clearance")

def sha256(raw):
    return hashlib.sha256(raw).hexdigest()

def blocker(code,category,action,details=""):
    return {"code":code,"severity":"P0","category":category,
            "required_fix":action,"details":str(details)[:220]}

def evidence_file(root,item):
    """File integrity *only*: no permission to claim the evidence is authentic."""
    if not isinstance(item,dict):return False
    name=item.get("path")
    digest=item.get("sha256")
    if not isinstance(name,str) or not isinstance(digest,str) or not SHA.fullmatch(digest):
        return False
    path=Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts or len(name)>240:return False
    try:
        # Resolve the whole path: checking only the final component would
        # follow a symlinked parent into another product or outside the VPS.
        private_root=Path(root)
        if private_root.is_symlink():return False
        private_root=private_root.resolve(strict=True)
        real=(private_root/path).resolve(strict=True)
        if private_root not in real.parents or not real.is_file():return False
        # An internal symlink is still not immutable product-owned evidence.
        if any((private_root/Path(*path.parts[:i])).is_symlink()
               for i in range(1,len(path.parts)+1)):return False
        if not 64<=real.stat().st_size<=MAX_EVIDENCE:return False
        return sha256(real.read_bytes())==digest
    except (OSError,ValueError,RuntimeError):
        return False

def load_registry(path):
    path=Path(path)
    data=json.loads(path.read_text(encoding="utf-8"))
    assert data.get("schema")==REGISTRY_SCHEMA
    entries=data["profiles"]
    assert isinstance(entries,list) and len(entries)==40
    by_id={p["id"]:p for p in entries}
    assert set(by_id)=={"F%02d"%i for i in range(1,41)}
    for item in entries:
        assert isinstance(item.get("specialist_tests"),list) and item["specialist_tests"]
        assert isinstance(item.get("deliverables"),list) and item["deliverables"]
    return by_id

def parse_iso_day(value):
    try:
        if not isinstance(value,str):return None
        got=date.fromisoformat(value)
        if got>date.today() or (date.today()-got).days>MAX_BENCHMARK_AGE_DAYS:
            return None
        return got
    except ValueError:
        return None

def inspect(data,root,registry,production_manifest=None):
    data=data if isinstance(data,dict) else {}
    issues=[]
    family=data.get("family_id")
    profile=registry.get(family)
    if not profile:
        issues.append(blocker("P0_UNMAPPED_PRODUCT_FAMILY","admission",
                       "Map this real recipe to one of the 40 exact family IDs using verified identity; never infer category from marketing copy."))
    artifact=data.get("artifact")
    if not evidence_file(root,artifact):
        issues.append(blocker("P0_ARTIFACT_UNVERIFIED","integrity",
                       "Provide the exact product build with version-bound actual byte checksum and reproducible technical QA."))
    if isinstance(production_manifest,dict):
        if production_manifest.get("qa_status")!="passed":
            issues.append(blocker("P0_TECHNICAL_QA_NOT_PASSED","technical",
                           "Resolve measured technical tests before professional assessment."))
        claimed=(artifact or {}).get("sha256") if isinstance(artifact,dict) else None
        if claimed!=production_manifest.get("artifact_sha256"):
            issues.append(blocker("P0_BUILD_HASH_NOT_MATCHING_MANIFEST","integrity",
                           "Bind independent quality report to the exact current manufacturing ZIP, not a stale artifact."))
        if production_manifest.get("commercial_status") not in (
                "private_internal_qa_pass_not_published","private_rework_not_published"):
            issues.append(blocker("P0_UNSAFE_COMMERCIAL_STATE","safety",
                           "Keep premium quality pending and distribution disabled."))
    proof=data.get("evidence")
    proof=proof if isinstance(proof,dict) else {}
    for d in DIMENSIONS:
        if not evidence_file(root,proof.get(d)):
            issues.append(blocker("P0_PROOF_MISSING:"+d,d,
                           "Provide item-specific, independently verifiable methodology, results, limitations and artifact-bound proof."))
    specialized=profile.get("specialist_tests",[]) if profile else []
    for test in specialized:
        if not isinstance(test,str) or not evidence_file(root,proof.get("specialist:"+test)):
            issues.append(blocker("P0_DOMAIN_SPECIALIST_PROOF_MISSING:"+str(test),"domain",
                           "Perform this family-specific technical/creative/scientific acceptance test with independent evidence."))
    competitors=data.get("comparators")
    competitors=competitors if isinstance(competitors,list) else []
    legitimate={}
    for item in competitors:
        if not isinstance(item,dict):continue
        name=item.get("name")
        if not isinstance(name,str) or not 3<=len(name.strip())<=150:continue
        if parse_iso_day(item.get("benchmark_date")) is None:continue
        if not evidence_file(root,item.get("benchmark_evidence")):continue
        legitimate[name.strip().casefold()]=item
    if len(legitimate)<MIN_CURRENT_COMPARATORS:
        issues.append(blocker("P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING","world_class",
                       "Compare with at least five distinct current leading comparators from the same exact market, using dated independently reproducible data.",
                       str(len(legitimate))+" structurally verifiable current comparators"))
    advantage=data.get("quantified_advantage")
    if not isinstance(advantage,dict) or not advantage.get("methodology") or not advantage.get("metric_unit") or not evidence_file(root,advantage.get("independent_measurement")):
        issues.append(blocker("P0_MEASURED_SUPERIORITY_UNVERIFIED","world_class",
                       "Provide independent, task-relevant benchmark showing material measurable improvement versus top competitors, including uncertainty and limitations."))
    innovations=data.get("innovations")
    innovations=innovations if isinstance(innovations,list) else []
    ids=set()
    for item in innovations:
        if not isinstance(item,dict):continue
        ident=item.get("id")
        if not isinstance(ident,str) or not re.fullmatch(r"[A-Za-z0-9_-]{4,80}",ident):continue
        if not evidence_file(root,item.get("working_prototype")):continue
        if not evidence_file(root,item.get("novelty_comparison")):continue
        ids.add(ident)
    if len(ids)<REQUIRED_INNOVATIONS:
        issues.append(blocker("P0_ORIGINAL_INNOVATIONS_UNPROVEN","innovation",
                      "Demonstrate at least two materially different, usable innovations with working prototype, original contribution and independent comparison."))
    if data.get("positioning") in ("new","new_original","brand_new") and (
            not parse_iso_day(data.get("new_product_announcement_date"))):
        issues.append(blocker("P0_NEW_PRODUCT_FRESHNESS_UNVERIFIED","novelty",
                     "Prove release chronology and present-day customer relevance; old/derivative content is not new merely because it is repackaged."))
    if data.get("self_certified_number_one") is True or data.get("self_approved") is True:
        issues.append(blocker("P0_SELF_CERTIFICATION_NOT_ACCEPTED","integrity",
                     "Marketing assertions, declarations and automated scores cannot certify #1 global product quality."))
    # Neither a SHA nor a field saying 'reviewed' authenticates a real scientist,
    # buyer, benchmark auditor or rights owner. Reserved for trusted external gate.
    issues.append(blocker("P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED","independent_review",
                  "Obtain external accountable reviewers and authenticated artifact/version-bound attestations; automation cannot self-sign."))
    issues.append(blocker("P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED","global_rank",
                  "No scientifically defensible claim of global #1 can be made without verified, repeatable evidence across the relevant market."))
    return {
        "schema":SCHEMA,
        "family_id":family,
        "family_name":profile.get("name_fa") if profile else None,
        "technical_test_passed":bool(production_manifest and production_manifest.get("qa_status")=="passed"),
        "technical_success_is_not_premium_approval":True,
        "quality_verdict":"BLOCKED_REWORK_REQUIRED",
        "quality_permit":False,
        "commercially_approved":False,
        "public_release_allowed":False,
        "world_number_one_verified":False,
        "independent_external_authentication":False,
        "global_comparators_structurally_verified":len(legitimate),
        "innovations_with_integrity_evidence":len(ids),
        "dimensions":list(DIMENSIONS),
        "family_specialist_tests":specialized,
        "blocker_count":len(issues),
        "blockers":issues,
        "note":"A valid SHA identifies bytes, not factual truth or reviewer independence; all items are preflight rejection findings, not a verified positive quality rating.",
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--registry",required=True)
    parser.add_argument("--candidate",required=True)
    parser.add_argument("--evidence-root",required=True)
    parser.add_argument("--report",required=True)
    parser.add_argument("--enforce-public-release",action="store_true")
    args=parser.parse_args()
    policy=load_registry(args.registry)
    doc=json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    result=inspect(doc,Path(args.evidence_root),policy)
    out=Path(args.report)
    if out.exists() or out.is_symlink():raise ValueError("NO_OVERWRITE_EXISTING_REPORT")
    out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print("GLOBAL_PREMIUM_QA_FAMILY="+str(result["family_id"]))
    print("GLOBAL_PREMIUM_QA_BLOCKER_COUNT="+str(result["blocker_count"]))
    print("GLOBAL_PREMIUM_QA_RESULT="+result["quality_verdict"])
    print("GLOBAL_PREMIUM_QA_WORLD_NUMBER_ONE_CLAIM=false")
    if args.enforce_public_release and not result["public_release_allowed"]:
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
