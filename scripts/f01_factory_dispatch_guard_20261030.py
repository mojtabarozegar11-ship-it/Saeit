#!/usr/bin/env python3
"""Read-only admission guard for new VPS factory scheduler work.

Unlike a diagnostic, the entrypoint returns a nonzero exit code when the
host is overloaded or cannot prove enough unprivileged storage headroom.
No writes, process signals, cron mutations, database access or secrets.
"""
import argparse
import json
import math
import os
from pathlib import Path

MIN_AVAILABLE_BYTES = 1024 ** 3
MIN_AVAILABLE_INODES = 1000
MAX_LOAD_PER_CPU = 2.0

def assess(cpu_count, one_min_load, available_bytes, available_inodes):
    reasons = []
    if type(cpu_count) is not int or cpu_count < 1:
        reasons.append("CPU_COUNT_UNAVAILABLE")
    if type(one_min_load) not in (int, float) or not math.isfinite(one_min_load):
        reasons.append("LOAD_UNAVAILABLE")
    elif type(cpu_count) is int and cpu_count >= 1 and one_min_load > cpu_count * MAX_LOAD_PER_CPU:
        reasons.append("ONE_MINUTE_LOAD_OVER_LIMIT")
    if type(available_bytes) is not int or available_bytes < MIN_AVAILABLE_BYTES:
        reasons.append("UNPRIVILEGED_DISK_HEADROOM_LOW")
    if type(available_inodes) is not int or available_inodes < MIN_AVAILABLE_INODES:
        reasons.append("UNPRIVILEGED_INODES_LOW")
    return {"schema": "f01-factory-dispatch-guard.v1",
            "decision": "SKIP" if reasons else "ADMIT",
            "reasons": reasons,
            "load_limit_per_cpu": MAX_LOAD_PER_CPU,
            "min_unprivileged_available_bytes": MIN_AVAILABLE_BYTES,
            "no_process_signals": True,
            "no_files_modified": True}

def inspect(ops):
    p = Path(ops)
    try:
        if not p.is_absolute() or any(x.is_symlink() for x in (p, *p.parents)):
            raise ValueError("INVALID_OR_SYMLINKED_OPS")
        if not p.is_dir():
            raise ValueError("OPS_NOT_DIRECTORY")
        fs = os.statvfs(p)
        return assess(os.cpu_count(), os.getloadavg()[0],
                      fs.f_frsize * fs.f_bavail, fs.f_favail)
    except (OSError, ValueError) as exc:
        return {"schema": "f01-factory-dispatch-guard.v1",
                "decision": "SKIP",
                "reasons": ["HOST_EVIDENCE_UNAVAILABLE"],
                "error_class": type(exc).__name__,
                "no_process_signals": True, "no_files_modified": True}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ops", required=True)
    args = ap.parse_args()
    result = inspect(args.ops)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"] == "ADMIT" else 75

if __name__ == "__main__":
    raise SystemExit(main())
