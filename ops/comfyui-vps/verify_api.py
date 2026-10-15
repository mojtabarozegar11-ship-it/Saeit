#!/usr/bin/env python3
"""Read-only private ComfyUI API readiness test, never submit a GPU/CPU job."""
import json
from urllib.request import urlopen

base = "http://127.0.0.1:18188"
candidate = "segmind_tiny_sd_candidate.safetensors"
with urlopen(base + "/system_stats", timeout=20) as response:
    stats = json.load(response)
    assert response.status == 200
    print("COMFYUI_SYSTEM_API_HTTP_200")
with urlopen(base + "/object_info/CheckpointLoaderSimple", timeout=25) as response:
    data = json.load(response)
    assert response.status == 200
    print("COMFYUI_NODE_REGISTRY_HTTP_200")
node = data.get("CheckpointLoaderSimple", {})
inputs = node.get("input", {}).get("required", {})
select = inputs.get("ckpt_name", [])
models = select[0] if isinstance(select, list) and select else []
print("COMFYUI_RECOGNIZED_CHECKPOINT_COUNT=" + str(len(models)))
if candidate not in models:
    print("COMFYUI_TINY_CHECKPOINT_NOT_RECOGNIZED")
    raise SystemExit(2)
print("COMFYUI_TINY_CHECKPOINT_RECOGNIZED")
with urlopen(base + "/queue", timeout=20) as response:
    queue = json.load(response)
    assert response.status == 200
    assert not queue.get("queue_running") and not queue.get("queue_pending"), "BUSY_GENERATION_QUEUE"
    print("COMFYUI_QUEUE_IDLE")
print("COMFYUI_API_MODEL_READINESS_PASS")
