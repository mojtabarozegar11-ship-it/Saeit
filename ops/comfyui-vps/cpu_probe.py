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


from pathlib import Path
import subprocess
root = Path.home() / "comfyui-isolated/.control/sd-cpp-runtime-sse2"
print("SSE2_RUNTIME_DIRECTORY_EXISTS=" + str(root.is_dir()))
print("SSE2_BINARY_PRESENT=" + str((root / "bin/sd-cli").is_file()))
archive = root / "archive.tar"
print("SSE2_ARCHIVE_PRESENT=" + str(archive.is_file()))
if archive.is_file():
    print("SSE2_ARCHIVE_BYTES=" + str(archive.stat().st_size))
    scan = subprocess.run(["tar", "-tf", str(archive)], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=15, check=False)
    entries = scan.stdout.decode("utf-8", "replace").splitlines()
    print("SSE2_ARCHIVE_TAR_EXIT=" + str(scan.returncode))
    print("SSE2_ARCHIVE_ENTRY_COUNT=" + str(len(entries)))
    print("SSE2_ARCHIVE_HAS_BIN_CLI=" + str("bin/sd-cli" in entries))
    print("SSE2_ARCHIVE_EXAMPLE_ENTRIES=" + repr(entries[:7]))
print("SSE2_RUNTIME_DIAGNOSTIC_COMPLETE")
