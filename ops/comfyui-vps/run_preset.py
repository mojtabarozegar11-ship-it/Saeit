#!/usr/bin/env python3
"""Submit allowlisted public-demo presets to the authenticated SSH-only ComfyUI API.

No freeform prompt is sent through public GitHub Actions workflow inputs.
"""
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PRESETS = {
    "orchard": "a beautiful sunlit almond orchard with precise rows of trees, cinematic landscape",
    "greenhouse": "modern greenhouse with healthy vegetable seedlings, editorial architecture photography",
    "product": "elegant botanical skincare packaging on a clean wooden table, professional product photograph",
    "abstract": "luminous botanical abstract shapes, refined green and gold visual composition",
}

def api_json(endpoint, payload=None, timeout=15):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    with urlopen(Request("http://127.0.0.1:18188" + endpoint, headers=headers, data=data), timeout=timeout) as r:
        return json.load(r)

def run(preset, steps):
    if preset not in PRESETS or steps not in (1, 2, 3):
        raise RuntimeError("INVALID_PRESET_OR_STEPS")
    nodes = {
        "1": {"class_type": "SaeitSafeCPURender", "inputs": {
            "prompt": PRESETS[preset], "steps": steps, "seed": 42, "cfg": 7.0}},
        "2": {"class_type": "SaveImage", "inputs": {
            "images": ["1", 0], "filename_prefix": "saeit_cpu_public_demo"}},
    }
    output = api_json("/prompt", {"prompt": nodes, "client_id": str(uuid.uuid4())})
    prompt_id = output.get("prompt_id")
    if not prompt_id or output.get("node_errors"):
        raise RuntimeError("CPU_IMAGE_GRAPH_NOT_ACCEPTED")
    print("PRESET_JOB_ACCEPTED", flush=True)
    deadline = time.monotonic() + 285
    while time.monotonic() < deadline:
        history = api_json("/history/" + str(prompt_id))
        if str(prompt_id) in history:
            record = history[str(prompt_id)]
            images = record.get("outputs", {}).get("2", {}).get("images", [])
            if not images:
                raise RuntimeError("CPU_JOB_FINISHED_NO_IMAGE")
            item = images[0]
            url = "http://127.0.0.1:18188/view?" + urlencode({
                "filename": item["filename"], "subfolder": item.get("subfolder", ""),
                "type": item.get("type", "output")})
            with urlopen(url, timeout=20) as r:
                image = r.read(5_000_000)
            if len(image) < 1024 or not image.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("NOT_A_VALID_PNG")
            destdir = Path.home() / "comfyui-isolated/.control/qa-render"
            destdir.mkdir(mode=0o700, parents=True, exist_ok=True)
            dest = destdir / ("preset_" + preset + ".png")
            dest.write_bytes(image)
            dest.chmod(0o600)
            print("PRESET_REAL_PNG_BYTES=" + str(len(image)), flush=True)
            print("PRESET_REAL_PNG_SHA256=" + hashlib.sha256(image).hexdigest(), flush=True)
            return
        time.sleep(3)
    raise RuntimeError("CPU_JOB_EXCEEDED_TIME_LIMIT")

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "orchard"
    try:
        steps = int(sys.argv[2]) if len(sys.argv) > 2 else 4
        run(name, steps)
    except Exception as exc:
        print("PRESET_QA_ERROR=" + str(exc)[:100], flush=True)
        raise SystemExit(1)
