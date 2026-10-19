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

SCHEMA="saeit.factory.production-instructions.v1"
CYCLE=re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
ID=re.compile(r"^WO-[0-9]{8}$")
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


def orders_once(root,engine,profiles,cycle,*,dry_run=False,max_active=297):
    root=Path(root)
    if not CYCLE.fullmatch(cycle):raise ValueError("CYCLE_ID_INVALID")
    dt.date.fromisoformat(cycle)
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
        active=sum(item["status"]!="completed_verified" for item in existing)
        missing=3-len(ours)
        if active+missing>max_active or len(existing)+missing>engine.MAX_ORDERS:
            raise RuntimeError("FACTORY_PENDING_CAPACITY_REACHED")
        # Select different real registered product families, rotate daily.
        day=dt.date.fromisoformat(cycle).toordinal()
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


def deliver_stock(factory_root,ware,warehouse_module,sender,ssh_key,ssh_hosts,max_products=3,*,dry_run=False):
    root=Path(factory_root)
    warehouse=Path(ware)
    inventory=warehouse_module.stock_summary(warehouse)
    # No undefined new product: confirm warehouse entry matches the current
    # finished source-manifest and is not in QA rework, then existing sender
    # transports private, SHA-checked packages to cPanel receiver.
    options=sender.host_ssh_options(Path(ssh_key),Path(ssh_hosts))
    results=[]
    for row in inventory:
        if len(results)>=max_products:break
        recipe=row["product_id"]
        if row["manufacturing_qc"]!="passed" or row["commercial_release"] is not False:continue
        source=root/"digital-products"/recipe/"manufacturing_manifest.json"
        if source.is_symlink() or not source.is_file():continue
        doc=json.loads(source.read_text(encoding="utf8"))
        if doc.get("source_sha256")!=row["version"] or doc.get("artifact_sha256")!=row["artifact_sha256"]:
            continue
        try:
            result=sender.deliver(recipe,root/"digital-products",options,dry_run=dry_run)
            results.append(result)
        except (OSError,ValueError,RuntimeError) as e:
            results.append({"recipe":recipe,"status":"blocked_"+type(e).__name__})
    return results


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
    order=orders_once(base,engine,family,a.cycle,dry_run=a.dry_run)
    results=deliver_stock(base,base/"production-warehouse",ware,sender,a.ssh_key,
                          a.known_hosts,a.max_ship,dry_run=a.dry_run)
    print("ZM_BRIDGE_ORDER_RECEIPT="+json.dumps(order,ensure_ascii=False,sort_keys=True))
    print("ZM_BRIDGE_DELIVERED_PRIVATE="+json.dumps(results,ensure_ascii=False,sort_keys=True))
    print("ZM_BRIDGE_ORDERS_THIS_CYCLE="+str(len(order["orders"])))
    print("ZM_BRIDGE_ORDERS_NEW="+str(order["new"]))
    print("ZM_BRIDGE_PUBLIC_SALES_ENABLED=false")


if __name__=="__main__":
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError,json.JSONDecodeError) as err:
        print("ZM_BRIDGE_CYCLE_FAILED="+type(err).__name__,file=sys.stderr)
        sys.exit(1)
