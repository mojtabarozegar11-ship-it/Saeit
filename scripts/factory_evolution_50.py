#!/usr/bin/env python3
"""Factory master-agent safe evolution protocol with a maximum of 50 generations.

One generation is a *measured policy promotion*, NOT a fictional AI model, code
self-edit or file count. Proposal generation and source inspection use local
data only. No production changes, no sites, no GPUs, no claims of product QA.

Fifty different reproducible mutation protocols are defined. Each requires
independent benchmarking, verified new product outcomes and a human-reviewed
signed decision before it can be promoted by a separate authorized operator.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

SCHEMA="saeit.factory.evolution-50.v1"
MAX_GENERATIONS=50
GENES=(
    "resource_load_guard","research_source_gate","rework_capacity_reserve",
    "duplicate_identity_threshold","failure_circuit_breaker",
    "human_review_independence","artifact_hash_integrity",
    "budget_admission_limit","phase_queue_fairness","rollback_recovery",
)
TEST_PHASES=("baseline","negative_case","regression","resource_stress","real_world_pilot")
CRITICAL_GATES=(
    "no_unverified_product_admission","no_website_transfer",
    "no_open_critical_defect","independent_review_required",
    "measurable_real_finished_goods","rollback_verified",
)
DEFAULT_POLICY={
    "max_new_workers":0,
    "rework_share_percent":25,
    "backlog_limit":300,
    "min_independent_quality_evidence":1,
    "new_goods_required_for_scale":1,
    "worker_gpu_enabled":False,
    "auto_publish":False,
    "human_final_review":True,
    "technical_zip_hash_required":True,
    "max_evolution_generation":MAX_GENERATIONS,
}

def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def read_json(path,limit=10_000_000):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>limit:
        raise RuntimeError("EVOLUTION_INVALID_SOURCE")
    obj=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(obj,dict):raise RuntimeError("EVOLUTION_EXPECTED_OBJECT")
    return obj

def writable_private(path):
    if path.is_symlink():raise RuntimeError("EVOLUTION_SYMLINK")
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not path.is_dir() or path.is_symlink():raise RuntimeError("EVOLUTION_UNSAFE_DIR")
    os.chmod(str(path),0o700)

def atomic(path,object_):
    writable_private(path.parent)
    raw=(json.dumps(object_,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf8")
    fd,tmp=tempfile.mkstemp(prefix=".evolution-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def genotype(n):
    if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=MAX_GENERATIONS:
        raise RuntimeError("EVOLUTION_GENERATION_RANGE")
    gene=GENES[(n-1)//5]
    phase=TEST_PHASES[(n-1)%5]
    return {"generation":n,"gene":gene,"benchmark_phase":phase,
            "phase_objectives":[
                "Inspect current real factory snapshots",
                "Reject fake successes or missing quality evidence",
                "Test failure recovery and unaffected workflows",
                "Test load and cost ceilings without unbounded tasks",
                "Prove net new quality-approved goods or remediation",
            ],
            "invariants":list(CRITICAL_GATES),
            "proposed_policy":dict(DEFAULT_POLICY),
            "code_self_modification":False,
            "automatic_upgrade_allowed":False,
            "requires_independent_signed_approval":True}

def snapshot(factory_private):
    root=Path(factory_private).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():raise RuntimeError("EVOLUTION_PRIVATE_FACTORY_MISSING")
    registry=read_json(root/"production-family-management"/"family-dashboard.json")
    lifecycle=read_json(root/"product-lifecycle"/"dashboard.json")
    warehouse=read_json(root/"production-warehouse"/"stock-register.json")
    orders=read_json(root/"production-instructions"/"order-status.json")
    if registry.get("schema")!="saeit.factory.family-master-dashboard.v1" or registry.get("registered_families")!=40:
        raise RuntimeError("EVOLUTION_REGISTRY_NOT_VERIFIED")
    if lifecycle.get("schema")!="saeit.factory.lifecycle.v1":
        raise RuntimeError("EVOLUTION_LIFECYCLE_NOT_VERIFIED")
    if (warehouse.get("distribution_enabled") is not False
            or registry.get("distribution_enabled") is not False
            or lifecycle.get("site_distribution_enabled") is not False):
        raise RuntimeError("EVOLUTION_SITE_DISTRIBUTION_NOT_DISABLED")
    return {
       "captured_utc":stamp(),
       "registered_families":registry["registered_families"],
       "verified_active_producers":registry.get("fully_verified_active_producer_families"),
       "authorized_workers":registry.get("max_total_simultaneous_jobs_authorized"),
       "unclassified_orders":sum(registry.get("unassigned_work_orders",{}).values()),
       "issued_orders":orders.get("instructions_issued_total"),
       "pending_orders":orders.get("pending_instructions"),
       "approved_final_stock":lifecycle.get("final_commercially_verified_stock"),
       "technical_qa_stock_not_final":warehouse.get("finished_goods_versions"),
       "open_defects":lifecycle.get("open_defects"),
       "unresolved_infrastructure_gaps":not lifecycle.get("manufacturing_order_automation_complete",False),
       "cost_real_measured_usd":None,
       "real_quality_gated_builds_this_tick":None,
       "business_or_sales_impact_proven":False,
       "sources":{
          "family_dashboard":"production-family-management/family-dashboard.json",
          "lifecycle_dashboard":"product-lifecycle/dashboard.json",
          "warehouse_register":"production-warehouse/stock-register.json",
          "order_status":"production-instructions/order-status.json",
       },
    }

def safe_strategy(policy):
    return (policy["max_new_workers"]==0
        and policy["auto_publish"] is False
        and policy["worker_gpu_enabled"] is False
        and policy["human_final_review"] is True
        and policy["technical_zip_hash_required"] is True
        and 20<=policy["rework_share_percent"]<=50
        and policy["backlog_limit"]<=300)

def tick(private_root):
    root=Path(private_root).expanduser().resolve()
    metrics=snapshot(root)
    area=root/"factory-evolution-50"
    writable_private(area)
    with (area/".evolution.lock").open("a+b") as lock:
        os.chmod(str(area/".evolution.lock"),0o600)
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {"status":"already_running"}
        state_path=area/"evolution-status.json"
        state=read_json(state_path) if state_path.exists() else {
             "schema":SCHEMA,"started_utc":stamp(),"verified_promoted_generation":0,
             "pending_candidate":None,"approved_code_upgrades":0,
             "self_modifying_code":False,"production_adapter_modified":False,
             "distribution_enabled":False}
        if state.get("schema")!=SCHEMA or state.get("distribution_enabled") is not False:
            raise RuntimeError("EVOLUTION_PREVIOUS_STATE_INVALID")
        promoted=state.get("verified_promoted_generation")
        if not isinstance(promoted,int) or isinstance(promoted,bool) or not 0<=promoted<=50:
            raise RuntimeError("EVOLUTION_INVALID_GENERATION")
        if state.get("pending_candidate") is None and promoted<MAX_GENERATIONS:
            candidate=genotype(promoted+1)
            if not safe_strategy(candidate["proposed_policy"]):
                raise RuntimeError("EVOLUTION_UNSAFE_CANDIDATE")
            cpath=area/("generation-%02d-proposed.json"%candidate["generation"])
            if cpath.exists():raise RuntimeError("EVOLUTION_EXISTING_UNRESOLVED_CANDIDATE")
            candidate.update({"created_utc":stamp(),"status":"awaiting_real_benchmark_and_independent_approval",
                              "baseline_metrics":metrics,"promoted":False,
                              "real_benchmark_passed":False,
                              "human_review_recorded":False})
            atomic(cpath,candidate)
            state["pending_candidate"]=candidate["generation"]
        state.update({"last_scan_utc":stamp(),"last_metrics":metrics,
                      "generation_limit":MAX_GENERATIONS,
                      "available_genetic_benchmark_blueprints":MAX_GENERATIONS,
                      "activation":"shadow_mode_only",
                      "source_mutation_performed":False,
                      "commercial_quality_gate_bypassed":False,
                      "last_action":"awaiting_real_evidence_not_fake_promotion"})
        atomic(state_path,state)
        return state

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    args=p.parse_args()
    state=tick(args.factory_private)
    print("FACTORY_EVOLUTION_MAX_GENERATIONS="+str(MAX_GENERATIONS))
    print("FACTORY_EVOLUTION_VERIFIED_PROMOTED_GENERATION="+str(state.get("verified_promoted_generation",0)))
    print("FACTORY_EVOLUTION_PENDING_BENCHMARK="+str(state.get("pending_candidate")))
    print("FACTORY_EVOLUTION_RELEASED_PRODUCT_CLAIMS=0")
    print("FACTORY_EVOLUTION_SELF_CODE_EDITING=false")
    print("FACTORY_EVOLUTION_WEBSITE_TRANSFER=false")

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("FACTORY_EVOLUTION_ERROR="+type(e).__name__+":"+str(e)[:220],file=sys.stderr)
        sys.exit(1)
