#!/usr/bin/env python3
"""Zomorod-only VPS-to-site bridge: 3 idempotent private factory work orders per
daily cycle, and up to 3 independently QA-passed warehouse products delivered
via the pre-existing pinned SSH sender into the site's private inbox.
Does not change the factory's own autonomous orders; no selling or auto-approval.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile

SCHEMA="saeit.factory.production-instructions.v1"
CYCLE=re.compile(r"^(?P<day>[0-9]{4}-[0-9]{2}-[0-9]{2})(?:-r(?P<run>[0-9]{5,20}))?$")
ID=re.compile(r"^WO-[0-9]+$")
FAMILY=re.compile(r"^F(?:0[1-9]|[1-3][0-9]|40)$")
SHA=re.compile(r"^[a-f0-9]{64}$")


def read_module(path,name):
    path=Path(path)
    if not path.is_file() or path.is_symlink():raise RuntimeError("MODULE_INVALID")
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def registry(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>300000:
        raise ValueError("FAMILY_REGISTRY_MISSING")
    doc=json.loads(path.read_text(encoding="utf8"))
    if doc.get("schema")!="saeit.factory.family-registry.v1":raise ValueError("FAMILY_REGISTRY_SCHEMA")
    profiles=doc.get("profiles",[])
    if len(profiles)!=40 or sorted(x.get("id") for x in profiles)!=["F"+str(i).zfill(2) for i in range(1,41)]:
        raise ValueError("FACTORY_40_FAMILIES_INVALID")
    if any(not FAMILY.fullmatch(x.get("id","")) or not x.get("name_fa") for x in profiles):
        raise ValueError("FACTORY_FAMILY_ENTRY_INVALID")
    return profiles


def orders_once(root,engine,profiles,cycle,*,dry_run=False,max_active=300):
    root=Path(root)
    found=CYCLE.fullmatch(cycle)
    if not found:raise ValueError("CYCLE_ID_INVALID")
    dt.date.fromisoformat(found.group("day"))
    if root.is_symlink() or not root.is_dir():raise RuntimeError("FACTORY_PRIVATE_ROOT_INVALID")
    area=root/"production-instructions"
    orderdir=area/"orders"
    if area.is_symlink() or orderdir.is_symlink() or not orderdir.is_dir():
        raise RuntimeError("FACTORY_NATIVE_ORDER_QUEUE_NOT_READY")
    receipt_dir=area/"zomorod-site-order-receipts"
    engine.ensure_private(receipt_dir)
    receipt=receipt_dir/(cycle+".json")
    lock=area/".orders.lock"
    with lock.open("a+b") as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
        existing=[]
        for file in sorted(orderdir.iterdir()):
            if file.is_symlink() or not file.is_file() or not engine.ORDER_RE.fullmatch(file.name):
                raise RuntimeError("FACTORY_NATIVE_ORDER_ENTRY_UNSAFE")
            existing.append(engine.validate_old(file))
        ours=[v for v in existing if v.get("requesting_site")=="zomorodmelal.ir"
              and v.get("bridge_cycle")==cycle]
        if len(ours)>3:raise RuntimeError("SITE_BRIDGE_DUPLICATE_ORDERS")
        slots={v.get("bridge_slot") for v in ours}
        if len(slots)!=len(ours) or any(s not in (1,2,3) for s in slots):
            raise RuntimeError("SITE_BRIDGE_EXISTING_ORDER_CONFLICT")
        if receipt.is_file():
            value=json.loads(receipt.read_text(encoding="utf8"))
            confirmed=[r["id"] for r in sorted(ours,key=lambda x:x["bridge_slot"])]
            if value.get("orders")!=confirmed or len(confirmed)!=3:
                raise RuntimeError("SITE_BRIDGE_RECEIPT_MISMATCH")
            return {"status":"already_issued","orders":confirmed,"new":0}
        # Research-evidence rework is tracked by the 12-stage governance plane;
        # it is not a manufacturable order. Keep every old WO intact, but do not
        # consume the separate site/manufacturing capacity with those records.
        # Unknown or unproven tasks still count against the manufacturing cap.
        def production_capacity_used(item):
            if item["status"]=="completed_verified":return False
            evidence_only=(
                item.get("phase")=="research_rework"
                and item.get("origin")=="local-factory-research"
                and isinstance(item.get("blocker"),str)
                and bool(item["blocker"].strip())
                and item.get("requesting_site") is None
            )
            return not evidence_only
        active=sum(production_capacity_used(item) for item in existing)
        missing=3-len(ours)
        # Select different real registered product families, rotate daily.
        day=dt.date.fromisoformat(found.group("day")).toordinal() + (int(found.group("run") or 0) % 40)
        selected=[profiles[((day*3)+(i-1))%40] for i in (1,2,3)]
        next_id=max([int(v["id"][3:]) for v in existing],default=0)+1
        to_write=[]
        for slot,profile in enumerate(selected,1):
            if slot in slots:continue
            slug=profile["slug"]
            title="زمرد ملل — طراحی محصول اصیل در خانواده "+profile["id"]+" ("+str(profile["name_fa"])+")"
            instruction=(
              "سفارش تولید از فروشگاه Zomorodmelal.ir برای خانواده ثبت‌شده "+profile["id"]+
              " و دسته "+str(profile["name_fa"])+". ابتدا کاربرد قابل عرضه برای مخاطبان سایت را "
              "بر اساس شواهد واقعی انتخاب کنید؛ مشخصات فنی دقیق، طراحی اصیل، بسته محصول واقعی، "
              "تست تکرارپذیر، منشأ محتوای علمی، حقوق مؤلف، راهنمای استفاده و گواهی SHA256 ارائه شود. "
              "هر شکست کنترل کیفیت برای اصلاح به مرحله طراحی برگردد. "
              "بدون تایید تخصصی و تجاری محصول را قابل فروش یا منتشرشده اعلام نکنید."
            )
            task={"origin":"site-topic-snapshot","source_product_id":"ZM"+cycle.replace("-","")+str(slot),
                  "source_sha256":hashlib.sha256((cycle+str(slot)+slug).encode()).hexdigest(),
                  "phase":"engineering_specification","slot":slot,"subject":title,
                  "instruction":instruction,"technical_product_release":False,
                  "acceptance":["Executable new artifact and reproducible tests",
                                "Real sources with evidence and licensing",
                                "Independent QA with rework on failure",
                                "Owner commercial review before public sale"]}
            fingerprint=engine.fingerprint(task)
            match=[x for x in existing if x.get("fingerprint")==fingerprint]
            if match:raise RuntimeError("FACTORY_SITE_ORDER_ALREADY_EXISTS_WITH_DIFFERENT_CYCLE")
            oid="WO-"+str(next_id).zfill(8);next_id+=1
            order=dict(task,schema=SCHEMA,id=oid,fingerprint=fingerprint,
                created_utc=engine.stamp(),status="issued",
                instruction_kind="private_factory_work_order",
                requesting_site="zomorodmelal.ir",bridge_cycle=cycle,bridge_slot=slot,
                family_id=profile["id"],independent_of_websites=False,
                requires_customer_order=False,api_required=False,
                manufacturing_qa_passed=False,publication_approved=False,
                public_distribution_allowed=False,warehouse_goods_created=False)
            to_write.append(order)
        if not dry_run:
            for item in to_write:
                target=orderdir/(item["id"]+".json")
                if target.exists() or target.is_symlink():raise RuntimeError("ORDER_ID_COLLISION")
                engine.atomic_json(target,item)
            current=ours+to_write
            confirmed=[x["id"] for x in sorted(current,key=lambda x:x["bridge_slot"])]
            if len(confirmed)!=3:raise RuntimeError("NOT_EXACTLY_THREE")
            engine.atomic_json(receipt,{"schema":"saeit.zomorod.site-factory-bridge.v1",
                "cycle":cycle,"orders":confirmed,"issued_new":len(to_write),
                "site":"zomorodmelal.ir","commercial_release":False})
        else:
            confirmed=[x["id"] for x in sorted(ours+to_write,key=lambda x:x["bridge_slot"])]
        return {"status":"issued" if to_write else "already_issued",
                "orders":confirmed,"new":len(to_write) if not dry_run else 0}


def stage_three_requests(root,engine,profiles,cycle,*,max_cycles=120):
    """Durable intake, not a native WO order. Three distinct requests per cycle."""
    match=CYCLE.fullmatch(cycle)
    if not match:raise ValueError("CYCLE_ID_INVALID")
    dt.date.fromisoformat(match.group("day"))
    root=Path(root)
    area=root/"production-instructions"
    if root.is_symlink() or not area.is_dir() or area.is_symlink():
        raise RuntimeError("FACTORY_NATIVE_ORDER_QUEUE_NOT_READY")
    intake=area/"zomorod-site-intake"
    engine.ensure_private(intake)
    path=intake/(cycle+".json")
    if path.is_symlink():raise RuntimeError("SITE_INTAKE_UNSAFE_ENTRY")
    # Serialized site-only intake and reconciliation across concurrent bridge runs.
    with (intake/".intake.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        valid_files=[]
        for entry in sorted(intake.iterdir()):
            if entry.name==".intake.lock":continue
            if entry.is_symlink() or not entry.is_file() or not entry.name.endswith(".json") or not CYCLE.fullmatch(entry.stem):
                raise RuntimeError("SITE_INTAKE_UNSAFE_ENTRY")
            valid_files.append(entry)
        if path.is_file():
            doc=json.loads(path.read_text(encoding="utf8"))
            _verify_site_intake(doc,path.stem)
            return doc,False
        day=dt.date.fromisoformat(match.group("day")).toordinal()+(int(match.group("run") or 0)%40)
        chosen=[profiles[((day*3)+(i-1))%40] for i in (1,2,3)]
        requests=[]
        for index,profile in enumerate(chosen,1):
            if not FAMILY.fullmatch(str(profile.get("id",""))):
                raise ValueError("FACTORY_FAMILY_ENTRY_INVALID")
            ident="ZMREQ-"+hashlib.sha256((cycle+"|"+str(index)+"|"+profile["id"]).encode()).hexdigest()[:20]
            requests.append({"request_id":ident,"slot":index,"family_id":profile["id"],
                "family_name":str(profile["name_fa"])[:150],
                "state":"awaiting_native_capacity","native_work_order":None})
        doc={"schema":"saeit.zomorod.site-factory-intake.v1","site":"zomorodmelal.ir",
            "cycle":cycle,"created_utc":engine.stamp(),"requests":requests,
            "is_native_order":False,"is_manufactured":False,"public_distribution":False}
        _verify_site_intake(doc,cycle)
        engine.atomic_json(path,doc)
        return doc,True


def _verify_site_intake(doc,cycle):
    if doc.get("schema")!="saeit.zomorod.site-factory-intake.v1" or doc.get("site")!="zomorodmelal.ir" or doc.get("cycle")!=cycle:
        raise RuntimeError("SITE_INTAKE_SCHEMA_INVALID")
    requests=doc.get("requests")
    if not isinstance(requests,list) or len(requests)!=3 or {v.get("slot") for v in requests}!={1,2,3}:
        raise RuntimeError("SITE_INTAKE_THREE_REQUESTS_INVALID")
    for v in requests:
        if not isinstance(v,dict) or not re.fullmatch(r"ZMREQ-[0-9a-f]{20}",str(v.get("request_id",""))) or not FAMILY.fullmatch(str(v.get("family_id",""))):
            raise RuntimeError("SITE_INTAKE_REQUEST_INVALID")
        if v.get("state") not in ("awaiting_native_capacity","admitted") or (
          v.get("state")=="admitted" and (not isinstance(v.get("native_work_order"),str) or not re.fullmatch(r"WO-[0-9]+",v["native_work_order"]))):
            raise RuntimeError("SITE_INTAKE_REQUEST_STATE_INVALID")
    if doc.get("is_native_order") is not False or doc.get("public_distribution") is not False:
        raise RuntimeError("SITE_INTAKE_PRIVACY_INVALID")


def reconcile_site_intake(root,engine,profiles,*,max_admit_cycles=1,max_active=300):
    """Promote staged site orders with manufacturing-only capacity accounting."""
    area=Path(root)/"production-instructions"
    intake=area/"zomorod-site-intake"
    if intake.is_symlink() or not intake.is_dir():
        raise RuntimeError("SITE_INTAKE_NOT_READY")
    lock_path=intake/".intake.lock"
    result={"admitted_cycles":0,"orders":[],"capacity_blocked":False,
        "waiting_cycles":0}
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        files=[]
        for p in sorted(intake.iterdir(),key=lambda x:x.name):
            if p.name==".intake.lock":continue
            if p.is_symlink() or not p.is_file() or not p.name.endswith(".json") or not CYCLE.fullmatch(p.stem):
                raise RuntimeError("SITE_INTAKE_UNSAFE_ENTRY")
            files.append(p)
        for p in files:
            doc=json.loads(p.read_text(encoding="utf8"))
            _verify_site_intake(doc,p.stem)
            if all(v["state"]=="admitted" for v in doc["requests"]):
                continue
            if result["admitted_cycles"]>=max_admit_cycles:
                result["waiting_cycles"]+=1
                continue
            try:
                admitted=orders_once(root,engine,profiles,p.stem,max_active=max_active)
            except RuntimeError as e:
                if str(e)!="FACTORY_PENDING_CAPACITY_REACHED":raise
                result["capacity_blocked"]=True
                result["waiting_cycles"]+=1
                continue
            ids=admitted["orders"]
            if len(ids)!=3:raise RuntimeError("SITE_INTAKE_ADMISSION_INCOMPLETE")
            by_slot={i+1:value for i,value in enumerate(ids)}
            for row in doc["requests"]:
                row["state"]="admitted"
                row["native_work_order"]=by_slot[row["slot"]]
            doc["admitted_utc"]=engine.stamp()
            doc["is_native_order"]=False
            engine.atomic_json(p,doc)
            result["admitted_cycles"]+=1
            result["orders"].extend(ids)
    return result


def deliver_stock(factory_root,ware,warehouse_module,sender,ssh_key,ssh_hosts,max_products=3,*,dry_run=False):
    root=Path(factory_root)
    warehouse=Path(ware)
    inventory=warehouse_module.stock_summary(warehouse)
    # No undefined new product: confirm warehouse entry matches the current
    # finished source-manifest and is not in QA rework, then existing sender
    # transports private, SHA-checked packages to cPanel receiver.
    options=sender.host_ssh_options(Path(ssh_key),Path(ssh_hosts))
    results=[]
    if max_products==0 or not inventory:return results
    # Rotate stock position across UTC days so older receipts cannot forever
    # starve new warehouse versions; already_received does not use ship quota.
    offset=(dt.datetime.now(dt.timezone.utc).date().toordinal()*3)%len(inventory)
    rotated=inventory[offset:]+inventory[:offset]
    checked=0
    for row in rotated:
        if len(results)>=max_products or checked>=min(len(inventory),max_products*8):break
        recipe=row["product_id"]
        if row["manufacturing_qc"]!="passed" or row["commercial_release"] is not False:continue
        source=root/"digital-products"/recipe/"manufacturing_manifest.json"
        if source.is_symlink() or not source.is_file():continue
        doc=json.loads(source.read_text(encoding="utf8"))
        if doc.get("source_sha256")!=row["version"] or doc.get("artifact_sha256")!=row["artifact_sha256"]:
            continue
        checked+=1
        try:
            result=sender.deliver(recipe,root/"digital-products",options,dry_run=dry_run)
            if result.get("status")!="already_received":
                results.append(result)
        except (OSError,ValueError,RuntimeError) as e:
            results.append({"recipe":recipe,"status":"blocked_"+type(e).__name__})
    return results


def deliver_customer_bundles(root,sender,ssh_key,ssh_hosts,max_products=3,*,dry_run=False):
    """Fair, durable private-courier scan across the entire customer catalog.

    A static newest-first scan capped at 3*8 would revisit the same 24 already
    delivered records forever once a catalog grows. A private, locked cursor
    advances after every bounded scan so older verified products get a turn.
    The cursor is deliberately NOT a manufacturing/publication approval.
    """
    root=Path(root)
    offers=root/"customer-packs"
    if root.is_symlink() or not root.is_dir() or offers.is_symlink():
        raise ValueError("CUSTOMER_CATALOG_SYMLINK")
    if max_products==0 or not offers.is_dir():return []
    options=sender.host_ssh_options(Path(ssh_key),Path(ssh_hosts))
    candidates=[]
    for recipe in offers.iterdir():
        if recipe.name=="status.json":continue
        if recipe.is_symlink() or not recipe.is_dir() or not sender.SLUG.fullmatch(recipe.name):
            raise ValueError("CUSTOMER_CATALOG_UNSAFE_ENTRY")
        for version in recipe.iterdir():
            if version.is_symlink() or not version.is_dir() or not sender.SHA.fullmatch(version.name):
                raise ValueError("CUSTOMER_VERSION_UNSAFE_ENTRY")
            receipt=version/"candidate_manifest.json"
            if receipt.is_symlink() or not receipt.is_file():continue
            candidates.append((receipt.stat().st_mtime,recipe.name,version.name))
            if len(candidates)>4000:raise ValueError("CUSTOMER_CATALOG_CAPACITY_LIMIT")
    candidates.sort(key=lambda x:(x[0],x[1],x[2]),reverse=True)
    if not candidates:return []
    cursor=root/".zomorod-customer-courier.cursor.json"
    mutex=root/".zomorod-customer-courier.lock"
    if cursor.is_symlink() or mutex.is_symlink():
        raise ValueError("CUSTOMER_COURIER_CURSOR_UNSAFE")
    flags=os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(mutex,flags,0o600)
    with os.fdopen(fd,"r+b") as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
        previous=None
        if cursor.exists():
            if cursor.is_symlink() or not cursor.is_file() or cursor.stat().st_size>1024:
                raise ValueError("CUSTOMER_COURIER_CURSOR_UNSAFE")
            saved=json.loads(cursor.read_text(encoding="utf8"))
            if not isinstance(saved,dict) or saved.get("schema")!="saeit.zomorod.private-courier.v1":
                raise ValueError("CUSTOMER_COURIER_CURSOR_INVALID")
            previous=saved.get("last_scanned")
            if not isinstance(previous,str) or not re.fullmatch(
                r"[a-z][a-z0-9_]{0,63}:[0-9a-f]{64}",previous
            ):
                raise ValueError("CUSTOMER_COURIER_CURSOR_INVALID")
        keys=[recipe+":"+version for _,recipe,version in candidates]
        offset=(keys.index(previous)+1)%len(keys) if previous in keys else 0
        rotated=candidates[offset:]+candidates[:offset]
        shipped=[];scanned=0;last_scanned=None
        for _,recipe,version in rotated:
            if len(shipped)>=max_products or scanned>=min(len(candidates),max_products*8):break
            scanned+=1
            last_scanned=recipe+":"+version
            try:
                sender.verify_consumer_source(root,recipe,version)
                original=sender.deliver(recipe,root/"digital-products",options,dry_run=dry_run)
                if original.get("status") not in ("received_private","already_received","dry_run_private_only"):
                    raise RuntimeError("CUSTOMER_ORIGINAL_NOT_RECEIVED")
                item=sender.deliver_consumer(recipe,root,version,options,dry_run=dry_run)
                if item.get("status")!="already_received_customer":
                    shipped.append(item)
            except (OSError,ValueError,RuntimeError) as exc:
                shipped.append({"recipe":recipe,"version":version,
                                "status":"blocked_"+type(exc).__name__})
        if last_scanned is not None and not dry_run:
            # Cursor writes do not change receipts, stock, approvals or payments.
            # Preserve progress atomically so a failed/restarted workflow can
            # resume without perpetually rescanning just the newest products.
            payload=json.dumps({
                "schema":"saeit.zomorod.private-courier.v1",
                "last_scanned":last_scanned
            },sort_keys=True).encode("utf8")+b"\n"
            temp_fd,temp_path=tempfile.mkstemp(prefix=".courier-cursor-",dir=str(root))
            try:
                with os.fdopen(temp_fd,"wb") as out:
                    os.fchmod(out.fileno(),0o600)
                    out.write(payload)
                    out.flush()
                    os.fsync(out.fileno())
                if cursor.is_symlink():
                    raise ValueError("CUSTOMER_COURIER_CURSOR_UNSAFE")
                os.replace(temp_path,cursor)
            finally:
                if os.path.exists(temp_path):os.unlink(temp_path)
        return shipped


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--orders-engine",required=True)
    p.add_argument("--warehouse-module",required=True)
    p.add_argument("--sender-module",required=True)
    p.add_argument("--families",required=True)
    p.add_argument("--ssh-key",required=True)
    p.add_argument("--known-hosts",required=True)
    p.add_argument("--cycle",default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"))
    p.add_argument("--max-ship",type=int,default=3)
    p.add_argument("--dry-run",action="store_true")
    a=p.parse_args()
    if not 0<=a.max_ship<=3:raise ValueError("MAX_SHIP_INVALID")
    base=Path(a.factory_private)
    engine=read_module(a.orders_engine,"zm_existing_orders_engine")
    ware=read_module(a.warehouse_module,"zm_existing_warehouse")
    sender=read_module(a.sender_module,"zm_existing_sender")
    family=registry(a.families)
    if a.dry_run:
        # No mutation of native queue or intake in read-only dry runs.
        try:
            order=orders_once(base,engine,family,a.cycle,dry_run=True)
        except RuntimeError as err:
            if str(err)!="FACTORY_PENDING_CAPACITY_REACHED":raise
            order={"status":"capacity_blocked","orders":[],"new":0}
        staged={"status":"dry_run_no_intake_write","requests":[]}
        admission={"admitted_cycles":0,"orders":[],"capacity_blocked":order["status"]=="capacity_blocked","waiting_cycles":0}
    else:
        doc,created=stage_three_requests(base,engine,family,a.cycle)
        staged={"status":"staged" if created else "already_staged",
                "requests":[v["request_id"] for v in doc["requests"]],
                "cycle":a.cycle}
        admission=reconcile_site_intake(base,engine,family)
    # Store delivery must not be blocked by the independent native order backlog.
    results=deliver_stock(base,base/"production-warehouse",ware,sender,a.ssh_key,
                          a.known_hosts,a.max_ship,dry_run=a.dry_run)
    consumer=deliver_customer_bundles(base,sender,a.ssh_key,a.known_hosts,
                                      a.max_ship,dry_run=a.dry_run)
    print("ZM_BRIDGE_SITE_REQUEST_RECEIPT="+json.dumps(staged,ensure_ascii=False,sort_keys=True))
    print("ZM_BRIDGE_NATIVE_ADMISSION="+json.dumps(admission,ensure_ascii=False,sort_keys=True))
    print("ZM_BRIDGE_DELIVERED_PRIVATE="+json.dumps(results,ensure_ascii=False,sort_keys=True))
    print("ZM_BRIDGE_CUSTOMER_PACKAGES_DELIVERED_PRIVATE="+json.dumps(consumer,ensure_ascii=False,sort_keys=True))
    print("ZM_BRIDGE_CUSTOMER_PACKAGES_NEW="+str(sum(x.get("status")=="received_private_customer" for x in consumer)))
    print("ZM_BRIDGE_REAL_CUSTOMER_PURCHASE_ORDERS_CONFIRMED=0")
    print("ZM_BRIDGE_REQUESTS_THIS_CYCLE="+str(len(staged["requests"])))
    print("ZM_BRIDGE_NATIVE_ORDERS_ADMITTED="+str(len(admission["orders"])))
    print("ZM_BRIDGE_NATIVE_CAPACITY_BLOCKED="+str(admission["capacity_blocked"]).lower())
    print("ZM_BRIDGE_PUBLIC_SALES_ENABLED=false")


if __name__=="__main__":
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError,json.JSONDecodeError) as err:
        # Never log paths, SSH details, credentials or arbitrary exception strings.
        # Expose only exact, hard-coded operational blocker codes to GitHub Actions.
        safe_codes={
            "MODULE_INVALID","FAMILY_REGISTRY_MISSING","FAMILY_REGISTRY_SCHEMA",
            "FACTORY_40_FAMILIES_INVALID","FACTORY_FAMILY_ENTRY_INVALID",
            "CYCLE_ID_INVALID","FACTORY_PRIVATE_ROOT_INVALID",
            "FACTORY_NATIVE_ORDER_QUEUE_NOT_READY","FACTORY_NATIVE_ORDER_ENTRY_UNSAFE",
            "SITE_BRIDGE_DUPLICATE_ORDERS","SITE_BRIDGE_EXISTING_ORDER_CONFLICT",
            "SITE_BRIDGE_RECEIPT_MISMATCH","FACTORY_PENDING_CAPACITY_REACHED",
            "FACTORY_SITE_ORDER_ALREADY_EXISTS_WITH_DIFFERENT_CYCLE",
            "ORDER_ID_COLLISION","NOT_EXACTLY_THREE",
            "ORDERS_EXISTING_RECORD_INVALID","ORDERS_EXISTING_RECORD_UNSAFE",
            "ORDERS_BAD_WORK_STATE","ORDERS_BAD_RECORD_FINGERPRINT",
            "ORDERS_UNSAFE_DIRECTORY","ORDERS_SYMLINK_PARENT",
            "SITE_INTAKE_SCHEMA_INVALID","SITE_INTAKE_THREE_REQUESTS_INVALID",
            "SITE_INTAKE_REQUEST_INVALID","SITE_INTAKE_REQUEST_STATE_INVALID",
            "SITE_INTAKE_PRIVACY_INVALID","SITE_INTAKE_NOT_READY",
            "SITE_INTAKE_ADMISSION_INCOMPLETE",
        }
        code=str(err)
        label=code if code in safe_codes else type(err).__name__
        print("ZM_BRIDGE_CYCLE_FAILED="+label,file=sys.stderr)
        sys.exit(1)
