#!/usr/bin/env python3
"""Produce deterministic rework tasks from independent quality gate findings."""
import argparse
import json
from pathlib import Path
from quality1000_evidence_gate import validate

OWNERS = {
 "functionality":"functional-builder", "security":"security-reviewer",
 "performance":"performance-builder", "mobile":"mobile-builder",
 "originality":"originality-reviewer", "documentation":"documentation-builder",
 "reproducibility":"reproducibility-builder", "domain_expert":"qualified-domain-reviewer",
 "commercial_readiness":"commercial-reviewer", "delivery":"delivery-builder",
}
def plan(manifest, root):
    failures = validate(manifest, root)
    tasks = []
    for failure in failures:
        key = failure.split(":", 1)[0]
        tasks.append({"criterion":key,"reason":failure,"owner":OWNERS.get(key,"quality-coordinator"),
                      "action":"repair_and_retest" if key not in ("domain_expert","commercial_readiness") else "obtain_independent_review"})
    return {"schema":"saeit.quality1000.rework.v1",
            "quality1000":"BLOCKED" if failures else "PASS",
            "tasks":tasks,"publication_allowed":not failures}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("manifest",type=Path)
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    data=json.loads(args.manifest.read_text(encoding="utf-8"))
    result=plan(data,args.root)
    rendered=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(rendered,encoding="utf-8")
    else:
        print(rendered,end="")
    raise SystemExit(1 if result["tasks"] else 0)
if __name__=="__main__":
    main()
