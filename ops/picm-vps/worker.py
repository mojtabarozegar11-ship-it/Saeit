#!/usr/bin/env python3
"""VPS-only PICM worker: private HTTPS queue to guarded local CPU renderer.

No inbound VPS port. No Termux. No arbitrary shell. Runs as githubops, outside
the existing factory process, with a single non-blocking lock and guarded CPU.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import struct
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

HOME = Path.home()
ROOT = HOME / ".local/share/saeit-picm"
TOKEN = ROOT / "worker-token"
SITE = "https://mojplaywin.com"
LOCAL = "http://127.0.0.1:18188"
CONTROL = ROOT / "control.sh"
FACTORY = HOME / "factory-runtime/operations/vps-only-loop.pid"
HEX = re.compile(r"^[0-9a-f]{32}$")
STEPS = {1, 2, 3}
CPU_ROOT = HOME / "comfyui-isolated"
CPU_BIN_DIR = CPU_ROOT / ".control/sd-cpp-runtime-sse2/bin"
CPU_BIN = CPU_BIN_DIR / "sd-cli"
CPU_MODEL = CPU_ROOT / "source-v0.40.0/models/checkpoints/segmind_tiny_sd_candidate.safetensors"
CPU_STATE = CPU_ROOT / ".control/qa-render"
CPU_MODEL_SHA256 = "92e00b860c409f8cfc521a94f779009c6ebd28bf07670bf50e747682ab7b3b72"
CPU_MIN_KIB = 950_000
CPU_MAX_SECONDS = 360


def authorization():
    if TOKEN.is_symlink() or not TOKEN.is_file():
        raise RuntimeError("MISSING_PRIVATE_WORKER_TOKEN")
    secret = TOKEN.read_text(encoding="ascii").strip()
    if len(secret) < 48 or len(secret) > 128:
        raise RuntimeError("INVALID_PRIVATE_WORKER_TOKEN")
    return secret


def query_api(endpoint, data=None, content_type="application/json", timeout=25, lease=None):
    headers = {"Authorization": "Bearer " + authorization(), "User-Agent": "PICM-Private-Worker/1"}
    if data is not None:
        headers["Content-Type"] = content_type
    if lease:
        headers["X-PICM-Lease"] = lease
    request = Request(SITE + endpoint, headers=headers, data=data)
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read(2_500_000)


def comfy_api(endpoint, data=None, timeout=20):
    body = json.dumps(data).encode() if data is not None else None
    with urlopen(Request(LOCAL + endpoint, data=body,
                         headers={"Content-Type": "application/json"} if body else {}),
                 timeout=timeout) as response:
        return json.load(response)


def factory_ok():
    try:
        pid = int(FACTORY.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def ram_ok():
    try:
        with open("/proc/meminfo", encoding="ascii") as mem:
            for line in mem:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) >= 2_850_000
    except OSError:
        pass
    return False



def free_kib():
    try:
        with open("/proc/meminfo", encoding="ascii") as mem:
            for line in mem:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return 0


def direct_cpu_ready():
    """Prefer the preinstalled SSE2 backend over starting memory-heavy ComfyUI.

    Never download a model, change the factory, or trust an unpinned checkpoint.
    Missing CPU prerequisites fall back to the original localhost-only graph.
    """
    if not CPU_BIN.is_file() or not CPU_MODEL.is_file():
        return False
    if CPU_BIN.is_symlink() or CPU_MODEL.is_symlink() or not os.access(CPU_BIN, os.X_OK):
        raise RuntimeError("PICM_CPU_BACKEND_UNSAFE")
    digest = hashlib.sha256()
    with CPU_MODEL.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != CPU_MODEL_SHA256:
        raise RuntimeError("PICM_CPU_MODEL_INTEGRITY_FAILURE")
    return True


def cpu_child_limits():
    os.nice(17)
    resource.setrlimit(resource.RLIMIT_DATA, (2_850_000_000, 2_850_000_000))


def render_direct_cpu(prompt, steps):
    """Render one real 256px PNG without starting PyTorch/ComfyUI.

    Locks against ComfyUI's own SSE2 render node, guards factory liveness,
    bounds wall time and memory, and refuses placeholder images.
    """
    if not factory_ok() or not ram_ok():
        raise RuntimeError("PICM_CPU_START_GUARD")
    if CPU_STATE.is_symlink():
        raise RuntimeError("PICM_CPU_UNSAFE_STATE")
    CPU_STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(CPU_STATE, 0o700)
    lockfile = CPU_STATE / "qa.lock"
    if lockfile.is_symlink():
        raise RuntimeError("PICM_CPU_UNSAFE_LOCK")
    with lockfile.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("PICM_CPU_RENDER_BUSY") from exc
        with tempfile.TemporaryDirectory(dir=str(CPU_STATE), prefix=".picm-") as work:
            result = Path(work) / "result.png"
            env = dict(os.environ, LD_LIBRARY_PATH=str(CPU_BIN_DIR), OMP_NUM_THREADS="1",
                       OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", MALLOC_ARENA_MAX="2")
            args = [str(CPU_BIN), "-m", str(CPU_MODEL), "-p", prompt, "-W", "256",
                    "-H", "256", "--steps", str(steps), "--seed", "42",
                    "--cfg-scale", "7.0", "--sampling-method", "euler_a",
                    "--diffusion-fa", "--vae-tiling", "--log-level", "error",
                    "-o", str(result)]
            with tempfile.TemporaryFile() as log:
                child = subprocess.Popen(args, cwd=str(CPU_STATE), env=env,
                                         stdin=subprocess.DEVNULL, stdout=log,
                                         stderr=subprocess.STDOUT, start_new_session=True,
                                         preexec_fn=cpu_child_limits)
                limit = time.monotonic() + CPU_MAX_SECONDS
                try:
                    while child.poll() is None and time.monotonic() < limit:
                        if not factory_ok() or free_kib() < CPU_MIN_KIB:
                            raise RuntimeError("PICM_CPU_RUNTIME_GUARD")
                        time.sleep(0.5)
                    if child.poll() is None:
                        raise RuntimeError("PICM_CPU_RENDER_TIMEOUT")
                    if child.returncode != 0 or not result.is_file():
                        raise RuntimeError("PICM_CPU_RENDER_FAILED")
                    png = result.read_bytes()
                    if (not 1024 <= len(png) <= 2_000_000
                            or not png.startswith(b"\x89PNG\r\n\x1a\n")
                            or struct.unpack(">II", png[16:24]) != (256, 256)):
                        raise RuntimeError("PICM_CPU_INVALID_PNG")
                    return png
                finally:
                    if child.poll() is None:
                        os.killpg(child.pid, signal.SIGTERM)
                        try:
                            child.wait(timeout=8)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            child.wait(timeout=8)


def start_comfy_if_needed():
    if not factory_ok() or not ram_ok():
        raise RuntimeError("FACTORY_OR_MEMORY_GUARD_BLOCKED")
    try:
        comfy_api("/system_stats", timeout=3)
        return
    except Exception:
        pass
    if not CONTROL.is_file():
        raise RuntimeError("COMFYUI_PRIVATE_CONTROLLER_MISSING")
    subprocess.run(["bash", str(CONTROL), "start", "15"], check=True,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=85, cwd=str(ROOT))
    comfy_api("/system_stats", timeout=8)


def render(job):
    ident, lease = job["id"], job["lease"]
    prompt, steps = job["prompt"], job["steps"]
    if (not HEX.fullmatch(ident) or not HEX.fullmatch(lease)
            or type(steps) is not int or steps not in STEPS
            or not isinstance(prompt, str) or not 4 <= len(prompt) <= 650):
        raise RuntimeError("INVALID_JOB")
    if direct_cpu_ready():
        return render_direct_cpu(prompt, steps)
    start_comfy_if_needed()
    graph = {
        "1": {"class_type": "SaeitSafeCPURender",
              "inputs": {"prompt": prompt, "steps": steps, "seed": 42, "cfg": 7.0}},
        "2": {"class_type": "SaveImage",
              "inputs": {"images": ["1", 0], "filename_prefix": "picm_private"}},
    }
    result = comfy_api("/prompt", {"prompt": graph, "client_id": str(uuid4())})
    if result.get("node_errors") or not result.get("prompt_id"):
        raise RuntimeError("PRIVATE_IMAGE_PROMPT_REJECTED")
    prompt_id = result["prompt_id"]
    deadline = time.monotonic() + 430
    while time.monotonic() < deadline:
        if not factory_ok() or not ram_ok():
            raise RuntimeError("FACTORY_OR_MEMORY_GUARD_DURING_RENDER")
        history = comfy_api("/history/" + str(prompt_id), timeout=12)
        if str(prompt_id) in history:
            record = history[str(prompt_id)]
            images = record.get("outputs", {}).get("2", {}).get("images", [])
            if not images:
                raise RuntimeError("PRIVATE_RENDER_NO_IMAGE")
            item = images[0]
            url = LOCAL + "/view?" + urlencode({
                "filename": item["filename"], "subfolder": item.get("subfolder", ""),
                "type": item.get("type", "output")})
            with urlopen(url, timeout=25) as response:
                png = response.read(2_000_001)
            if (not 1024 <= len(png) <= 2_000_000
                    or not png.startswith(b"\x89PNG\r\n\x1a\n")
                    or struct.unpack(">II", png[16:24]) != (256, 256)):
                raise RuntimeError("PRIVATE_RENDER_INVALID_PNG")
            return png
        time.sleep(4)
    raise RuntimeError("PRIVATE_RENDER_TIMED_OUT")


def once():
    code, body = query_api("/picm/worker/next/")
    if code == 204:
        return "PICM_QUEUE_EMPTY"
    if code != 200:
        raise RuntimeError("PICM_QUEUE_HTTP_UNEXPECTED")
    job = json.loads(body)
    ident, lease = job.get("id", ""), job.get("lease", "")
    if not HEX.fullmatch(ident) or not HEX.fullmatch(lease):
        raise RuntimeError("PICM_JOB_SCHEMA_INVALID")
    print("PICM_JOB_CLAIMED", flush=True)
    try:
        image = render(job)
    except Exception as exc:
        safe_code = str(exc)
        permitted = {"PICM_CPU_BACKEND_UNSAFE", "PICM_CPU_MODEL_INTEGRITY_FAILURE",
                     "PICM_CPU_START_GUARD", "PICM_CPU_UNSAFE_STATE", "PICM_CPU_UNSAFE_LOCK",
                     "PICM_CPU_RENDER_BUSY", "PICM_CPU_RUNTIME_GUARD",
                     "PICM_CPU_RENDER_TIMEOUT", "PICM_CPU_RENDER_FAILED", "PICM_CPU_INVALID_PNG"}
        print("PICM_RENDER_ERROR=" + (safe_code if safe_code in permitted
                                      else type(exc).__name__), flush=True)
        code, _ = query_api("/picm/worker/finish/" + ident + "/",
                            data=b"{}", lease=lease)
        return "PICM_JOB_REPORTED_FAILED_" + str(code)
    code, _ = query_api("/picm/worker/finish/" + ident + "/", data=image,
                        content_type="image/png", lease=lease, timeout=40)
    return "PICM_JOB_DELIVERED_" + str(code)


def main():
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.umask(0o077)
    lock_path = ROOT / "worker.lock"
    if lock_path.is_symlink():
        raise RuntimeError("PICM_UNSAFE_WORKER_LOCK")
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("PICM_WORKER_ALREADY_ACTIVE", flush=True)
            return 0
        while True:
            try:
                print(once(), flush=True)
            except Exception as exc:
                print("PICM_WORKER_RECOVERABLE_ERROR=" + type(exc).__name__, flush=True)
            time.sleep(60)


if __name__ == "__main__":
    sys.exit(main())
