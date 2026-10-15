#!/usr/bin/env python3
"""VPS-only PICM worker: private HTTPS queue to localhost ComfyUI.

No inbound VPS port. No Termux. No arbitrary shell. Runs as githubops, outside
the existing factory process, with a single non-blocking lock and guarded CPU.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
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
        print("PICM_RENDER_ERROR=" + type(exc).__name__, flush=True)
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
