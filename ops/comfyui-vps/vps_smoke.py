#!/usr/bin/env python3
"""Isolated VPS CPU image proof. Produces only a small fixed demo PNG.

No public listener, root permissions, factory changes, external prompts, or
checkpoint downloads. The child process has a separate process group and a
real-time RAM/factory watchdog.
"""
from __future__ import annotations

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

HOME = Path.home()
BASE = HOME / "comfyui-isolated"
ENGINE_DIR = BASE / ".control/sd-cpp-runtime/bin"
ENGINE = ENGINE_DIR / "sd-cli"
MODEL = BASE / "source-v0.40.0/models/checkpoints/segmind_tiny_sd_candidate.safetensors"
FACTORY_PID = HOME / "factory-runtime/operations/vps-only-loop.pid"
STATE = BASE / ".control/qa-render"
OUTPUT = STATE / "vps_cpu_smoke_256.png"
CHECKPOINT_SHA256 = "92e00b860c409f8cfc521a94f779009c6ebd28bf07670bf50e747682ab7b3b72"

def factory_ok():
    try:
        pid = int(FACTORY_PID.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False

def available_kib():
    with open("/proc/meminfo", encoding="ascii") as stream:
        for line in stream:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1])
    raise RuntimeError("Cannot inspect available RAM")

def child_limits():
    os.nice(17)
    cap = 3_000_000_000
    resource.setrlimit(resource.RLIMIT_DATA, (cap, cap))

def verify_file():
    if not MODEL.is_file() or MODEL.is_symlink():
        raise RuntimeError("Installed private Tiny-SD checkpoint is missing")
    digest = hashlib.sha256()
    with MODEL.open("rb") as stream:
        for chunk in iter(lambda: stream.read(2 * 1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != CHECKPOINT_SHA256:
        raise RuntimeError("Installed checkpoint SHA-256 mismatch")

def main():
    if os.geteuid() == 0:
        raise RuntimeError("Must run as unprivileged VPS account")
    if not ENGINE.is_file() or not os.access(ENGINE, os.X_OK):
        raise RuntimeError("Private sd-cli binary not present")
    verify_file()
    if not factory_ok() or available_kib() < 2_850_000:
        raise RuntimeError("Factory or safe RAM headroom could not be verified")
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    with (STATE / "qa.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if OUTPUT.exists():
            OUTPUT.unlink()
        args = [
            str(ENGINE), "-m", str(MODEL),
            "-p", "green seedling in a sunny field, watercolor art",
            "-W", "256", "-H", "256", "--steps", "2", "--seed", "42",
            "--cfg-scale", "7", "--sampling-method", "euler_a",
            "--diffusion-fa", "--vae-tiling", "-o", str(OUTPUT),
        ]
        env = dict(os.environ, LD_LIBRARY_PATH=str(ENGINE_DIR),
                   OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                   MKL_NUM_THREADS="1", MALLOC_ARENA_MAX="2")
        logfile = STATE / "vps_smoke.log"
        print("VPS_CPU_PROOF_BEGIN", flush=True)
        with logfile.open("wb") as log:
            proc = subprocess.Popen(
                args, cwd=str(STATE), env=env, stdout=log,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True, preexec_fn=child_limits,
            )
            done = threading.Event()
            abort = []
            def watchdog():
                while not done.wait(0.5) and proc.poll() is None:
                    if not factory_ok() or available_kib() < 975_000:
                        abort.append("Factory/RAM safety stop")
                        try:
                            os.killpg(proc.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        break
            thread = threading.Thread(target=watchdog, daemon=True)
            thread.start()
            try:
                try:
                    status = proc.wait(timeout=360)
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError("CPU inference timed out") from exc
                if abort:
                    raise RuntimeError(abort[0])
                if status:
                    # Never leak environment or private paths through logs.
                    print("VPS_CPU_ENGINE_NONZERO_EXIT=" + str(status), flush=True)
                    raise RuntimeError("CPU renderer exited unsuccessfully")
                raw = OUTPUT.read_bytes()
                if not raw.startswith(bytes.fromhex("89504e470d0a1a0a")):
                    raise RuntimeError("Output not PNG")
                width, height = struct.unpack(">II", raw[16:24])
                if (width, height) != (256, 256) or len(raw) < 1000:
                    raise RuntimeError("Image dimensions or length invalid")
                OUTPUT.chmod(0o600)
                print("VPS_CPU_REAL_PNG_VERIFIED", flush=True)
                print("VPS_CPU_PNG_SIZE=" + str(len(raw)), flush=True)
                print("VPS_CPU_PNG_DIMENSIONS=256x256", flush=True)
                print("VPS_CPU_PNG_SHA256=" + hashlib.sha256(raw).hexdigest(), flush=True)
            finally:
                done.set()
                if proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=8)
                thread.join(timeout=2)
                print("VPS_CPU_CHILD_EXITED", flush=True)
                print("VPS_FACTORY_STILL_ALIVE=" + str(factory_ok()), flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("VPS_CPU_PROOF_FAILED=" + type(exc).__name__ + ":" + str(exc)[:120], flush=True)
        sys.exit(1)
