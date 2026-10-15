#!/usr/bin/env python3
"""PICM HTTPS pull worker for an independently provided private GPU.

One job per invocation. Owner references never enter GitHub or a public
model endpoint; no cloud GPU is rented by this code. Never execute this on
the autonomous factory VPS; run on a separate, provisioned GPU host.
"""
import argparse
import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import ssl
import stat
import sys
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPHandler, HTTPSHandler, HTTPRedirectHandler

from story_pipeline import process, verify_generating_graph
from story_comfy import load_workflow, check_gpu, validate_local_url

ORIGIN = "https://mojplaywin.com"
IDENT = re.compile(r"^[a-f0-9]{32}$")
CHUNK = 1024 * 1024
LIMIT = 128 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("PICM_CROSS_ORIGIN_REDIRECT_FORBIDDEN")


def _token(path):
    f = Path(path)
    st = f.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077:
        raise RuntimeError("PICM_GPU_TOKEN_MUST_BE_0600")
    data = f.read_text(encoding="ascii").strip()
    if not 48 <= len(data) <= 128 or not data.isascii():
        raise RuntimeError("PICM_GPU_TOKEN_INVALID")
    return data


def _private_dir(path):
    p = Path(path)
    if p.is_symlink() or not p.is_dir() or p.stat().st_mode & 0o077:
        raise RuntimeError("PICM_PRIVATE_WORK_DIRECTORY_REQUIRED_0700")
    return p


def _id(value):
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise RuntimeError("PICM_INVALID_JOB_ID")
    return value


class Transport:
    def __init__(self, token, *, origin=ORIGIN):
        if origin != ORIGIN:  # fixed origin; never send private tokens to override URLs
            raise RuntimeError("PICM_ORIGIN_MUST_MATCH_PRODUCTION_HTTPS_HOST")
        self.token = token
        self.origin = origin
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))

    def request(self, method, route, *, lease=None, data=None, headers=None):
        if not route.startswith("/picm/video/") or "//" in route:
            raise RuntimeError("PICM_INVALID_API_ROUTE")
        common = {"Authorization": "Bearer " + self.token,
                  "Cache-Control": "no-store"}
        if lease is not None:
            _id(lease)
            common["X-PICM-Video-Lease"] = lease
        common.update(headers or {})
        req = Request(self.origin + route, data=data,
                      headers=common, method=method)
        with self.opener.open(req, timeout=120) as response:
            if response.status == 204:
                return None
            if response.status not in (200, 201):
                raise RuntimeError("PICM_UNEXPECTED_WORKER_HTTP_STATUS")
            # Individual transfer responses are max 6MB; video is uploaded in 1MB chunks.
            body = response.read(7 * 1024 * 1024)
            if len(body) >= 7 * 1024 * 1024:
                raise RuntimeError("PICM_OVERSIZED_SERVER_REPLY")
            return body

    def json(self, method, route, *, lease=None, payload=None, headers=None):
        raw = self.request(
            method, route, lease=lease,
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})})
        return None if raw is None else json.loads(raw)


def upload_rendered(transport, ident, lease, output, receipt):
    """Resume bounded binary upload by the *server-confirmed* offset."""
    ident, lease = _id(ident), _id(lease)
    total = output.stat().st_size
    if total != receipt.get("bytes") or not 2048 <= total <= LIMIT:
        raise RuntimeError("PICM_BAD_VERIFIED_MP4_SIZE")
    if receipt.get("job_id") != ident:
        raise RuntimeError("PICM_WRONG_JOB_RECEIPT")
    with output.open("rb") as check:
        h = hashlib.sha256()
        for block in iter(lambda: check.read(CHUNK), b""):
            h.update(block)
    if h.hexdigest() != receipt.get("sha256"):
        raise RuntimeError("PICM_CHANGED_MP4_SINCE_FFPROBE")
    stem = "/picm/video/worker/"
    progress = transport.json("GET", stem + "progress/" + ident + "/", lease=lease)
    offset = progress["offset"]
    if type(offset) is not int or not 0 <= offset <= total:
        raise RuntimeError("PICM_INVALID_UPLOAD_RESUME_POSITION")
    with output.open("rb") as video:
        video.seek(offset)
        while offset < total:
            block = video.read(CHUNK)
            raw = transport.request(
                "POST", stem + "chunk/" + ident + "/", lease=lease,
                data=block,
                headers={"X-PICM-Offset": str(offset), "X-PICM-Total": str(total),
                         "X-PICM-SHA256": receipt["sha256"],
                         "Content-Type": "application/octet-stream"})
            state = json.loads(raw)
            if state.get("offset") != offset + len(block):
                raise RuntimeError("PICM_REMOTE_CHUNK_ACK_MISMATCH")
            offset = state["offset"]
    response = transport.json("POST", stem + "finish/" + ident + "/",
                              lease=lease, payload=receipt)
    if response.get("state") != "done" or response.get("id") != ident:
        raise RuntimeError("PICM_REMOTE_MOVIE_DELIVERY_NOT_CONFIRMED")
    return response


def deliver_once(private_dir, token_path, workflow_api, node_map, *,
                 comfy="http://127.0.0.1:8188"):
    private = _private_dir(private_dir)
    # Do NOT claim the owner's staged job if GPU/model configuration is absent.
    graph, mapping = load_workflow(workflow_api, node_map)
    verify_generating_graph(graph, mapping)
    check_gpu(validate_local_url(comfy))
    transport = Transport(_token(token_path))
    selected = transport.json("GET", "/picm/video/worker/next/")
    if selected is None:
        return {"state": "no_owner_video_jobs"}
    ident, lease = _id(selected["id"]), _id(selected["lease"])
    job = private / ident
    job.mkdir(mode=0o700, exist_ok=False)
    metadata, photo = job / (ident + ".stage.json"), job / (ident + ".input")
    for dst, route, max_len in (
            (metadata, "metadata", 20000),
            (photo, "reference", 6 * 1024 * 1024 + 10)):
        raw = transport.request("GET", "/picm/video/worker/" + route + "/" + ident + "/",
                                lease=lease)
        if not isinstance(raw, bytes) or not 128 <= len(raw) <= max_len:
            raise RuntimeError("PICM_PRIVATE_REFERENCE_TRANSFER_INVALID")
        with dst.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(raw)
    receipt = process(metadata, photo, workflow_api, node_map,
                      job / "render", comfy=comfy)
    output = job / "render" / "story.mp4"
    result = upload_rendered(transport, ident, lease, output, receipt)
    # Remove temporary user photos and video only *after* owner download
    # is confirmed available on cPanel. No claim of secure disk erasure.
    shutil.rmtree(job)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--workflow-api", required=True)
    parser.add_argument("--node-map", required=True)
    parser.add_argument("--comfy", default="http://127.0.0.1:8188")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        result = deliver_once(args.private_dir, args.token_file,
                              args.workflow_api, args.node_map,
                              comfy=args.comfy)
    except Exception as exc:
        # Do not print file paths, photos, prompt contents, bearer tokens.
        print(json.dumps({"state": "blocked_no_video_claim",
                          "reason_class": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()
