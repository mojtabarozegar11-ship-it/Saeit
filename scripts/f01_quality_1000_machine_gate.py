#!/usr/bin/env python3
"""F01 scoped QC1000 machine evidence gate."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
SCHEMA="saeit.factory.f01-quality-100-groups.v1"
PRODUCT="farm_enterprise_economics"
EVIDENCE_SCHEMA="saeit.factory.f01-quality-evidence.v1"
def sha256(path:Path)->str:
    if path.is_symlink() or not path.is_file(): raise ValueError("F01_PACKAGE_MISSING_OR_UNSAFE")
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()
def load_catalog(path:Path)->dict:
    if path.is_symlink() or not path.is_file(): raise ValueError("F01_QUALITY_CATALOG_MISSING_OR_UNSAFE")
    try: data=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError) as exc: raise ValueError("F01_QUALITY_CATALOG_INVALID_JSON") from exc
    if not isinstance(data,dict): raise ValueError("F01_QUALITY_CATALOG_NOT_OBJECT")
    criteria=data.get("criteria")
    if data.get("schema")!=SCHEMA or data.get("product_id")!=PRODUCT: raise ValueError("F01_QUALITY_CATALOG_SCHEMA_MISMATCH")
    if not isinstance(criteria,list) or len(criteria)!=100: raise ValueError("F01_QUALITY_CATALOG_MUST_HAVE_100_CRITERIA")
    try:
        points=sum(int(x["points"]) for x in criteria); ids=[x["id"] for x in criteria]; required=[x["required_evidence"] for x in criteria]
    except (KeyError,TypeError,ValueError) as exc: raise ValueError("F01_QUALITY_CATALOG_CRITERIA_INVALID") from exc
    if points!=1000 or len(set(ids))!=100 or any(not isinstance(x,str) or not x for x in ids): raise ValueError("F01_QUALITY_CATALOG_IDS_OR_POINTS_INVALID")
    if any(not isinstance(x,str) or not x or Path(x).is_absolute() or ".." in Path(x).parts for x in required): raise ValueError("F01_QUALITY_CATALOG_EVIDENCE_PATH_INVALID")
    return data
def evidence_passes(path:Path,cid:str,artifact:str)->bool:
    if path.is_symlink() or not path.is_file(): return False
    try: doc=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError,UnicodeError): return False
    return isinstance(doc,dict) and doc.get("schema")==EVIDENCE_SCHEMA and doc.get("product_id")==PRODUCT and doc.get("criterion_id")==cid and doc.get("artifact_sha256")==artifact and doc.get("status")=="PASS"
def evaluate(package:Path,catalog_path:Path,evidence_root:Path)->dict:
    catalog=load_catalog(catalog_path); artifact=sha256(package); measured=[]; missing=[]; root=evidence_root.resolve()
    for criterion in catalog["criteria"]:
        cid=criterion["id"]; ep=root/criterion["required_evidence"]
        try: ep.resolve().relative_to(root)
        except ValueError: missing.append(cid); continue
        (measured if evidence_passes(ep,cid,artifact) else missing).append(cid)
    return {"schema":"saeit.factory.f01-quality-machine-evaluation.v1","product_id":PRODUCT,"artifact_sha256":artifact,"criterion_count":100,"machine_documentary_points":len(measured)*10,"machine_documentary_target":1000,"machine_documentary_gap":1000-len(measured)*10,"measured_criteria":measured,"missing_criteria":missing,"professional_quality_points":None,"professional_qc1000_certified":False,"independent_reviewer_authentication":False,"commercial_release_allowed":False,"reason":"INDEPENDENT_SPECIALIST_AND_RIGHTS_SIGNOFFS_REQUIRED"}
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--package",type=Path,required=True); ap.add_argument("--catalog",type=Path,required=True); ap.add_argument("--evidence-root",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args()
    result=evaluate(a.package,a.catalog,a.evidence_root); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps({k:result[k] for k in ("machine_documentary_points","machine_documentary_gap","professional_qc1000_certified","commercial_release_allowed")},ensure_ascii=False,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
