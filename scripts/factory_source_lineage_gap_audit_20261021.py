#!/usr/bin/env python3
"""Read-only, bounded analysis of real QA workorders and source-provenance gaps.

Never takes a ZIP for its source or fabricates a production adapter. Source paths
are inspected only in explicit allowlisted, non-symlink recipe directories.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

SKU = re.compile(r"^[a-z][a-z0-9_]{1,65}$")
SHA = re.compile(r"^[0-9a-f]{64}$")

def check_file(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("UNTRUSTED_RECEIPT")
    value=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(value,dict):
        raise ValueError("INVALID_RECEIPT")
    return value

def source_state(path):
    if path.is_symlink(): return "unsafe_symlink"
    if not path.is_dir(): return "absent"
    if not (path/"README.md").is_file() or (path/"README.md").is_symlink():
        return "no_readme"
    tests=any(p.is_file() and not p.is_symlink() for p in path.glob("test_*.py"))
    return "buildable_recipe" if tests else "missing_recipe_tests"

def analyze(factory,roots):
    factory=Path(factory)
    if factory.is_symlink() or not factory.is_dir():
        raise ValueError("UNSAFE_FACTORY_ROOT")
    if not 1<=len(roots)<=8:
        raise ValueError("SOURCE_ROOT_LIMIT")
    roots=[Path(x) for x in roots]
    for root in roots:
        if root.is_symlink():raise ValueError("SOURCE_ROOT_SYMLINK")
    if len({str(x.resolve()) for x in roots})!=len(roots):
        raise ValueError("DUPLICATED_SOURCE_ROOT")
    workorders=factory/"quality-excellence"/"production-workorders"
    if workorders.is_symlink() or not workorders.is_dir():
        raise ValueError("QA_WORKORDERS_NOT_PRESENT")
    counts=Counter();rows=[];roots_info=[{"slot":i,"exists":p.is_dir()} for i,p in enumerate(roots)]
    for folder in sorted(workorders.iterdir()):
        if not folder.is_dir() or folder.is_symlink() or not SKU.fullmatch(folder.name):
            continue
        name=folder.name
        try:
            workorder=check_file(folder/"current.json")
            if workorder.get("schema")!="saeit.factory.production-rework-order.v1" or workorder.get("recipe")!=name:
                raise ValueError("UNBOUND_WORKORDER")
            receipt=workorder.get("source_quality_receipt_sha256")
            if not isinstance(receipt,str) or not SHA.fullmatch(receipt):
                raise ValueError("UNBOUND_QUALITY_HASH")
            candidate_paths=[source_state(root/name) for root in roots]
            matches=[i for i,state in enumerate(candidate_paths) if state=="buildable_recipe"]
            orig=factory/"digital-products"/name/"manufacturing_manifest.json"
            manifest=check_file(orig) if orig.is_file() else {}
            issues=workorder.get("unresolved_technical_or_domain_defects") or []
            if not isinstance(issues,list):raise ValueError("INVALID_QA_DEFECT_CODES")
            finding={
                "recipe":name,
                "family_id":manifest.get("family_id") if isinstance(manifest.get("family_id"),str) else None,
                "source_slots":matches,
                "source_states":candidate_paths,
                "manifest_source_hash_present":isinstance(manifest.get("source_sha256"),str) and bool(SHA.fullmatch(manifest["source_sha256"])),
                "manifest_artifact_hash_present":isinstance(manifest.get("artifact_sha256"),str) and bool(SHA.fullmatch(manifest["artifact_sha256"])),
                "technical_qa_passed":manifest.get("qa_status")=="passed",
                "defect_codes":sorted({str(x)[:100] for x in issues if isinstance(x,str)})[:12],
                "expected_documentary_groups":workorder.get("missing_documentary_group_count"),
            }
            if len(matches)==1:
                disposition="ready_for_source_revision" if issues else "only_independent_criteria_missing"
            elif len(matches)>1:
                disposition="ambiguous_multiple_buildable_sources"
            else:
                disposition="missing_buildable_source"
            finding["source_disposition"]=disposition
            counts[disposition]+=1
            for state in candidate_paths:
                counts["root_state:"+state]+=1
            rows.append(finding)
        except (OSError,ValueError,TypeError,json.JSONDecodeError):
            counts["invalid_workorder"]+=1
    result={
        "schema":"saeit.factory.source-lineage-gap-readonly.v1",
        "observed_workorders":len(rows),
        "source_state_counts":dict(sorted(counts.items())),
        "source_roots":roots_info,
        "unresolved": [r for r in rows if r["source_disposition"]!="only_independent_criteria_missing"],
        "commercial_release_authorized":False,
        "manufacturing_data_modified":False,
        "professional_quality_bypassed":False
    }
    print("FACTORY_SOURCE_LINEAGE_GAP_AUDIT="+json.dumps(result,sort_keys=True,ensure_ascii=True))
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--recipe-root",action="append",required=True)
    args=p.parse_args()
    analyze(args.factory_private,args.recipe_root)
if __name__=="__main__":main()
