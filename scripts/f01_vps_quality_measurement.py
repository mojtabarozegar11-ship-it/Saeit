#!/usr/bin/env python3
"""Measure the latest private VPS F01 artifact with the scoped QC1000 gate."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from f01_quality_1000_machine_gate import evaluate

def safe_latest(folder: Path) -> Path:
    if folder.is_symlink() or not folder.is_dir():
        raise RuntimeError("F01_PRIVATE_PRODUCT_FOLDER_MISSING_OR_UNSAFE")
    files=[p for p in folder.glob("*.zip") if p.is_file() and not p.is_symlink()]
    if not files:
        raise RuntimeError("F01_PRIVATE_F01_ARTIFACT_MISSING")
    return max(files,key=lambda p:p.stat().st_mtime_ns)

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--private-root",type=Path,required=True)
    ap.add_argument("--catalog",type=Path,required=True)
    ap.add_argument("--gate",type=Path,required=True)
    ap.add_argument("--run-id",required=True)
    a=ap.parse_args()
    private=a.private_root.resolve()
    if private.is_symlink() or not private.is_dir():
        raise RuntimeError("F01_PRIVATE_ROOT_MISSING_OR_UNSAFE")
    artifact=safe_latest(private/"digital-products"/"farm_enterprise_economics")
    evidence=private/"quality-excellence"/"f01-qc1000"/"evidence"
    result=evaluate(artifact,a.catalog,evidence)
    result.update({"run_id":a.run_id,"artifact_path":str(artifact),"evidence_root":str(evidence)})
    out=private/"quality-excellence"/"f01-qc1000"/("evaluation-"+a.run_id+".json")
    out.parent.mkdir(parents=True,exist_ok=True)
    os.chmod(out.parent,0o700)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.chmod(out,0o600)
    print("F01_QC1000_ARTIFACT_SHA256="+result["artifact_sha256"])
    print("F01_QC1000_MACHINE_DOCUMENTARY_POINTS="+str(result["machine_documentary_points"]))
    print("F01_QC1000_MACHINE_DOCUMENTARY_GAP="+str(result["machine_documentary_gap"]))
    print("F01_QC1000_PROFESSIONAL_CERTIFIED=false")
    print("F01_QC1000_COMMERCIAL_RELEASE=false")
    print("F01_QC1000_RECEIPT="+str(out))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
