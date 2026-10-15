#!/usr/bin/env python3
"""Bounded standalone CPU rendering proof using the existing private tiny checkpoint.

Companion backend is stable-diffusion.cpp, not native ComfyUI inference.
"""
import fcntl
import hashlib
import os
from pathlib import Path
import resource
import signal
import struct
import subprocess
import sys
import threading
import time

home = Path.home()
root = home / "comfyui-isolated"
exe_dir = root / ".control/sd-cpp-runtime/bin"
executable = exe_dir / "sd-cli"
model = root / "source-v0.40.0/models/checkpoints/segmind_tiny_sd_candidate.safetensors"
state = root / ".control/qa-render"
factory_file = home / "factory-runtime/operations/vps-only-loop.pid"


def factory_ok():
    try:
        pid = int(factory_file.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, OSError):
        return False


def available_ram():
    with open("/proc/meminfo", encoding="utf-8") as inp:
        for line in inp:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1])
    return 0


def limits():
    os.nice(17)
    cap = 2_850_000_000
    resource.setrlimit(resource.RLIMIT_DATA, (cap, cap))


def run():
    if not executable.is_file() or not model.is_file():
        raise RuntimeError("CPU_COMPANION_NOT_STAGED_OR_MODEL_MISSING")
    if available_ram() < 2_900_000 or not factory_ok():
        raise RuntimeError("FACTORY_OR_AVAILABLE_RAM_GUARD_BLOCKED")
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state, 0o700)
    output = state / "cpu_companion_smoke.png"
    if output.exists():
        output.unlink()
    with (state / "qa.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        env = dict(os.environ, LD_LIBRARY_PATH=str(exe_dir), OMP_NUM_THREADS="1",
                   OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", MALLOC_ARENA_MAX="2")
        args = [str(executable), "-m", str(model), "-p",
                "green seedling in a sunlit agricultural field, watercolor painting",
                "-W", "512", "-H", "512", "--steps", "4", "--seed", "42",
                "--cfg-scale", "7", "--sampling-method", "euler_a",
                "--diffusion-fa", "-o", str(output)]
        logfile = state / "cpu-companion.log"
        with logfile.open("wb") as fp:
            child = subprocess.Popen(
                args, stdout=fp, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                cwd=str(state), env=env, start_new_session=True, preexec_fn=limits,
            )
            stopped = threading.Event()
            protected = []
            def monitor():
                while not stopped.is_set() and child.poll() is None:
                    if available_ram() < 950_000 or not factory_ok():
                        protected.append("RAM_OR_FACTORY_WATCHDOG_ABORT")
                        try:
                            os.killpg(child.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        return
                    stopped.wait(0.25)
            watcher = threading.Thread(target=monitor, daemon=True)
            watcher.start()
            try:
                try:
                    code = child.wait(timeout=240)
                except subprocess.TimeoutExpired:
                    raise RuntimeError("CPU_COMPANION_RENDER_TIME_BUDGET_EXCEEDED")
                if protected:
                    raise RuntimeError(protected[0])
                if code != 0:
                    raise RuntimeError("CPU_COMPANION_EXIT_" + str(code))
                if not output.is_file():
                    raise RuntimeError("CPU_COMPANION_PNG_MISSING")
                data = output.read_bytes()
                if len(data) < 1000 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise RuntimeError("CPU_COMPANION_OUTPUT_NOT_PNG")
                w, h = struct.unpack(">II", data[16:24])
                if (w, h) != (512, 512):
                    raise RuntimeError("CPU_COMPANION_WRONG_DIMENSIONS")
                print("CPU_COMPANION_REAL_PNG_VERIFIED", flush=True)
                print("CPU_COMPANION_IMAGE_BYTES=" + str(len(data)), flush=True)
                print("CPU_COMPANION_IMAGE_DIMENSIONS=512x512", flush=True)
                print("CPU_COMPANION_IMAGE_SHA256=" + hashlib.sha256(data).hexdigest(), flush=True)
                return
            finally:
                stopped.set()
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=8)
                watcher.join(timeout=2)
                print("CPU_COMPANION_CHILD_CLEANUP_DONE", flush=True)
                print("CPU_COMPANION_FACTORY_ALIVE_AFTER=" + str(factory_ok()), flush=True)


try:
    run()
except Exception as exc:
    print("CPU_COMPANION_QA_FAILED=" + type(exc).__name__ + ":" + str(exc)[:100], flush=True)
    sys.exit(1)
