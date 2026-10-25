#!/usr/bin/env python3
"""Remove only expired Stage1 atomic-write leftovers blocking a single English order.

Do not delete work orders, accepted stage receipts, research evidence, QA goods,
customer deliveries, or any storefront. Fail closed if writers are active.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path("/home/githubops/factory-runtime/private/autonomous-product-cycle")
AREA=ROOT/"production-instructions"
INBOX=AREA/"stage-02/inbox"
OPS=Path("/home/githubops/factory-runtime/operations/production-instructions")
ORDER_LIST=AREA/"orders"
PENDING_NAME=".stage1-zx5q3y1a"
TEMP_RE=re.compile(r"\.stage1-[a-zA-Z0-9_]{8}\Z")

def checksum_orders():
    h=hashlib.sha256()
    orders=sorted(ORDER_LIST.glob("WO-*.json"))
    if len(orders)!=2588:raise RuntimeError("WORK_ORDER_LIST_CHANGED")
    for p in orders:
        if p.is_symlink() or not p.is_file():raise RuntimeError("BAD_ORDER_LIST")
        h.update(p.name.encode())
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()

def run(apply):
    if os.geteuid()==0 or os.getenv("USER")!="githubops":
        raise RuntimeError("EXPECTED_NONROOT_OPERATOR")
    for folder in (ROOT,AREA,INBOX,OPS,ORDER_LIST):
        if folder.is_symlink() or not folder.is_dir():
            raise RuntimeError("PRIVATE_SCOPE_UNSAFE")
    crons=subprocess.run(["crontab","-l"],capture_output=True,text=True,timeout=9,check=True).stdout
    active=[x for x in crons.splitlines() if x.strip() and not x.lstrip().startswith("#")]
    if sum("SAEIT_ENGLISH_FIRST_SINGLE_ACTIVE_20261025" in x for x in active)!=1:
        raise RuntimeError("ENGLISH_CONTROLLER_NOT_SINGLE")
    if any("SAEIT_FACTORY_OWNER_DELEGATE_COORDINATION_V1" in x for x in active):
        raise RuntimeError("COMPETING_BULK_STILL_ACTIVE")
    locks=[]
    if apply:
        for p in (OPS/".english-first-single-active.lock",AREA/"stage-02/.worker.lock"):
            if p.is_symlink():raise RuntimeError("WORKER_LOCK_UNSAFE")
            fd=os.open(p,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                raise RuntimeError("STAGE_WRITER_ACTIVE_RETRY")
            locks.append(fd)
    try:
        hash_before=checksum_orders()
        names=sorted(INBOX.iterdir())
        if len(names)>200:raise RuntimeError("UNEXPECTED_BULK_REAPPEARED")
        stale=[]
        for p in names:
            if p.name.startswith(".stage1-"):
                if not TEMP_RE.fullmatch(p.name) or not p.is_file() or p.is_symlink():
                    raise RuntimeError("BAD_ATOMIC_TEMP_FILE")
                meta=p.stat()
                if meta.st_nlink!=1 or meta.st_size>300000 or time.time()-meta.st_mtime<600:
                    raise RuntimeError("ATOMIC_TEMP_STILL_ACTIVE_OR_UNSAFE:"+p.name)
                stale.append((p,meta))
            elif not re.fullmatch(r"WO-[0-9]{8}--r[0-9]{3}\.json",p.name):
                raise RuntimeError("UNKNOWN_STAGE2_INBOX_NAME:"+p.name)
        if not stale or PENDING_NAME not in {p.name for p,_ in stale}:
            raise RuntimeError("EXPECTED_STALE_ORPHAN_NOT_PRESENT")
        result={"mode":"APPLY" if apply else "DRY_RUN",
                "only_stale_stage1_atomic_orphans":len(stale),
                "stale_names":[p.name for p,_ in stale],
                "bytes":sum(meta.st_size for _,meta in stale),
                "valid_work_orders_preserved":2588,"english_controller_preserved":True,
                "paid_storefront_modified":False,"customer_orders_modified":False,
                "approved_artifacts_modified":False}
        if apply:
            for p,meta in stale:
                cur=p.stat()
                if (cur.st_ino!=meta.st_ino or cur.st_size!=meta.st_size
                        or cur.st_mtime_ns!=meta.st_mtime_ns):
                    raise RuntimeError("TEMP_CHANGED_DURING_SCOPE_CHECK")
                p.unlink()
            if any(p.exists() for p,_ in stale):
                raise RuntimeError("LEFTOVER_ATOMIC_TEMP_EXISTS")
            result["deleted_stale_atomic_temp_files"]=len(stale)
        if checksum_orders()!=hash_before:raise RuntimeError("ORDER_LIST_FINGERPRINT_CHANGED")
        return result
    finally:
        for fd in reversed(locks):os.close(fd)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    try:print("STAGE2_STALE_ATOMIC_ORPHANS="+json.dumps(run(args.apply),sort_keys=True),flush=True)
    except Exception as exc:
        print("STAGE2_STALE_ATOMIC_ORPHANS_FAILED="+type(exc).__name__+":"+str(exc)[:160],file=sys.stderr,flush=True)
        sys.exit(1)
