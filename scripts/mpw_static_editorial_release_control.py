"""Atomic, strictly MojPlayWin main-domain-only static editorial publishing.

Publishes under /home/zomorod2/mojplaywin.com/mpw-standalone-guides exclusively.
Never touches .htaccess, other domain directories, Django/Passenger, databases,
payments or other site trees. Actual external HTTP smoke test runs separately
before scheduled publishing is installed. Safe, idempotent, rollbackable.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
EVO=ROOT/"evolution_runtime_20261018"
STAGE=ROOT/"v91_verified_main_port_20261018"
CODE=STAGE/"mpw_v91_port"
DOCROOT=Path("/home/zomorod2/mojplaywin.com")
LIVE=DOCROOT/"mpw-standalone-guides"
ROLLBACKS=EVO/"standalone_guides_rollback_20261024"
CONTROL=EVO/"standalone_guides_publication_state_20261024.json"
LOCK=EVO/"standalone_guides_publication_20261024.lock"
ENABLED=STAGE/"operator_state/enabled"
MARKER="MPW_MAIN_STATIC_EDITORIAL_20261018"

def require(ok,reason):
    if not ok:raise RuntimeError(reason)

def private(path):
    return path.is_dir() and not path.is_symlink() and not (path.stat().st_mode & 0o077)

def read_json(path,limit=9000):
    require(path.is_file() and not path.is_symlink()
            and path.stat().st_size<=limit,"PRIVATE_PUBLICATION_RECORD_UNSAFE")
    v=json.loads(path.read_text("utf8"))
    require(isinstance(v,dict) and v.get("tenant")=="mojplaywin-main","PUBLICATION_TENANT_MISMATCH")
    return v

def atomic_json(path,value):
    require(not path.is_symlink(),"PUBLICATION_CONTROL_SYMLINK")
    raw=json.dumps(value,sort_keys=True).encode("utf8")
    require(len(raw)<9000,"PUBLICATION_CONTROL_TOO_LARGE")
    fd,temp=tempfile.mkstemp(prefix=".mpw-publish-",dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.lexists(temp):os.unlink(temp)

def verify():
    require(os.geteuid()==DOCROOT.stat().st_uid,"PUBLISHER_OWNER_NOT_DOCUMENTROOT")
    require(all(private(p) for p in (ROOT,EVO,STAGE,STAGE/"operator_state",CODE)),
            "PRIVATE_PUBLISHER_ENVIRONMENT_INVALID")
    require(ENABLED.is_file() and not ENABLED.is_symlink()
            and ENABLED.read_text().strip()=="MPW_V91_MAIN_ONLY_PRIVATE_20261018",
            "MAIN_TENANT_AGENT_DISABLED")
    require(not LIVE.is_symlink(),"PUBLICATION_TARGET_SYMLINK")
    from mpw_v91_port.public_editorial_publisher import verify_public_target
    verify_public_target(DOCROOT,LIVE)
    require(not CONTROL.is_symlink(),"PUBLICATION_CONTROL_TARGET_SYMLINK")

def _files(root):
    return sorted(x for x in root.rglob("*") if x.is_file())

def _public_permissions(root):
    for item in root.rglob("*"):
        require(not item.is_symlink(),"PUBLISHER_STAGE_UNSAFE_SYMLINK")
        item.chmod(0o755 if item.is_dir() else 0o644)
    root.chmod(0o755)

def _content_signature(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

def _publish():
    from mpw_v91_port.public_editorial_publisher import render_to_staging,OWNER
    old=read_json(LIVE/OWNER,9000) if LIVE.exists() else None
    tmp=Path(tempfile.mkdtemp(prefix=".mpw-standalone-guides-prepare-",dir=DOCROOT))
    tmp.chmod(0o700)
    try:
        result=render_to_staging(EVO,tmp)
        fresh=read_json(tmp/OWNER,9000)
        if old and old.get("content_fingerprints")==fresh.get("content_fingerprints"):
            return {"status":"already_published_no_change","articles":result["generated_articles"],
                    "no_public_site_shared_files_changed":True}
        if not ROLLBACKS.exists():ROLLBACKS.mkdir(mode=0o700)
        require(private(ROLLBACKS),"ROLLBACK_STORAGE_NOT_PRIVATE")
        # Keep only one authoritative rollback snapshot; refuse ambiguity.
        prior=ROLLBACKS/"previous"
        if prior.exists():
            state=read_json(CONTROL)
            require(state.get("status")=="published_verified_by_external_smoke"
                    and prior.is_dir() and not prior.is_symlink()
                    and read_json(prior/OWNER).get("scope")==
                    "mojplaywin-main-static-standalone-guides-only",
                    "PREVIOUS_ROLLBACK_NOT_RECONCILED")
            # Rotate one explicitly owned prior backup only after successful
            # external smoke of the currently live release.
            shutil.rmtree(prior)
        require(not prior.exists() and not prior.is_symlink(),"PREVIOUS_ROLLBACK_NOT_RECONCILED")
        _public_permissions(tmp)
        if LIVE.exists():
            require(LIVE.is_dir() and not LIVE.is_symlink(),"LIVE_PATH_NOT_OWNED")
            os.replace(LIVE,prior)
        try:
            os.replace(tmp,LIVE)
        except BaseException:
            if prior.exists() and not LIVE.exists():
                os.replace(prior,LIVE)
            raise
        state={"tenant":"mojplaywin-main",
               "status":"published_standalone_awaiting_external_smoke",
               "articles":result["generated_articles"],
               "content_signature":_content_signature(fresh),
               "has_previous":prior.exists(),
               "published_utc":datetime.now(timezone.utc).isoformat(),
               "public_prefix":"/mpw-standalone-guides/",
               "original_site_files_modified":False,
               "passenger_restarted":False}
        atomic_json(CONTROL,state)
        return state
    finally:
        if tmp.exists() and tmp != LIVE:
            shutil.rmtree(tmp)

def _rollback():
    from mpw_v91_port.public_editorial_publisher import OWNER
    state=read_json(CONTROL)
    if not LIVE.is_dir() or LIVE.is_symlink():
        raise RuntimeError("PUBLICATION_TARGET_MISSING_FOR_ROLLBACK")
    current=read_json(LIVE/OWNER,9000)
    require(_content_signature(current)==state.get("content_signature"),
            "PUBLICATION_ROLLBACK_CONTENT_NOT_MATCHED")
    previous=ROLLBACKS/"previous"
    discard=ROLLBACKS/"discard-current"
    require(not discard.exists() and not discard.is_symlink(),"ROLLBACK_DISCARD_PATH_CONFLICT")
    os.replace(LIVE,discard)
    try:
        if previous.exists():
            require(previous.is_dir() and not previous.is_symlink()
                    and read_json(previous/OWNER,9000).get("scope")==
                    "mojplaywin-main-static-standalone-guides-only","PREVIOUS_ROLLBACK_NOT_OWNED")
            os.replace(previous,LIVE)
    except BaseException:
        if not LIVE.exists():os.replace(discard,LIVE)
        raise
    shutil.rmtree(discard)
    atomic_json(CONTROL,{"tenant":"mojplaywin-main","status":"last_static_editorial_release_rolled_back",
                         "original_site_files_modified":False,"passenger_restarted":False})
    return {"status":"isolated_editorial_rolled_back",
            "previous_restored":LIVE.exists(),"other_site_files_touched":False}

def _finalize():
    from mpw_v91_port.public_editorial_publisher import OWNER
    state=read_json(CONTROL)
    require(state.get("status")=="published_standalone_awaiting_external_smoke",
            "PUBLICATION_PENDING_STATE_NOT_VERIFIED")
    require(LIVE.is_dir() and not LIVE.is_symlink(),"PUBLICATION_TARGET_NOT_AVAILABLE")
    require(_content_signature(read_json(LIVE/OWNER))==state.get("content_signature"),
            "PUBLICATION_PROOF_CHANGED")
    # Keep the most recent verified prior release as the restoration snapshot.
    state["status"]="published_verified_by_external_smoke"
    atomic_json(CONTROL,state)
    return {"status":"standalone_public_content_smoke_confirmed","articles":state["articles"]}

def _cron():
    from mpw_v91_port.public_editorial_publisher import OWNER
    state=read_json(CONTROL)
    require(state.get("status")=="published_verified_by_external_smoke",
            "NO_SUCCESSFUL_EXTERNAL_HTTP_PUBLICATION_PROOF")
    raw=subprocess.run(["crontab","-l"],text=True,capture_output=True,timeout=15)
    require(raw.returncode==0,"CRON_READ_FAILED")
    lines=[x for x in raw.stdout.splitlines() if MARKER in x]
    command=("12 * * * * /usr/bin/flock -n "+str(EVO/"editorial_cron.lock")
             +" /usr/bin/python3 -B "+str(CODE.parent/"scripts"/"mpw_static_editorial_release_control.py")
             +" --publish > "+str(EVO/"editorial_cron_last.log")
             +" 2>&1 # "+MARKER)
    require(len(lines)<=1,"DUPLICATE_PUBLISHER_CRON")
    if lines:
        require(lines[0]==command,"UNEXPECTED_PUBLISHER_CRON_OWNERSHIP")
        return {"status":"private_editorial_publisher_hourly_cron_already_installed"}
    # Source code is stored in a private scripts directory installed by a
    # separate checked deploy; never points to shared application runtime.
    script=CODE.parent/"scripts"/"mpw_static_editorial_release_control.py"
    require(script.is_file() and not script.is_symlink(),"PINNED_PUBLISHER_SCRIPT_MISSING")
    backed=EVO/"editorial_crontab_before.txt"
    require(not backed.is_symlink(),"CRON_BACKUP_SYMLINK")
    if not backed.exists():
        backed.write_text(raw.stdout)
        backed.chmod(0o600)
    new=raw.stdout.rstrip("\n")+"\n"+command+"\n"
    p=subprocess.run(["crontab","-"],input=new,text=True,capture_output=True,timeout=15)
    require(p.returncode==0,"PUBLISHER_CRON_INSTALL_FAILED")
    after=subprocess.run(["crontab","-l"],text=True,capture_output=True,timeout=15)
    require(after.returncode==0 and after.stdout.strip()==new.strip()
            and all(x in after.stdout for x in raw.stdout.splitlines()),
            "PUBLISHER_CRON_VERIFY_FAILED")
    return {"status":"independent_static_editorial_hourly_cron_active",
            "cron":"12 * * * *","other_cron_entries_preserved":True}

def main():
    cli=argparse.ArgumentParser()
    flags=cli.add_mutually_exclusive_group(required=True)
    flags.add_argument("--publish",action="store_true")
    flags.add_argument("--rollback",action="store_true")
    flags.add_argument("--finalize",action="store_true")
    flags.add_argument("--install-cron",action="store_true")
    args=cli.parse_args()
    os.umask(0o077)
    sys.path.insert(0,str(STAGE))
    verify()
    fd=os.open(str(LOCK),os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        if args.publish: result=_publish()
        elif args.rollback:result=_rollback()
        elif args.finalize:result=_finalize()
        else:result=_cron()
    finally:
        os.close(fd)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
