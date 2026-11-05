#!/usr/bin/env python3
"""Import provenance-matched, hash-pinned evidence into one product QC dossier.

Records from mushroom cultivation or farm-management books are not admissible
evidence for the separate farm-enterprise calculator. Missing exact product
binding is a hard stop before any filesystem write. Independent review and
commercial release remain distinct requirements.
"""
import argparse, hashlib, json, os, re, shutil, tempfile
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "factory_config" / "farm_enterprise_economics_library_evidence_import.v1.json"
PRODUCT_ID = "farm_enterprise_economics"
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""): h.update(chunk)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--inbox", required=True)
    p.add_argument("--product-root", required=True)
    args=p.parse_args()
    if Path(args.product_root).is_symlink() or Path(args.inbox).is_symlink():
        raise SystemExit("SOURCE_OR_PRODUCT_ROOT_UNSAFE")
    inbox=Path(args.inbox).resolve(strict=True)
    root=Path(args.product_root).resolve(strict=True)
    if not inbox.is_dir() or not root.is_dir(): raise SystemExit("SOURCE_OR_PRODUCT_ROOT_UNSAFE")
    plan=json.loads(CONFIG.read_text(encoding="utf-8"))
    if plan.get("schema")!="saeit.factory.library-evidence-import.v1" or plan.get("product")!=PRODUCT_ID:
        raise SystemExit("EVIDENCE_PLAN_PRODUCT_MISMATCH")
    entries={}
    for record in plan.get("source_records",[]):
        name=record.get("name")
        if (not isinstance(name,str) or Path(name).name!=name or name in entries
                or not isinstance(record.get("sha256"),str) or not SHA256.fullmatch(record["sha256"])):
            raise SystemExit("EVIDENCE_SOURCE_RECORD_INVALID")
        entries[name]=record
    proposed=plan.get("criteria_evidence")
    if not isinstance(proposed,dict) or not proposed:
        raise SystemExit("NO_PRODUCT_BOUND_EVIDENCE")
    selected={}
    for criterion,claim in proposed.items():
        if not re.fullmatch(r"Q\d{3}",criterion) or not isinstance(claim,dict):
            raise SystemExit("EVIDENCE_CRITERION_INVALID")
        name=claim.get("source")
        record=entries.get(name)
        if not record or record.get("source_product_id")!=PRODUCT_ID:
            raise SystemExit("EVIDENCE_SOURCE_PRODUCT_MISMATCH:"+criterion)
        selected[name]=record["sha256"]
    # Validate every source and existing destination before creating anything.
    evidence=root/"evidence-inbox"
    if evidence.is_symlink() or (evidence.exists() and not evidence.is_dir()):
        raise SystemExit("EVIDENCE_ROOT_UNSAFE")
    for name,wanted in selected.items():
        src=inbox/name
        if src.is_symlink() or not src.is_file(): raise SystemExit("EVIDENCE_MISSING:"+name)
        if digest(src)!=wanted: raise SystemExit("EVIDENCE_HASH_MISMATCH:"+name)
        dst=evidence/name
        if dst.is_symlink() or (dst.exists() and (not dst.is_file() or digest(dst)!=wanted)):
            raise SystemExit("EVIDENCE_DESTINATION_CONFLICT:"+name)
    evidence.mkdir(mode=0o700,exist_ok=True)
    refs={}
    for name,wanted in selected.items():
        src=inbox/name
        dst=evidence/name
        if not dst.exists():
            fd,staged=tempfile.mkstemp(prefix=".incoming-evidence-",dir=str(evidence))
            try:
                with os.fdopen(fd,"wb") as out, src.open("rb") as incoming:
                    shutil.copyfileobj(incoming,out)
                    out.flush(); os.fsync(out.fileno())
                if digest(Path(staged))!=wanted: raise SystemExit("EVIDENCE_COPY_HASH_MISMATCH:"+name)
                os.chmod(staged,0o600)
                os.replace(staged,dst)
            finally:
                if os.path.exists(staged): os.unlink(staged)
        refs[name]={"path":"evidence-inbox/"+name,"sha256":wanted}
    candidate=root/"global_quality_candidate.json"
    prior={}
    if candidate.is_file() and not candidate.is_symlink():
        prior=json.loads(candidate.read_text(encoding="utf-8"))
        if not isinstance(prior,dict): raise SystemExit("CANDIDATE_SCHEMA")
    dossier=prior.get("criteria_evidence") or {}
    if not isinstance(dossier,dict): raise SystemExit("CANDIDATE_EVIDENCE_SCHEMA")
    dossier=dict(dossier)
    for criterion,claim in proposed.items(): dossier[criterion]=refs[claim["source"]]
    prior["schema"]="saeit.factory.global-quality-candidate.v1"
    prior["recipe"]="farm_enterprise_economics"
    prior["criteria_evidence"]=dossier
    prior["evidence_import"]={"schema":"saeit.factory.library-evidence-import.v1",
        "source":"hash-pinned private Library records",
        "independent_certification":False,
        "commercial_release_allowed":False}
    raw=(json.dumps(prior,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    tmp=candidate.with_name(".candidate.tmp")
    with tmp.open("wb") as f: f.write(raw); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp,0o600); os.replace(tmp,candidate)
    print("FACTORY_LIBRARY_EVIDENCE_IMPORT=PASS")
    print("FACTORY_IMPORTED_CRITERIA="+str(len(proposed)))
    print("FACTORY_INDEPENDENT_CERTIFICATION=FALSE")
    print("FACTORY_COMMERCIAL_RELEASE=FALSE")
if __name__=="__main__": main()
