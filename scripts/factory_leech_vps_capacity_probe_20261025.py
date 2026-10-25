#!/usr/bin/env python3
"""Read-only owner VPS resource preflight for an offline leech manuscript engine.

Does not run or download a model, read secrets, inspect customer data, or mutate files.
"""
import json
import os
from pathlib import Path
import shutil


def meminfo_mib():
    wanted = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    result = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0].rstrip(":") in wanted:
            result[fields[0].rstrip(":")] = round(int(fields[1]) / 1024)
    return result


def cgroup_mib(path):
    try:
        raw = Path(path).read_text().strip()
        return None if raw == "max" else round(int(raw) / (1024**2))
    except (OSError, ValueError):
        return None


def main():
    runtime = Path("/home/githubops/factory-runtime")
    disk = os.statvfs(str(runtime))
    result = {
        "memory_mib": meminfo_mib(),
        "cgroup_memory_limit_mib": cgroup_mib("/sys/fs/cgroup/memory.max"),
        "cgroup_memory_used_mib": cgroup_mib("/sys/fs/cgroup/memory.current"),
        "cpu_count": os.cpu_count(),
        "load_average_1_5_15": [round(v, 2) for v in os.getloadavg()],
        "disk_free_gib": round(disk.f_bavail * disk.f_frsize / 1024**3, 2),
        "toolchain": {name: bool(shutil.which(name)) for name in ("cmake", "git", "g++", "curl", "flock", "nice", "systemd-run", "crontab")},
    }
    print("LEECH_VPS_CAPACITY=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
