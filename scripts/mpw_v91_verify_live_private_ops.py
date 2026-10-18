"""Independently verify private MojPlayWin V91 worker state and scheduled cron."""
import json
from pathlib import Path
import shutil,subprocess
from datetime import datetime,timezone
ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018")
STATE=ROOT/"operator_state"
p=STATE/"heartbeat.json"
result={"kind":"MPW_V91_PRIVATE_OPERATIONS_INDEPENDENT_VERIFICATION",
        "public_site_changed":False,
        "factory_changed":False,
        "subsites_changed":False}
if p.is_file() and not p.is_symlink() and p.stat().st_size<10000:
    row=json.loads(p.read_text(encoding="utf8"))
    ts=row.get("last_master_callback_utc")
    age=None
    if isinstance(ts,str):
        date=datetime.strptime(ts,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age=int((datetime.now(timezone.utc)-date).total_seconds()/60)
    result.update({"heartbeat_found":True,"heartbeat_status":row.get("status"),
        "last_master_callback_age_minutes":age,
        "master_generation":row.get("master_generation"),
        "publish_disabled":row.get("auto_publish") is False,
        "factory_connected":row.get("factory_connected")})
else:
    result["heartbeat_found"]=False
program=shutil.which("crontab")
if program:
    p=subprocess.run([program,"-l"],capture_output=True,text=True,timeout=10)
    if p.returncode==0:
        entries=[l for l in p.stdout.splitlines() if l.strip() and not l.lstrip().startswith("#")]
        own=[l for l in entries if "# MPW_V91_MAIN_ONLY_20261018" in l]
        result["schedule_main_only_entry_count"]=len(own)
        result["all_other_cron_entries_preserved"]=len(entries)-len(own)==8
        result["scheduled_hourly"]=len(own)==1 and own[0].startswith("17 * * * * ")
    else:
        result["cron_read_failure"]=True
result["private_agent_active"]=bool(
    result.get("heartbeat_status")=="active_private" and
    result.get("master_generation")==64 and
    result.get("publish_disabled") and
    result.get("factory_connected") is False and
    result.get("scheduled_hourly") and
    result.get("all_other_cron_entries_preserved"))
print(json.dumps(result,sort_keys=True))
if not result["private_agent_active"]:raise SystemExit(2)
