#!/usr/bin/env python3
"""Family-aware, fail-closed QUALITY preflight (never an automatic commercial approval).

Book F01 targets evidence and depth comparable in METHOD to a specialist
reference such as Kirklin/Barratt-Boyes, not its copyrighted text.
Game F14 rejects legacy/derivative designs sold as new, even if code works.
For remaining families no generic green PASS is possible without a dedicated rubric.
Unverifiable human reviews are NOT silently accepted as authenticated.
"""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "saeit.factory.reference-depth-and-game-novelty.v1"
CURRENT_YEAR = date.today().year
LEGACY_LOOP = frozenset(("base_build", "resource_collect", "troop_train",
                          "raid_attack", "clan_war", "upgrade_wait"))
FAMILIES = {"F%02d" % x for x in range(1, 41)}
RELEASE_GATES = (
    "independent_human_quality_review",
    "authentic_scientific_or_game_design_review",
    "real_user_utility_or_playtest",
    "rights_and_asset_provenance",
    "source_bound_versioned_signoff",
    "security_and_accessibility",
    "owner_approval_for_exact_release",
)
EVIDENCE_CRITICAL = {
    "F01": ("claim_to_reference_matrix", "independent_subject_expert_report",
            "fact_check_errata_log", "illustration_and_table_rights",
            "real_pdf_epub_accessibility", "safety_and_limitations",
            "chapter_technical_editorial_report"),
    "F14": ("independent_novelty_review", "comparator_analysis",
            "prototype_mechanic_demonstrations", "blind_player_sessions",
            "real_android_ios_performance", "accessibility_keyboard_screenreader",
            "age_appropriate_monetization_and_privacy"),
    "F28": ("domain_model_and_units", "independent_benchmark_dataset",
            "out_of_sample_model_error", "scientific_method_and_uncertainty",
            "subject_expert_validation", "real_buyer_decision_tasks"),
}
MIN_GAME_COMPARATORS = 3
MIN_VERIFIABLE_NOVEL_MECHANICS = 2
MIN_BOOK_PARTS = 5
MIN_BOOK_CHAPTERS = 20

def rejection(code,reason,action,kind="stop_ship"):
    return {"code":code,"severity":"P0" if kind=="stop_ship" else "P1",
            "finding":reason,"required_fix":action}

def sha256(blob):
    return hashlib.sha256(blob).hexdigest()

def file_evidence(root,item):
    # Hash attests same bytes, NOT actual truth, provenance or reviewer identity.
    if not isinstance(item,dict):
        return False
    rel=item.get("path");want=item.get("sha256")
    if not isinstance(rel,str) or len(rel)>200 or not isinstance(want,str):
        return False
    if not re.fullmatch(r"[0-9a-f]{64}",want):
        return False
    path=Path(rel)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return False
    candidate=root / path
    if not candidate.is_file() or candidate.is_symlink() or candidate.stat().st_size>5_000_000:
        return False
    return sha256(candidate.read_bytes())==want

def examine(candidate, root, policy_families=FAMILIES):
    if not isinstance(candidate,dict):
        candidate={}
    root=Path(root)
    family=candidate.get("family")
    issues=[]
    if family not in policy_families:
        issues.append(rejection("FAMILY_NOT_REGISTERED","Unknown or unsupported family.",
                                "Bind to a verified factory family ID."))
        return report(family,issues,{},candidate)
    intended=candidate.get("distribution_claim","new_original_commercial_product")
    proof=candidate.get("evidence") if isinstance(candidate.get("evidence"),dict) else {}
    required=EVIDENCE_CRITICAL.get(family)
    if required is None:
        issues.append(rejection("FAMILY_SPECIALIST_RUBRIC_NOT_IMPLEMENTED",
                                "No family-specific scientific/creative rubric exists.",
                                "Create a versioned, expert-validated rubric and adversarial tests for this family."))
        required=()
    coverage={}
    for name in required:
        valid=file_evidence(root,proof.get(name))
        coverage[name]=valid
        if not valid:
            issues.append(rejection("EVIDENCE_MISSING_OR_BAD_HASH:"+name,
                          "Independent item evidence absent, changed, or has an invalid SHA.",
                          "Supply actual traceable evidence bytes; validate provenance and reviewer identity."))
    if family=="F01":
        b=candidate.get("book") if isinstance(candidate.get("book"),dict) else {}
        parts=b.get("parts"); chapters=b.get("chapters")
        if not isinstance(parts,list) or len(set(map(str,parts)))<MIN_BOOK_PARTS:
            issues.append(rejection("BOOK_INSUFFICIENT_SYSTEMATIC_COVERAGE",
                           "Specialist reference lacks a demonstrated coherent multi-part scope map.",
                           "Define 5+ nonredundant major sections and peer-review coverage omissions."))
        if not isinstance(chapters,list) or len(chapters)<MIN_BOOK_CHAPTERS:
            issues.append(rejection("BOOK_REFERENCE_DEPTH_NOT_DEMONSTRATED",
                           "A full reference edition lacks a chapter-by-chapter deep specialist structure.",
                           "Build 20+ substantive expert-edited chapters, each mapped to claims and learning/clinical decisions."))
        else:
            for ch in chapters:
                if not isinstance(ch,dict) or not isinstance(ch.get("subject"),str) or not ch.get("subject", "").strip() or not isinstance(ch.get("citations"),list) or len(ch["citations"])<3 or not isinstance(ch.get("methods_and_limits"),str) or len(ch["methods_and_limits"].strip())<30:
                    issues.append(rejection("BOOK_CHAPTER_EVIDENCE_GAPS",
                                   "At least one chapter lacks sufficient traceable references, subject or methodological limits.",
                                   "Document every chapter's sources, methodology, uncertainty and section-specific expert review."))
                    break
        if b.get("type") in ("medical","clinical") and not b.get("patient_safety_review_verified"):
            issues.append(rejection("BOOK_CLINICAL_HARM_REVIEW_MISSING",
                           "Clinical material has no independently authenticated patient-safety review.",
                           "Require qualified clinical review of diagnostics, interventions, contraindications, and errors."))
        year=b.get("literature_reviewed_through_year")
        if not isinstance(year,int) or type(year) is bool or year<CURRENT_YEAR-2 or year>CURRENT_YEAR:
            issues.append(rejection("BOOK_LITERATURE_NOT_CURRENT",
                           "Literature update or its coverage through the last 2 years is undocumented.",
                           "Trace new guidelines, retractions, conflicting evidence and editorial cutoff date."))
        if not b.get("original_analysis_per_chapter"):
            issues.append(rejection("BOOK_COMPILATION_NOT_EXPERT_SYNTHESIS",
                           "Reference may compile generic content without critical expert synthesis.",
                           "Require independently assessed reasoning, controversies, comparative outcomes and original insight."))
    elif family=="F14":
        g=candidate.get("game") if isinstance(candidate.get("game"),dict) else {}
        release_year=g.get("original_release_year")
        if intended=="new_original_commercial_product" and (
            type(release_year) is not int or release_year<CURRENT_YEAR-2 or release_year>CURRENT_YEAR):
            issues.append(rejection("GAME_OLD_OR_UNPROVEN_NEW_RELEASE",
                            "Existing old release or undated product cannot be sold as a newly original game.",
                            "Provide independently validated new-product origin and chronology; legacy products need new positioning, not a new-game claim."))
        comparators=g.get("independent_comparators")
        if not isinstance(comparators,list) or len({
                str(x.get("identifier","")).casefold() for x in comparators if isinstance(x,dict) and x.get("identifier")
            })<MIN_GAME_COMPARATORS:
            issues.append(rejection("GAME_COMPETITOR_NOVELTY_COMPARISON_MISSING",
                           "No distinct comparison against 3 existing games and their core mechanics.",
                           "Produce a dated independent feature/mechanic overlap matrix covering at least 3 competitors."))
        innovations=g.get("original_playtested_mechanics")
        if not isinstance(innovations,list) or len({
                str(x.get("id","")) for x in innovations if isinstance(x,dict)
                and x.get("id") and x.get("running_prototype_sha256")
                and re.fullmatch(r"[0-9a-f]{64}",str(x.get("running_prototype_sha256"))) 
            })<MIN_VERIFIABLE_NOVEL_MECHANICS:
            issues.append(rejection("GAME_NO_VERIFIABLE_NOVEL_GAMEPLAY",
                           "No 2 independently testable, distinctive gameplay mechanics were identified.",
                           "Create and demonstrate 2 distinct mechanics and have players compare them blind against competition."))
        core=set(g.get("core_loop_tags",[])) if isinstance(g.get("core_loop_tags"),list) else set()
        if len(core & LEGACY_LOOP)>=4 and (
            not isinstance(innovations,list) or len(innovations)<MIN_VERIFIABLE_NOVEL_MECHANICS):
            issues.append(rejection("GAME_LEGACY_CLONE_MECHANICS",
                           "New product repeats a mature base/raid/resource/time-upgrade loop without substantial verified difference.",
                           "Reject derivative concept; prototype fundamentally new strategy and decision loops."))
        if not g.get("documented_2026_player_need"):
            issues.append(rejection("GAME_MODERN_PLAYER_VALUE_NOT_SHOWN",
                           "No evidence for current audience needs or player value distinct from mature competitors.",
                           "Conduct documented contemporary player discovery and usability sessions."))
        if not g.get("accessible_without_pointer"):
            issues.append(rejection("GAME_CONTROLS_INCOMPLETE",
                           "Full alternative input path and accessibility are not demonstrated.",
                           "Add and actually test keyboard/gamepad/touch alternatives where appropriate."))
    elif family=="F28":
        s=candidate.get("simulator") if isinstance(candidate.get("simulator"),dict) else {}
        for name in ("units_and_model","uncertainty","external_validation",
                     "decision_usefulness"):
            if s.get(name)!="independently_verified":
                issues.append(rejection("SIMULATOR_UNVERIFIED:"+name,
                               "Scientific model's "+name+" not independently validated.",
                               "Document tests, real datasets and specialist review for "+name+"."))
    # Product claims and review identity are not verifiable merely through metadata.
    if candidate.get("release_status") in ("approved","published","commercially_approved"):
        issues.append(rejection("SELF_DECLARED_APPROVAL_NOT_EVIDENCE",
                        "A self-declared approval cannot override missing independent gates.",
                        "Require authenticated external review and owner approval from trusted authority."))
    for k in RELEASE_GATES:
        if candidate.get("attested_"+k) is not True:
            issues.append(rejection("EXTERNAL_RELEASE_GATE_UNVERIFIED:"+k,
                "Independent release obligation has no authenticated completion evidence.",
                "Complete and independently authenticate "+k+"."))
    if family in EVIDENCE_CRITICAL:
        # External review must be authenticated outside this metadata-only preflight.
        issues.append(rejection("INDEPENDENT_HUMAN_AUTHENTICATION_PENDING",
              "Names, document hashes and self-attested reviewers cannot authenticate approval on their own.",
              "Have an authorized expert independently verify source facts and personally sign the exact artifact hash."))
    return report(family,issues,coverage,candidate)

def report(family,issues,coverage,candidate):
    seen=set()
    compact=[]
    for item in issues:
        if item["code"] not in seen:
            seen.add(item["code"])
            compact.append(item)
    return {
      "schema":SCHEMA,"family":family,
      "candidate_id":str(candidate.get("id") or "")[:120],
      "verdict":"BLOCKED_REWORK_REQUIRED" if compact else "NEEDS_AUTHENTICATED_INDEPENDENT_REVIEW",
      "blockers":compact,
      "critical_blocker_count":sum(x["severity"]=="P0" for x in compact),
      "evidence_hash_preflight":coverage,
      "external_human_verification_completed":False,
      "commercial_release_authorized":False,
      "publish_allowed":False,
      "doctoral_grade_certified":False,
      "professional_game_certified":False,
      "important_note":"Automated coverage/sha checks cannot verify scientific truth, genuine originality, expert identity or user enjoyment."
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",required=True)
    ap.add_argument("--evidence-root",required=True)
    ap.add_argument("--report",required=True)
    ap.add_argument("--enforce-commercial",action="store_true")
    a=ap.parse_args()
    target=Path(a.manifest)
    if target.is_file() and not target.is_symlink():
        data=json.loads(target.read_text(encoding="utf-8"))
    else:
        data={}
    result=examine(data,Path(a.evidence_root))
    Path(a.report).write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("FACTORY_NOVELTY_REFERENCE_VERDICT="+result["verdict"])
    print("FACTORY_NOVELTY_REFERENCE_BLOCKER_COUNT="+str(result["critical_blocker_count"]))
    for issue in result["blockers"]:
        print("FACTORY_DOMAIN_DEFECT="+issue["code"])
    print("FACTORY_AUTO_COMMERCIAL_APPROVAL=0")
    if a.enforce_commercial:
        raise SystemExit(2)

if __name__=="__main__":
    main()
