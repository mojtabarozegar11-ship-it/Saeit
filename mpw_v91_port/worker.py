"""Small MojPlayWin-main V91 master/agent runner; private, bounded, opt-in.

No Django, factory, payment, public website, Passenger, network or other tenants.
Executed by an optional cPanel cron only in the verified private stage.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from datetime import datetime, timezone

PREFIX=Path("/home/zomorod2/.private_mojplaywin_main_agents")
STAGE=PREFIX/"v91_verified_main_port_20261018"
ENGINE_MODULES_MIN=70
MAX_PENDING=2
MAX_INPUT=24_000
MAX_STATE_BYTES=2_000_000

def private(root):
    return root.is_dir() and not root.is_symlink() and (root.stat().st_mode & 0o077)==0

def origin_ok():
    if not private(PREFIX) or not private(STAGE):
        return False
    source=STAGE/"mpw_v91_port"/"ORIGIN.json"
    if not source.is_file() or source.is_symlink():return False
    try:
        metadata=json.loads(source.read_text(encoding="utf8"))
        files=metadata["modules"]
        if not (ENGINE_MODULES_MIN<=len(files)<=100) or metadata.get("file_count")!=len(files):
            return False
        # Verify every module from the original preserved V91 snapshot before use.
        for row in files:
            path=STAGE.joinpath(*Path(row["destination"]).parts)
            if not path.is_file() or path.is_symlink(): return False
            if hashlib.sha256(path.read_bytes()).hexdigest()!=row["sha256"]: return False
        return metadata.get("scope")=="MojPlayWin main site ONLY; excluded all other sites"
    except (OSError,KeyError,TypeError,ValueError):
        return False

def atomic_json(path,obj):
    raw=json.dumps(obj,ensure_ascii=False,sort_keys=True).encode("utf8")
    if len(raw)>MAX_INPUT:raise ValueError("output_too_large")
    fd,tmp=tempfile.mkstemp(prefix=".tmp_mpw_agent_",dir=str(path.parent))
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as out:
            out.write(raw);out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def tick():
    if not origin_ok():
        return {"status":"disabled_invalid_source"}
    root=STAGE/"operator_state"
    if root.is_symlink():return {"status":"unsafe_state_dir"}
    root.mkdir(mode=0o700,exist_ok=True)
    if not private(root):return {"status":"unsafe_state_dir"}
    if not (root/"enabled").is_file() or (root/"enabled").is_symlink():
        return {"status":"disabled_by_owner"}
    lock=root/"worker.lock"
    if lock.is_symlink():return {"status":"unsafe_lock"}
    fd=os.open(str(lock),os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {"status":"another_cycle_running"}
        # No sensitive env credentials inherited by the V91 original engines.
        os.environ.pop("DJANGO_SETTINGS_MODULE",None)
        os.environ.pop("DATABASE_URL",None)
        os.environ["PYTHONDONTWRITEBYTECODE"]="1"
        sys.dont_write_bytecode=True
        sys.path.insert(0,str(STAGE))
        from mpw_v91_port.legacy.site_master.bridge import route_once
        from mpw_v91_port.runtime import review_draft
        now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        def master_callback():
            return {"tenant":"mojplaywin-main","mode":"private-review-only","state":"ready","utc":now}
        response=route_once("mpw-main-agents-health-"+now,master_callback)
        if not isinstance(response,dict) or response.get("tenant")!="mojplaywin-main":
            return {"status":"master_callback_failed"}
        q=root/"queue"
        done=root/"processed"
        drafts=root/"drafts"
        for folder in (q,done,drafts):
            if folder.is_symlink():return {"status":"unsafe_subfolder"}
            folder.mkdir(mode=0o700,exist_ok=True)
            if not private(folder):return {"status":"unsafe_subfolder"}
        current=sum(p.stat().st_size for d in (q,done,drafts) for p in d.iterdir()
                    if p.is_file() and not p.is_symlink())
        if current>=MAX_STATE_BYTES:
            return {"status":"private_storage_limit_reached"}
        count=0
        for item in sorted(q.glob("*.json")):
            if count>=MAX_PENDING:break
            if item.is_symlink() or item.stat().st_size>MAX_INPUT:
                continue
            data=item.read_bytes()
            try:
                req=json.loads(data)
                if not isinstance(req,dict) or req.get("tenant")!="mojplaywin-main" or req.get("review_only") is not True:
                    continue
                name=hashlib.sha256(data).hexdigest()[:24]
                target=drafts/(name+".json")
                if target.exists():continue
                out=review_draft(req)
                atomic_json(target,{"task_id":name,"generated_utc":now,"draft":out})
                item.rename(done/item.name)
                count+=1
            except (ValueError,TypeError,RuntimeError):
                # Inputs remain in the private queue for owner review; no auto-publication.
                continue
        atomic_json(root/"heartbeat.json",{"status":"active_private","tenant":"mojplaywin-main",
                    "last_master_callback_utc":now,"master_generation":64,
                    "processed_review_drafts":count,"auto_publish":False,
                    "factory_connected":False,"shared_django_modified":False})
        return {"status":"active_private","processed_review_drafts":count,
                "main_site":True,"published_to_website":False}
    finally:
        os.close(fd)

def main():
    parser=argparse.ArgumentParser(description="MojPlayWin V91 protected agent worker")
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check",action="store_true")
    group.add_argument("--once",action="store_true")
    args=parser.parse_args()
    os.umask(0o077)
    if args.check:
        result={"status":"source_verified" if origin_ok() else "source_invalid",
                "tenant":"mojplaywin-main","website_deployed":False}
    else:
        result=tick()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"] in ("source_verified","active_private","disabled_by_owner","another_cycle_running") else 1

if __name__=="__main__":
    raise SystemExit(main())
