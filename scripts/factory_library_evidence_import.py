#!/usr/bin/env python3
"""Attach already-existing, hash-pinned evidence to one product's QC dossier.

The importer is deliberately conservative: it copies only allowlisted files,
checks their SHA-256, and writes criteria_evidence references relative to the
product directory. It never creates reviewer identities or release approval.
"""
import argparse, hashlib, json, os, shutil
from pathlib import Path

MAP = {
    "Q023": "B01_EN_I_II_BATCH_PRIVATE_RELEASE_GATE_MANIFEST.json",
    "Q032": "B01_C92_C113_FIXED_PRIVATE_REVIEW_20261101_BATCH.zip",
    "Q035": "Cycle36_Working_Evidence.zip",
    "Q036": "B01_EN_I_II_BATCH_PRIVATE_RELEASE_GATE_MANIFEST.json",
    "Q068": "B01_C92_C113_FIXED_PRIVATE_REVIEW_20261101_BATCH.zip",
    "Q077": "B01_C92_C113_FIXED_PRIVATE_REVIEW_20261101_BATCH.zip",
    "Q092": "B01_EN_I_II_BATCH_PRIVATE_RELEASE_GATE_MANIFEST.json",
}
EXPECTED = {
    "B01_C92_C113_FIXED_PRIVATE_REVIEW_20261101_BATCH.zip": "c34b08c772fc85a7e20114273f834eaa60e6c68846b367cea2b471bd7b327e41",
    "Cycle36_Working_Evidence.zip": "a29b7f5f1a37e34309366d2d38c83467562e9db9e3416031b829d72543752547",
    "B01_EN_I_II_BATCH_PRIVATE_RELEASE_GATE_MANIFEST.json": "2d62810038733b252546e4aee4bb72f6a6ced83a9190dd72408b41b17b4ee8df",
    "Cycle37_Reader_and_31_Action_Evidence.zip": "2234f5d105ad4b628a1f37f6a9b60b18b17a118744f52d4e755cee4f69fccb33",
}
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
    inbox=Path(args.inbox).resolve(strict=True)
    root=Path(args.product_root).resolve(strict=True)
    if not root.is_dir() or root.is_symlink(): raise SystemExit("PRODUCT_ROOT_UNSAFE")
    evidence=root/"evidence-inbox"
    evidence.mkdir(mode=0o700, exist_ok=True)
    if evidence.is_symlink(): raise SystemExit("EVIDENCE_ROOT_UNSAFE")
    refs={}
    for name,wanted in EXPECTED.items():
        src=inbox/name
        if src.is_symlink() or not src.is_file(): raise SystemExit("EVIDENCE_MISSING:"+name)
        actual=digest(src)
        if actual != wanted: raise SystemExit("EVIDENCE_HASH_MISMATCH:"+name)
        dst=evidence/name
        if dst.exists() and digest(dst)!=wanted: raise SystemExit("EVIDENCE_DESTINATION_CONFLICT:"+name)
        if not dst.exists(): shutil.copyfile(src,dst); os.chmod(dst,0o600)
        refs[name]={"path":"evidence-inbox/"+name,"sha256":wanted}
    candidate=root/"global_quality_candidate.json"
    prior={}
    if candidate.is_file() and not candidate.is_symlink():
        prior=json.loads(candidate.read_text(encoding="utf-8"))
        if not isinstance(prior,dict): raise SystemExit("CANDIDATE_SCHEMA")
    dossier=dict(prior.get("criteria_evidence") or {})
    for criterion,name in MAP.items(): dossier[criterion]=refs[name]
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
    print("FACTORY_IMPORTED_CRITERIA="+str(len(MAP)))
    print("FACTORY_INDEPENDENT_CERTIFICATION=FALSE")
    print("FACTORY_COMMERCIAL_RELEASE=FALSE")
if __name__=="__main__": main()
