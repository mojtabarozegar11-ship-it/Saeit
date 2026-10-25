#!/usr/bin/env python3
"""English-edition-first, single-active-order private factory admission.

Each scheduler tick admits only the current ranked order to Stage 1 and keeps it
active until *independent* 12-stage warehouse certification. No storefront, paid
entitlement, order JSON or QC verdict is changed. Unsupported content stalls
honestly rather than being recorded as completed.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

SCHEMA = "saeit.factory.english-first-single-active.v1"
QUEUE_SCHEMA = "saeit.factory.english-first-ranked-queue.v1"
ORDER = re.compile(r"WO-[0-9]{8}\Z")
MARKER = "SAEIT_ENGLISH_FIRST_SINGLE_ACTIVE_20261025"
RESERVE = 2 * 1024 ** 3
PRIORITY_LABELS = ("english_only", "english_and_other", "other_language", "language_unspecified")


def checked(path: Path, limit=300000):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise RuntimeError("UNSAFE_OR_MISSING_PRIVATE_JSON:" + path.name)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict): raise RuntimeError("NOT_A_JSON_OBJECT")
    return doc


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def atomic(path: Path, data: dict):
    if path.is_symlink() or not path.parent.is_dir() or path.parent.is_symlink():
        raise RuntimeError("UNSAFE_PRIVATE_STATE_DESTINATION")
    fd,tmp=tempfile.mkstemp(prefix=".english-first-",dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            json.dump(data,handle,ensure_ascii=False,sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def locale_group(item:dict):
    entries=item.get("editions")
    if not isinstance(entries,list): entries=[]
    declared=[]
    for edition in entries:
        if not isinstance(edition,dict): continue
        loc=edition.get("locale")
        if isinstance(loc,str) and loc.strip():
            declared.append(loc.strip().lower().replace("_","-"))
    english=any(x=="en" or x.startswith("en-") for x in declared)
    if english:
        return 0 if len(declared)==1 else 1
    return 2 if declared else 3


def workorders(area:Path):
    folder=area/"orders"
    if folder.is_symlink() or not folder.is_dir():raise RuntimeError("ORDER_LIST_MISSING")
    names=sorted(folder.iterdir())
    if len(names)<2000:raise RuntimeError("ORDER_QUEUE_UNEXPECTEDLY_SMALL")
    h=hashlib.sha256()
    ranked=[]
    counts=Counter()
    for path in names:
        if path.is_symlink() or not path.is_file() or path.suffix!=".json" or not ORDER.fullmatch(path.stem):
            raise RuntimeError("BAD_ORDER_FILE_IN_QUEUE")
        raw=path.read_bytes()
        h.update(path.name.encode())
        h.update(bytes.fromhex(digest(raw)))
        order=json.loads(raw)
        if not isinstance(order,dict) or order.get("id")!=path.stem:
            raise RuntimeError("ORDER_IDENTITY_INVALID")
        if order.get("status") not in ("issued","in_engineering","blocked_rework","completed_verified"):
            raise RuntimeError("UNRECOGNIZED_ORDER_STATUS")
        cat=locale_group(order)
        counts[PRIORITY_LABELS[cat]]+=1
        rank=order.get("priority_rank")
        priority=(0 if order.get("priority")=="P0" else 1,
                  rank if type(rank) is int and rank>=0 else 999999)
        ranked.append((cat,*priority,path.stem))
    ranked.sort()
    ids=[r[-1] for r in ranked]
    if len(set(ids))!=len(ids):raise RuntimeError("DUPLICATE_ORDER")
    return ids,h.hexdigest(),dict(counts)


def load_python(path, module_name):
    if path.is_symlink() or not path.is_file():raise RuntimeError("REQUIRED_WORKER_UNAVAILABLE:"+path.name)
    spec=importlib.util.spec_from_file_location(module_name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def certified(root,ops,order):
    strict=load_python(ops/"strict-serial-fullcycle-v1.py","english_first_warehouse_cert")
    governance=strict.load_governance(ops)
    return strict.certified_finished(root,order,governance)


def cron_single():
    crons=subprocess.run(["crontab","-l"],check=True,text=True,capture_output=True,timeout=6).stdout
    active=[x for x in crons.splitlines() if x.strip() and not x.lstrip().startswith("#")]
    if sum(MARKER in x for x in active)!=1:
        raise RuntimeError("SERIAL_CRON_NOT_EXACTLY_ONCE")
    if any("SAEIT_FACTORY_STAGE1_INDEPENDENT_V1" in x for x in active):
        raise RuntimeError("COMPETING_BULK_STAGE1_STILL_ACTIVE")
    if any("SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025" in x for x in active):
        raise RuntimeError("COMPETING_AGRI200_SERIAL_ACTIVE")


def run(factory_private,operations,dry_run=False,require_cron=False,stage2_timeout=8):
    root=Path(factory_private)
    ops=Path(operations)
    area=root/"production-instructions"
    statepath=area/"stage-06/english-first-active-v1.json"
    queuepath=area/"english-first-ranked-order-list-v1.json"
    if any(p.is_symlink() or not p.is_dir() for p in (root,ops,area,statepath.parent)):
        raise RuntimeError("PRIVATE_FACTORY_ROOT_UNSAFE")
    ids,sha,counts=workorders(area)
    if require_cron:cron_single()
    def get_state():
        if not statepath.exists():
            return {"index":0,"active_order":ids[0],"tick":0}
        state=checked(statepath,16384)
        index=state.get("index")
        if (state.get("schema")!=SCHEMA or state.get("queue_sha256")!=sha
                or type(index) is not int or not 0<=index<=len(ids)
                or state.get("active_order")!=(ids[index] if index<len(ids) else None)):
            raise RuntimeError("ENGLISH_FIRST_ACTIVE_STATE_STALE_OR_CORRUPT")
        return state
    current=get_state()
    active=current["active_order"]
    base={"schema":SCHEMA,"orders_preserved":len(ids),"language_groups":counts,
          "active_order":active,"index":current["index"],
          "sites_modified":False,"automatic_quality_approvals":0,
          "storage_hold":shutil.disk_usage(root).free<RESERVE}
    if active is None:return dict(base,all_certified=True)
    details=checked(area/"orders"/(active+".json"))
    edits=details.get("editions",[])
    base["active_order_locale"]=[x.get("locale") for x in edits if isinstance(x,dict)] if isinstance(edits,list) else []
    base["active_order_site"]=[x.get("site") for x in edits if isinstance(x,dict)] if isinstance(edits,list) else []
    if dry_run:return dict(base,mode="dry_run_no_writes")
    lock=ops/".english-first-single-active.lock"
    if lock.is_symlink():raise RuntimeError("ENGLISH_FIRST_LOCK_SYMLINK")
    fd=os.open(lock,os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return dict(base,already_running=True)
        ids2,sha2,counts2=workorders(area)
        if ids2!=ids or sha2!=sha:raise RuntimeError("ORDERS_CHANGED_DURING_TICK")
        current=get_state()
        active=current["active_order"]
        if active is None:return dict(base,all_certified=True)
        # No rotation without authentic approved finished-goods certification.
        is_certified=certified(root,ops,active)
        if is_certified:
            next_index=current["index"]+1
            next_active=ids[next_index] if next_index<len(ids) else None
            atomic(statepath,{"schema":SCHEMA,"queue_sha256":sha,
                 "index":next_index,"active_order":next_active,"tick":0,
                 "last_order":active,"last_order_qc1000":True,
                 "updated_utc":datetime.now(timezone.utc).isoformat()})
            return dict(base,just_certified=True,next_active_order=next_active,
                        admitted_to_stage1=False)
        # Do not reclassify an explicitly blocked return as an initial work order.
        if details.get("status") not in ("issued","in_engineering"):
            return dict(base,blocked_reason="ORDER_REQUIRES_RETURN_REWORK_NOT_STAGE1",
                        admitted_to_stage1=False)
        if queuepath.exists():
            q=checked(queuepath,300000)
            if q.get("schema")!=QUEUE_SCHEMA or q.get("queue_sha256")!=sha or q.get("orders")!=ids:
                raise RuntimeError("ENGLISH_QUEUE_SNAPSHOT_CHANGED")
        stage1=load_python(ops/"stage1-english-first-worker.py","english_first_stage1")
        # Stage 1 is an idempotent, fingerprint-bound *private* handoff.
        created=stage1.forward(root,details,revision=1)
        if not queuepath.exists():
            atomic(queuepath,{"schema":QUEUE_SCHEMA,"orders":ids,
                 "queue_sha256":sha,"language_groups":counts,
                 "rule":"english_only,english_and_other,other_language,unspecified; P0/rank/id",
                 "public_release":False})
        else:
            q=checked(queuepath,300000)
            if q.get("schema")!=QUEUE_SCHEMA or q.get("queue_sha256")!=sha or q.get("orders")!=ids:
                raise RuntimeError("ENGLISH_QUEUE_SNAPSHOT_CHANGED")
        stage2="STORAGE_RESERVE_HOLD"
        if shutil.disk_usage(root).free>=RESERVE:
            runner=ops/"stage2-research-serial.py"
            if runner.is_file() and not runner.is_symlink():
                py=ops.parent.parent/".venv/bin/python"
                completed=subprocess.run([str(py),"-B",str(runner),
                    "--factory-private",str(root),"--only-order-id",active,
                    "--batch","1"],capture_output=True,timeout=stage2_timeout,check=False)
                stage2=("WORKER_RETURN_"+str(completed.returncode))
            else:stage2="STAGE2_WORKER_MISSING"
        atomic(statepath,{"schema":SCHEMA,"queue_sha256":sha,
             "index":current["index"],"active_order":active,
             "tick":current.get("tick",0)+1,"last_stage1_created":bool(created),
             "stage2":stage2,"updated_utc":datetime.now(timezone.utc).isoformat(),
             "quality_approved":False,"sites_modified":False})
        return dict(base,admitted_to_stage1=True,new_stage1_handoff=bool(created),
                    stage2_status=stage2,certified=False,
                    next_active_order=active)
    finally:
        os.close(fd)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--operations",required=True)
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--require-cron",action="store_true")
    args=p.parse_args()
    try:print(json.dumps(run(args.factory_private,args.operations,
                 dry_run=args.dry_run,require_cron=args.require_cron),
                 ensure_ascii=False,sort_keys=True),flush=True)
    except Exception as e:
        print("ENGLISH_FIRST_SERIAL_ERROR="+type(e).__name__+":"+str(e)[:200],
              file=sys.stderr,flush=True)
        raise SystemExit(1)


if __name__=="__main__":main()
