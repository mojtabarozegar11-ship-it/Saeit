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
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        result["selfhosted_private_inference_port_open"] = probe.connect_ex(("127.0.0.1", 18767)) == 0
    result["selfhosted_model_bytes"] = model.stat().st_size if model.is_file() and not model.is_symlink() else 0
    partial = engine / "models/Qwen3-1.7B-Q4_K_M.gguf.partial"
    result["selfhosted_model_partial_bytes"] = partial.stat().st_size if partial.is_file() and not partial.is_symlink() else 0
    try:
        import subprocess
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=4)
        result["selfhosted_cron_installed"] = ("saeit-private-leech-vps-selfhosted-author-20261025" in cron.stdout)
    except (OSError, subprocess.TimeoutExpired):
        result["selfhosted_cron_installed"] = False
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
    try:
        import platform
        import subprocess
        result["platform_libc"] = platform.libc_ver()
        result["platform_machine"] = platform.machine()
        env = {**os.environ, "LD_LIBRARY_PATH": str(engine / "bin")}
        if executable.is_file() and os.access(executable, os.X_OK):
            smoke = subprocess.run([str(executable), "--help"],
                    capture_output=True, text=True, timeout=8, env=env)
            result["selfhosted_binary_smoke_exit"] = smoke.returncode
            if smoke.returncode != 0:
                result["selfhosted_binary_smoke_error"] = (smoke.stderr or smoke.stdout)[-400:]
        dynamic = subprocess.run(["ldd", str(executable)],
                    capture_output=True, text=True, timeout=8, env=env)
        result["selfhosted_missing_dynamic_libs"] = [
            line.strip().split()[0] for line in dynamic.stdout.splitlines()
            if "not found" in line
        ][:12]
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["selfhosted_binary_smoke_error"] = type(exc).__name__
    try:
        cpu_first = Path("/proc/cpuinfo").read_text(encoding="utf-8").split("\n\n", 1)[0]
        cpu_map = dict((part.split(":",1)[0].strip(),part.split(":",1)[1].strip()) for part in cpu_first.splitlines() if ":" in part)
        flags = set(cpu_map.get("flags", "").split())
        result["cpu_model"] = cpu_map.get("model name", "").strip()[:85]
        result["cpu_relevant_flags"] = sorted(set((
            "sse2","ssse3","sse4_1","sse4_2","avx","avx2","fma",
            "f16c","bmi1","bmi2","avx512f","avx512bw","avx512_vnni"
        )) & flags)
    except OSError:
        result["cpu_relevant_flags"] = []
    # Inspect only this leech operator's processes; never report other VPS jobs or arguments.
    try:
        import subprocess
        ps = subprocess.run(["ps", "-eo", "pid=,etimes=,time=,stat=,comm="],
                            capture_output=True, text=True, timeout=5)
        active = []
        if ps.returncode == 0:
            for row in ps.stdout.splitlines():
                fields = row.strip().split(None, 4)
                if len(fields) != 5:
                    continue
                pid, elapsed, cpu_time, state, name = fields
                if name not in ("llama-server", "python3"):
                    continue
                if name == "python3":
                    try:
                        cmdline = (Path("/proc") / pid / "cmdline").read_bytes()
                        if b"leech-vps-resource-guarded-author.py" not in cmdline:
                            continue
                    except OSError:
                        continue
                active.append({"program": "llama-server" if name == "llama-server" else "leech-author",
                               "elapsed_seconds": int(elapsed), "cpu_time": cpu_time,
                               "state": state[:8]})
        result["selfhosted_active_workers"] = active
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result["selfhosted_active_workers"] = "unavailable"
    # Query only bounded numeric slot-progress fields from the private loopback engine;
    # intentionally never return prompts, outputs, tokens or other manuscript data.
    if result.get("selfhosted_private_inference_port_open"):
        try:
            import urllib.request
            with urllib.request.urlopen("http://127.0.0.1:18767/slots", timeout=3) as response:
                slots = json.load(response)
            counters = []
            if isinstance(slots, list):
                for slot in slots[:2]:
                    if not isinstance(slot, dict):
                        continue
                    row = {str(k)[:60]: v for k, v in list(slot.items())[:65]
                           if isinstance(v, (int, float, bool))}
                    for key in ("generated_text", "prompt"):
                        if isinstance(slot.get(key), str):
                            row[key + "_char_count_only"] = len(slot[key])
                    for key in ("timings", "generation", "task"):
                        if isinstance(slot.get(key), dict):
                            row[key + "_numbers_only"] = {str(k)[:40]: v
                                for k, v in list(slot[key].items())[:24]
                                if isinstance(v, (int, float, bool))}
                    counters.append(row)
            result["selfhosted_token_progress"] = counters
        except (OSError, ValueError, TypeError):
            result["selfhosted_token_progress"] = "slots_endpoint_unavailable"
    # Determine actual accepted words even if the operator status only updates at completion.
    try:
        author = operations / "leech-professional-author.py"
        if author.is_file() and not author.is_symlink():
            checkpoint = subprocess.run(["/usr/bin/python3", "-B", str(author), "status"],
                            capture_output=True, text=True, timeout=15,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            if checkpoint.returncode == 0:
                progress = json.loads(checkpoint.stdout)
                result["selfhosted_verified_private_manuscript"] = {
                    k: progress.get(k) for k in ("order_id", "verified_unreviewed_prose_words",
                                                "next_chapter", "next_part", "quality1000_approved")}
            else:
                result["selfhosted_verified_private_manuscript"] = "readonly_status_unavailable"
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result["selfhosted_verified_private_manuscript"] = "readonly_status_unavailable"
    print("LEECH_VPS_CAPACITY=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
