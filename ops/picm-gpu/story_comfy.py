#!/usr/bin/env python3
"""Local-only ComfyUI adapter for PICM multi-shot image-to-video.

Requires a real locally hosted GPU workflow exported with ComfyUI's
'Export Workflow (API)' command. Does NOT install models, open public ports,
operate the shared VPS factory, or silently replace missing shots with motion
effects. It runs only when explicitly launched on the isolated GPU worker.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import uuid4

from story_assemble import AssemblyError, load_plan, video_duration

NODE_KEYS = {"image", "text", "length", "output"}
URL_LOCAL = {"localhost", "127.0.0.1", "::1"}
MAX_INPUT = 6 * 1024 * 1024
MAX_OUTPUT = 250 * 1024 * 1024
CLIP_FILE = re.compile(r"^shot_[0-9]{2}\.mp4$")


class NoExternalRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AssemblyError("ComfyUI_HTTP_redirect_forbidden")


LOCAL_HTTP = build_opener(NoExternalRedirect)

def validate_local_url(base_url):
    u = urlsplit(base_url)
    if (u.scheme != "http" or u.hostname not in URL_LOCAL or
            u.username or u.password or u.query or u.fragment or
            (u.path not in ("", "/"))):
        raise AssemblyError("ComfyUI_must_be_local_loopback_http")
    return base_url.rstrip("/")


def load_workflow(template, mappings):
    path = Path(template)
    nodes_path = Path(mappings)
    if (not path.is_file() or path.is_symlink()
            or not nodes_path.is_file() or nodes_path.is_symlink()):
        raise AssemblyError("api_template_or_nodes_missing")
    graph = json.loads(path.read_text(encoding="utf-8"))
    node = json.loads(nodes_path.read_text(encoding="utf-8"))
    if not isinstance(graph, dict) or not isinstance(node, dict) or not NODE_KEYS.issubset(node):
        raise AssemblyError("invalid_ComfyUI_api_graph_mapping")
    for role, node_id in node.items():
        if role not in NODE_KEYS | {"fps"} or type(node_id) is not str or node_id not in graph:
            raise AssemblyError("ComfyUI_node_mapping_missing_" + role)
    for entry in graph.values():
        if not isinstance(entry, dict) or not isinstance(entry.get("inputs"), dict):
            raise AssemblyError("ComfyUI_API_export_required")
    return graph, node


def set_scene_inputs(graph, nodes, scene, image_filename, fps=16):
    if type(fps) is not int or not 8 <= fps <= 30:
        raise AssemblyError("invalid_scene_fps")
    adapted = copy.deepcopy(graph)
    fields = [
        ("image", "image", image_filename),
        ("text", "text", "Cinematic natural action; one consistent adult person from reference; " +
         str(scene["action"]) + "; coherent physical movement, realistic environments"),
        ("length", "length", int(scene["duration"] * fps) + 1),
    ]
    if "fps" in nodes:
        fields.append(("fps", "fps", fps))
    for role, key, value in fields:
        node_id = nodes[role]
        if key not in adapted[node_id]["inputs"]:
            raise AssemblyError("ComfyUI_input_missing_" + role + "_" + key)
        adapted[node_id]["inputs"][key] = value
    return adapted


def http_json(url, payload=None, timeout=30):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {} if payload is None else {"Content-Type": "application/json"}
    request = Request(url, data=body, headers=headers)
    with LOCAL_HTTP.open(request, timeout=timeout) as response:
        if response.status not in (200, 201):
            raise AssemblyError("ComfyUI_HTTP_error")
        return json.loads(response.read(5_000_000))


def check_gpu(base):
    stats = http_json(base + "/system_stats")
    devices = stats.get("devices", [])
    if not isinstance(devices, list):
        raise AssemblyError("ComfyUI_invalid_device_state")
    names = " ".join(str(d.get("type", "")) + " " + str(d.get("name", ""))
                     for d in devices if isinstance(d, dict)).lower()
    if not any(s in names for s in ("cuda", "nvidia", "rocm", "amd", "mps")):
        raise AssemblyError("actual_GPU_required_no_CPU_video_substitute")


def upload_reference(base, path):
    raw = Path(path).read_bytes()
    if not 128 <= len(raw) <= MAX_INPUT:
        raise AssemblyError("private_reference_size_invalid")
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        extension, mime = ".png", "image/png"
    elif raw.startswith(b"\xff\xd8\xff"):
        extension, mime = ".jpg", "image/jpeg"
    else:
        raise AssemblyError("unsupported_reference_image")
    name = "picm-" + uuid4().hex + extension
    boundary = "picm-" + uuid4().hex
    start = ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\""
             + name + "\"\r\nContent-Type: " + mime + "\r\n\r\n").encode()
    end = ("\r\n--" + boundary + "--\r\n").encode()
    req = Request(base + "/upload/image", data=start + raw + end, headers={
        "Content-Type": "multipart/form-data; boundary=" + boundary}, method="POST")
    with LOCAL_HTTP.open(req, timeout=120) as resp:
        result = json.loads(resp.read(2_000_000))
    stored = result.get("name")
    if not isinstance(stored, str) or not stored.startswith("picm-") or "/" in stored or "\\" in stored:
        raise AssemblyError("ComfyUI_reference_upload_invalid")
    return stored


def await_video(base, prompt_id, output_node, timeout_seconds):
    expires = time.monotonic() + timeout_seconds
    while time.monotonic() < expires:
        details = http_json(base + "/history/" + prompt_id)
        history = details.get(prompt_id)
        if history:
            status = history.get("status", {})
            if status.get("status_str") == "error":
                raise AssemblyError("GPU_model_render_failed")
            outputs = history.get("outputs", {}).get(output_node, {})
            for field in ("videos", "gifs"):
                for item in outputs.get(field, []):
                    fname = item.get("filename", "")
                    if (isinstance(fname, str) and fname.lower().endswith(".mp4")
                            and item.get("type") == "output" and
                            "/" not in fname and "\\" not in fname):
                        folder = item.get("subfolder", "")
                        if not isinstance(folder, str) or ".." in folder or folder.startswith("/"):
                            raise AssemblyError("untrusted_ComfyUI_output_subfolder")
                        return fname, folder
            if status.get("completed"):
                raise AssemblyError("ComfyUI_completed_without_real_MP4")
        time.sleep(5)
    raise AssemblyError("GPU_render_timed_out")


def save_mp4(base, filename, subfolder, destination):
    query = urlencode({"filename": filename, "subfolder": subfolder, "type": "output"})
    req = Request(base + "/view?" + query)
    fd, temporary = tempfile.mkstemp(prefix=".picm-video-", suffix=".tmp",
                                     dir=destination.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as output, LOCAL_HTTP.open(req, timeout=180) as response:
            count = 0
            while True:
                buf = response.read(1024 * 1024)
                if not buf:
                    break
                count += len(buf)
                if count > MAX_OUTPUT:
                    raise AssemblyError("generated_scene_exceeds_private_limit")
                output.write(buf)
        if count < 2048:
            raise AssemblyError("empty_real_video")
        if video_duration(Path(temporary)) < 0.5:
            raise AssemblyError("video_stream_invalid")
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def generate(base, plan, image_path, workflow, mapping, clips, fps, timeout):
    base = validate_local_url(base)
    check_gpu(base)
    if not shutil.which("ffprobe"):
        raise AssemblyError("ffprobe_required_for_real_MP4_validation")
    root = Path(clips)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink():
        raise AssemblyError("unsafe_clip_directory")
    os.chmod(root, 0o700)
    uploaded = upload_reference(base, image_path)
    for scene in plan["scenes"]:
        name = "shot_%02d.mp4" % scene["shot"]
        if not CLIP_FILE.fullmatch(name):
            raise AssemblyError("invalid_clip_name")
        target = root / name
        if target.exists() or target.is_symlink():
            if target.is_symlink() or video_duration(target) + 0.12 < scene["duration"]:
                raise AssemblyError("unsafe_or_incomplete_existing_clip")
            continue
        prompt = set_scene_inputs(workflow, mapping, scene, uploaded, fps)
        response = http_json(base + "/prompt",
                             {"prompt": prompt, "client_id": uuid4().hex})
        pid = response.get("prompt_id")
        if not isinstance(pid, str) or not re.fullmatch(r"[a-fA-F0-9-]{32,36}", pid):
            raise AssemblyError("ComfyUI_did_not_accept_scene")
        fname, subfolder = await_video(base, pid, mapping["output"], timeout)
        save_mp4(base, fname, subfolder, target)
        if video_duration(target) + 0.12 < scene["duration"]:
            target.unlink(missing_ok=True)
            raise AssemblyError("model_output_shorter_than_scene")
    return str(root)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata", required=True)
    p.add_argument("--reference", required=True)
    p.add_argument("--workflow-api", required=True)
    p.add_argument("--node-map", required=True)
    p.add_argument("--clips", required=True)
    p.add_argument("--comfy", default="http://127.0.0.1:8188")
    p.add_argument("--fps", type=int, default=16)
    p.add_argument("--timeout-per-shot", type=int, default=3600)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    plan = load_plan(args.metadata)
    graph, node = load_workflow(args.workflow_api, args.node_map)
    for scene in plan["scenes"]:
        set_scene_inputs(graph, node, scene, "private-reference-placeholder.png", args.fps)
    base = validate_local_url(args.comfy)
    if args.dry_run:
        print(json.dumps({"state": "configured_not_rendered",
                          "scenes": len(plan["scenes"]), "duration": plan["duration"],
                          "requires": "running_loopback_ComfyUI_GPU_with_loaded_i2v_models"}))
        return
    print(json.dumps({"state": "render_started", "scenes": len(plan["scenes"])}), flush=True)
    clips = generate(base, plan, args.reference, graph, node, args.clips,
                     args.fps, args.timeout_per_shot)
    print(json.dumps({"state": "real_AI_scene_clips_ready",
                      "private_clip_directory": clips}))


if __name__ == "__main__":
    main()
