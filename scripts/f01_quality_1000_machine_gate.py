#!/usr/bin/env python3
"""F01 scoped QC1000 machine evidence gate.

This gate measures only artifact-bound, reproducible evidence. It never
creates professional approval, independent review, or commercial clearance.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SCHEMA = "saeit.factory.f01-quality-100-groups.v1"
PRODUCT = "farm_enterprise_economics"

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""): h.update(chunk)
    return h.hexdigest()

def load_catalog(path: Path) -> dict:
    data=json.loads(path.read_text(encoding="utf-8"))
    criteria=data.get("criteria",[])
    if data.get("schema")!=SCHEMA or data.get("product_id")!=PRODUCT:
        raise ValueError("F01_QUALITY_CATALOG_SCHEMA_MISMATCH")
    if len(criteria)!=100 or sum(int(x.get("points",0)) for x in criteria)!=1000:
        raise ValueError("F01_QUALITY_CATALOG_MUST_BE_100_CRITERIA_1000_POINTS")
    ids=[x.get("id") for x in criteria]
    if len(set(ids))!=100 or any(not x for x in ids):
        raise ValueError("F01_QUALITY_CATALOG_IDS_INVALID")
    return data

def evaluate(package: Path, catalog_path: Path, evidence_root: Path) -> dict:
    catalog=load_catalog(catalog_path)
    artifact=sha256(package)
    measured=[]; missing=[]
    for criterion in catalog["criteria"]:
        cid=criterion["id"]
        ep=evidence_root / criterion["required_evidence"]
        ok=False
        if ep.is_file() and not ep.is_symlink():
            try:
                doc=json.loads(ep.read_text(encoding="utf-8"))
                ok=(doc.get("schema")=="saeit.factory.f01-quality-evidence.v1"
                    and doc.get("product_id")==PRODUCT
                    and doc.get("criterion_id")==cid
                    and doc.get("artifact_sha256")==artifact
                    and doc.get("status")=="PASS")
            except (OSError, ValueError, TypeError):
                ok=False
        (measured if ok else missing).append(cid)
    points=sum(10 for _ in measured)
    return {
        "schema":"saeit.factory.f01-quality-machine-evaluation.v1",
        "product_id":PRODUCT,
        "artifact_sha256":artifact,
        "criterion_count":100,
        "machine_documentary_points":points,
        "machine_documentary_target":1000,
        "machine_documentary_gap":1000-points,
        "measured_criteria":measured,
        "missing_criteria":missing,
        "professional_quality_points":None,
        "professional_qc1000_certified":False,
        "independent_reviewer_authentication":False,
        "commercial_release_allowed":False,
        "reason":"INDEPENDENT_SPECIALIST_AND_RIGHTS_SIGNOFFS_REQUIRED",
    }

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--package",type=Path,required=True)
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--evidence-root",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    result=evaluate(a.package,a.catalog,a.evidence_root)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("machine_documentary_points","machine_documentary_gap","professional_qc1000_certified","commercial_release_allowed")},ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
