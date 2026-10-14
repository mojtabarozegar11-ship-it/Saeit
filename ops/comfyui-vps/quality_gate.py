#!/usr/bin/env python3
"""Read-only ComfyUI VPS readiness checks; no model loading or network exposure."""
import json
import os
from pathlib import Path

home = Path.home()
root = home / "comfyui-isolated"
src = root / "source-v0.40.0"
categories = ("checkpoints", "diffusion_models", "unet", "loras", "vae", "clip", "text_encoders", "controlnet", "upscale_models")
checks = {}
checks["runtime_present"] = (src / "main.py").is_file()
checks["private_dir"] = root.is_dir() and not (root.stat().st_mode & 0o077)
checks["python_present"] = (root / "env-cpu/bin/python").exists()
checks["models"] = {}
for category in categories:
    folder = src / "models" / category
    models = []
    if folder.is_dir():
        for p in folder.rglob("*"):
            if (p.is_file() and not p.is_symlink() and not p.name.startswith(".")
                and p.suffix.lower() in (".safetensors", ".ckpt")
                and p.stat().st_size > 200000):
                models.append(p)
    checks["models"][category] = len(models)
checks["model_total"] = sum(checks["models"].values())
checks["temporary_download_present"] = bool(list((src / "models/checkpoints").glob(".candidate-download.*")))
checks["tiny_model_final_present"] = (src / "models/checkpoints/segmind_tiny_sd_candidate.safetensors").is_file()

factory_pid = home / "factory-runtime/operations/vps-only-loop.pid"
checks["factory_loop_running"] = False
if factory_pid.is_file():
    try:
        pid = int(factory_pid.read_text().strip())
        os.kill(pid, 0)
        checks["factory_loop_running"] = True
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        pass
checks["cgroup_v2"] = Path("/sys/fs/cgroup/cgroup.controllers").is_file()
checks["user_cgroup_delegation"] = False
cgroup = Path("/proc/self/cgroup")
if checks["cgroup_v2"] and cgroup.is_file():
    for line in cgroup.read_text().splitlines():
        if line.startswith("0::"):
            active = Path("/sys/fs/cgroup") / line.split("::", 1)[1].lstrip("/")
            checks["user_cgroup_delegation"] = os.access(active, os.W_OK)
checks["private_tailscale_binary"] = (home / ".local/opt/comfyui-tailnet/binaries-1.104.1/tailscale").exists()

candidate = src / "models/checkpoints/segmind_tiny_sd_candidate.safetensors"
if candidate.is_file():
    import hashlib
    expected = "92e00b860c409f8cfc521a94f779009c6ebd28bf07670bf50e747682ab7b3b72"
    h = hashlib.sha256()
    with candidate.open("rb") as inp:
        for chunk in iter(lambda: inp.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    checks["tiny_model_hash_verified"] = h.hexdigest() == expected
    with candidate.open("rb") as inp:
        length = int.from_bytes(inp.read(8), "little")
        assert length < 3000000, "INVALID_SAFETENSORS_HEADER"
        metadata = json.loads(inp.read(length))
    keys = [str(k) for k in metadata if k != "__metadata__"]
    checks["checkpoint_key_count"] = len(keys)
    checks["checkpoint_structure"] = {
        "unet": sum(k.startswith("model.diffusion_model.") for k in keys),
        "clip": sum(k.startswith("cond_stage_model.") for k in keys),
        "vae": sum(k.startswith("first_stage_model.") for k in keys),
    }
print("COMFYUI_QUALITY_GATE=" + json.dumps(checks, sort_keys=True))
if not checks["runtime_present"] or not checks["private_dir"] or not checks["python_present"]:
    raise SystemExit(1)
