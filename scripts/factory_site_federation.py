#!/usr/bin/env python3
"""One-pass federated cPanel-to-VPS capability inventory and isolated staging.

Collect private *receipts* at the sites; mirror an authenticated snapshot to VPS.
Never treat import, a cron entry or legacy generation number as executing code.
No production site writes, workflow triggers, customer content or secrets.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile

SCHEMA = "saeit.factory.site-federation.v1"
ROLES = ("agriculture","commerce","content","economic","master","media",
         "quality","research","security","seo","weather")
FIVE = ("main_route_observer","editorial_integrity","draft_fingerprint",
        "editorial_review_queue","agent_runtime_watch")
SIX = ("seo_metadata","reference_origin","release_reconciliation",
       "public_content_security","disk_capacity","publication_worklist")
MAX_BYTES = 1200000


def read_report(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else None
    except (ValueError, UnicodeError, OSError):
        return None


def checksum(path):
    h=hashlib.sha256()
    with path.open("rb") as file:
        for part in iter(lambda:file.read(65536),b""):
            h.update(part)
    return h.hexdigest()


def report_status(report, state_key="status"):
    if not isinstance(report,dict):
        return "unknown"
    state=report.get(state_key)
    return str(state)[:70] if isinstance(state,str) else "unknown"


def collect_sites(home):
    """Pure read-only cPanel inspection, never list secrets or private contents."""
    home=Path(home).resolve()
    base=home/".private_mojplaywin_main_agents"
    evo=base/"evolution_runtime_20261018"
    v91=base/"v91_verified_main_port_20261018"/"mpw_v91_port"
    zm=home/".private"/"zomorod-business"/"site_agents.sqlite3"
    roles=[]
    if zm.is_file() and not zm.is_symlink():
        db=sqlite3.connect("file:"+str(zm)+"?mode=ro",uri=True,timeout=10)
        try:
            agent_rows=db.execute("SELECT code, enabled FROM agents ORDER BY code").fetchall()
            recent=dict(db.execute("SELECT agent_code, MAX(id) FROM runs GROUP BY agent_code").fetchall())
            for code, enabled in agent_rows:
                if code in ROLES:
                    roles.append({"code":code,"enabled":bool(enabled),
                                  "observed_run": bool(recent.get(code))})
        finally:
            db.close()
    master=read_report(base/"v91_verified_main_port_20261018"/"operator_state"/"heartbeat.json")
    gen=read_report(evo/"gen65_operational_report.json")
    modules=read_report(evo/"all_77_modules_last_run.json")
    robot5=read_report(evo/"robots_execution_20261018.json")
    robot6=read_report(evo/"extended_robots_status_20261018.json")
    report77=(modules or {}).get("per_module_capability_registry") or []
    slots=[]
    for i in range(77):
        item=report77[i] if i<len(report77) and isinstance(report77[i],dict) else {}
        name=item.get("module")
        if not isinstance(name,str) or not re.fullmatch("[A-Za-z0-9_.]{1,120}",name):
            name="unverified_slot_"+str(i+1)
        slots.append({"slot":i+1,"module":name,"import_verified":item.get("loaded") is True,
                      "functional_execution_verified":False})
    robots=[]
    for group, names, report in ((5,FIVE,robot5),(6,SIX,robot6)):
        records=(report or {}).get("roles") or []
        index={row.get("name"):row for row in records if isinstance(row,dict)}
        for name in names:
            robots.append({"name":name,"group":group,
                           "reported_status":report_status(index.get(name))})
    files=[]
    if v91.is_dir() and not v91.is_symlink():
        for p in sorted(v91.rglob("*.py")):
            if len(files)>=160:
                break
            if p.is_symlink() or not p.is_file() or p.stat().st_size>250000:
                continue
            rel=p.relative_to(v91).as_posix()
            if any(x in rel.lower() for x in ("secret","credential","wallet","payment","token","keyfile")):
                continue
            files.append({"path":rel,"sha256":checksum(p),"bytes":p.stat().st_size})
    return {"schema":SCHEMA,"source":"private_cpanel_readonly",
            "observed_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "zomorod_site_roles":roles,"mojplaywin_master_gen64":report_status(master),
            "mojplaywin_evolution_gen65":report_status(gen),
            "reported_master_generation":(master or {}).get("master_generation"),
            "reported_evolution_generation":(gen or {}).get("active_private_generation"),
            "module_slots":slots,"robot_roles":robots,
            "robot_reports_present":int(robot5 is not None)+int(robot6 is not None),
            "v91_source_files":files,
            "separate_factory_workers_started":0,
            "commercial_approval_given":False,
            "private_runtime_modified":False}


def safe_write(path,obj):
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("SYMLINK_DESTINATION")
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(str(path.parent),0o700)
    fd,tmp=tempfile.mkstemp(prefix=".federation-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as output:
            json.dump(obj,output,ensure_ascii=False,sort_keys=True,indent=2)
            output.write("\n")
        os.chmod(tmp,0o600)
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def install_snapshot(snapshot,heritage,output):
    obj=read_report(Path(snapshot))
    if obj is None or obj.get("schema")!=SCHEMA or obj.get("source")!="private_cpanel_readonly":
        raise ValueError("INVALID_REAL_SITE_SNAPSHOT")
    slots=obj.get("module_slots")
    if not isinstance(slots,list) or len(slots)!=77 or [x.get("slot") for x in slots]!=list(range(1,78)):
        raise ValueError("INVALID_77_MODULE_INVENTORY")
    robots=obj.get("robot_roles")
    if not isinstance(robots,list) or len(robots)!=11 or {x.get("name") for x in robots}!=set(FIVE+SIX):
        raise ValueError("INVALID_ROBOT_INVENTORY")
    t=datetime.fromisoformat(obj["observed_utc"].replace("Z","+00:00"))
    age=(datetime.now(timezone.utc)-t).total_seconds()
    if t.tzinfo is None or age < -120 or age>1800:
        raise ValueError("SITE_SNAPSHOT_STALE")
    heritage=Path(heritage)
    if not heritage.is_dir() or heritage.is_symlink():
        raise ValueError("MISSING_HERITAGE_SOURCE")
    indexed={x["path"]:x["sha256"] for x in obj.get("v91_source_files",[])
             if isinstance(x,dict) and isinstance(x.get("path"),str)
             and re.fullmatch("[a-zA-Z0-9_./-]{1,180}",x["path"])}
    known=[]
    mismatched=[]
    for rel,site_hash in sorted(indexed.items()):
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise ValueError("UNSAFE_RELATIVE_SOURCE_PATH")
        p=heritage/rel
        if p.is_symlink() or not p.is_file() or p.stat().st_size>250000:
            mismatched.append(rel);continue
        try:
            ast.parse(p.read_text(encoding="utf-8"),filename=rel)
        except (SyntaxError,UnicodeError):
            mismatched.append(rel);continue
        if checksum(p)==site_hash:
            known.append({"path":rel,"sha256":site_hash,"source_verified":True})
        else:
            mismatched.append(rel)
    report={
        "schema":SCHEMA,"last_site_observed_utc":obj["observed_utc"],
        "received_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "federation_sync_active":True,"site_roles_observed":len(obj.get("zomorod_site_roles",[])),
        "site_master_status":obj.get("mojplaywin_master_gen64"),
        "site_evolution_status":obj.get("mojplaywin_evolution_gen65"),
        "robots_inventory_total":11,"robots_execution_verified_by_factory":0,
        "module_slots_total":77,
        "modules_import_receipt_claims":sum(bool(x.get("import_verified")) for x in slots),
        "modules_execution_verified_by_factory":0,
        "matched_site_source_candidates":known,"source_mismatches":mismatched,
        "matched_site_source_count":len(known),
        "source_comparisons_attempted":len(indexed),
        "all_77_live_in_factory":False,"standalone_cpanel_code_execution_on_vps":False,
        "automatic_quality_approval":False,"automatic_product_publication":False,
        "site_services_modified":False,
        "next_action":"review incompatible modules independently before execution"
    }
    safe_write(Path(output),report)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--collect-cpanel",action="store_true")
    p.add_argument("--home")
    p.add_argument("--snapshot")
    p.add_argument("--heritage")
    p.add_argument("--output")
    a=p.parse_args()
    if a.collect_cpanel:
        result=collect_sites(a.home or str(Path.home()))
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    else:
        if not a.snapshot or not a.heritage or not a.output:
            p.error("--snapshot, --heritage and --output required")
        r=install_snapshot(a.snapshot,a.heritage,a.output)
        print("FEDERATION_SOURCE_MATCHED="+str(r["matched_site_source_count"]))
        print("FEDERATION_77_MODULES_IMPORTED_TO_FACTORY_RUNTIME=0")
        print("FEDERATION_ROBOTS_EXECUTED_ON_FACTORY=0")
        print("FEDERATION_PRIVATE_SYNC=ACTIVE")


if __name__=="__main__":
    main()
