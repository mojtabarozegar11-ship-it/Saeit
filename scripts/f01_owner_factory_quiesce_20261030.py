#!/usr/bin/env python3
"""Owner-approved scoped factory pause. Deliberately excludes web/cPanel services.

Two modes: --audit (strictly read only), --pause (disable factory-owned user
cron entries, TERM then KILL only positively identified githubops factory
processes and their same-user descendants). No file/DB deletion or reboot.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import pwd
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

MAX_PROC=2400
MAX_TARGET=900
FACTORY_ROOT=b"/home/githubops/factory-runtime/"
# Never use arbitrary substrings such as "factory", "master-agent", or
# "factory_" to justify terminating a process; unrelated shell arguments
# and service commands may legitimately mention those terms.
CRON_EXACT_MARKERS=(
    "SAEIT_FACTORY_", "SAEIT_FACTORY_EVERY_MINUTE_V1",
    "SAEIT_FACTORY_LIFECYCLE_12_V1",
    "SAEIT_FACTORY_FORTY_FAMILY_", "SAEIT_FACTORY_BUILD50_",
)
CRON_SCOPED_PATHS=(
    "/home/githubops/factory-runtime/", "$HOME/factory-runtime/",
    "HOME/factory-runtime/", "~/factory-runtime/",
)
PAUSE_TAG="# F01_OWNER_PAUSED_FACTORY_20261030 "

def cron_is_factory(line):
    v=line.strip()
    if not v or v.startswith("#") or "=" in v.split()[0]:
        return False
    # Restrict the classification to known owner cron markers or a
    # fully scoped factory-runtime path. Unknown entries remain untouched.
    return any(m in v.upper() for m in CRON_EXACT_MARKERS) or any(
        p.lower() in v.lower() for p in CRON_SCOPED_PATHS
    )

def cron_lines():
    p=subprocess.run(["crontab","-l"],stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL,text=True,timeout=12)
    if p.returncode:raise RuntimeError("OWNER_CRONTAB_UNAVAILABLE")
    return p.stdout

def paused_cron(text):
    lines=text.splitlines(keepends=True)
    active=sum(cron_is_factory(x) for x in lines)
    replaced=[PAUSE_TAG+x if cron_is_factory(x) else x for x in lines]
    return "".join(replaced),active

def is_scoped_factory_process(cmdline):
    """Conservative argv predicate; ambiguous processes require operator review."""
    args=[a for a in cmdline.lower().split(b"\\0") if a]
    if not args:
        return False
    executable=args[0].rsplit(b"/",1)[-1]
    if executable not in (b"python",b"python3",b"python3.11",
                          b"bash",b"sh",b"dash",b"flock",b"timeout"):
        return False
    if any(a in (b"-c",b"--command") for a in args):
        return False
    return any(a.startswith(FACTORY_ROOT) for a in args[1:])

def proc_info():
    current=os.getpid()
    owner=os.getuid()
    items={}
    count=0
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():continue
        count+=1
        if count>MAX_PROC:raise RuntimeError("PROC_SCAN_LIMIT")
        pid=int(entry.name)
        if pid==current:continue
        try:
            if entry.stat(follow_symlinks=False).st_uid!=owner:continue
            p=Path("/proc")/entry.name
            cmd=(p/"cmdline").read_bytes()[:16384].lower()
            if not cmd:continue
            text=(p/"stat").read_text(encoding="utf8")[:4096]
            _,marker,tail=text.rpartition(") ")
            if not marker:continue
            fields=tail.split()
            ppid=int(fields[1])
            start=int(fields[19])
            state=fields[0][:1]
            direct=is_scoped_factory_process(cmd)
            items[pid]=(ppid,start,state,direct)
        except (OSError,ValueError,IndexError):
            continue
    # Exclude the current program's full ancestor chain, even if a command
    # happens to include "factory" as an unrelated string.
    protected={current}
    parent=os.getppid()
    for _ in range(15):
        if parent<2 or parent in protected:break
        protected.add(parent)
        item=items.get(parent)
        if not item:break
        parent=item[0]
    direct={p for p,item in items.items() if item[3] and p not in protected}
    if len(direct)>MAX_TARGET:raise RuntimeError("TOO_MANY_FACTORY_TARGETS")
    # Do not recursively expand to arbitrary descendants: a child can be
    # an unrelated SSH/network or payment helper. All selected processes
    # must independently meet the exact factory-runtime argv predicate.
    chosen=set(direct)
    return items,chosen,direct

def live_identity(pid, start):
    try:
        p=Path("/proc")/str(pid)
        if p.stat().st_uid!=os.getuid():return False
        raw=(p/"stat").read_text(encoding="utf8")[:4096]
        _,marker,tail=raw.rpartition(") ")
        return bool(marker) and int(tail.split()[19])==start
    except (OSError,ValueError,IndexError):
        return False

def audit():
    if pwd.getpwuid(os.getuid()).pw_name!="githubops" or os.getuid()==0:
        raise RuntimeError("UNEXPECTED_OS_IDENTITY")
    c=cron_lines()
    items,targets,direct=proc_info()
    load=os.getloadavg()
    fs=os.statvfs("/home/githubops")
    return {"schema":"f01-owner-factory-quiesce.v1",
            "observed_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "cron_sha256":hashlib.sha256(c.encode()).hexdigest(),
            "cron_factory_active":sum(cron_is_factory(x) for x in c.splitlines()),
            "cron_nonfactory_active":sum(bool(x.strip()) and not x.lstrip().startswith("#")
                                           and not cron_is_factory(x) and
                                           "=" not in x.split()[0]
                                           for x in c.splitlines()),
            "factory_direct_processes":len(direct),
            "factory_descendant_processes_included":len(targets)-len(direct),
            "factory_target_processes":len(targets),
            "user_processes_inspected":len(items),
            "load1":round(load[0],2),
            "unprivileged_free_bytes":fs.f_bavail*fs.f_frsize,
            "operation":"AUDIT_ONLY",
            "sites_mutated":False}

def pause(expected_sha):
    if not re.fullmatch("[0-9a-f]{64}",expected_sha):
        raise RuntimeError("CRON_SHA_REQUIRED")
    before=cron_lines()
    if hashlib.sha256(before.encode()).hexdigest()!=expected_sha:
        raise RuntimeError("CRON_CHANGED_SINCE_ENCRYPTED_ESCROW")
    updated,paused=paused_cron(before)
    if paused<1:
        raise RuntimeError("NO_FACTORY_CRON_TO_PAUSE")
    # Explicitly preserve every unrelated row byte-for-byte.
    p=subprocess.run(["crontab","-"],input=updated,
                     stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                     text=True,timeout=15)
    if p.returncode!=0:raise RuntimeError("CRONTAB_PAUSE_INSTALL_FAILED")
    actual=cron_lines()
    if actual!=updated or any(cron_is_factory(x) for x in actual.splitlines()):
        raise RuntimeError("CRON_READBACK_MISMATCH_STOP_ABORTED")
    items,targets,direct=proc_info()
    stopped_term=0
    for pid in sorted(targets,reverse=True):
        if live_identity(pid,items[pid][1]):
            try:os.kill(pid,signal.SIGTERM);stopped_term+=1
            except (ProcessLookupError,PermissionError):pass
    deadline=time.monotonic()+18
    while time.monotonic()<deadline:
        if not any(live_identity(p,items[p][1]) for p in targets):break
        time.sleep(.75)
    # Never SIGKILL a worker that could be writing SQLite. A graceful
    # timeout means PARTIAL_STOP and requires a separately inspected
    # operator decision, not unconditional process termination.
    stopped_kill=0
    time.sleep(2)
    _,remaining,direct_remaining=proc_info()
    cron_after=cron_lines()
    verified=(not remaining and not any(cron_is_factory(x)
                   for x in cron_after.splitlines()))
    return {"schema":"f01-owner-factory-quiesce.v1",
            "observed_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "status":"SCOPED_USER_FACTORY_CRON_AND_PROCESS_STOP_VERIFIED" if verified else "PARTIAL_STOP",
            "full_factory_stop_verified":False,
            "owned_factory_cron_disabled":paused,
            "cron_nonfactory_lines_unchanged":True,
            "owner_processes_targeted":len(targets),
            "sigterm_sent":stopped_term,
            "sigkill_sent":stopped_kill,
            "remaining_factory_targets":len(remaining),
            "remaining_direct_factory_targets":len(direct_remaining),
            "forced_termination_disabled":True,
            "system_level_timers_verified":False,
            "owner_cron_factory_active_after":sum(cron_is_factory(x) for x in cron_after.splitlines()),
            "other_service_users_unmodified":True,
            "db_touched":False,
            "reboot_performed":False,
            "public_sites_touched":False,
            "backup_completed":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--pause",action="store_true")
    ap.add_argument("--expected-cron-sha")
    a=ap.parse_args()
    if a.audit == a.pause:raise SystemExit("CHOOSE_ONE_MODE")
    try:
        out=audit() if a.audit else pause(a.expected_cron_sha or "")
        print(json.dumps(out,sort_keys=True))
        return 0 if a.audit or out["status"].endswith("_VERIFIED") else 3
    except Exception as e:
        print(json.dumps({"schema":"f01-owner-factory-quiesce.v1",
                          "status":"BLOCKED","error_type":type(e).__name__,
                          "public_sites_touched":False,
                          "backup_completed":False},sort_keys=True))
        return 4

if __name__=="__main__":
    sys.exit(main())
