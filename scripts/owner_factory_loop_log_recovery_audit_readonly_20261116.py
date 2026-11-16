#!/usr/bin/env python3
"""Read-only verification of the factory loop after historical log cleanup."""
import json
import os
import pwd
import stat
import subprocess
from pathlib import Path

uid = os.geteuid()
assert pwd.getpwuid(uid).pw_name == "githubops", "WRONG_OWNER"
ops = Path("/home/githubops/factory-runtime/operations")
st = ops.lstat()
assert stat.S_ISDIR(st.st_mode) and st.st_uid == uid, "UNSAFE_FACTORY_ROOT"
loop = ops / "vps-only-loop.sh"
pidfile = ops / "vps-only-loop.pid"
log = ops / "vps-only-factory.log"
out = {"schema": "owner.factory.loop_log_safety.readonly.v1",
       "ops_verified": True, "source_log_expected_by_monitors": True,
       "loop_script": "unknown", "pidfile": "unknown", "main_log": "unknown",
       "loop_pid_matches_active_process": False, "matching_loop_processes": 0,
       "deleted_log_open_fds": 0, "deleted_log_open_fds_unobservable": False,
       "loop_script_references_log": False, "cron_references_log": False,
       "files_modified": False, "service_restarted": False,
       "repair_applied": False, "new_costs": False}
for label, path in (("loop_script", loop), ("pidfile", pidfile), ("main_log", log)):
    try:
        s = path.lstat()
        out[label] = ("safe_file" if stat.S_ISREG(s.st_mode) and s.st_uid == uid
                      else "unsafe_or_non_file")
    except FileNotFoundError:
        out[label] = "absent"
assert out["loop_script"] != "unsafe_or_non_file"
assert out["pidfile"] != "unsafe_or_non_file"
assert out["main_log"] != "unsafe_or_non_file"
expected = -1
if out["pidfile"] == "safe_file":
    data = pidfile.read_text(encoding="ascii", errors="replace")[:50].strip()
    if data.isdecimal():
        expected = int(data)
if out["loop_script"] == "safe_file":
    if loop.stat().st_size <= 131072:
        out["loop_script_references_log"] = (
            "vps-only-factory.log" in loop.read_text(errors="replace"))
    else:
        out["loop_script"] = "unexpected_size"
cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
if cron.returncode == 0:
    out["cron_references_log"] = "vps-only-factory.log" in cron.stdout
    out["cron_available"] = True
else:
    out["cron_available"] = "no crontab for" in cron.stderr.lower()
pidset = []
for candidate in Path("/proc").iterdir():
    if not candidate.name.isdigit():
        continue
    try:
        if candidate.stat().st_uid != uid:
            continue
        cmd = (candidate / "cmdline").read_bytes()[:32768].replace(bytes([0]), b" ").decode("utf-8", "replace")
        if str(loop) in cmd and ("sh " in cmd or "bash " in cmd):
            pidset.append(int(candidate.name))
        fd = candidate / "fd"
        if fd.exists():
            for item in list(fd.iterdir())[:2000]:
                try:
                    to = os.readlink(item)
                    if to.startswith(str(log)) and to.endswith(" (deleted)"):
                        out["deleted_log_open_fds"] += 1
                except FileNotFoundError:
                    continue
                except PermissionError:
                    out["deleted_log_open_fds_unobservable"] = True
    except FileNotFoundError:
        continue
    except PermissionError:
        out["deleted_log_open_fds_unobservable"] = True
out["matching_loop_processes"] = len(pidset)
out["loop_pid_matches_active_process"] = len(pidset) == 1 and pidset[0] == expected
print("FACTORY_LOOP_LOG_READONLY=" + json.dumps(out, sort_keys=True))
