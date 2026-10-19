#!/usr/bin/env python3
"""Offline factory master allocator for 40 product families.

Resource-aware *planning* is not equivalent to manufacturing. No unverified
adapter is launched, no product is auto-certified, no sites are contacted.
Never promotes incomplete technical-only inventory into final stock.
Python 3.8+, standard library only.
"""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unicodedata

REGISTRY_SCHEMA="saeit.factory.family-registry.v1"
DASHBOARD_SCHEMA="saeit.factory.family-master-dashboard.v1"
FAMILY_RE=re.compile(r"^F(?:0[1-9]|[1-3][0-9]|40)$")
ORDER_RE=re.compile(r"^WO-[0-9]{8}\.json$")
HEX_RE=re.compile(r"^[a-f0-9]{64}$")
CLOSED={"in_finished_goods_warehouse_not_distributed","completed_verified"}
ACTIVE={"production_in_progress","prototype_in_progress"}
NOT_READY={"awaiting_executor_validation","awaiting_infrastructure",
           "awaiting_review","awaiting_benchmark"}
UNIVERSAL={"completeness","correctness_functionality","originality_and_licensing",
           "user_experience","delivery_integrity","critical_defect_zero"}
REWORK_STATES={"rework_required","expert_review","waiting_retest"}
PLAN_MAX_TOTAL=2
MEMORY_RESERVE_MB=1024
DISK_RESERVE_MB=2048

def private_dir(p):
    if p.is_symlink():raise RuntimeError("MASTER_SYMLINK_DIRECTORY")
    p.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not p.is_dir() or p.is_symlink():raise RuntimeError("MASTER_DIRECTORY_INVALID")
    os.chmod(p,0o700)

def read_obj(p,limit=5_000_000):
    if p.is_symlink() or not p.is_file() or p.stat().st_size>limit:
        raise RuntimeError("MASTER_BAD_JSON:"+p.name)
    data=json.loads(p.read_text(encoding="utf8"))
    if not isinstance(data,dict):raise RuntimeError("MASTER_EXPECTED_JSON_OBJECT")
    return data

def atomic_json(path,obj):
    private_dir(path.parent)
    raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf8")
    fd,tmp=tempfile.mkstemp(prefix=".master-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def registry_valid(reg):
    profiles=reg.get("profiles")
    if reg.get("schema")!=REGISTRY_SCHEMA or reg.get("distribution_enabled") is not False:
        raise RuntimeError("MASTER_INVALID_REGISTRY_HEADER")
    if not isinstance(profiles,list) or len(profiles)!=40:
        raise RuntimeError("MASTER_EXPECTED_FORTY_FAMILIES")
    ids=[x.get("id") for x in profiles if isinstance(x,dict)]
    if ids!=["F%02d"%i for i in range(1,41)]:
        raise RuntimeError("MASTER_FAMILY_ORDER_MISMATCH")
    slugs=set()
    for p in profiles:
        if not isinstance(p,dict) or p.get("id") not in ids:raise RuntimeError("MASTER_BAD_PROFILE")
        if not isinstance(p.get("slug"),str) or not re.fullmatch("[a-z][a-z0-9_]{2,64}",p["slug"]):
            raise RuntimeError("MASTER_INVALID_FAMILY_SLUG")
        if p["slug"] in slugs:raise RuntimeError("MASTER_DUPLICATE_FAMILY")
        slugs.add(p["slug"])
        for k in ("subcategories","audiences","languages","uses","deliverables","formats",
                  "specialist_tests","required_proofs"):
            if not isinstance(p.get(k),list) or not p[k]:
                raise RuntimeError("MASTER_MISSING_PROFILE_FIELD:"+k)
        if not UNIVERSAL.issubset(set(p.get("universal_tests",[]))):
            raise RuntimeError("MASTER_WEAK_UNIVERSAL_QA")
        if not isinstance(p.get("producer_adapter"),str) or len(p["producer_adapter"])<5:
            raise RuntimeError("MASTER_MISSING_ADAPTER")
        cap=p.get("resource_policy",{})
        if not isinstance(cap,dict) or not all(
                isinstance(cap.get(k),int) and not isinstance(cap[k],bool) and cap[k]>=1
                for k in ("cpu_cores_max","memory_mb_max","disk_mb_max",
                          "time_limit_seconds","max_concurrent_jobs")):
            raise RuntimeError("MASTER_INVALID_RESOURCE_LIMIT")
        if p.get("production_activation_allowed") is not False or p.get("readiness") not in NOT_READY:
            raise RuntimeError("MASTER_UNVERIFIED_LINE_MUST_START_DISABLED")
        if p.get("verified_consecutive_pilot_batches")!=0 or p.get("qa_owner")!="independent_quality_team":
            raise RuntimeError("MASTER_FALSE_PILOT_CLAIM")
        if p.get("distribution_targets")!="configured_later_only":
            raise RuntimeError("MASTER_DISTRIBUTION_MUST_STAY_DISABLED")
    return profiles

def cpu_mem_snapshot(ops):
    total=os.cpu_count() or 1
    try:load=float(os.getloadavg()[0])
    except (AttributeError,OSError):load=None
    available=None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                available=int(line.split()[1])//1024
                break
    except (ValueError,OSError):pass
    disk=shutil.disk_usage(str(ops))
    disk_mb=disk.free//1048576
    # We do not assume GPU availability; a driver directory is not a free VRAM check.
    cpu_slots=max(0,min(PLAN_MAX_TOTAL,max(0,total-1)))
    if load is None or load>=max(1,total-0.5):cpu_slots=0
    mem_slots=0 if available is None else max(0,(available-MEMORY_RESERVE_MB)//512)
    disk_slots=max(0,(disk_mb-DISK_RESERVE_MB)//1024)
    return {"cpu_cores_total":total,"cpu_load_1m":load,
            "memory_available_mb":available,"disk_free_mb":disk_mb,
            "gpu_free_vram_mb":None,"gpu_availability_verified":False,
            "worker_slots_theoretical":min(cpu_slots,mem_slots,disk_slots),
            "production_job_slots_authorized":0,
            "limits":{"max_total_unverified_job_dispatch":0,
                      "max_total_if_adapters_and_benchmarks_verified":PLAN_MAX_TOTAL,
                      "memory_reserve_mb":MEMORY_RESERVE_MB,
                      "disk_reserve_mb":DISK_RESERVE_MB},
            "resource_metrics_provenance":"local_os_snapshot"}

def normalized(v):
    if not isinstance(v,str):return ""
    return " ".join(unicodedata.normalize("NFKC",v).casefold().split())[:500]

def product_signature(family,speciality,audience,problem,level,language):
    data=[normalized(x) for x in (family,speciality,audience,problem,level,language)]
    if not all(data):return None
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,separators=(",",":")).encode("utf8")).hexdigest()

def classify(order,passport,by_id,by_slug):
    fid=passport.get("family_id") if passport else order.get("family_id")
    if fid in by_id:return fid
    if isinstance(fid,str) and fid in by_slug:return by_slug[fid]["id"]
    return None

def find_records(root,by_id,by_slug):
    source=root/"production-instructions"/"orders"
    if not source.is_dir() or source.is_symlink():raise RuntimeError("MASTER_MISSING_WORK_ORDER_SOURCE")
    pproot=root/"product-lifecycle"/"passports"
    liferoot=root/"product-lifecycle"/"records"
    final=root/"product-lifecycle"/"approved-finished-goods"
    counts={fid:Counter() for fid in by_id}
    metadata={fid:{"signatures":set(),"source_hashes":set(),"artifact_hashes":set()} for fid in by_id}
    unassigned=Counter()
    lengths={fid:[] for fid in by_id}
    for filename in sorted(source.iterdir()):
        if not filename.is_file() or filename.is_symlink() or not ORDER_RE.fullmatch(filename.name):
            raise RuntimeError("MASTER_UNEXPECTED_ORDER_FILE")
        order=read_obj(filename,200000)
        if order.get("id")!=filename.stem:raise RuntimeError("MASTER_CORRUPT_ORDER_ID")
        wid=filename.stem
        pf=pproot/(wid+".json")
        doc=read_obj(pf,200000) if pf.exists() else {}
        fid=classify(order,doc,by_id,by_slug)
        if fid is None:
            unassigned["awaiting_family_profile_and_passport"]+=1
            continue
        stat=counts[fid]
        stat["total_orders"]+=1
        sf=liferoot/(wid+".json")
        record=read_obj(sf,200000) if sf.exists() else {}
        state=str(record.get("status",order.get("status","issued")))
        if state in REWORK_STATES or "rework" in state or "expert_review" in state:
            stat["in_rework"]+=1
        elif state in ACTIVE:stat["in_production"]+=1
        elif state in CLOSED:stat["completed"]+=1
        else:stat["waiting"]+=1
        if state not in CLOSED:
            stat["unassigned_executable_until_passport_and_adapter_validated"]+=1
        errors=record.get("defects",[])
        if isinstance(errors,list):
            stat["open_defects"]+=sum(1 for e in errors if isinstance(e,dict) and e.get("status")!="resolved")
        stage=record.get("current_stage")
        if isinstance(stage,int) and 1<=stage<=12:stat["stage_"+str(stage)]+=1
        signature=product_signature(fid,doc.get("specialty"),doc.get("target_audience"),
                                    doc.get("problem_solved"),doc.get("level"),doc.get("language"))
        if signature:
            if signature in metadata[fid]["signatures"]:stat["duplicate_product_identity"]+=1
            metadata[fid]["signatures"].add(signature)
        for kind,key in (("source_hashes","source_sha256"),("artifact_hashes","artifact_sha256")):
            h=doc.get(key)
            if isinstance(h,str) and HEX_RE.fullmatch(h):
                if h in metadata[fid][kind]:stat["duplicate_"+kind]+=1
                metadata[fid][kind].add(h)
        try:
            born=datetime.fromisoformat(record["created_utc"])
            end=datetime.fromisoformat(record.get("last_checked_utc",record["created_utc"]))
            lengths[fid].append(max(0,(end-born).total_seconds()))
        except (ValueError,TypeError,KeyError):pass
    if final.exists():
        if final.is_symlink() or not final.is_dir():raise RuntimeError("MASTER_BAD_FINAL_STOCK")
        for folder in sorted(final.iterdir()):
            if folder.is_symlink() or not folder.is_dir():raise RuntimeError("MASTER_BAD_FINAL_GOODS_FOLDER")
            receipt=folder/"receipt.json"
            if not receipt.is_file():raise RuntimeError("MASTER_MISSING_FINAL_RECEIPT")
            data=read_obj(receipt,100000)
            work_order=data.get("order")
            pf=pproot/(str(work_order)+".json")
            passport=read_obj(pf,200000) if pf.is_file() else {}
            fid=classify({},passport,by_id,by_slug)
            # A standalone JSON receipt is not a product. Confirm the actual
            # immutable artifact, checksums and ten approval receipts exist.
            archive=folder/"product.zip"
            record_file=liferoot/(str(work_order)+".json")
            record=read_obj(record_file,200000) if record_file.is_file() else {}
            valid=(archive.is_file() and not archive.is_symlink()
                   and archive.stat().st_size==data.get("bytes")
                   and data.get("stage_gates_passed")==10
                   and data.get("distributed") is False
                   and record.get("final_warehouse_id")==work_order
                   and record.get("stage_status",{}).get("11")=="passed"
                   and isinstance(data.get("artifact_sha256"),str))
            if valid:
                digest=hashlib.sha256()
                with archive.open("rb") as fh:
                    for chunk in iter(lambda:fh.read(1048576),b""):
                        digest.update(chunk)
                valid=digest.hexdigest()==data["artifact_sha256"]
            if not valid:
                unassigned["invalid_or_unverified_final_goods"]+=1
            elif fid:
                counts[fid]["final_approved"]+=1
            else:
                unassigned["final_goods_unclassified"]+=1
    return counts,unassigned,lengths

def run(root,registry):
    root=Path(root).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():raise RuntimeError("MASTER_INVALID_PRIVATE_FACTORY_ROOT")
    profiles=registry_valid(read_obj(Path(registry),2_000_000))
    ops=root/"production-family-management"
    private_dir(ops)
    with (ops/".master.lock").open("a+b") as lock:
        os.chmod(ops/".master.lock",0o600)
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {"status":"already_running"}
        by_id={p["id"]:p for p in profiles}
        by_slug={p["slug"]:p for p in profiles}
        count,unassigned,durations=find_records(root,by_id,by_slug)
        measured=cpu_mem_snapshot(ops)
        rows=[]
        for profile in profiles:
            fid=profile["id"]
            stat=count[fid]
            paused_reason="unverified_production_adapter_and_no_real_pilot"
            if profile["resource_policy"]["gpu_required"] and not measured["gpu_availability_verified"]:
                paused_reason="gpu_vram_not_measured_and_adapter_unverified"
            item={
                "family_id":fid,"family_name":profile["name_fa"],"family_slug":profile["slug"],
                "readiness":"awaiting_executor_validation","ready":0,
                "in_production":stat["in_production"],"in_rework":stat["in_rework"],
                "pending_review_or_spec":stat["waiting"],
                "approved_final_stock":stat["final_approved"],
                "technical_qa_trial_count":0,
                "last_real_verified_production_duration_seconds":None,
                "actual_cost_usd":None,"planned_concurrent_jobs":0,
                "critical_defects_open":stat["open_defects"],
                "duplicate_identity_warning_count":stat["duplicate_product_identity"],
                "source_duplicate_hash_count":stat["duplicate_source_hashes"],
                "functional_duplicate_review_required":True,
                "blocked_reason":paused_reason,
                "producer_adapter":profile["producer_adapter"],
                "specialist_test_count":len(profile["specialist_tests"]),
                "resource_budget_policy":profile["resource_policy"],
                "actual_resource_benchmark_available":False,
                "site_distribution_enabled":False,
            }
            rows.append(item)
        report={
            "schema":DASHBOARD_SCHEMA,"updated_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "registered_families":len(rows),"production_ready_families":0,
            "fully_verified_active_producer_families":0,
            "all_family_profiles_complete":True,
            "families":rows,"unassigned_work_orders":dict(unassigned),
            "measured_vps_capacity":measured,
            "resource_policy":"reserve_capacity_for_rework_before_new_builds",
            "max_total_simultaneous_jobs_authorized":0,
            "new_work_ready_to_dispatch":0,
            "distribution_enabled":False,
            "sites_contacted":0,"final_stock_not_inferred_from_technical_qa":True,
            "master_mode":"inventory_and_admission_planning_only",
            "next_steps":["benchmarked_real_producer_adapters",
                          "human_review_of_family_specific_qa",
                          "pilot_one_real_product_per_line",
                          "three_consecutive_approved_pilots_to_scale",
                          "semantic_content_and_functional_duplicate_evaluator"],
        }
        atomic_json(ops/"family-dashboard.json",report)
        return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--registry",required=True)
    a=p.parse_args()
    r=run(a.factory_private,a.registry)
    print("FACTORY_40_FAMILY_REGISTRY="+str(r.get("registered_families","locked")))
    print("FACTORY_40_VERIFIED_ACTIVE_LINES="+str(r.get("fully_verified_active_producer_families",0)))
    print("FACTORY_40_JOBS_EXECUTED_BY_MASTER=0")
    print("FACTORY_40_SITE_TRANSFERS=0")
    print("FACTORY_40_MASTER_STATUS="+r.get("master_mode",r.get("status","unknown")))
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("FACTORY_40_MASTER_ERROR="+str(e)[:250],file=sys.stderr)
        sys.exit(1)
