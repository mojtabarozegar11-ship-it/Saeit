#!/usr/bin/env python3
"""Surgical evidence-revision-only Stage4 resume. No budget, cap or QA bypass.

Patches the single verified live autonomous_brain wait branch, with backups.
A waiting or exhausted run may *revalidate* only when its stored real research
evidence has changed, and must pass the existing Stage4 source validation.
Original 100-evidence cap and independent specialist/publication gates stand.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

OLD='''            if progress.get("status") == "capacity_exhausted" or (due and due > timezone.now()):
                return {"action": "waiting_for_evidence", "reason": "Stage 4 research is waiting for its persisted budget window or capacity policy."}'''
NEW='''            if progress.get("status") == "capacity_exhausted" or (due and due > timezone.now()):
                # Reopen only an unchanged-budget *evaluation*, not research
                # acquisition, when new evidence actually replaced old evidence.
                from .factory_stage4 import effective_research
                prior_evidence = (progress.get("research") or {}).get("evidence") or []
                current_evidence = (effective_research(state["product"].metadata or {}) or {}).get("evidence") or []
                revised_evidence = (isinstance(prior_evidence, list)
                    and isinstance(current_evidence, list)
                    and 0 < len(current_evidence) <= 100
                    and current_evidence != prior_evidence)
                if not revised_evidence:
                    return {"action": "waiting_for_evidence", "reason": "Stage 4 research is waiting for its persisted budget window or capacity policy."}'''

def patch_text(source):
    if source.count(OLD)!=1:
        if source.count(NEW)==1 and source.count(OLD)==0:return source,False
        raise RuntimeError("STAGE4_EXACT_PREIMAGE_MISMATCH")
    result=source.replace(OLD,NEW)
    compile(result,"autonomous_brain.py","exec")
    if result.count("Stage 4 research is waiting for its persisted budget window or capacity policy.")!=1:
        raise RuntimeError("STAGE4_WAITING_POLICY_LOST")
    return result,True

def evidence_revised(prior,current):
    """Pure mirror of the injected fail-closed comparison for regression tests."""
    return (isinstance(prior,list) and isinstance(current,list)
            and 0<len(current)<=100 and current!=prior)

def install(target,backup_root):
    target=Path(target);backup_root=Path(backup_root)
    expected=Path.home()/"factory-runtime/django-app/core/autonomous_brain.py"
    if target!=expected or target.is_symlink() or not target.is_file() or target.stat().st_size>180000:
        raise RuntimeError("STAGE4_UNTRUSTED_TARGET")
    if backup_root.is_symlink() or not backup_root.is_dir():
        raise RuntimeError("STAGE4_BACKUP_ROOT_UNSAFE")
    original=target.read_bytes()
    before=hashlib.sha256(original).hexdigest()
    updated,changed=patch_text(original.decode("utf8"))
    if not changed:
        return {"patched":False,"already_patched":True,"source_sha256":before}
    backup=backup_root/("autonomous_brain-"+before[:24]+".before.py")
    if backup.is_symlink():raise RuntimeError("UNSAFE_BACKUP_LINK")
    if backup.exists():
        if backup.read_bytes()!=original:raise RuntimeError("BACKUP_CONFLICT")
    else:
        with backup.open("xb") as f:
            f.write(original);f.flush();os.fsync(f.fileno())
        os.chmod(backup,0o600)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=before:
        raise RuntimeError("CONCURRENT_STAGE4_SOURCE_CHANGE")
    fd,temp=tempfile.mkstemp(prefix=".stage4-guard-",dir=str(target.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(updated.encode("utf8"));f.flush();os.fsync(f.fileno())
        os.chmod(temp,target.stat().st_mode & 0o777)
        if hashlib.sha256(target.read_bytes()).hexdigest()!=before:
            raise RuntimeError("STAGE4_SOURCE_CHANGED_DURING_PATCH")
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    result={"patched":True,"backup_sha256":before,
            "source_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
            "evidence_cap_100_preserved":True,
            "public_or_commercial_approval_created":False,
            "unmodified_evidence_still_waits":True}
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--target",required=True)
    p.add_argument("--backup-root",required=True)
    a=p.parse_args()
    import json
    print("STAGE4_REVISION_ONLY_RETRY_GUARD="+json.dumps(install(a.target,a.backup_root),sort_keys=True))

if __name__=="__main__":main()
