"""Read-only private MojPlayWin site-agent output and admin chart source audit.

Do NOT log draft contents, private source URLs, titles, DB/customer details or secrets.
No writes to any file, no cron modifications, no network requests or app imports.
"""
import json,hashlib,stat
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018")
STATE=ROOT/"operator_state"
TYPES={"research_digest","product_blueprint"}
res={"classification":"MPW_V91_AGENT_OPERATIONAL_OUTPUT_AUDIT_20261018",
"private_stage_found":ROOT.is_dir() and not ROOT.is_symlink(),
"state_available":False,"main_site_only":True,
"auto_publishing":False,"live_site_modified":False,
"subsites_modified":False,"factory_modified":False}

def safe_dir(p):
    try:return p.is_dir() and not p.is_symlink() and p.stat().st_mode&0o077==0
    except OSError:return False
def read(p):
    try:
        if not p.is_file() or p.is_symlink() or p.stat().st_size>24000:return None
        data=json.loads(p.read_text(encoding="utf8"))
        return data if isinstance(data,dict) else None
    except (OSError,UnicodeError,ValueError):return None

if safe_dir(STATE):
    res["state_available"]=True
    heartbeat=read(STATE/"heartbeat.json")
    if heartbeat:
        res["master_generation"]=heartbeat.get("master_generation") if heartbeat.get("master_generation")==64 else "unverified"
        res["heartbeat_status"]=heartbeat.get("status")
        ts=heartbeat.get("last_master_callback_utc")
        if isinstance(ts,str):
            try:
                dt=datetime.fromisoformat(ts.replace("Z","+00:00"))
                age=(datetime.now(timezone.utc)-dt).total_seconds()
                res["heartbeat_age_minutes"]=int(age/60)
                res["heartbeat_fresh_within_2h"]=0<=age<=7200
            except (ValueError,TypeError):pass
        res["auto_publishing"]=bool(heartbeat.get("auto_publish",False))
        res["factory_connected"]=heartbeat.get("factory_connected")
    totals={t:{"queued":0,"processed":0,"matched_drafts":0,"past_14_days":0} for t in TYPES}
    other={"queued_invalid":0,"processed_unrecognized":0,"orphan_drafts":0}
    checked=0
    processed_tokens=set()
    for folder_name in ("queue","processed"):
        base=STATE/folder_name
        if not safe_dir(base):continue
        for path in sorted(base.iterdir()):
            checked+=1
            if checked>1500:
                res["inventory_truncated"]=True
                break
            if path.suffix!=".json" or path.is_symlink():continue
            req=read(path)
            if not req or req.get("tenant")!="mojplaywin-main" or req.get("review_only") is not True or req.get("kind","research_digest") not in TYPES:
                other["queued_invalid" if folder_name=="queue" else "processed_unrecognized"]+=1
                continue
            kind=req.get("kind","research_digest")
            totals[kind]["queued" if folder_name=="queue" else "processed"]+=1
            if folder_name=="processed":
                token=hashlib.sha256(path.read_bytes()).hexdigest()[:24]
                processed_tokens.add(token)
                draft=read(STATE/"drafts"/(token+".json"))
                if draft and isinstance(draft.get("draft"),dict):
                    payload=draft["draft"]
                    if payload.get("tenant")=="mojplaywin-main" and payload.get("review_required") is True and payload.get("published") is False:
                        totals[kind]["matched_drafts"]+=1
                        stamp=draft.get("generated_utc")
                        try:
                            when=datetime.fromisoformat(stamp.replace("Z","+00:00"))
                            if timedelta(0)<=datetime.now(timezone.utc)-when<=timedelta(days=14):
                                totals[kind]["past_14_days"]+=1
                        except (AttributeError,ValueError,TypeError):pass
        if checked>1500:break
    drafts=STATE/"drafts"
    if safe_dir(drafts):
        for path in drafts.iterdir():
            if path.is_file() and path.suffix==".json" and not path.is_symlink() and path.stem not in processed_tokens:
                other["orphan_drafts"]+=1
    res["activity_by_agent"]={k:totals[k] for k in sorted(TYPES)}
    res["unclassified_counts"]=other
    res["records_scanned"]=checked
print(json.dumps(res,ensure_ascii=False,sort_keys=True))
