"""PICM video-only owner bridge. Staged protocol: NO automatic deployment.

A separate GPU pulls one owner-staged story over authenticated HTTPS, then
uploads its genuine ffprobed MP4 in bounded, lease-bound chunks. No public
ComfyUI listener, no GitHub photo transfer, no changes to the factory queue.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
from uuid import uuid4

from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .picm_access import owner_allowed, owner_id
from .picm_views import locked, UUID_RE, PICM_REFERENCE_TTL_SECONDS

MAX_CHUNK = 1024 * 1024
MAX_MOVIE = 128 * 1024 * 1024
LEASE_TTL = 8 * 3600
MOVIE_TTL = 48 * 3600
SHA256 = re.compile(r"^[a-f0-9]{64}$")
LEASE = re.compile(r"^[a-f0-9]{32}$")


def _nocache(response):
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _worker_ok(request, root):
    path = root / "gpu-worker-token"
    if path.is_symlink() or not path.is_file():
        return False
    if path.stat().st_mode & 0o077:
        return False
    try:
        token = path.read_text(encoding="ascii").strip()
    except (UnicodeError, OSError):
        return False
    supplied = request.headers.get("Authorization", "")
    return (len(token) >= 48 and len(token) <= 128
            and len(supplied) <= 150
            and hmac.compare_digest(supplied, "Bearer " + token))


def _status_path(root, ident):
    if not UUID_RE.fullmatch(ident):
        raise Http404
    return root / (ident + ".video.json")


def _state(root, ident):
    path = _status_path(root, ident)
    if path.is_symlink():
        raise Http404
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _write_state(root, ident, state):
    path = _status_path(root, ident)
    fd, name = tempfile.mkstemp(dir=root, prefix=".video-state-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _valid_stage(root, path, now):
    if path.is_symlink() or not path.is_file():
        return None
    name = path.name
    if not name.endswith(".stage.json") or not UUID_RE.fullmatch(name[:32]):
        return None
    if name != name[:32] + ".stage.json":
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        stamp = float(data["created"])
    except (OSError, ValueError, TypeError, KeyError):
        return None
    if (data.get("id") != name[:32] or data.get("mode") != "story_video"
            or data.get("state") != "staged_awaiting_gpu"
            or str(data.get("user_id")) != owner_id(root)
            or owner_id(root) is None
            or stamp > now + 120
            or now - stamp >= PICM_REFERENCE_TTL_SECONDS):
        return None
    image = root / (name[:32] + ".input")
    if (image.is_symlink() or not image.is_file()
            or not 128 <= image.stat().st_size <= 6 * 1024 * 1024):
        return None
    return data


def _leased(root, request, ident):
    if not _worker_ok(request, root):
        return None, HttpResponse(status=403)
    s = _state(root, ident)
    lease = request.headers.get("X-PICM-Video-Lease", "")
    if (s is None or not LEASE.fullmatch(lease)
            or not hmac.compare_digest(str(s.get("lease", "")), lease)):
        return None, HttpResponse(status=409)
    if time.time() - float(s.get("claimed", 0)) >= LEASE_TTL:
        return None, HttpResponse(status=410)
    return s, None


def _discard_expired_video(root, now):
    # No arbitrary file cleanup: only names and jobs created by this module.
    for path in root.glob("*.video.json"):
        ident = path.name[:-11]
        if not UUID_RE.fullmatch(ident) or path.is_symlink():
            continue
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
            age = now - float(s.get("claimed", 0))
        except (ValueError, KeyError, OSError, TypeError):
            continue
        if s.get("state") == "done":
            if now - float(s.get("completed", 0)) < MOVIE_TTL:
                continue
        elif age < LEASE_TTL:
            continue
        for suffix in (".mp4.part", ".mp4"):
            f = root / (ident + suffix)
            if f.is_file() and not f.is_symlink():
                f.unlink()
        path.unlink(missing_ok=True)


@never_cache
@require_GET
def video_worker_next(request):
    with locked() as root:
        if not _worker_ok(request, root):
            return HttpResponse(status=403)
        now = time.time()
        _discard_expired_video(root, now)
        # One GPU transfer at a time keeps storage bounded on cPanel.
        busy = any(
            j.get("state") in ("gpu_claimed", "uploading")
            for f in root.glob("*.video.json")
            if f.is_file() and not f.is_symlink()
            for j in [json.loads(f.read_text(encoding="utf-8"))]
        )
        if busy:
            return HttpResponse(status=204)
        for path in sorted(root.glob("*.stage.json")):
            stage = _valid_stage(root, path, now)
            if stage is None:
                continue
            ident = stage["id"]
            if _state(root, ident) is not None:
                continue
            s = {"id": ident, "owner": str(stage["user_id"]),
                 "state": "gpu_claimed", "lease": uuid4().hex,
                 "claimed": now, "offset": 0}
            _write_state(root, ident, s)
            return _nocache(JsonResponse({
                "id": ident, "lease": s["lease"],
                "duration": stage["storyboard"]["duration"]}))
    return HttpResponse(status=204)


@never_cache
@require_GET
def video_worker_metadata(request, ident):
    with locked() as root:
        s, error = _leased(root, request, ident)
        if error is not None:
            return error
        if s["state"] not in ("gpu_claimed", "uploading"):
            return HttpResponse(status=409)
        path = root / (ident + ".stage.json")
        stage = _valid_stage(root, path, time.time())
        if stage is None or str(stage["user_id"]) != s["owner"]:
            return HttpResponse(status=410)
        return _nocache(JsonResponse(stage))


@never_cache
@require_GET
def video_worker_reference(request, ident):
    with locked() as root:
        s, error = _leased(root, request, ident)
        if error is not None:
            return error
        if s["state"] not in ("gpu_claimed", "uploading"):
            return HttpResponse(status=409)
        if _valid_stage(root, root / (ident + ".stage.json"), time.time()) is None:
            return HttpResponse(status=410)
        path = root / (ident + ".input")
        if path.is_symlink() or not path.is_file():
            return HttpResponse(status=410)
        file = path.open("rb")
    return _nocache(FileResponse(file, content_type="application/octet-stream"))


@never_cache
@require_GET
def video_worker_progress(request, ident):
    with locked() as root:
        s, error = _leased(root, request, ident)
        if error is not None:
            return error
        if s["state"] not in ("gpu_claimed", "uploading"):
            return HttpResponse(status=409)
        return _nocache(JsonResponse({"offset": s["offset"],
                                      "state": s["state"]}))


@csrf_exempt  # Separate GPU-only bearer token + unguessable lease; not a browser endpoint.
@never_cache
@require_POST
def video_worker_chunk(request, ident):
    content_length = request.META.get("CONTENT_LENGTH", "")
    if content_length.isdigit() and int(content_length) > MAX_CHUNK:
        return HttpResponse(status=413)
    offset = request.headers.get("X-PICM-Offset", "")
    total = request.headers.get("X-PICM-Total", "")
    digest = request.headers.get("X-PICM-SHA256", "")
    if (not offset.isascii() or not offset.isdecimal()
            or not total.isascii() or not total.isdecimal()
            or not SHA256.fullmatch(digest)
            or int(total) < 2048 or int(total) > MAX_MOVIE):
        return HttpResponse(status=400)
    body = request.body
    if not 0 < len(body) <= MAX_CHUNK:
        return HttpResponse(status=413)
    with locked() as root:
        s, error = _leased(root, request, ident)
        if error is not None:
            return error
        if s["state"] not in ("gpu_claimed", "uploading"):
            return HttpResponse(status=409)
        start, size = int(offset), int(total)
        if start != s["offset"] or start + len(body) > size:
            return HttpResponse(status=409)
        if s["state"] == "gpu_claimed":
            if start != 0:
                return HttpResponse(status=409)
            # Reserve storage only when first chunk arrives.
            with (root / (ident + ".mp4.part")).open("xb") as output:
                os.fchmod(output.fileno(), 0o600)
            s["total"], s["sha256"] = size, digest
            s["state"] = "uploading"
        if s.get("total") != size or not hmac.compare_digest(s.get("sha256", ""), digest):
            return HttpResponse(status=409)
        part = root / (ident + ".mp4.part")
        if part.is_symlink() or not part.is_file() or part.stat().st_size != start:
            return HttpResponse(status=409)
        with part.open("ab") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
        s["offset"] = start + len(body)
        _write_state(root, ident, s)
        return _nocache(JsonResponse({"offset": s["offset"]}))


@csrf_exempt  # Machine-to-machine only; never accepts browser credentials.
@never_cache
@require_POST
def video_worker_finish(request, ident):
    if request.META.get("CONTENT_LENGTH", "0").isdigit() and int(
            request.META.get("CONTENT_LENGTH", "0")) > 4096:
        return HttpResponse(status=413)
    if len(request.body) > 4096:
        return HttpResponse(status=413)
    try:
        receipt = json.loads(request.body)
    except (ValueError, TypeError):
        return HttpResponse(status=400)
    if not isinstance(receipt, dict):
        return HttpResponse(status=400)
    with locked() as root:
        s, error = _leased(root, request, ident)
        if error is not None:
            return error
        if s["state"] != "uploading":
            return HttpResponse(status=409)
        if (receipt.get("job_id") != ident
                or receipt.get("state") != "real_mp4_rendered_and_ffprobed"
                or receipt.get("bytes") != s.get("total")
                or receipt.get("sha256") != s.get("sha256")
                or s["offset"] != s["total"]):
            return HttpResponse(status=422)
        part = root / (ident + ".mp4.part")
        if part.is_symlink() or not part.is_file() or part.stat().st_size != s["total"]:
            return HttpResponse(status=422)
        with part.open("rb") as stream:
            header = stream.read(min(2 * 1024 * 1024, s["total"]))
            if header[4:8] != b"ftyp" or b"moov" not in header:
                return HttpResponse(status=422)
            stream.seek(0)
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if not hmac.compare_digest(digest.hexdigest(), s["sha256"]):
            return HttpResponse(status=422)
        stage = root / (ident + ".stage.json")
        data = _valid_stage(root, stage, time.time())
        if (data is None or data["storyboard"]["duration"] != receipt.get("duration")
                or str(data["user_id"]) != s["owner"]):
            return HttpResponse(status=410)
        target = root / (ident + ".mp4")
        if target.exists() or target.is_symlink():
            return HttpResponse(status=409)
        os.replace(part, target)
        os.chmod(target, 0o600)
        s["state"], s["completed"] = "done", time.time()
        s.pop("lease", None)
        _write_state(root, ident, s)
    return _nocache(JsonResponse({"state": "done", "id": ident}))


@never_cache
@require_GET
def video_owner_status(request, ident):
    if not owner_allowed(request.user):
        raise Http404
    with locked() as root:
        s = _state(root, ident)
        if s is None:
            stage = _valid_stage(root, root / (ident + ".stage.json"), time.time())
            if stage is None or str(stage["user_id"]) != str(request.user.pk):
                raise Http404
            return _nocache(JsonResponse({"state": "staged_awaiting_gpu",
                                          "video_url": None}))
        if s["owner"] != str(request.user.pk):
            raise Http404
        if s["state"] == "done" and time.time() - s["completed"] >= MOVIE_TTL:
            return _nocache(JsonResponse({"state": "expired"}, status=410))
        return _nocache(JsonResponse({
            "state": s["state"],
            "video_url": "/picm/video/download/" + ident + "/"
            if s["state"] == "done" else None}))


@never_cache
@require_GET
def video_owner_download(request, ident):
    if not owner_allowed(request.user):
        raise Http404
    with locked() as root:
        s = _state(root, ident)
        if (s is None or s["owner"] != str(request.user.pk)
                or s["state"] != "done"
                or time.time() - s["completed"] >= MOVIE_TTL):
            raise Http404
        path = root / (ident + ".mp4")
        if path.is_symlink() or not path.is_file():
            raise Http404
        stream = path.open("rb")
    response = FileResponse(stream, content_type="video/mp4")
    response["Content-Disposition"] = 'attachment; filename="picm-story-' + ident + '.mp4"'
    return _nocache(response)
