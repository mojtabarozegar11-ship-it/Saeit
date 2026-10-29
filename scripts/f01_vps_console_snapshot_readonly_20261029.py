#!/usr/bin/env python3
"""F-01 bounded read-only VPS guest evidence snapshot; no SSH, writes, or deploy."""
import argparse
import errno
import stat
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

def cron_schedule_summary(lines):
    """Summarize cron cadence without returning commands, schedules or paths."""
    per_minute = factory_per_minute = special = 0
    for line in lines:
        parts = line.split(None, 5)
        if not parts:
            continue
        if parts[0].startswith("@"):
            special += 1
        elif len(parts) >= 6 and parts[0] in ("*", "*/1") and all(x == "*" for x in parts[1:5]):
            per_minute += 1
            if "factory" in line.lower() or "master-agent" in line.lower():
                factory_per_minute += 1
    return {"per_minute_entries": per_minute,
            "factory_per_minute_entries": factory_per_minute,
            "special_entries": special,
            "exact_duplicate_entries": len(lines) - len(set(lines)),
            "commands_and_schedules_redacted": True}

def cron():
    x = command(["crontab", "-l"])
    if x["state"] != "OBSERVED":
        return x
    lines = [s.strip() for s in x["output"].splitlines()
             if s.strip() and not s.lstrip().startswith("#") and "=" not in s.split()[0]]
    return {"state": "OBSERVED", "active_entries": len(lines),
            "factory_entries": sum("factory" in s.lower() for s in lines),
            **cron_schedule_summary(lines),
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


def parse_proc_stat(raw):
    """Parse /proc/PID/stat without confusing parentheses in process names."""
    _, marker, tail = raw.rpartition(") ")
    if not marker:
        raise ValueError("Malformed proc stat")
    fields = tail.split()
    if len(fields) < 20:
        raise ValueError("Short proc stat")
    return {"state": fields[0], "ppid": int(fields[1]),
            "cpu_ticks": int(fields[11]) + int(fields[12]),
            "threads": int(fields[17])}



def classify_process_origin(executable, cmdline):
    """Return only a fixed category; never expose command lines or process IDs."""
    name = executable.lower()
    cmd = cmdline.lower()
    if name in ("cron", "crond") or b"/cron" in cmd or b"crond" in cmd:
        return "cron"
    if name == "systemd" or b"/systemd" in cmd:
        return "systemd"
    if b"master-agent" in cmd or b"master_agent" in cmd:
        return "master-agent"
    if b"factory" in cmd:
        return "factory"
    if name.startswith("python"):
        return "python"
    if name in ("bash", "sh", "dash"):
        return "shell"
    return "other"

def dominant_parent_origin(pid):
    """Inspect only a bounded parent chain; output fixed categories, not PIDs/argv."""
    lineage = []
    seen = set()
    status = "OBSERVED"
    for _ in range(8):
        if pid <= 1 or pid in seen:
            break
        seen.add(pid)
        try:
            with open("/proc/" + str(pid) + "/stat", encoding="utf-8") as handle:
                meta = parse_proc_stat(handle.read(4096))
            with open("/proc/" + str(pid) + "/cmdline", "rb") as handle:
                cmd = handle.read(4096).replace(b"\0", b" ")
            try:
                exe = os.path.basename(os.readlink("/proc/" + str(pid) + "/exe"))
            except OSError:
                exe = "unavailable"
            lineage.append({"category": classify_process_origin(exe, cmd),
                            "state": meta["state"][:1],
                            "threads": meta["threads"]})
            pid = meta["ppid"]
        except (OSError, ValueError, IndexError):
            status = "PARTIAL"
            break
    return {"state": status, "lineage": lineage, "depth_observed": len(lineage),
            "pid_argv_and_paths_redacted": True}


def process_pressure():
    """Aggregate process storm evidence; never emit PID, command line or private path."""
    states, factory_states, executable_types, parents = {}, {}, {}, {}
    parent_child_states = {}
    scanned = factory = factory_threads = factory_cpu_ticks = 0
    limit = 1200
    try:
        for entry in os.scandir("/proc"):
            if not entry.name.isdigit():
                continue
            scanned += 1
            if scanned > limit:
                break
            try:
                with open("/proc/" + entry.name + "/stat", encoding="utf-8") as handle:
                    meta = parse_proc_stat(handle.read(4096))
                with open("/proc/" + entry.name + "/cmdline", "rb") as handle:
                    cmd = handle.read(4096).replace(b"\0", b" ").lower()
            except (OSError, ValueError, IndexError):
                continue
            state = meta["state"][:1]
            states[state] = states.get(state, 0) + 1
            if b"factory" not in cmd and b"master-agent" not in cmd:
                continue
            factory += 1
            factory_states[state] = factory_states.get(state, 0) + 1
            factory_threads += meta["threads"]
            factory_cpu_ticks += meta["cpu_ticks"]
            parent = meta["ppid"]
            parents[parent] = parents.get(parent, 0) + 1
            by_state = parent_child_states.setdefault(parent, {})
            by_state[state] = by_state.get(state, 0) + 1
            try:
                executable = os.path.basename(os.readlink("/proc/" + entry.name + "/exe")).lower()
            except OSError:
                executable = "unavailable"
            if executable.startswith("python"):
                kind = "python"
            elif executable.startswith("node"):
                kind = "node"
            elif executable in ("bash", "sh", "dash"):
                kind = "shell"
            elif executable in ("cron", "crond"):
                kind = "cron"
            elif executable == "unavailable":
                kind = "unavailable"
            else:
                kind = "other"
            executable_types[kind] = executable_types.get(kind, 0) + 1
        dominant = max(parents, key=parents.get) if parents else None
        origin = dominant_parent_origin(dominant) if dominant is not None else {"state": "NONE", "lineage": [], "depth_observed": 0, "pid_argv_and_paths_redacted": True}
        return {"state": "OBSERVED", "pids_scanned": min(scanned, limit),
                "truncated": scanned > limit, "all_process_states": states,
                "factory_name_matches": factory, "factory_states": factory_states,
                "factory_threads": factory_threads,
                "factory_cpu_ticks_cumulative": factory_cpu_ticks,
                "factory_distinct_parent_count": len(parents),
                "factory_max_children_same_parent": max(parents.values(), default=0),
                "dominant_parent_child_states": parent_child_states.get(dominant, {}),
                "dominant_parent_origin": origin,
                "factory_executable_categories": executable_types,
                "pid_command_and_paths_redacted": True,
                "worker_health_verified": False}
    except OSError as exc:
        return {"state": "UNAVAILABLE", "error_class": type(exc).__name__}

def queue(path):
    """Count entries through no-follow directory descriptors; never enumerate contents."""
    try:
        if has_symlink_component(path):
            return {"state": "SYMLINK_NOT_FOLLOWED"}
        parts = Path(path).absolute().parts
        flags = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                 | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
        fd = os.open("/", flags)
        try:
            for component in parts[1:]:
                next_fd = os.open(component, flags, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            count = 0
            with os.scandir(fd) as entries:
                for _ in entries:
                    count += 1
                    if count >= LIMIT:
                        break
            return {"state": "OBSERVED", "entries_at_least": count,
                    "truncated": count >= LIMIT, "contents_redacted": True}
        finally:
            os.close(fd)
    except FileNotFoundError:
        return {"state": "MISSING"}
    except OSError as exc:
        return {"state": "UNAVAILABLE", "error_class": type(exc).__name__}

def _open_sqlite_regular_nofollow(path):
    """Open each directory component by fd, blocking ancestor/leaf link swaps."""
    parts = Path(path).absolute().parts
    dir_flags = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                 | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    leaf_flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                  | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    parent_fd = os.open("/", dir_flags)
    try:
        for component in parts[1:-1]:
            next_fd = os.open(component, dir_flags, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = next_fd
        leaf_fd = os.open(parts[-1], leaf_flags, dir_fd=parent_fd)
        try:
            if not stat.S_ISREG(os.fstat(leaf_fd).st_mode):
                raise OSError(errno.EINVAL, "Not a regular SQLite file")
            return leaf_fd
        except BaseException:
            os.close(leaf_fd)
            raise
    finally:
        os.close(parent_fd)


def sqlite(path):
    """Read SQLite magic only; no SQLite connection or integrity/write attempt."""
    try:
        fd = _open_sqlite_regular_nofollow(path)
        with os.fdopen(fd, "rb") as f:
            metadata = os.fstat(f.fileno())
            header = f.read(16)
        return {"state": "PRESENT", "is_file": True, "is_dir": False,
                "bytes": metadata.st_size,
                "mtime_utc": dt.datetime.fromtimestamp(metadata.st_mtime, UTC).isoformat(),
                "sqlite_header_valid": header == b"SQLite format 3\0",
                "integrity_check": "NOT_RUN"}
    except FileNotFoundError:
        return {"state": "MISSING"}
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
            "block_topology": topo, "cron": cron(), "worker": workers(), "process_pressure": process_pressure(),
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
