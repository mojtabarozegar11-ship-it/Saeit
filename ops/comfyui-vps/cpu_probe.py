#!/usr/bin/env python3
"""Read-only CPU capability audit for the private ComfyUI renderer."""
import os
import platform
from pathlib import Path
p = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
first = p.split("\n\n")[0]
lines = dict((line.split(":",1)[0].strip().lower(), line.split(":",1)[1].strip())
             for line in first.splitlines() if ":" in line)
flags = set(lines.get("flags", "").split())
print("CPU_MODEL=" + lines.get("model name", "unknown")[:120])
print("CPU_LOGICAL_CORES=" + str(os.cpu_count()))
print("CPU_MACHINE=" + platform.machine())
print("CPU_FLAGS_SAFE=" + " ".join(feature + ":" + ("yes" if feature in flags else "no")
    for feature in ("sse2","ssse3","sse4_1","sse4_2","avx","avx2","fma","f16c","avx512f","bmi2")))
log = Path.home() / "comfyui-isolated/.control/qa-render/vps_smoke.log"
if log.is_file():
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-12:]:
        # Output only internal CPU compiler/engine messages, not user prompts.
        if any(word in line.lower() for word in ("illegal", "instruction", "error", "exception", "cpu", "ggml", "abort", "crash")):
            print("CPU_RENDER_DIAGNOSTIC=" + line[:180])
print("CPU_CAPABILITY_READONLY_COMPLETE")
