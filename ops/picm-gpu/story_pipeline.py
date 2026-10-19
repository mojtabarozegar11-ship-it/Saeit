#!/usr/bin/env python3
"""Run a private PICM story job on an *already provisioned* real GPU machine.

No GPU rental, public endpoint, website deployment, download of private
inputs, or AI render is performed by this script on its own. Dry-run only
checks configuration; real mode rejects CPU-only ComfyUI and missing footage.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

from story_assemble import AssemblyError, assemble, load_plan, video_duration
from story_comfy import (check_gpu, generate, load_workflow, set_scene_inputs,
                         validate_local_url)

STAGE_ID = re.compile(r"^[0-9a-f]{32}$")
ALLOWED_SAMPLERS = ("KSampler", "SamplerCustom", "WanVideoSampler",
                    "LTXVSampler", "WanSampler", "HunyuanVideoSampler")
MAX_REFERENCE = 6 * 1024 * 1024
MAX_STAGE_AGE = 24 * 3600


def _private_file(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise AssemblyError("story_input_must_be_private_regular_0600")
    return path


def validate_stage(metadata, reference, *, now=None):
    """Accept only the exact pair created for the authenticated PICM owner.

    Neither a URL nor arbitrary filenames are accepted, and expired inputs
    must be re-submitted by the owner instead of being rendered indefinitely.
    """
    metadata = _private_file(metadata)
    reference = _private_file(reference)
    raw = metadata.read_bytes()
    if len(raw) > 20_000:
        raise AssemblyError("oversized_private_stage_metadata")
    data = json.loads(raw)
    ident = data.get("id", "")
    if (not isinstance(ident, str) or not STAGE_ID.fullmatch(ident)
            or metadata.name != ident + ".stage.json"
            or reference.name != ident + ".input"):
        raise AssemblyError("story_stage_reference_pair_mismatch")
    if data.get("mode") != "story_video" or data.get("user_id") is None:
        raise AssemblyError("not_an_owner_story_video_job")
    stamp = data.get("created")
    if not isinstance(stamp, (int, float)) or isinstance(stamp, bool):
        raise AssemblyError("missing_story_stage_timestamp")
    current = time.time() if now is None else now
    if stamp > current + 120 or current - stamp >= MAX_STAGE_AGE:
        raise AssemblyError("private_story_stage_expired")
    if data.get("state") != "staged_awaiting_gpu":
        raise AssemblyError("story_stage_not_waiting_for_gpu")
    size = reference.stat().st_size
    if not 128 <= size <= MAX_REFERENCE:
        raise AssemblyError("reference_image_size_invalid")
    with reference.open("rb") as stream:
        header = stream.read(8)
    if not (header == b"\x89PNG\r\n\x1a\n" or header[:3] == b"\xff\xd8\xff"):
        raise AssemblyError("reference_must_be_png_or_jpeg")
    return load_plan(metadata), ident


def verify_generating_graph(graph, mapping):
    """Require connected image/text/length conditioning and a real sampler.

    This is a structural fail-closed gate; it is not proof of visual quality
    or the model's actual weights. Those require an independent GPU render.
    """
    output = mapping["output"]
    visited = set()
    stack = [output]
    while stack:
        node_id = stack.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        inputs = graph[node_id].get("inputs", {})
        for value in inputs.values():
            if (isinstance(value, list) and len(value) == 2
                    and isinstance(value[1], int)
                    and str(value[0]) in graph):
                stack.append(str(value[0]))
    needed = {mapping[k] for k in ("image", "text", "length")}
    if not needed.issubset(visited):
        raise AssemblyError("image_text_or_length_not_connected_to_video_output")
    sampler_found = any(
        any(token in str(graph[key].get("class_type", ""))
            for token in ALLOWED_SAMPLERS)
        for key in visited
    )
    if not sampler_found:
        raise AssemblyError("no_connected_generative_video_sampler")
    if graph[output].get("class_type") not in ("SaveVideo", "VHS_VideoCombine"):
        raise AssemblyError("expected_real_video_output_node")
    return True


def process(metadata, reference, workflow_api, node_map, workspace, *,
            comfy="http://127.0.0.1:8188", fps=16, timeout=3600,
            dry_run=False):
    base = validate_local_url(comfy)
    plan, ident = validate_stage(metadata, reference)
    graph, nodes = load_workflow(workflow_api, node_map)
    verify_generating_graph(graph, nodes)
    for scene in plan["scenes"]:
        set_scene_inputs(graph, nodes, scene, "private-reference-placeholder.png", fps)
    # Never create a file or claim a render for dry runs.
    if dry_run:
        return {"state": "configuration_validated_not_rendered",
                "scenes": len(plan["scenes"]), "duration": plan["duration"]}
    # Ensure a real model worker exists BEFORE any output folder is created.
    check_gpu(base)
    folder = Path(workspace)
    if folder.is_symlink() or folder.exists():
        raise AssemblyError("job_workspace_must_be_new_and_private")
    parent = folder.parent.resolve(strict=True)
    if not parent.is_dir() or parent.stat().st_mode & 0o077:
        raise AssemblyError("job_workspace_parent_not_private_0700")
    folder.mkdir(mode=0o700)
    clips = folder / "clips"
    generate(base, plan, reference, graph, nodes, clips, fps, timeout)
    output = folder / "story.mp4"
    assemble(plan, clips, output)
    # Report success only after ffprobe checks the actual assembled video.
    runtime = video_duration(output)
    if abs(runtime - plan["duration"]) > 0.5:
        raise AssemblyError("final_story_length_mismatch")
    digest = hashlib.sha256()
    with output.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    receipt = {"state": "real_mp4_rendered_and_ffprobed",
               "job_id": ident, "duration": plan["duration"],
               "bytes": output.stat().st_size,
               "sha256": digest.hexdigest()}
    receipt_path = folder / "receipt.json"
    with receipt_path.open("x", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(receipt, stream, sort_keys=True)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata", required=True)
    p.add_argument("--reference", required=True)
    p.add_argument("--workflow-api", required=True)
    p.add_argument("--node-map", required=True)
    p.add_argument("--workspace", required=True,
                   help="New private job folder under an existing 0700 parent")
    p.add_argument("--comfy", default="http://127.0.0.1:8188")
    p.add_argument("--fps", type=int, default=16)
    p.add_argument("--timeout-per-shot", type=int, default=3600)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    os.umask(0o077)
    try:
        report = process(args.metadata, args.reference,
                         args.workflow_api, args.node_map, args.workspace,
                         comfy=args.comfy, fps=args.fps,
                         timeout=args.timeout_per_shot, dry_run=args.dry_run)
    except (AssemblyError, OSError, ValueError, KeyError) as exc:
        reason = str(exc)
        print(json.dumps({"state": "blocked_no_video_claim",
                          "reason": reason[:120]}), file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
