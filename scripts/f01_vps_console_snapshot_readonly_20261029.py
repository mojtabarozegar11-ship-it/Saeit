#!/usr/bin/env python3
"""F-01 bounded read-only VPS guest evidence snapshot; no SSH, writes, or deploy."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

UTC = dt.timezone.utc
LIMIT = 500

def has_symlink_component(path):
    """Reject a linked ancestor too; checking only the leaf can follow a link."""
    p = Path(path).absolute()
    return any(part.is_symlink() for part in (p, *p.parents))


def stat_path(path):
    try:
        p = Path(path)
        if has_symlink_component(p):
            return {"state": "SYMLINK_NOT_FOLLOWED"}
        s = p.stat()
        return {"state": "PRESENT", "is_file": p.is_file(), "is_dir": p.is_dir(),
                "bytes": s.st_size if p.is_file() else None,
                "mtime_utc": dt.datetime.fromtimestamp(s.st_mtime, UTC).isoformat()}
    except FileNotFoundError:
        return {"state": "MISSING"}
    except OSError as exc:
        return {"state": "UNAVAILABLE", "error_class": type(exc).__name__}

def mount(path):
    try:
        if has_symlink_component(path):
            return {"state": "SYMLINK_NOT_FOLLOWED"}
        v = os.statvfs(path)
        return {"state": "OBSERVED", "total_bytes": v.f_frsize * v.f_blocks,
                "available_bytes": v.f_frsize * v.f_bavail,
                "free_bytes": v.f_frsize * v.f_bfree,
                "available_inodes": v.f_favail}
    except OSError as exc:
        return {"state": "UNAVAILABLE", "error_class": type(exc).__name__}

def command(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=6,
                           check=False, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})
        return {"state": "OBSERVED", "output": p.stdout[:12000]} if p.returncode == 0 else {
            "state": "UNAVAILABLE", "exit_code": p.returncode}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"state": "UNAVAILABLE", "error_class": type(exc).__name__}

def memory():
    try:
        result = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, raw = line.partition(":")
            if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
                result[key + "_kib"] = int(raw.strip().split()[0])
        return result
    except (OSError, ValueError, IndexError) as exc:
        return {"state": "UNAVAILABLE", "error_class": type(exc).__name__}

def cron():
    x = command(["crontab", "-l"])
    if x["state"] != "OBSERVED":
        return x
    lines = [s.strip() for s in x["output"].splitlines()
             if s.strip() and not s.lstrip().startswith("#") and "=" not in s.split()[0]]
    return {"state": "OBSERVED", "active_entries": len(lines),
            "factory_entries": sum("factory" in s.lower() for s in lines),
            "contents_redacted": True}

def workers():
    count = matched = 0
    try:
        for e in os.scandir("/proc"):
            if not e.name.isdigit():
                continue
            count += 1
            if count > LIMIT:
                break
            try:
                with open("/proc/" + e.name + "/cmdline", "rb") as f:
                    cmd = f.read(8192).replace(b"\0", b" ").lower()
                if b"factory" in cmd or b"master-agent" in cmd:
                    matched += 1
            except OSError:
                pass
        return {"state": "OBSERVED", "pids_scanned": min(count, LIMIT),
                "factory_name_matches": matched, "truncated": count > LIMIT,
                "command_lines_redacted": True}
    except OSError as exc:
        return {"state": "UNAVAILABLE", "error_class": type(exc).__name__}

def queue(path):
    s = stat_path(path)
    if s["state"] != "PRESENT" or not s["is_dir"]:
        return s
    try:
        count = 0
        with os.scandir(path) as entries:
            for _ in entries:
                count += 1
                if count >= LIMIT:
                    break
        return {"state": "OBSERVED", "entries_at_least": count,
                "truncated": count >= LIMIT, "contents_redacted": True}
    except OSError as exc:
        return {"state": "UNAVAILABLE", "error_class": type(exc).__name__}

def sqlite(path):
    s = stat_path(path)
    if s["state"] != "PRESENT" or not s["is_file"]:
        return s
    try:
        # Fail closed on a swapped symlink leaf; never follow it to another file.
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        with os.fdopen(os.open(path, flags), "rb") as f:
            header = f.read(16)
        return {**s, "sqlite_header_valid": header == b"SQLite format 3\0",
                "integrity_check": "NOT_RUN"}
    except OSError as exc:
        return {"state": "UNAVAILABLE", "error_class": type(exc).__name__}

def indexed_targets(paths, reader):
    # Public Actions logs must not disclose private DB/backup/lock path names.
    return {"target_" + str(i + 1): reader(path) for i, path in enumerate(paths)}

def capture(args):
    # Device topology must not disclose private mountpoint paths in CI logs.
    topo = command(["lsblk", "-b", "-J", "-o", "NAME,SIZE,FSTYPE,TYPE"])
    if topo["state"] == "OBSERVED":
        try:
            # Defense in depth: strip unexpected path-bearing fields from JSON.
            def scrub_device(node):
                if isinstance(node, list):
                    return [scrub_device(x) for x in node]
                if isinstance(node, dict):
                    return {k: scrub_device(v) for k, v in node.items()
                            if k.lower() in {"blockdevices", "children", "name", "size", "fstype", "type"}}
                return node
            topo = {"state": "OBSERVED", "devices": scrub_device(json.loads(topo["output"]))}
        except ValueError:
            topo = {"state": "UNAVAILABLE", "error_class": "InvalidLsblkJson"}
    try:
        load = list(os.getloadavg())
    except OSError:
        load = None
    return {"schema": "f01-vps-console-readonly.v1",
            "observed_utc": dt.datetime.now(UTC).isoformat(),
            "read_only": True, "production_change": False, "deployment_authorized": False,
            "path_labels_redacted": True,
            "guest": {"uid": os.getuid(), "cpu_count": os.cpu_count(),
                      "loadavg": load, "memory": memory()},
            "filesystem": indexed_targets(args.mount, mount),
            "block_topology": topo, "cron": cron(), "worker": workers(),
            "queue": indexed_targets(args.queue, queue),
            "locks": indexed_targets(args.lock, stat_path),
            "sqlite": indexed_targets(args.sqlite, sqlite),
            "backup": indexed_targets(args.backup, stat_path),
            "offhost_backup_restored": "NOT_VERIFIED",
            "worker_running_verified": False,
            "notes": ["Process-name matches do not prove worker health.",
                      "No SQLite integrity, backup restore, resize, deletion or restart."]}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("mount", "queue", "lock", "sqlite", "backup"):
        p.add_argument("--" + key, action="append", default=[])
    a = p.parse_args()
    if not a.mount:
        a.mount = ["/", "/home", "/home/githubops/factory-runtime"]
    json.dump(capture(a), sys.stdout, ensure_ascii=False, sort_keys=True, indent=2)
    sys.stdout.write("\n")

if __name__ == "__main__":
    main()
