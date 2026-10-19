"""Read-only as-of-now operational audit of MojPlayWin-only V91 worker on cPanel."""
from datetime import datetime,timezone
from pathlib import Path
import json,subprocess,shutil,hashlib

ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018")
STATE=ROOT/"operator_state"
NOW=datetime.now(timezone.utc)
result={"kind":"MOJPLAYWIN_MAIN_V91_WORKER_FRESH_STATUS",
        "checked_at_utc":NOW.isoformat(),"read_only":True,"site_files_changed":False,
        "worker_invoked":False,"database_touched":False}
def safe_dir(path):
    return path.is_dir() and not path.is_symlink() and (path.stat().st_mode & 0o077)==0
def read_json(p):
    if not p.is_file() or p.is_symlink() or p.stat().st_size>25000:
        return None
    try:return json.loads(p.read_bytes())
    except (OSError,ValueError,UnicodeError):return None
result["original_source_private"]=safe_dir(ROOT)
result["private_state_secure"]=safe_dir(STATE)
row=read_json(STATE/"heartbeat.json") if result["private_state_secure"] else None
result["heartbeat_exists"]=isinstance(row,dict)
if isinstance(row,dict):
    ts=row.get("last_master_callback_utc")
    age=None
    if isinstance(ts,str) and len(ts)<40:
        try:
            instant=datetime.fromisoformat(ts.replace("Z","+00:00"))
            age=round((NOW-instant).total_seconds()/60,1)
        except (ValueError,TypeError):pass
    result.update({"heartbeat_utc":ts if isinstance(ts,str) else None,
                   "heartbeat_age_minutes":age,
                   "master_generation":row.get("master_generation"),
                   "worker_reported_status":row.get("status"),
                   "automatic_publishing":row.get("auto_publish"),
                   "factory_connected":row.get("factory_connected"),
                   "processed_in_latest_cycle":row.get("processed_review_drafts"),
                   "recent_heartbeat":bool(age is not None and 0<=age<=100)})
program=shutil.which("crontab")
result["crontab_available"]=bool(program)
if program:
    try:
        p=subprocess.run([program,"-l"],capture_output=True,text=True,timeout=10)
        if p.returncode==0:
            lines=[s.strip() for s in p.stdout.splitlines() if s.strip() and not s.lstrip().startswith("#")]
            ours=[s for s in lines if s.endswith("# MPW_V91_MAIN_ONLY_20261018")]
            result["total_cron_entries_count"]=len(lines)
            result["mojplaywin_cron_entries_count"]=len(ours)
            result["hourly_schedule_installed"]=len(ours)==1 and ours[0].startswith("17 * * * * ")
            result["other_crons_not_in_scope"]=len(lines)-len(ours)
        else:result["cron_read_status"]="failed"
    except (OSError,subprocess.TimeoutExpired):result["cron_read_status"]="timeout_or_unavailable"
drafts,processed,queue={},{},{}
for folder,data in (("drafts",drafts),("processed",processed),("queue",queue)):
    p=STATE/folder
    if safe_dir(p):
        for item in list(p.glob("*.json"))[:120]:
            data[item.stem]=True
    result[folder+"_count"]=len(data) if safe_dir(p) else None

by_kind={"research_digest":0,"product_blueprint":0,"other":0}
verified_pairs=0
if safe_dir(STATE/"processed") and safe_dir(STATE/"drafts"):
    for p in list((STATE/"processed").glob("*.json"))[:120]:
        request=read_json(p)
        if not isinstance(request,dict) or request.get("tenant")!="mojplaywin-main" or request.get("review_only") is not True:
            continue
        d=read_json(STATE/"drafts"/(hashlib.sha256(p.read_bytes()).hexdigest()[:24]+".json"))
        if not isinstance(d,dict):continue
        draft=d.get("draft")
        if not isinstance(draft,dict) or draft.get("tenant")!="mojplaywin-main" or draft.get("published") is not False:
            continue
        verified_pairs+=1
        k=request.get("kind","research_digest")
        by_kind[k if k in by_kind else "other"]+=1
result["verified_private_drafts_by_agent"]=by_kind
result["verified_processed_draft_pairs"]=verified_pairs
result["live_main_site_publication_confirmed"]=False
result["worker_active_currently_confirmed"]=bool(
    result.get("hourly_schedule_installed") and result.get("recent_heartbeat")
    and result.get("worker_reported_status")=="active_private"
    and result.get("master_generation")==64
    and result.get("automatic_publishing") is False
    and result.get("factory_connected") is False
)
print(json.dumps(result,sort_keys=True))
