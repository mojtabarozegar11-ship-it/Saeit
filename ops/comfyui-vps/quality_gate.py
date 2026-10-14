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
            if p.is_file() and not p.is_symlink() and p.stat().st_size > 200000:
                models.append(p)
    checks["models"][category] = len(models)
checks["model_total"] = sum(checks["models"].values())
print("COMFYUI_QUALITY_GATE=" + json.dumps(checks, sort_keys=True))
if not checks["runtime_present"] or not checks["private_dir"] or not checks["python_present"]:
    raise SystemExit(1)
