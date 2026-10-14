#!/usr/bin/env python3
"""Bounded, local-only ComfyUI CPU inference QA; preserves factory processes."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

home = Path.home()
root = home / "comfyui-isolated"
source = root / "source-v0.40.0"
python = root / "env-cpu/bin/python"
state = root / ".control" / "qa-render"
checkpoint = source / "models/checkpoints/segmind_tiny_sd_candidate.safetensors"
factory_pidfile = home / "factory-runtime/operations/vps-only-loop.pid"
base = "http://127.0.0.1:18190"
limit_seconds = 240

def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def factory_alive():
    try:
        pid = int(factory_pidfile.read_text().strip())
        return alive(pid)
    except (OSError, ValueError):
        return False

def mem_avail_kib():
    with open("/proc/meminfo", encoding="ascii") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1])
    return 0

def http_json(path, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = Request(base + path, headers=headers, data=data)
    with urlopen(req, timeout=timeout) as reply:
        return json.load(reply)

def guard_limits():
    os.nice(17)
    cap = 2_850_000_000
    resource.setrlimit(resource.RLIMIT_DATA, (cap, cap))

def main():
    if not source.joinpath("main.py").is_file() or not python.is_file() or not checkpoint.is_file():
        raise RuntimeError("MISSING_COMFYUI_CPU_RUNTIME_OR_CHECKPOINT")
    if mem_avail_kib() < 2_900_000:
        raise RuntimeError("INSUFFICIENT_AVAILABLE_RAM")
    if not factory_alive():
        raise RuntimeError("FACTORY_LOOP_NOT_VERIFIED_REFUSE")
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 18190)) == 0:
            raise RuntimeError("QA_PORT_BUSY_REFUSE")
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state, 0o700)
    with (state / "qa.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        log = state / "qa-run.log"
        env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                   OPENBLAS_NUM_THREADS="1", MALLOC_ARENA_MAX="2",
                   PYTHONNOUSERSITE="1")
        with log.open("wb") as log_fp:
            child = subprocess.Popen(
                [str(python), "main.py", "--cpu", "--listen", "127.0.0.1",
                 "--port", "18190", "--disable-auto-launch"],
                cwd=str(source), stdout=log_fp, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, env=env, start_new_session=True,
                preexec_fn=guard_limits,
            )
            trouble = []
            finished = threading.Event()
            def monitor():
                while not finished.is_set() and child.poll() is None:
                    if mem_avail_kib() < 950_000 or not factory_alive():
                        trouble.append("RESOURCE_GUARD_ABORTED")
                        try:
                            os.killpg(child.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        return
                    finished.wait(0.2)
            watcher = threading.Thread(target=monitor, daemon=True)
            watcher.start()
            try:
                started = time.monotonic()
                while time.monotonic() - started < 65:
                    if child.poll() is not None:
                        raise RuntimeError("COMFYUI_SERVER_EXITED_BEFORE_HEALTH")
                    if trouble:
                        raise RuntimeError(trouble[0])
                    try:
                        if http_json("/system_stats").get("system"):
                            print("QA_COMFYUI_CPU_API_HEALTHY", flush=True)
                            break
                    except (URLError, ValueError, TimeoutError):
                        pass
                    time.sleep(1)
                else:
                    raise RuntimeError("COMFYUI_START_TIMEOUT")
                model = "segmind_tiny_sd_candidate.safetensors"
                graph = {
                    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
                    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 128, "height": 128, "batch_size": 1}},
                    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "green seedling in a sunny farm field", "clip": ["4", 1]}},
                    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "text, logo, watermark", "clip": ["4", 1]}},
                    "3": {"class_type": "KSampler", "inputs": {
                        "seed": 42, "steps": 3, "cfg": 5.0, "sampler_name": "euler",
                        "scheduler": "normal", "denoise": 1.0,
                        "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
                        "latent_image": ["5", 0]}},
                    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
                    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "saeit_comfy_cpu_smoke", "images": ["8", 0]}},
                }
                answer = http_json("/prompt", {"prompt": graph, "client_id": str(uuid.uuid4())}, 25)
                if answer.get("error") or answer.get("node_errors"):
                    raise RuntimeError("COMFYUI_GRAPH_REJECTED")
                prompt_id = answer.get("prompt_id")
                if not prompt_id:
                    raise RuntimeError("COMFYUI_PROMPT_NOT_ACCEPTED")
                print("QA_PROMPT_ACCEPTED", flush=True)
                deadline = time.monotonic() + 145
                while time.monotonic() < deadline:
                    if trouble:
                        raise RuntimeError(trouble[0])
                    if child.poll() is not None:
                        raise RuntimeError("COMFYUI_SERVER_EXITED_DURING_GENERATION")
                    history = http_json("/history/" + str(prompt_id), timeout=15)
                    if str(prompt_id) in history:
                        record = history[str(prompt_id)]
                        files = record.get("outputs", {}).get("9", {}).get("images", [])
                        if not files:
                            raise RuntimeError("COMFYUI_JOB_FINISHED_NO_OUTPUT")
                        record_file = files[0]
                        params = urlencode({"filename": record_file["filename"],
                                            "subfolder": record_file.get("subfolder", ""),
                                            "type": record_file.get("type", "output")})
                        with urlopen(base + "/view?" + params, timeout=20) as response:
                            body = response.read(5_000_000)
                        if not (body.startswith(b"\x89PNG\r\n\x1a\n") and len(body) > 500):
                            raise RuntimeError("COMFYUI_OUTPUT_NOT_A_REAL_PNG")
                        output = state / "comfy_cpu_sample.png"
                        output.write_bytes(body)
                        output.chmod(0o600)
                        print("QA_REAL_PNG_BYTES=" + str(len(body)), flush=True)
                        print("QA_REAL_PNG_SHA256=" + hashlib.sha256(body).hexdigest(), flush=True)
                        print("QA_FACTORY_ALIVE=" + str(factory_alive()), flush=True)
                        return
                    time.sleep(3)
                raise RuntimeError("COMFYUI_CPU_RENDER_TIMEOUT")
            finally:
                finished.set()
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=8)
                watcher.join(timeout=2)
                print("QA_COMFYUI_TEST_PROCESS_STOPPED", flush=True)
                print("QA_FACTORY_ALIVE_AFTER=" + str(factory_alive()), flush=True)

try:
    main()
except Exception as exc:
    print("QA_RESULT_FAILED=" + type(exc).__name__ + ":" + str(exc)[:100], flush=True)
    sys.exit(1)
