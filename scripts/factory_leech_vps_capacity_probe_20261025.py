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
    operations = runtime / "operations/production-instructions"
    engine = operations / "leech-offline-engine-20261025"
    status = engine / "self-hosted-author-status.json"
    model = engine / "models/Qwen3-1.7B-Q4_K_M.gguf"
    executable = engine / "bin/llama-server"
    result["selfhosted_engine_binary_ready"] = executable.is_file() and os.access(executable, os.X_OK)
    result["selfhosted_model_bytes"] = model.stat().st_size if model.is_file() and not model.is_symlink() else 0
    if status.is_file() and not status.is_symlink() and status.stat().st_size < 12000:
        try:
            current = json.loads(status.read_text(encoding="utf-8"))
            result["selfhosted_last_cycle"] = {
                k: current.get(k) for k in
                ("result", "reason", "verified_words", "accepted_words", "next_chapter",
                 "next_part", "checked_utc", "paid_inference_api_cost_usd", "published")
            }
        except (OSError, ValueError):
            result["selfhosted_last_cycle"] = "unreadable"
    print("LEECH_VPS_CAPACITY=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
