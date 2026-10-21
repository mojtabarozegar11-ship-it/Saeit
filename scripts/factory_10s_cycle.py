#!/usr/bin/env python3
"""Private 10-second factory dispatcher. A pulse is NOT a quality approval."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

SCHEMA = "saeit.factory.private-10-second-cycle.v1"
TASK_INTERVALS = {"repair": 60, "production_evolution": 120,
                  "generations": 300, "code_improvement": 600}
TIMEOUTS = {"repair": 220, "production_evolution": 220,
            "generations": 220, "code_improvement": 90}

def roots():
    base = Path.home() / "factory-runtime"
    ops = base / "operations"
    private = base / "private" / "autonomous-product-cycle"
    target = ops / "factory-ten-second-v1"
    return base, ops, private, target

def checked():
    base, ops, private, target = roots()
    for path in (base, ops, private, target, target / "modules",
                 private / "quality-excellence"):
        if not path.is_dir() or path.is_symlink():
            raise RuntimeError("TEN_SECOND_UNSAFE_OR_MISSING_ROOT:" + path.name)
    for name in ("factory_autonomous_jump_repair_v1.py",
                 "factory_qa_native_rebuild_bridge_20261021.py",
                 "factory_product_maker.py",
                 "factory_personal_owner_passport_policy_20261020.py",
                 "factory_ten_generation_builder_v1.py",
                 "factory_f19_ten_generations_v1.py", "factory_build_50.py"):
        path = target / "modules" / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("TEN_SECOND_MISSING_MODULE:" + name)
    for path in (ops / "autonomous-product-runtime" / "run-local-cycle.sh",
                 ops / "factory-code-self-upgrade" / "run-scan-and-edit.sh",
                 target / "modules" / "forty_families.json"):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("TEN_SECOND_UNAVAILABLE_TASK:" + path.name)
    state_dir = private / "quality-excellence" / "ten-second-control"
    if state_dir.exists() and (state_dir.is_symlink() or not state_dir.is_dir()):
        raise RuntimeError("TEN_SECOND_UNSAFE_STATE_DIR")
    return base, ops, private, target, state_dir

def atomic_json(path, value):
    if path.exists() and path.is_symlink():
        raise RuntimeError("TEN_SECOND_STATE_SYMLINK")
    fd, name = tempfile.mkstemp(prefix=".pulse-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(value, file, sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def load_state(path):
    if not path.exists():
        return {"schema": SCHEMA, "ticks": 0, "last_started": {}}
    if path.is_symlink() or path.stat().st_size > 65536:
        raise RuntimeError("TEN_SECOND_UNSAFE_STATE")
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema") != SCHEMA or not isinstance(state.get("last_started"), dict):
        raise RuntimeError("TEN_SECOND_STATE_SCHEMA")
    return state

def resources_ok(private):
    available = 0
    with open("/proc/meminfo", encoding="ascii") as file:
        for line in file:
            if line.startswith("MemAvailable:"):
                available = int(line.split()[1]) * 1024
                break
    if available < 850 * 1024 * 1024:
        return False, "memory"
    if shutil.disk_usage(private).free < 3 * 1024 ** 3:
        return False, "disk"
    cores = min(os.cpu_count() or 1, 4)
    if os.getloadavg()[0] > max(1.5, cores * 0.8):
        return False, "cpu"
    return True, "ready"

def choose_due(last_started, now):
    for task, minimum in TASK_INTERVALS.items():
        previous = float(last_started.get(task, 0))
        if now - previous >= minimum:
            return task
    return None

def task_commands(task):
    base, ops, private, target, _ = checked()
    m = target / "modules"
    py = str(base / ".venv" / "bin" / "python")
    root = str(private)
    if task == "repair":
        return [[py, "-B", str(m / "factory_autonomous_jump_repair_v1.py"),
                 "--private-root", root, "--families", str(m / "forty_families.json"),
                 "--source-root", str(private / "generated-product-recipes"),
                 "--maker", str(m / "factory_product_maker.py"),
                 "--bridge", str(m / "factory_qa_native_rebuild_bridge_20261021.py"),
                 "--additional-source-root", str(ops / "autonomous-product-runtime" / "product_recipes"),
                 "--additional-source-root", str(private / "recovered-original-product-recipes"),
                 "--rounds", "1", "--limit", "2"]]
    if task == "production_evolution":
        return [["/bin/bash", str(ops / "autonomous-product-runtime" / "run-local-cycle.sh")]]
    if task == "generations":
        return [
            [py, "-B", str(m / "factory_ten_generation_builder_v1.py"),
             "--private-root", root, "--source-root", str(private / "generated-product-recipes"),
             "--maker", str(m / "factory_product_maker.py"), "--limit", "2"],
            [py, "-B", str(m / "factory_f19_ten_generations_v1.py"),
             "--factory-private", root, "--build50", str(m / "factory_build_50.py")]]
    if task == "code_improvement":
        return [["/bin/bash", str(ops / "factory-code-self-upgrade" / "run-scan-and-edit.sh")]]
    raise ValueError("TEN_SECOND_UNKNOWN_TASK")

def pulse():
    _, _, private, target, state_dir = checked()
    state_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(state_dir, 0o700)
    lock = state_dir / ".pulse.lock"
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(), 0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("FACTORY_10S_PULSE=BUSY")
            return
        state_path = state_dir / "state.json"
        state = load_state(state_path)
        now = time.time()
        state["ticks"] = int(state.get("ticks", 0)) + 1
        state["last_tick_utc_epoch"] = now
        state["last_decision"] = "heartbeat"
        ok, reason = resources_ok(private)
        work_lock = state_dir / ".worker.lock"
        with work_lock.open("a+b") as worker_guard:
            os.fchmod(worker_guard.fileno(), 0o600)
            if not ok:
                state["last_decision"] = "resource_gate_" + reason
            else:
                try:
                    fcntl.flock(worker_guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    state["last_decision"] = "worker_busy"
                else:
                    fcntl.flock(worker_guard.fileno(), fcntl.LOCK_UN)
                    task = choose_due(state["last_started"], now)
                    if task:
                        proc = subprocess.Popen([sys.executable, "-B", str(target / "factory_10s_cycle.py"),
                                                 "--mode", "work", "--task", task],
                                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                stderr=subprocess.DEVNULL, start_new_session=True,
                                                close_fds=True)
                        state["last_started"][task] = now
                        state["last_decision"] = "dispatched_" + task
                        state["last_worker_pid"] = proc.pid
        atomic_json(state_path, state)
        print("FACTORY_10S_PULSE=" + state["last_decision"])
        print("FACTORY_10S_TICK_COUNT=" + str(state["ticks"]))

def work(task):
    _, _, private, _, state_dir = checked()
    state_dir.mkdir(mode=0o700, exist_ok=True)
    lock = state_dir / ".worker.lock"
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(), 0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        ok, reason = resources_ok(private)
        results = []
        if ok:
            for command in task_commands(task):
                try:
                    proc = subprocess.run(command, timeout=TIMEOUTS[task],
                                          capture_output=True, text=True, check=False,
                                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
                    results.append({"returncode": proc.returncode,
                                    "stdout_tail": proc.stdout[-14000:],
                                    "stderr_tail": proc.stderr[-2000:]})
                except subprocess.TimeoutExpired:
                    results.append({"returncode": 124, "reason": "timeout"})
                if results[-1]["returncode"] != 0:
                    break
        else:
            results.append({"returncode": 75, "reason": "resource_gate_" + reason})
        receipt = {"schema": SCHEMA, "task": task, "finished_at_utc_epoch": time.time(),
                   "all_commands_succeeded": all(item["returncode"] == 0 for item in results),
                   "results": results, "quality_1000_certified": False,
                   "public_release_authorized": False}
        atomic_json(state_dir / ("last-" + task + ".json"), receipt)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("check", "tick", "work"), required=True)
    p.add_argument("--task", choices=tuple(TASK_INTERVALS))
    args = p.parse_args()
    checked()
    if args.mode == "check":
        for task in TASK_INTERVALS:
            task_commands(task)
        print("FACTORY_10S_DEPENDENCIES_CHECKED=PASS")
    elif args.mode == "tick":
        pulse()
    elif not args.task:
        p.error("--task required for work")
    else:
        work(args.task)

if __name__ == "__main__":
    main()
