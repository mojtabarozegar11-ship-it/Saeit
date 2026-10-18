"""Append ONE private MojPlayWin V91 hourly cron entry preserving every prior job.

Works only for the verified cPanel staging user. No site code, passenger,
other user crons, factory, database or public page changes.
"""
import getpass
import json
import os
import pathlib
import shutil
import subprocess
import sys
from hashlib import sha256

STAGE=pathlib.Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018")
TAG="# MPW_V91_MAIN_ONLY_20261018"
def read_cron(program):
    p=subprocess.run([program,"-l"],capture_output=True,text=True,timeout=12)
    if p.returncode==0:return p.stdout
    if p.returncode==1 and "no crontab" in p.stderr.lower():return ""
    raise RuntimeError("CANNOT_SAFELY_READ_ORIGINAL_CRONTAB")

def validate_stage():
    if getpass.getuser()!="zomorod2":raise RuntimeError("INVALID_CPANEL_IDENTITY")
    if not STAGE.is_dir() or STAGE.is_symlink() or STAGE.stat().st_mode & 0o077:
        raise RuntimeError("STAGING_DIRECTORY_IS_NOT_PRIVATE")
    from mpw_v91_port.worker import origin_ok
    if not origin_ok():raise RuntimeError("AGENT_ORIGINAL_SOURCE_MISMATCH")
    state=STAGE/"operator_state"
    enabled=state/"enabled"
    if not state.is_dir() or state.is_symlink() or state.stat().st_mode & 0o077:
        raise RuntimeError("PRIVATE_AGENT_STATE_MISSING")
    if enabled.is_symlink() or not enabled.is_file() or enabled.read_text().strip()!="MPW_V91_MAIN_ONLY_PRIVATE_20261018":
        raise RuntimeError("OWNER_PRIVATE_FLAG_NOT_ENABLED")

def main():
    os.umask(0o077)
    sys.path.insert(0,str(STAGE))
    validate_stage()
    program=shutil.which("crontab")
    if not program:raise RuntimeError("CPANEL_CRON_UNAVAILABLE")
    original=read_cron(program)
    python=str(pathlib.Path(sys.executable).resolve())
    if not os.path.isabs(python) or not pathlib.Path(python).exists():
        raise RuntimeError("UNKNOWN_CPANEL_PYTHON")
    schedule=("17 * * * * PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="+str(STAGE)+
              " "+python+" -B -m mpw_v91_port.worker --once >/dev/null 2>&1 "+TAG)
    lines=original.splitlines()
    previous=sum(1 for s in lines if s.strip() and not s.lstrip().startswith("#"))
    if TAG in original:
        if sum(TAG in x for x in lines)!=1 or schedule not in lines:
            raise RuntimeError("EXISTING_MPW_CRON_NOT_IDENTICAL")
        print(json.dumps({"status":"MPW_MAIN_AGENT_SCHEDULE_ALREADY_INSTALLED","existing_entries":previous-1,
            "other_jobs_preserved":True,"cadence":"hourly","website_exposed":False},sort_keys=True))
        return
    if read_cron(program)!=original:
        raise RuntimeError("CRON_CHANGED_DURING_PREFLIGHT")
    updated=original.rstrip("\n")+"\n"+schedule+"\n"
    p=subprocess.run([program,"-"],input=updated,text=True,
                     capture_output=True,timeout=16)
    if p.returncode!=0:raise RuntimeError("CRON_INSTALL_REJECTED")
    after=read_cron(program)
    if after.rstrip("\n")!=updated.rstrip("\n"):
        # Refuse overwrite of any simultaneous changes made by other apps.
        raise RuntimeError("CRON_READBACK_DIFFERED_REQUIRES_OPERATOR_INSPECTION")
    if after.splitlines()[:-1] != updated.splitlines()[:-1]:
        raise RuntimeError("CRON_EXISTING_ENTRIES_NOT_IDENTICAL")
    print(json.dumps({"status":"MPW_MAIN_AGENT_SCHEDULE_INSTALLED",
        "previous_noncomment_entries":previous,
        "previous_entries_preserved_exactly":True,
        "matching_new_entries":sum(TAG in x for x in after.splitlines()),
        "cadence":"hourly_at_minute_17",
        "website_exposed":False,"shared_passenger_touched":False,
        "site_database_touched":False,"factory_touched":False,
        "source_v91_touched":False},sort_keys=True))
if __name__=="__main__":
    main()
