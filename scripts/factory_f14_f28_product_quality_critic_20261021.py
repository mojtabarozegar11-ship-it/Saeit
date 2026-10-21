#!/usr/bin/env python3
"""Product-quality discriminator (NOT another 1000x arithmetic success counter).

Separates technical correctness from science-grade domain adequacy, usable
interaction and independently substantiated buyer value. Deterministic,
source-pinned audits give explicit BLOCKED reasons. A human expert approval
cannot be created by this tool or by self-reported test counts.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess

SCHEMA="saeit.factory.product-critical-review.v2"
SOURCE={"F14":"fab699b275f04ce69912c56e7d0a881ef9ee2d8d",
        "F28":"458052d5663102f0cc896047e1cad171bb80ef24"}
RELEASE_FIELDS=("specialist_approved","science_grade_verified","commercial_approved",
                "rights_cleared","real_device_qa_verified","human_review_complete",
                "owner_publication_authorized","publicly_published")

class Inputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.attrs={}
    def handle_starttag(self,tag,attrs):
        if tag!="input":
            return
        a=dict(attrs)
        if a.get("id"):
            self.ids.append(a["id"])
            self.attrs[a["id"]]=a

def source_pin(root,family):
    assert root.is_dir() and not root.is_symlink(),family
    commit=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],
                                   text=True,timeout=15).strip()
    assert commit==SOURCE[family], "SOURCE_UNPINNED:"+family
    return commit

def read(root,relative):
    path=root/relative
    assert path.is_file() and not path.is_symlink(),relative
    return path.read_text(encoding="utf-8")

def issue(code,severity,finding,action,category,source):
    assert severity in ("P0","P1","P2")
    return dict(code=code,severity=severity,finding=finding,required_action=action,
                category=category,evidence=source)

def audit_f28(root):
    path="product_recipes/greenhouse_crop_margin/greenhouse_margin_lab_pilot.html"
    html=read(root,path)
    calculator=read(root,"product_recipes/greenhouse_crop_margin/calculator.py")
    doc=read(root,"product_recipes/greenhouse_crop_margin/COMMERCIAL_PILOT.md")
    parser=Inputs()
    parser.feed(html)
    seen=set(parser.ids)
    core={"area","yield","price","variable","fixed","reject","currency"}
    problems=[]
    if not core.issubset(seen):
        problems.append(issue("F28_P0_MISSING_CORE_INPUTS","P0",
            "Calculator core inputs are missing.","Restore input contract and recertify.",
            "functional_correctness",path))
    if not any(any(part in field.lower() for part in
                   ("crop","species","cultivar","cycle","harvest_date","season"))
               for field in seen):
        problems.append(issue("F28_P0_NO_CROP_OR_SEASON_MODEL","P0",
            "Actual input form has no crop/variety/season/growth-cycle specification.",
            "Develop validated crop-specific and season-specific assumptions and expose parameters.",
            "domain_adequacy",path))
    missing=[c for c in ("water","energy","labor","climate") if not any(
        c in field.lower() for field in seen)]
    if missing:
        problems.append(issue("F28_P0_RESOURCE_COST_DRIVERS_MISSING","P0",
            "Inputs omit explicit drivers: "+", ".join(missing)+". Cost totals alone cannot validate feasibility.",
            "Model actual water, energy, labor and climate drivers, with units and source provenance.",
            "domain_adequacy",path))
    if "nine scenario stress tests" in html.lower() and not re.search(
        r"id=[\"'](?:uncertainty_distribution|simulations|confidence_interval)[\"']",html,re.I):
        problems.append(issue("F28_P1_NINE_FIXED_SCENARIOS_NOT_RISK_MODEL","P1",
            "Three-by-three handpicked scenarios do not establish yield/price uncertainty or probabilistic risk.",
            "Introduce documented risk assumptions, uncertainty propagation and validation, not just random trials.",
            "scientific_method",path))
    if "not market data" in doc.lower() or "synthetic and not market data" in doc.lower():
        problems.append(issue("F28_P0_UNCALIBRATED_MARKET_ASSUMPTIONS","P0",
            "The recipe itself says example inputs are synthetic and not market data.",
            "Provide traceable field/market observations, out-of-sample error analysis and specialist sign-off.",
            "external_validity","product_recipes/greenhouse_crop_margin/COMMERCIAL_PILOT.md"))
    if "results are scenarios, not guaranteed production" in calculator.lower():
        problems.append(issue("F28_P1_LIMITED_PREDICTIVE_SCOPE","P1",
            "Reference engine explicitly disclaims prediction of actual production.",
            "Demonstrate benchmark accuracy and quantify the limits of intended customer decisions.",
            "customer_value","product_recipes/greenhouse_crop_margin/calculator.py"))
    problems.extend([
        issue("F28_P0_SCHOLARLY_VALIDATION_NOT_VERIFIED","P0",
            "No independently authenticated scientific-method/peer-review approval exists in this audit.",
            "Obtain expert domain review with cited methods, reproducible data and validity limits.",
            "independent_human_validation","independent review not present"),
        issue("F28_P0_CUSTOMER_DECISION_UTILITY_UNPROVEN","P0",
            "Passing deterministic arithmetic checks cannot show usefulness to greenhouse operators.",
            "Run witnessed real-user decision tasks, compare alternative methods and report error cases.",
            "real_customer_validation","real buyer task evidence not present"),
    ])
    return dict(family="F28",name="Greenhouse Margin Lab",
        assessed_product_type="agriculture-economics-decision-tool",
        source_file_sha256=hashlib.sha256(html.encode()).hexdigest(),
        observed_input_ids=parser.ids,
        observed_input_count=len(parser.ids),
        observed_scenario_count=9,
        advanced_scholarly_quality_verified=False,
        issues=problems)

def keyboard_probe(root,probe_script):
    engine=root/"product_recipes/rootline_bloom_defense/engine.js"
    game=root/"product_recipes/rootline_bloom_defense/game.js"
    p=subprocess.run(["node",str(probe_script),str(engine),str(game)],
                     text=True,capture_output=True,timeout=20)
    if p.returncode!=0:
        raise RuntimeError("Interaction probe could not execute: "+p.stderr[-1200:])
    result=json.loads(p.stdout)
    assert result["detection_positive_control"]=="PASS"
    assert result["observed_successful_pointer_placements"]>=1
    return result

def audit_f14(root,probe_script):
    page="product_recipes/rootline_bloom_defense/index.html"
    html=read(root,page)
    engine=read(root,"product_recipes/rootline_bloom_defense/engine.js")
    controller=read(root,"product_recipes/rootline_bloom_defense/game.js")
    observation=keyboard_probe(root,probe_script)
    problems=[]
    if not observation["keyboard_planting_supported"]:
        problems.append(issue("F14_P0_KEYBOARD_PLANTING_MISSING","P0",
            "Runtime replay started a real game and placed via pointer, but not via keyboard.",
            "Implement focusable grid navigation, position announcements, Enter/Space placement and keyboard tests.",
            "functional_accessibility","runtime_controller_probe"))
    if not re.search(r'<section class="status"[^>]*aria-live',html):
        problems.append(issue("F14_P1_LIVE_BATTLE_STATE_NOT_SCREENREADER_ANNOUNCED","P1",
            "The board has a static canvas label; no ARIA live battle-state region on status panel.",
            "Expose lane/cell/enemy/action state through accessible nonvisual interaction.",
            "accessibility",page))
    if ("const ROWS=5, COLS=8" in engine and "const kinds" not in engine
        and "beetle" in engine):
        problems.append(issue("F14_P1_LIMITED_PROTOTYPE_SCOPE","P1",
            "Five-lane prototype mechanics do not independently demonstrate professional game depth.",
            "Conduct independent gameplay review with multi-session balancing and content-depth acceptance.",
            "game_design","product_recipes/rootline_bloom_defense/engine.js"))
    quality_doc=read(root,"product_recipes/rootline_bloom_defense/COMMERCIAL_PILOT.md")
    if ("competitor novelty matrix" not in quality_doc.lower()
            or "novel mechanics independently validated" not in quality_doc.lower()):
        problems.append(issue("F14_P0_GAME_ORIGINALITY_NOT_PROVEN","P0",
            "Real gameplay may work, but its core strategy loop has no dated independent competitor/novelty comparison.",
            "Compare multiple modern and legacy competitors (including mature 2012 base-building templates), prototype two testable unique gameplay mechanisms, and obtain independent player validation.",
            "modern_game_innovation","product_recipes/rootline_bloom_defense/COMMERCIAL_PILOT.md"))
    if "private pilot" in html.lower() or "private technical" in html.lower():
        problems.append(issue("F14_P1_PROTOTYPE_NOT_RELEASE_CONTENT","P1",
            "Product labels itself private or prototype; product-market acceptance is absent.",
            "Document the commercial audience and deliver a reviewed release candidate with screenshots and builds.",
            "product_completeness",page))
    problems.extend([
        issue("F14_P0_PLAYER_PLAYTESTS_UNVERIFIED","P0",
            "Automated state tests do not measure enjoyment, clarity, level pacing or retention.",
            "Witness independent player sessions, capture friction and balance changes, retest.",
            "human_playability","user playtest records not verified"),
        issue("F14_P0_REAL_DEVICE_QUALITY_UNVERIFIED","P0",
            "No independently verified Android/iOS/mobile performance and touch/visibility trial.",
            "Capture real device screen recordings, frametimes, battery/heat checks, crash rates and device matrix.",
            "device_compatibility","real device QA receipts not verified"),
        issue("F14_P0_INDEPENDENT_VISUAL_DESIGN_REVIEW_MISSING","P0",
            "Code and vectors alone cannot certify game art, animation quality or visual appeal.",
            "Have an independent game artist/designer evaluate rendered visuals and documented revisions.",
            "visual_professionalism","human visual QA receipt not verified"),
    ])
    return dict(family="F14",name="ROOTLINE Bloom Defense",
        assessed_product_type="tactical-browser-game",
        source_file_sha256=hashlib.sha256(html.encode()).hexdigest(),
        accessibility_runtime_probe=observation,
        observed_plant_types=3,observed_lanes=5,
        professionally_playtested=False,
        issues=problems)

def assess(f14,f28,probe):
    source_pin(f14,"F14")
    source_pin(f28,"F28")
    assessments=[audit_f14(f14,probe),audit_f28(f28)]
    generic=[
      issue("ALL_P0_ITEMIZED_COMMERCIAL_RIGHTS_UNVERIFIED","P0",
          "No authenticated item-by-item commercial redistribution clearance was supplied.",
          "Complete asset/license/ownership chain and independent rights verification.",
          "legal_gate","not independently cleared"),
      issue("ALL_P0_OWNER_RELEASE_APPROVAL_ABSENT","P0",
          "No authenticated owner approval for this specific publishable version.",
          "Obtain explicit version-bound owner approval after independent evaluation.",
          "owner_gate","approval not verified"),
    ]
    for a in assessments:
        a["issues"].extend(generic)
        a["blocking_issue_count"]=sum(x["severity"] in ("P0","P1") for x in a["issues"])
        a["quality_verdict"]="BLOCKED_REWORK_REQUIRED"
        a["independent_specialist_verified"]=False
        a["commercial_ready"]=False
    report={
        "schema":SCHEMA,"source_commits":SOURCE,
        "assessments":assessments,
        "aggregate_product_quality_verdict":"BLOCKED_REWORK_REQUIRED",
        "technical_suite_green_does_not_imply_quality":True,
        "release_authorized":False,
        "legal_review_and_human_gate_outstanding":True,
        "automated_detection_scope":"code/interaction/feature gaps and missing independently verified evidence; not a subjective quality score",
        "never_auto_approve_from_test_count":True,
    }
    report.update({k:False for k in RELEASE_FIELDS})
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--f14",required=True)
    ap.add_argument("--f28",required=True)
    ap.add_argument("--probe",default="scripts/factory_f14_keyboard_runtime_probe_20261021.js")
    ap.add_argument("--report",required=True)
    ap.add_argument("--enforce",action="store_true",
                    help="Intentionally fail release gate if products remain blocked")
    opt=ap.parse_args()
    r=assess(Path(opt.f14),Path(opt.f28),Path(opt.probe))
    dest=Path(opt.report)
    dest.write_text(json.dumps(r,indent=2,ensure_ascii=False,sort_keys=True)+"\n",
                    encoding="utf-8")
    for p in r["assessments"]:
        print("FACTORY_PRODUCT_QUALITY_FAMILY="+p["family"])
        print("FACTORY_PRODUCT_QUALITY_VERDICT="+p["quality_verdict"])
        for finding in p["issues"]:
            print("QUALITY_BLOCKER="+finding["code"]+" "+finding["finding"])
    print("FACTORY_PRODUCT_QUALITY_RELEASE_ALLOWED=0")
    if opt.enforce:
        raise SystemExit(2)

if __name__=="__main__":
    main()
