#!/usr/bin/env python3
"""Only checks that ComfyUI registered the isolated CPU image node."""
import json
from urllib.request import urlopen

with urlopen("http://127.0.0.1:18188/object_info/SaeitSafeCPURender", timeout=20) as reply:
    data = json.load(reply)
    assert reply.status == 200
node = data.get("SaeitSafeCPURender")
if not node:
    raise SystemExit("COMFYUI_CPU_CUSTOM_NODE_NOT_REGISTERED")
assert node.get("output") == ["IMAGE"]
required = node.get("input", {}).get("required", {})
for name in ("prompt", "steps", "seed", "cfg"):
    assert name in required, name
print("COMFYUI_SAFE_CPU_IMAGE_NODE_REGISTERED")
print("COMFYUI_SAFE_CPU_BRIDGE_REMOTE_API_READY")
