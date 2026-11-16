#!/usr/bin/env python3
"""Read-only bounded evidence for owner cPanel npm cache and VPS factory logs.

NO modifications, cleanup, data exports, service changes or backup reads.
Only abstract counts, byte quantities and classification flags are emitted.
"""
import json
import os
import pwd
import stat
import subprocess
import sys
import time
from pathlib import Path


def must_plain_dir(p, uid):
    st = p.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid:
        raise RuntimeError("DIRECTORY_OWNER_OR_TYPE_INVALID")
    return st


def disk_free(p):
    s = os.statvfs(p)
    return s.f_bavail * s.f_frsize


def owned_process_use(uid, target):
    ref_count, candidate_package_procs, unknown, scanned = 0, 0, 0, 0
    prefix = str(target)
    needles = ("npm ", "npx ", "pnpm ", "yarn ", "pip install", "pip download", "gradle ")
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != uid:
                continue
            scanned += 1
            if scanned > 750:
                unknown += 1
                break
            cmd = (proc / "cmdline").read_bytes()[:32768].replace(b"\\x00", b" ").decode("utf-8", "replace").lower()
            if any(n in cmd for n in needles):
                candidate_package_procs += 1
            links = []
            for name in ("cwd", "exe"):
                try:
                    links.append(os.readlink(proc / name))
                except FileNotFoundError:
                    continue
                except OSError:
                    unknown += 1
            try:
                entries = list((proc / "fd").iterdir())
                if len(entries) > 2000:
                    unknown += 1
                    entries = entries[:2000]
                for fd in entries:
                    try:
                        links.append(os.readlink(fd))
                    except FileNotFoundError:
                        pass
                    except OSError:
                        unknown += 1
            except FileNotFoundError:
                pass
            except OSError:
                unknown += 1
            ref_count += sum(v == prefix or v.startswith(prefix + "/") for v in links)
        except FileNotFoundError:
            continue
        except OSError:
            unknown += 1
    return {"owner_processes_scanned": scanned,
            "package_processes": candidate_package_procs,
            "open_cache_refs": ref_count,
            "proc_visibility_unknown": unknown}


def tree_review(path, uid, device):
    count, symlinks, foreign, hardlinks, unknown = 0, 0, 0, 0, False
    if not path.is_dir():
        return {"tree": "absent"}
    for base, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            try:
                st = (Path(base) / name).lstat()
                count += 1
                if stat.S_ISLNK(st.st_mode):
                    symlinks += 1
                if st.st_uid != uid or st.st_dev != device:
                    foreign += 1
                if stat.S_ISREG(st.st_mode) and st.st_nlink > 1:
                    hardlinks += 1
            except OSError:
                unknown = True
            if count >= 50000:
                unknown = True
                break
        if unknown:
            break
    return {"entries_checked": count, "symlinks": symlinks,
            "foreign_or_other_mount_entries": foreign,
            "hardlinked_files": hardlinks,
            "scan_complete": not unknown}


def cpanel_audit():
    uid = os.geteuid()
    if pwd.getpwuid(uid).pw_name != "zomorod2":
        raise RuntimeError("CPANEL_WRONG_ACCOUNT")
    home = Path("/home/zomorod2")
    must_plain_dir(home, uid)
    npm = home / ".npm"
    must_plain_dir(npm, uid)
    cache = npm / "_cacache"
    if not cache.exists():
        return {"schema": "owner.storage.cp.readonly.v2",
                "npm_cache": "absent", "read_only": True, "delete_permitted": False}
    st = must_plain_dir(cache, uid)
    if st.st_dev != home.stat().st_dev:
        raise RuntimeError("CACHE_OTHER_DEVICE")
    du = subprocess.run(["du", "-sk", "--", str(cache)], capture_output=True,
                        text=True, timeout=55, check=True)
    allocated = int(du.stdout.split()[0]) * 1024
    check = owned_process_use(uid, cache)
    tree = tree_review(cache, uid, st.st_dev)
    safe_candidate = (not check["open_cache_refs"]
                      and not check["package_processes"]
                      and not check["proc_visibility_unknown"]
                      and tree.get("scan_complete") is True
                      and not tree["symlinks"]
                      and not tree["foreign_or_other_mount_entries"]
                      and not tree["hardlinked_files"])
    return {"schema": "owner.storage.cp.readonly.v2",
            "cache_mib": round(allocated / 1048576, 2),
            "cache_age_days": int((time.time() - st.st_mtime) / 86400),
            "cache_identity_verified": True,
            "process_use": check, "tree_review": tree,
            "eligible_for_separate_owner-reviewed_action": safe_candidate,
            "read_only": True, "delete_permitted": False,
            "protected_apps_or_backups_touched": False}


def vps_audit():
    uid = os.geteuid()
    if pwd.getpwuid(uid).pw_name != "githubops":
        raise RuntimeError("VPS_WRONG_ACCOUNT")
    base = Path("/home/githubops/factory-runtime")
    ops = base / "operations"
    must_plain_dir(base, uid)
    must_plain_dir(ops, uid)
    logfile = ops / "vps-only-factory.log"
    if logfile.is_symlink():
        raise RuntimeError("OPERATIONAL_LOG_SYMLINK")
    log_state = "present" if logfile.is_file() else "absent"
    log_bytes = logfile.stat().st_size if logfile.is_file() else 0
    cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                          timeout=8)
    if cron.returncode and "no crontab for" not in cron.stderr.lower():
        cron_state = "unavailable"
    else:
        cron_state = "available"
    cron_refs = ("vps-only-factory.log" in cron.stdout)
    log_count, old_log_count = 0, 0
    for file in ops.iterdir():
        try:
            st = file.lstat()
            if file.name.endswith(".log") and stat.S_ISREG(st.st_mode) and st.st_uid == uid:
                log_count += 1
                if st.st_mtime < time.time() - 7 * 86400:
                    old_log_count += 1
        except OSError:
            continue
    return {"schema": "owner.storage.vps.readonly.v2",
            "free_bytes": disk_free(base), "factory_root_verified": True,
            "factory_log_state": log_state, "factory_log_bytes": log_bytes,
            "factory_cron_readable": cron_state,
            "factory_cron_log_reference": cron_refs,
            "root_operation_log_count": log_count,
            "root_operation_logs_older7d": old_log_count,
            "read_only": True, "delete_permitted": False,
            "protected_apps_or_backups_touched": False}


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("cpanel", "vps"):
            raise RuntimeError("INVALID_MODE")
        report = cpanel_audit() if sys.argv[1] == "cpanel" else vps_audit()
        print("OWNER_STORAGE_READONLY_EVIDENCE=" +
              json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)
    except Exception as exc:
        print("OWNER_STORAGE_READONLY_BLOCKED=" + type(exc).__name__, flush=True)
        raise SystemExit(1)
