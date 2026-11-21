#!/usr/bin/env python3
"""Bounded read-only diagnostic: evidence of inherited factory scheduler lock FD.

Never emits PIDs, commands, file names, usernames or private paths. An open FD
alone does NOT prove an active flock lock; do not kill processes from this.
"""
import datetime as dt
import json
import os
from pathlib import Path

LOCK=Path("/home/githubops/factory-runtime/operations/.forty-execution-scheduler.lock")
MAX_PIDS=900

def describe(factory_cmd, is_init_parent, is_shell, fd9_target, target_lock):
    """Side-effect-free process classification, returns fixed flags only."""
    return {
        "factory": factory_cmd,
        "init_parent_shell": factory_cmd and is_init_parent and is_shell,
        "inherits_dispatch_fd9": factory_cmd and fd9_target == target_lock,
        "init_parent_dispatch_fd9": factory_cmd and is_init_parent and fd9_target == target_lock,
    }

def snapshot():
    if LOCK.is_symlink() or any(p.is_symlink() for p in LOCK.parents):
        return {"status":"BLOCKED_LINKED_PATH","read_only":True}
    out={"schema":"f01-factory-inherited-lock-probe.v1",
         "observed_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
         "read_only":True,
         "processes_scanned":0,
         "factory_command_matches":0,
         "factory_init_parent_shell_matches":0,
         "factory_dispatch_fd9_matches":0,
         "init_parent_dispatch_fd9_matches":0,
         "fd9_read_failures":0,
         "truncated":False,
         "advisory_flock_owner_verified":False,
         "process_mutation_performed":False}
    try:
        with os.scandir("/proc") as entries:
            for e in entries:
                if not e.name.isdigit(): continue
                out["processes_scanned"]+=1
                if out["processes_scanned"]>MAX_PIDS:
                    out["truncated"]=True
                    break
                p=Path("/proc")/e.name
                try:
                    cmd=(p/"cmdline").read_bytes()[:8192].lower()
                    if b"factory" not in cmd and b"master-agent" not in cmd:
                        continue
                    raw=(p/"stat").read_text(encoding="utf-8")[:4096]
                    _,marker,tail=raw.rpartition(") ")
                    if not marker:continue
                    f=tail.split()
                    ppid=int(f[1])
                    try:
                        exe=os.path.basename(os.readlink(p/"exe")).lower()
                    except OSError:
                        exe="unavailable"
                    try:
                        fd9=os.readlink(p/"fd"/"9")
                    except OSError:
                        out["fd9_read_failures"]+=1
                        fd9=None
                    flags=describe(True,ppid==1,exe in ("sh","bash","dash"),fd9,str(LOCK))
                    out["factory_command_matches"]+=1
                    out["factory_init_parent_shell_matches"]+=int(flags["init_parent_shell"])
                    out["factory_dispatch_fd9_matches"]+=int(flags["inherits_dispatch_fd9"])
                    out["init_parent_dispatch_fd9_matches"]+=int(flags["init_parent_dispatch_fd9"])
                except (OSError,ValueError,IndexError):
                    continue
    except OSError:
        return {"status":"PROC_UNAVAILABLE","read_only":True}
    out["status"]="OBSERVED" if not out["truncated"] else "INCOMPLETE"
    return out

if __name__=="__main__":
    print(json.dumps(snapshot(),sort_keys=True))
