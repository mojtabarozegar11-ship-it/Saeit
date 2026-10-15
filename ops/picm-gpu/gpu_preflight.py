#!/usr/bin/env python3
"""PICM separate GPU preflight: no cloud billing, models, images, or jobs touched.

Run only on an independently provisioned model host. Reports verified
hardware/runtime readiness, NEVER claims to produce or have produced a film.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.error import HTTPError, URLError

from story_assemble import AssemblyError
from story_comfy import http_json, load_workflow, validate_local_url
from story_pipeline import verify_generating_graph

# Minimum usable *free* driver-reported VRAM. Threshold is a readiness gate,
# not a guarantee of speed or quality; Wan 5B also needs CPU offloading/RAM.
GPU_PROFILES = {"standard-24gb": 20000, "wan22-5b-offload-8gb": 7000}


def inspect(host_root, workflow_api, node_map, *,
            comfy="http://127.0.0.1:8188",
            minimum_gpu_mib=20000,
            minimum_free_disk_gib=20,
            probe=None, gpu_command=None, gpu_profile="standard-24gb"):
    """Return safe, non-identifying read-only facts and unmet conditions."""
    problems = []
    details = {}
    if gpu_profile not in GPU_PROFILES:
        problems.append("unknown_GPU_profile")
    root = Path(host_root)
    if root.is_symlink() or not root.is_dir():
        problems.append("private_gpu_work_dir_missing")
    elif root.stat().st_mode & 0o077:
        problems.append("private_gpu_work_dir_requires_0700")
    if root.is_dir():
        free = shutil.disk_usage(root).free // (1024 ** 3)
        details["free_disk_gib"] = free
        if free < minimum_free_disk_gib:
            problems.append("insufficient_free_gpu_disk")

    for command in ("ffmpeg", "ffprobe"):
        if shutil.which(command) is None:
            problems.append(command + "_not_installed")

    try:
        graph, mapping = load_workflow(workflow_api, node_map)
        verify_generating_graph(graph, mapping)
        if gpu_profile == "wan22-5b-offload-8gb":
            # Prevent accidental acceptance of a larger 14B image-to-video
            # graph merely because its sampler and hardware API exist.
            # Only nodes that actually contribute to SaveVideo count.
            reachable = set()
            pending = [mapping["output"]]
            while pending:
                node_id = pending.pop()
                if node_id in reachable:
                    continue
                reachable.add(node_id)
                for value in graph[node_id]["inputs"].values():
                    if (isinstance(value, list) and len(value) == 2
                            and isinstance(value[1], int)
                            and str(value[0]) in graph):
                        pending.append(str(value[0]))
            models = [graph[node_id] for node_id in reachable
                      if graph[node_id].get("class_type") == "UNETLoader"]
            if not any(
                    "wan2.2_ti2v_5b" in str(node.get("inputs", {}).get("unet_name", "")).lower()
                    for node in models):
                problems.append("wan22_5b_checkpoint_not_selected_in_workflow")
            if not any(graph[node_id].get("class_type") == "Wan22ImageToVideoLatent"
                       for node_id in reachable):
                problems.append("wan22_5b_i2v_latent_node_missing")
        details["connected_i2v_graph"] = True
    except (AssemblyError, OSError, ValueError, KeyError, TypeError):
        details["connected_i2v_graph"] = False
        problems.append("real_connected_i2v_workflow_not_configured")

    try:
        base = validate_local_url(comfy)
        stats = (probe or http_json)(base + "/system_stats")
        devices = stats.get("devices", [])
        if not isinstance(devices, list):
            devices = []
        matches = [d for d in devices if isinstance(d, dict) and any(
            tag in str(d.get("type", "")).lower() + " " +
            str(d.get("name", "")).lower()
            for tag in ("cuda", "nvidia", "rocm", "amd", "mps"))]
        details["gpu_comfy_visible"] = bool(matches)
        if not matches:
            problems.append("no_local_comfy_gpu")
    except (AssemblyError, OSError, ValueError, TimeoutError, URLError, HTTPError,
            json.JSONDecodeError):
        details["gpu_comfy_visible"] = False
        problems.append("loopback_comfy_service_unavailable")

    # Hardware memory must come from the GPU driver; no assumed VRAM.
    run = gpu_command or (lambda: subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.total,memory.free",
         "--format=csv,noheader,nounits"], capture_output=True, text=True,
        timeout=10, check=True).stdout)
    try:
        output = run()
        pairs = []
        for line in output.splitlines():
            vals = [v.strip() for v in line.split(",")]
            if len(vals) == 2:
                pairs.append((int(vals[0]), int(vals[1])))
        if not pairs:
            raise ValueError("missing_nvidia_gpu_memory")
        total, free = max(pairs, key=lambda item: item[1])
        details["total_gpu_vram_mib"] = total
        details["free_gpu_vram_mib"] = free
        if total < minimum_gpu_mib or free < minimum_gpu_mib:
            problems.append("insufficient_free_gpu_vram")
    except (OSError, ValueError, subprocess.SubprocessError):
        details["free_gpu_vram_mib"] = None
        problems.append("gpu_memory_unverified_nvidia_only")

    return {"state": "runtime_preflight_ready_not_rendered" if not problems
            else "blocked_no_real_video_claim",
            "ready": not bool(problems), "requirements": problems,
            "details": details,
            "note": "This does not confirm model weights or film quality."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--workflow-api", required=True)
    ap.add_argument("--node-map", required=True)
    ap.add_argument("--comfy", default="http://127.0.0.1:8188")
    ap.add_argument("--gpu-profile", choices=tuple(GPU_PROFILES),
                    default="standard-24gb")
    ap.add_argument("--minimum-free-vram-mib", type=int, default=None)
    ap.add_argument("--minimum-free-disk-gib", type=int, default=20)
    args = ap.parse_args()
    minimum_vram = GPU_PROFILES[args.gpu_profile]
    if args.minimum_free_vram_mib is not None:
        # Threshold overrides can only be stricter than the selected profile.
        minimum_vram = args.minimum_free_vram_mib
        if minimum_vram < GPU_PROFILES[args.gpu_profile]:
            ap.error("unsafe_GPU_vram_requirement_below_profile")
    if not 1000 <= minimum_vram <= 200000:
        ap.error("invalid_GPU_vram_requirement")
    if not 1 <= args.minimum_free_disk_gib <= 1000:
        ap.error("invalid_disk_requirement")
    report = inspect(args.work_dir, args.workflow_api, args.node_map,
                     comfy=args.comfy,
                     minimum_gpu_mib=minimum_vram,
                     minimum_free_disk_gib=args.minimum_free_disk_gib,
                     gpu_profile=args.gpu_profile)
    report["gpu_profile"] = args.gpu_profile
    report["minimum_free_vram_mib"] = minimum_vram
    print(json.dumps(report, sort_keys=True))
    if not report["ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
