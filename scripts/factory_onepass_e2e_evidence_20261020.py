#!/usr/bin/env python3
"""One-shot, independent live VPS E2E verification for the 3000-tool router.
Writes an evidence digest; does not claim synthetic role labels are live agents,
nor equate tool availability with 40 production engines or commercial sales.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROLES=("planner","controller","quality","inventory","delivery","research","support_tools","site_bridge")
FAMILIES=("F01","F10","F18","F19","F27","F31","F34","F40")
OPS=(1,26,36,60,74,75,14,22)
def fail(cond,msg):
    if not cond:raise RuntimeError("E2E_"+msg)
def load(path,name):
    p=Path(path)
    fail(p.is_file() and not p.is_symlink(),"MISSING_MODULE_"+name)
    spec=importlib.util.spec_from_file_location(name,str(p))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def utc_now():return datetime.now(timezone.utc)
def observe_heartbeat(path):
    if not path.is_file() or path.is_symlink():return {"exists":False,"recent":False}
    try:
        d=json.loads(path.read_text())
        stamp=datetime.fromisoformat(d["observed_utc"].replace("Z","+00:00"))
        seconds=(utc_now()-stamp).total_seconds()
        return {"exists":True,"recent":0<=seconds<=1200,"age_seconds":round(seconds),
            "families":d.get("families_connected"),"bindings":d.get("registered_tool_bindings")}
    except (KeyError,ValueError,TypeError,OSError):
        return {"exists":True,"recent":False,"invalid_or_unreadable":True}
def run(root,ops,registry,run_id):
    root=Path(root);ops=Path(ops);registry=Path(registry)
    fail(root.is_dir() and not root.is_symlink(),"PRIVATE_ROOT")
    fail(ops.is_dir() and not ops.is_symlink(),"OPS_ROOT")
    fail(bool(re.fullmatch(r"[0-9]{6,16}",run_id)),"RUN_ID_INVALID")
    execution=ops/"forty-execution"
    router=load(execution/"factory_tool_router.py","independent_e2e_router")
    wb,cat,families,regsha,catsha=router.verified(ops,root,registry)
    fail(len(families["profiles"])==40,"FORTY_PROFILES")
    baseline=observe_heartbeat(root/"tool-router/dashboard.json")
    cron=subprocess.check_output(["crontab","-l"],text=True,timeout=12)
    schedule=execution/"periodic-dispatch.sh"
    fail(schedule.is_file() and not schedule.is_symlink(),"SCHEDULER_FILE")
    source=schedule.read_text()
    fail("factory_tool_router.py" in source and source.count("factory_tool_router.py")==1,"SCHEDULER_ROUTER_HOOK")
    fail(str(schedule) in cron and cron.count("SAEIT_FACTORY_FORTY_FAMILY_OPERATIONAL_DISPATCH_V1")==1,"ACTIVE_CRON_REGISTRATION")
    fail(subprocess.run(["bash","-n",str(schedule)],capture_output=True,timeout=10).returncode==0,"SCHEDULER_SYNTAX")
    # Every family-bound tool is executed, not merely counted.
    checks=router.selftest(ops,root,registry)
    fail(checks=={"routed":3000,"new":2000,"failed":0},"ALL_TOOLS")
    proofdir=router.private_dir(root/"evidence/tool-router-onepass")
    tag="e2e"+run_id
    inbox=router.private_dir(root/"tool-router/requests")
    output=router.private_dir(root/"tool-router/results")
    processed=router.private_dir(root/"tool-router/processed")
    rejected=router.private_dir(root/"tool-router/rejected")
    # Eight role-labelled requests are TEST PROBES only, not autonomous agent invocations.
    expected={}
    for i,(role,family,op) in enumerate(zip(ROLES,FAMILIES,OPS)):
        ident=tag+"_"+str(i)
        path=inbox/(ident+".json")
        response=output/(ident+".json")
        archive=processed/(ident+".json")
        fail(not path.exists() and not response.exists() and not archive.exists(),"PROOF_ID_ALREADY_USED")
        payload=wb.fixture(op)
        tool_id=family+"-T%02d"%op
        want=router.execute(wb,cat,tool_id,payload)["result"]
        data={"schema":router.REQUEST_SCHEMA,"request_id":ident,
              "role":role,"tool_id":tool_id,"payload":payload}
        router.atomic_json(path,data)
        expected[ident]={"tool_id":tool_id,"role":role,"expected_digest":router.digest(router.json_bytes(want))}
    negative=tag+"_bad"
    badfile=inbox/(negative+".json")
    fail(not badfile.exists() and not (rejected/badfile.name).exists(),"BAD_ID_ALREADY_USED")
    router.atomic_json(badfile,{"schema":router.REQUEST_SCHEMA,"request_id":negative,
      "role":"nonexistent_role","tool_id":"F01-T01","payload":{"text":"invalid request"}})
    ticks=[]
    for _ in range(5):
        tick=router.tick(ops,root,registry,max_jobs=10)
        if tick.get("status")=="busy":
            time.sleep(1);continue
        fail(tick["registered_tool_bindings"]==3000 and tick["families_connected"]==40,"TICK_ROUTING")
        fail(tick["support_invocations_this_tick"]==400,"FOUR_HUNDRED_REAL_CALLS")
        fail(len(tick["family_readbacks"])==40 and
            len({x["family_id"] for x in tick["family_readbacks"]})==40,"FAMILY_RECEIPTS")
        ticks.append({"invocations":tick["support_invocations_this_tick"],
              "completed_queue":tick["queued_requests"]["completed"],
              "rejected_queue":tick["queued_requests"]["rejected"]})
        if (all((output/(ident+".json")).is_file() for ident in expected)
                and (rejected/(negative+".json")).is_file()):
            break
    response_proofs=[]
    for ident,wanted in expected.items():
        raw=router.read_bytes(output/(ident+".json"),200000)
        v=json.loads(raw)
        fail(v["request_id"]==ident and v["tool_id"]==wanted["tool_id"],"QUEUE_RESPONSE_ID")
        fail(v["role_claimed_by_local_caller"]==wanted["role"],"QUEUE_ROLE")
        fail(v["commercial_release"] is False,"QUEUE_NO_COMMERCIAL")
        fail(router.digest(router.json_bytes(v["result"]))==wanted["expected_digest"],"QUEUE_RESULT_CORRUPTION")
        fail((processed/(ident+".json")).is_file(),"QUEUE_ARCHIVE_MISSING")
        response_proofs.append({"role_label":wanted["role"],"tool_id":wanted["tool_id"],
            "response_sha256":router.digest(raw)})
    fail((rejected/(negative+".json")).is_file(),"REJECTED_INVALID_ROLE")
    # Verify BUILD50 independently using its actual on-VPS source/proof scanner.
    bridge=load(execution/"factory_build50_family_bridge.py","e2e_original_50stage_bridge")
    proto=load(execution/"factory_build_50.py","e2e_original_50stage_verifier")
    master=load(execution/"factory_40_family_master.py","e2e_original_family_registry")
    ledger=bridge.inventory(root,registry,proto,master)
    counts=ledger["counts"]
    fail(counts["registered_families"]==40 and len(ledger["families"])==40,"LEDGER_40")
    verified_ids=sorted(x["family_id"] for x in ledger["families"]
        if x["technical_50_stage_completed"]>0)
    pilot_only=sorted(x["family_id"] for x in ledger["families"]
        if x["technical_pilot_count"]>0 and x["technical_50_stage_completed"]==0)
    lacking=sorted(x["family_id"] for x in ledger["families"]
        if x["technical_50_stage_completed"]==0)
    fail(len(verified_ids)+len(lacking)==40,"LEDGER_PARTITION")
    # Prior persistent snapshots expose presence and role definitions, NOT proof of live agents.
    capability=root/"capability-organization/dashboard.json"
    agent_summary={"present":False,"separate_agents_confirmed_running":0}
    if capability.is_file() and not capability.is_symlink():
        d=json.loads(capability.read_text())
        agent_summary={"present":True,"source_role_definitions":len(d.get("roles",[])),
          "separate_agents_confirmed_running":d.get("separate_agents_started",0),
          "support_bindings_reported":d.get("support_tool_bindings_available"),
          "source_robot_role_count":len(d.get("legacy",{}).get("robot_roles",[]))}
    # One-shot proof must never assert production gains beyond real native evidence.
    result={"schema":"saeit.factory.onepass-e2e-evidence.v1",
      "verified_at_utc":utc_now().isoformat(),
      "run_id":run_id,"catalog_sha256":catsha,"registry_sha256":regsha,
      "tool_fixture_invocations_verified":3000,"new_tool_bindings_verified":2000,
      "family_count":40,"real_support_invocations_per_successful_tick":400,
      "successful_ticks":len(ticks),"tick_metrics":ticks,
      "local_role_label_probes_verified":len(response_proofs),
      "role_probes_are_actual_workers":False,
      "queue_e2e_results":response_proofs,"invalid_role_denied":True,
      "live_cron_registration_verified":True,
      "scheduler_hook_verified":True,
      "prior_heartbeat":baseline,
      "independent_build50_inventory":counts,"verified_technical_family_ids":verified_ids,
      "technical_pilots_without_50stages":pilot_only,
      "families_without_50stage_technical_proof":lacking,
      "legacy_agent_source_snapshot":agent_summary,
      "all_independent_agents_using_router_proven":False,
      "all_40_native_production_engines_proven":len(verified_ids)==40,
      "new_products_created_by_this_proof":0,
      "store_publications_by_this_proof":0,"payments_changed":False,
      "cron_changed":False,"commercial_approval_claimed":False,
      "scope":"live_VPS_local_tool_queue_and_independent_native_build50_proofs"}
    receipt=proofdir/(tag+"-receipt.json")
    fail(not receipt.exists(),"PROOF_DESTINATION_COLLISION")
    router.atomic_json(receipt,result)
    diskhash=router.digest(router.read_bytes(receipt,200000))
    summary={"tool_count":3000,"families_routed":40,
      "successful_live_queue_role_label_probes":len(response_proofs),
      "independent_50_stage_families":len(verified_ids),
      "pilot_only_families":len(pilot_only),"without_50stage_proof":len(lacking),
      "verified_technical_family_ids":verified_ids,
      "preexisting_heartbeat_recent":baseline.get("recent"),
      "role_labels_not_live_agents":True,
      "all_agents_proven":False,"receipt_sha256":diskhash}
    print("ONEPASS_VPS_E2E_PROOF="+json.dumps(summary,sort_keys=True))
    print("ONEPASS_VPS_QUEUE_TOOL_ROUTER=PASS")
    print("ONEPASS_VPS_NATIVE_PRODUCT_50STAGE_INDEPENDENT_AUDIT=PASS")
    print("ONEPASS_VPS_ALL_AGENTS_AND_ALL_40_BUILDERS=NOT_PROVEN")
    return result
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--factory-private",required=True)
    ap.add_argument("--ops",required=True)
    ap.add_argument("--registry",required=True)
    ap.add_argument("--run-id",required=True)
    args=ap.parse_args()
    return run(args.factory_private,args.ops,args.registry,args.run_id)
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("ONEPASS_E2E_FAILURE="+type(exc).__name__+":"+str(exc)[:220],file=sys.stderr)
        sys.exit(1)
