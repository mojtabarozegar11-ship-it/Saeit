#!/usr/bin/env python3
"""MojPlayWin-only factory order issuer. Three durable instructions per unique courier run.

Orders are not manufactured artifacts. No sale, publication or inferred approval.
Reuses the existing native production-instructions contract and lock.
"""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import re

TENANT = "mojplaywin-main"
SITE = "mojplaywin.com"
SCHEMA = "saeit.factory.production-instructions.v1"
RECEIPT_SCHEMA = "mpw.factory.three-orders.v1"
CYCLE = re.compile(r"^[0-9]{8}-[0-9]{8,20}$")
FAMILIES = (
    ("F14", "browser_games", "Build a distinct browser game prototype with original assets, accessibility, mobile controls, reproducible gameplay tests and fair non-manipulative progression."),
    ("F02", "fiction_books", "Develop an original illustrated digital storybook with editorial review, child-appropriate narrative and documented asset rights."),
    ("F12", "mobile_games", "Design an original mobile game prototype with tested core loop, privacy-safe telemetry and reusable assets."),
    ("F18", "web_apps", "Build a useful interactive web application or educational mini-game with accessibility and security tests."),
    ("F10", "assessment_packs", "Develop a playable learning and assessment pack with measurable goals and fact-reviewed explanations."),
    ("F40", "audiobooks", "Prepare a rights-cleared narrated audio product with verified text provenance, audio quality and usable packaging."),
)

def _module(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("NATIVE_ORDERS_ENGINE_MISSING")
    spec = importlib.util.spec_from_file_location("mpw_native_orders", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _verify_existing(engine, orders):
    result = []
    for path in sorted(orders.iterdir()):
        if not path.is_file() or path.is_symlink() or not engine.ORDER_RE.fullmatch(path.name):
            raise RuntimeError("NATIVE_ORDER_QUEUE_UNSAFE_ENTRY")
        result.append(engine.validate_old(path))
        if len(result) > engine.MAX_ORDERS:
            raise RuntimeError("NATIVE_ORDER_QUEUE_LIMIT")
    return result

def issue_three(root, native_engine, cycle, *, dry_run=False, max_active=297):
    if not CYCLE.fullmatch(cycle):
        raise ValueError("INVALID_MPW_CYCLE")
    dt.datetime.strptime(cycle[:8], "%Y%m%d")
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("FACTORY_PRIVATE_ROOT_MISSING")
    engine = _module(native_engine) if isinstance(native_engine, (str, Path)) else native_engine
    area = root / "production-instructions"
    orders = area / "orders"
    if area.is_symlink() or orders.is_symlink() or not orders.is_dir():
        raise RuntimeError("NATIVE_ORDER_QUEUE_NOT_READY")
    receipt_dir = area / "mojplaywin-order-receipts"
    engine.ensure_private(receipt_dir)
    receipt_path = receipt_dir / (cycle + ".json")
    lock_path = area / ".orders.lock"
    if lock_path.is_symlink():
        raise RuntimeError("NATIVE_ORDER_LOCK_SYMLINK")
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        old = _verify_existing(engine, orders)
        ours = [x for x in old if x.get("requesting_site") == SITE and x.get("bridge_cycle") == cycle]
        slots = {x.get("bridge_slot") for x in ours}
        if len(ours) > 3 or len(slots) != len(ours) or slots - {1, 2, 3}:
            raise RuntimeError("MPW_EXISTING_CYCLE_CORRUPTED")
        if receipt_path.exists() or receipt_path.is_symlink():
            if receipt_path.is_symlink():
                raise RuntimeError("MPW_RECEIPT_SYMLINK")
            receipt = engine.read_json(receipt_path, max_bytes=100_000)
            if (receipt.get("schema") != RECEIPT_SCHEMA or
                    receipt.get("requesting_site") != SITE or
                    receipt.get("cycle") != cycle):
                raise RuntimeError("MPW_RECEIPT_MISMATCH")
            if receipt.get("status") == "waiting_for_native_capacity":
                requests = receipt.get("requests")
                if not isinstance(requests,list) or len(requests)!=3 or len(set(requests))!=3:
                    raise RuntimeError("MPW_DEFERRED_ORDER_RECEIPT_INVALID")
                inbox = area / "mojplaywin-pending-instructions"
                for request in requests:
                    candidate = inbox / (request + ".json")
                    if not candidate.is_file() or candidate.is_symlink():
                        raise RuntimeError("MPW_DEFERRED_ORDER_NOT_DURABLE")
                    entry=engine.read_json(candidate,max_bytes=100_000)
                    if entry.get("site")!=SITE or entry.get("cycle")!=cycle:
                        raise RuntimeError("MPW_DEFERRED_ORDER_SCOPE_MISMATCH")
                return {"status":"waiting_for_native_capacity", "orders":[],
                        "requests":requests, "new":0, "requested":3,
                        "native_accepted":0, "publications":0, "manufacturing_claimed":False}
            expected = [x["id"] for x in sorted(ours, key=lambda x:x["bridge_slot"])]
            if receipt.get("orders") != expected or len(expected) != 3:
                raise RuntimeError("MPW_RECEIPT_MISMATCH")
            return {"status":"already_issued", "orders":expected, "new":0,
                    "requested":3, "native_accepted":3,
                    "publications":0, "manufacturing_claimed":False}
        missing = 3 - len(ours)
        active = sum(x["status"] != "completed_verified" for x in old)
        if active + missing > max_active or len(old) + missing > engine.MAX_ORDERS:
            # The factory currently holds a full native queue. Accept exactly
            # three site requests into a separate bounded PRIVATE inbox instead
            # of inventing native acceptance or overflowing its production limit.
            inbox=area/"mojplaywin-pending-instructions"
            engine.ensure_private(inbox)
            existing_requests=list(inbox.glob("*.json"))
            if len(existing_requests)+3>1000:
                raise RuntimeError("MPW_DEFERRED_SITE_INBOX_CAPACITY_REACHED")
            seed=int(cycle.split("-")[1])%len(FAMILIES)
            requests=[]
            for slot in (1,2,3):
                family,slug,instruction=FAMILIES[(seed+slot-1)%len(FAMILIES)]
                identity="MPW-"+cycle+"-S"+str(slot)
                file=inbox/(identity+".json")
                if file.exists() or file.is_symlink():
                    raise RuntimeError("MPW_DUPLICATE_DEFERRED_INSTRUCTION")
                engine.atomic_json(file,{"schema":RECEIPT_SCHEMA,
                    "request_id":identity,"site":SITE,"tenant":TENANT,
                    "cycle":cycle,"slot":slot,"family_id":family,"family_slug":slug,
                    "instruction":instruction,"status":"waiting_for_native_capacity",
                    "created_utc":engine.stamp(),"native_order_id":None,
                    "commercial_approval":False,"manufactured":False})
                requests.append(identity)
            engine.atomic_json(receipt_path,{"schema":RECEIPT_SCHEMA,
                "requesting_site":SITE,"tenant":TENANT,"cycle":cycle,
                "status":"waiting_for_native_capacity","requests":requests,
                "orders":[],"native_accepted":0,"requested":3,
                "capacity_reason":"NATIVE_FACTORY_300_PENDING_BACKLOG"})
            return {"status":"waiting_for_native_capacity","orders":[],
                    "requests":requests,"requested":3,"new":3,
                    "native_accepted":0,"publications":0,
                    "manufacturing_claimed":False}
        next_id = max((int(x["id"][3:]) for x in old), default=0) + 1
        # Rotate by run ID; same rerun always has same exact three family slots.
        seed = int(cycle.split("-")[1]) % len(FAMILIES)
        to_write = []
        for slot in (1,2,3):
            if slot in slots:
                continue
            family,slug,instruction = FAMILIES[(seed + slot - 1) % len(FAMILIES)]
            task = {
                "origin":"site-topic-snapshot",
                "source_product_id":"MPW"+cycle.replace("-","")+"S"+str(slot),
                "source_sha256":hashlib.sha256((cycle+str(slot)+slug+SITE).encode()).hexdigest(),
                "phase":"engineering_specification", "slot":slot,
                "subject":"MojPlayWin original digital product — "+slug,
                "instruction":instruction+" Record executable source, actual tests and observed defect evidence. The family may require an unimplemented specialist adapter; do not report a manufactured product until built.",
                "acceptance":["New functioning version and independently reproducible tests",
                              "Documented source provenance and verified third-party licenses",
                              "Product-specific content/factual QA and defect repair loop",
                              "Authorized owner release and store compatibility check"],
                "technical_product_release":False
            }
            order = dict(task, schema=SCHEMA, id="WO-"+str(next_id).zfill(8),
                fingerprint=engine.fingerprint(task), created_utc=engine.stamp(),
                status="issued", instruction_kind="private_factory_work_order",
                requesting_site=SITE, tenant=TENANT, bridge_cycle=cycle, bridge_slot=slot,
                family_id=family, family_slug=slug, independent_of_websites=False,
                requires_customer_order=False, api_required=False,
                manufacturing_qa_passed=False, publication_approved=False,
                public_distribution_allowed=False, warehouse_goods_created=False)
            if any(x["fingerprint"] == order["fingerprint"] for x in old):
                raise RuntimeError("MPW_ORDER_FINGERPRINT_COLLISION")
            next_id += 1
            to_write.append(order)
        current = sorted(ours + to_write, key=lambda x:x["bridge_slot"])
        ids = [x["id"] for x in current]
        if len(ids) != 3 or len(set(ids)) != 3:
            raise RuntimeError("MPW_NOT_EXACTLY_THREE_ORDERS")
        if not dry_run:
            for item in to_write:
                dest = orders / (item["id"] + ".json")
                if dest.exists() or dest.is_symlink():
                    raise RuntimeError("MPW_ORDER_ID_COLLISION")
                engine.atomic_json(dest, item)
            engine.atomic_json(receipt_path, {
                "schema":RECEIPT_SCHEMA, "tenant":TENANT, "requesting_site":SITE,
                "cycle":cycle, "orders":ids, "issued_new":len(to_write), "requested":3, "native_accepted":3,
                "manufactured_products_verified":0, "store_publication":False})
        return {"status":"dry_run" if dry_run else "issued",
                "orders":ids, "new":0 if dry_run else len(to_write),
                "requested":3, "native_accepted":0 if dry_run else 3,
                "publications":0, "manufacturing_claimed":False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--factory-private",required=True)
    parser.add_argument("--native-engine",required=True)
    parser.add_argument("--cycle",required=True)
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    result=issue_three(args.factory_private,args.native_engine,args.cycle,dry_run=args.dry_run)
    print("MPW_FACTORY_THREE_ORDERS="+json.dumps(result,sort_keys=True))

if __name__=="__main__":
    main()
