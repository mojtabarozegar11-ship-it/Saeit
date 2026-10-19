#!/usr/bin/env python3
"""Overflow intake ONLY for Zomorodmelal.ir.

Exactly three idempotent PRIVATE REQUESTS per unique cycle when the native VPS
factory queue has no capacity. These are not native WO work orders, do not
reserve scarce native IDs, and must never be labelled manufacturing accepted.
The factory native backlog and autonomous manufacturing executor are untouched.
"""
import datetime as dt
import fcntl
import hashlib
import json
import re
from pathlib import Path

CYCLE=re.compile(r"^(?P<day>[0-9]{4}-[0-9]{2}-[0-9]{2})(?:-r(?P<run>[0-9]{5,20}))?$")
REQUEST=re.compile(r"^ZR-[0-9]{8}-R[0-9]{5,20}-0[123]\.json$")
MAX_PENDING=30

def pending_once(root,engine,profiles,cycle,*,max_pending=MAX_PENDING):
    match=CYCLE.fullmatch(cycle)
    if not match:raise ValueError("SITE_PENDING_BAD_CYCLE")
    day=dt.date.fromisoformat(match.group("day"))
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise RuntimeError("SITE_PENDING_BAD_ROOT")
    area=root/"production-instructions"
    if area.is_symlink() or not area.is_dir():raise RuntimeError("SITE_PENDING_NO_FACTORY_AREA")
    queue=area/"zomorod-site-pending"
    if queue.is_symlink():raise RuntimeError("SITE_PENDING_SYMLINK")
    engine.ensure_private(queue)
    serial=match.group("run") or "00000"
    prefix="ZR-"+day.strftime("%Y%m%d")+"-R"+serial+"-"
    ids=[prefix+f"0{n}" for n in (1,2,3)]
    receipt=queue/("receipt-"+cycle+".json")
    with (area/".orders.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        files=[]
        for path in sorted(queue.iterdir()):
            if path.is_symlink() or not path.is_file():raise RuntimeError("SITE_PENDING_UNEXPECTED_ENTRY")
            if not REQUEST.fullmatch(path.name) and not path.name.startswith("receipt-"):
                raise RuntimeError("SITE_PENDING_UNEXPECTED_ENTRY")
            if REQUEST.fullmatch(path.name):files.append(path)
        if receipt.exists():
            if receipt.is_symlink() or not receipt.is_file():raise RuntimeError("SITE_PENDING_BAD_RECEIPT")
            document=engine.read_json(receipt,max_bytes=15000)
            if document.get("request_ids")!=ids or document.get("state")!="awaiting_factory_capacity":
                raise RuntimeError("SITE_PENDING_RECEIPT_CONFLICT")
            for name in ids:
                path=queue/(name+".json")
                if not path.is_file() or path.is_symlink():raise RuntimeError("SITE_PENDING_INCOMPLETE")
                value=engine.read_json(path,max_bytes=15000)
                if value.get("id")!=name or value.get("state")!="awaiting_factory_capacity":
                    raise RuntimeError("SITE_PENDING_REQUEST_CONFLICT")
            return {"status":"awaiting_factory_capacity","request_ids":ids,"new_requests":0,
                    "native_order_ids":[],"native_orders_new":0}
        existing_ids={x.name for x in files}
        this_cycle=[x for x in files if x.name.startswith(prefix)]
        # Recover an interrupted run only if its existing records match.
        if any(x.name not in {name+".json" for name in ids} for x in this_cycle):
            raise RuntimeError("SITE_PENDING_REQUEST_CONFLICT")
        active=0
        for p in files:
            info=engine.read_json(p,max_bytes=15000)
            if info.get("state")=="awaiting_factory_capacity":active+=1
        missing=len(ids)-len(this_cycle)
        if active+missing>max_pending:raise RuntimeError("SITE_PENDING_CAPACITY_REACHED")
        selected=[]
        for slot in (1,2,3):
            profile=profiles[((day.toordinal()*3)+(slot-1))%40]
            name=ids[slot-1]
            task={"schema":"saeit.zomorod.pending-production-request.v1",
                  "id":name,"site":"zomorodmelal.ir","bridge_cycle":cycle,
                  "slot":slot,"family_id":profile["id"],"family_name":profile["name_fa"],
                  "state":"awaiting_factory_capacity","native_factory_accepted":False,
                  "native_factory_order_id":None,"commercial_release":False,
                  "public_distribution_allowed":False,
                  "quality_gate":"factory_capacity_then_actual_artifact_QA_and_owner_approval",
                  "created_utc":engine.stamp(),
                  "intent_sha256":hashlib.sha256((cycle+str(slot)+profile["id"]).encode()).hexdigest()}
            selected.append(task)
        for item in selected:
            p=queue/(item["id"]+".json")
            if p.exists():
                if p.is_symlink() or engine.read_json(p,max_bytes=15000).get("intent_sha256")!=item["intent_sha256"]:
                    raise RuntimeError("SITE_PENDING_REQUEST_CONFLICT")
                continue
            engine.atomic_json(p,item)
        engine.atomic_json(receipt,{"schema":"saeit.zomorod.pending-batch-receipt.v1",
             "cycle":cycle,"state":"awaiting_factory_capacity",
             "request_ids":ids,"native_order_ids":[],"accepted_into_factory":False,
             "site":"zomorodmelal.ir"})
        return {"status":"awaiting_factory_capacity","request_ids":ids,
                "new_requests":missing,"native_order_ids":[],"native_orders_new":0}
