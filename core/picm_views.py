"""Private, bounded image queue for MojPlayWin /picm/.

No direct browser -> ComfyUI connection. The VPS worker retrieves jobs over
authenticated HTTPS; all user results are private and stored outside docroot.
"""
import fcntl
import hmac
import json
import os
from pathlib import Path
import re
import struct
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

UUID_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_JOBS = 80
DAILY_QUOTA = 2
MAX_IMAGE_BYTES = 2_000_000
STYLE = {
    "cinematic": "cinematic soft lighting, striking composition",
    "natural": "natural photography, realistic colors",
    "illustration": "detailed storybook illustration",
    "product": "clean professional product photography",
}


def root_path():
    root = Path(os.environ.get("PICM_STORAGE_DIR", str(Path.home() / ".picm-queue")))
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise RuntimeError("PICM unsafe storage root")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    return root


@contextmanager
def locked():
    root = root_path()
    lockfile = root / ".lock"
    if lockfile.is_symlink():
        raise RuntimeError("PICM unsafe lock")
    with lockfile.open("a+b") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield root
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def job_path(root, ident):
    if not UUID_RE.fullmatch(str(ident)):
        raise Http404
    return root / (ident + ".json")


def load_job(root, ident):
    path = job_path(root, ident)
    if not path.is_file() or path.is_symlink():
        raise Http404
    return json.loads(path.read_text(encoding="utf-8"))


def save_job(root, job):
    path = job_path(root, job["id"])
    data = (json.dumps(job, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    fd, tmp = tempfile.mkstemp(dir=root, prefix=".picm-", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def job_records(root):
    for path in root.glob("*.json"):
        if not path.is_symlink() and UUID_RE.fullmatch(path.stem):
            try:
                yield json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue


def worker_authorized(request, root):
    secret_file = root / "worker-token"
    if not secret_file.is_file() or secret_file.is_symlink():
        return False
    try:
        secret = secret_file.read_text(encoding="ascii").strip()
    except OSError:
        return False
    authorization = request.headers.get("Authorization", "")
    return (len(secret) >= 48 and len(authorization) <= 160
            and hmac.compare_digest(authorization, "Bearer " + secret))


def unauthenticated():
    response = JsonResponse({"error": "authentication_required"}, status=401)
    response["Cache-Control"] = "no-store"
    return response


@never_cache
@require_GET
def picm_page(request):
    """Entry page: never mix the login form with the image workbench."""
    return redirect("/picm/workspace/" if request.user.is_authenticated else "/picm/login/")


@never_cache
@require_GET
def picm_workbench(request):
    """The protected second page, reached only after login."""
    if not request.user.is_authenticated:
        return redirect("/picm/login/")
    return render(request, "picm/index.html", {
        "picm_authenticated": True,
        "picm_daily_limit": DAILY_QUOTA,
    })


@never_cache
@require_POST
def picm_submit(request):
    if not request.user.is_authenticated:
        return unauthenticated()
    if len(request.body) > 2000:
        return JsonResponse({"error": "request_too_large"}, status=413)
    try:
        payload = json.loads(request.body)
        prompt = payload.get("prompt", "")
        style = payload.get("style", "cinematic")
        steps = payload.get("steps", 2)
    except (ValueError, AttributeError, TypeError):
        return JsonResponse({"error": "invalid_json"}, status=400)
    if (not isinstance(prompt, str) or not 4 <= len(prompt.strip()) <= 580
            or style not in STYLE or type(steps) is not int or steps not in (1, 2, 3)):
        return JsonResponse({"error": "invalid_input"}, status=400)
    now = time.time()
    with locked() as root:
        records = list(job_records(root))
        # No unlimited public CPU consumption; cap pending load and per-user use.
        if len(records) >= MAX_JOBS:
            return JsonResponse({"error": "studio_capacity_reached"}, status=503)
        recent = [j for j in records if j.get("user_id") == request.user.pk
                  and now - j.get("created", 0) < 86400]
        if len(recent) >= DAILY_QUOTA:
            return JsonResponse({"error": "daily_limit_reached"}, status=429)
        pending = sum(j.get("state") in ("queued", "running") for j in records)
        if pending >= 8:
            return JsonResponse({"error": "queue_full"}, status=503)
        ident = uuid4().hex
        job = {"id": ident, "user_id": request.user.pk,
               "prompt": prompt.strip() + ", " + STYLE[style],
               "style": style, "steps": steps, "created": now,
               "state": "queued", "attempts": 0, "updated": now}
        save_job(root, job)
    response = JsonResponse({"id": ident, "state": "queued"}, status=202)
    response["Cache-Control"] = "no-store"
    return response


@never_cache
@require_GET
def picm_status(request, ident):
    if not request.user.is_authenticated:
        return unauthenticated()
    with locked() as root:
        job = load_job(root, ident)
    if job.get("user_id") != request.user.pk:
        raise Http404
    response = JsonResponse({
        "id": ident, "state": job["state"],
        "image_url": "/picm/image/" + ident + "/" if job["state"] == "done" else None,
        "message": "A render is taking longer than expected" if job["state"] == "failed" else "",
    })
    response["Cache-Control"] = "no-store"
    return response


@never_cache
@require_GET
def picm_image(request, ident):
    if not request.user.is_authenticated:
        raise Http404
    with locked() as root:
        job = load_job(root, ident)
        if job.get("user_id") != request.user.pk or job.get("state") != "done":
            raise Http404
        path = root / (ident + ".png")
        if path.is_symlink() or not path.is_file():
            raise Http404
        image = path.open("rb")
    response = FileResponse(image, content_type="image/png")
    response["Cache-Control"] = "private, no-store"
    response["Content-Disposition"] = 'attachment; filename="picm-' + ident + '.png"'
    return response


@never_cache
@require_GET
def picm_worker_next(request):
    with locked() as root:
        if not worker_authorized(request, root):
            return HttpResponse(status=403)
        now = time.time()
        _clean_expired_staging(root, now)
        records = sorted(job_records(root), key=lambda j: j.get("created", 0))
        for job in records:
            if job.get("state") == "running" and now - job.get("updated", 0) > 900:
                # Retry one abandoned lease, then fail closed.
                job["state"] = "queued" if job.get("attempts", 0) < 2 else "failed"
                job["updated"] = now
                save_job(root, job)
        for job in records:
            if job.get("state") != "queued":
                continue
            job["state"] = "running"
            job["attempts"] = job.get("attempts", 0) + 1
            job["updated"] = now
            job["lease"] = uuid4().hex
            save_job(root, job)
            response = JsonResponse({
                "id": job["id"], "prompt": job["prompt"],
                "steps": job["steps"], "lease": job["lease"]})
            response["Cache-Control"] = "no-store"
            return response
    return HttpResponse(status=204)


@csrf_exempt  # Machine-to-machine bearer token; browser endpoints remain CSRF-protected.
@never_cache
@require_POST
def picm_worker_finish(request, ident):
    if len(request.body) > MAX_IMAGE_BYTES:
        return HttpResponse(status=413)
    with locked() as root:
        if not worker_authorized(request, root):
            return HttpResponse(status=403)
        try:
            job = load_job(root, ident)
        except Http404:
            return HttpResponse(status=404)
        lease = request.headers.get("X-PICM-Lease", "")
        if not lease or not hmac.compare_digest(str(job.get("lease", "")), lease):
            return HttpResponse(status=409)
        if job["state"] != "running":
            return HttpResponse(status=409)
        if request.content_type == "image/png":
            image = request.body
            if (len(image) < 1024 or not image.startswith(b"\x89PNG\r\n\x1a\n")
                    or len(image) < 24 or struct.unpack(">II", image[16:24]) != (256, 256)):
                return HttpResponse(status=422)
            fd, tmp = tempfile.mkstemp(dir=root, prefix=".picm-", suffix=".png")
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb") as fp:
                    fp.write(image)
                    fp.flush()
                    os.fsync(fp.fileno())
                os.replace(tmp, root / (ident + ".png"))
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            job["state"] = "done"
        elif request.content_type == "application/json":
            job["state"] = "failed"
        else:
            return HttpResponse(status=415)
        job.pop("lease", None)
        job["updated"] = time.time()
        save_job(root, job)
    return JsonResponse({"state": job["state"]})


@never_cache
@require_GET
def picm_worker_health(request):
    with locked() as root:
        if not worker_authorized(request, root):
            return HttpResponse(status=403)
    response = JsonResponse({"ready": True, "engine": "private-vps-polling"})
    response["Cache-Control"] = "no-store"
    return response


# Photo-based PICM Pro input staging. No worker is allowed to claim staged jobs:
# video, image-to-image and true 8K detail upscaling require a separate GPU engine.
PICM_REFERENCE_MAX_BYTES = 6 * 1024 * 1024
PICM_REFERENCE_MAX_DIMENSION = 8192
PICM_REFERENCE_MAX_PIXELS = 24_000_000
PICM_REFERENCE_TTL_SECONDS = 86400
PICM_REFERENCE_ALLOWED_MODES = frozenset(("image_edit", "image_video", "upscale_8k"))


def _reference_dimensions(data):
    """Read bounded PNG/JPEG headers without executing image decoders on cPanel."""
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        if data[12:16] != b"IHDR" or struct.unpack(">I", data[8:12])[0] != 13:
            return None
        width, height = struct.unpack(">II", data[16:24])
        return "png", width, height
    if not data.startswith(b"\xff\xd8\xff"):
        return None
    offset = 2
    # Walk JPEG markers to read the real SOF dimensions; never trust extensions.
    while offset + 4 < len(data):
        if data[offset] != 0xFF:
            return None
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            return None
        marker = data[offset]
        offset += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if marker == 0xDA:
            return None  # JPEG scan before SOF is malformed
        if offset + 2 > len(data):
            return None
        size = struct.unpack(">H", data[offset:offset + 2])[0]
        if size < 2 or offset + size > len(data):
            return None
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if size < 7:
                return None
            height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
            return "jpeg", width, height
        offset += size
    return None


def _clean_expired_staging(root, now):
    # Only PICM reference names, never historic production jobs or other files.
    for metadata_path in root.glob("*.stage.json"):
        if metadata_path.is_symlink() or not UUID_RE.fullmatch(metadata_path.name[:32]):
            continue
        if metadata_path.name != metadata_path.name[:32] + ".stage.json":
            continue
        try:
            record = json.loads(metadata_path.read_text(encoding="utf-8"))
            if now - float(record["created"]) < PICM_REFERENCE_TTL_SECONDS:
                continue
            image_path = root / (metadata_path.name[:32] + ".input")
            if image_path.is_file() and not image_path.is_symlink():
                image_path.unlink()
            metadata_path.unlink()
        except (OSError, ValueError, KeyError, TypeError):
            continue


@never_cache
@require_POST
def picm_reference_stage(request):
    """Accept a private owner-scoped image; do NOT promise an unavailable GPU render."""
    if not request.user.is_authenticated:
        return unauthenticated()
    if request.META.get("CONTENT_LENGTH", "").isdigit():
        if int(request.META["CONTENT_LENGTH"]) > PICM_REFERENCE_MAX_BYTES + 65536:
            return JsonResponse({"error": "reference_too_large"}, status=413)
    mode = request.POST.get("mode", "")
    prompt = request.POST.get("prompt", "")
    if mode not in PICM_REFERENCE_ALLOWED_MODES:
        return JsonResponse({"error": "invalid_mode"}, status=400)
    if not isinstance(prompt, str) or len(prompt) > 580:
        return JsonResponse({"error": "invalid_prompt"}, status=400)
    if mode in ("image_edit", "image_video") and len(prompt.strip()) < 4:
        return JsonResponse({"error": "prompt_required"}, status=400)
    if mode == "upscale_8k" and prompt.strip():
        return JsonResponse({"error": "upscale_does_not_take_prompt"}, status=400)
    image = request.FILES.get("photo")
    if image is None:
        return JsonResponse({"error": "reference_photo_required"}, status=400)
    if image.size < 128 or image.size > PICM_REFERENCE_MAX_BYTES:
        return JsonResponse({"error": "invalid_reference_size"}, status=413)
    # Read only a bounded amount; never derive a server path from uploaded filename.
    raw = image.read(PICM_REFERENCE_MAX_BYTES + 1)
    if len(raw) != image.size or len(raw) > PICM_REFERENCE_MAX_BYTES:
        return JsonResponse({"error": "invalid_reference_size"}, status=413)
    dimensions = _reference_dimensions(raw)
    if dimensions is None:
        return JsonResponse({"error": "unsupported_reference_file"}, status=415)
    kind, width, height = dimensions
    if (width < 128 or height < 128
            or max(width, height) > PICM_REFERENCE_MAX_DIMENSION
            or width * height > PICM_REFERENCE_MAX_PIXELS):
        return JsonResponse({"error": "invalid_reference_dimensions"}, status=422)
    now = time.time()
    with locked() as root:
        _clean_expired_staging(root, now)
        staged = []
        for path in root.glob("*.stage.json"):
            if path.is_symlink():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if data.get("user_id") == request.user.pk:
                staged.append(data)
        if len(staged) >= 3:
            return JsonResponse({"error": "photo_limit_reached"}, status=429)
        ident = uuid4().hex
        filename = root / (ident + ".input")
        fd, tempname = tempfile.mkstemp(dir=root, prefix=".picm-reference-", suffix=".tmp")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as dest:
                dest.write(raw)
                dest.flush()
                os.fsync(dest.fileno())
            os.replace(tempname, filename)
        finally:
            if os.path.exists(tempname):
                os.unlink(tempname)
        metadata = {
            "id": ident, "mode": mode, "prompt": prompt.strip(),
            "user_id": request.user.pk, "created": now,
            "format": kind, "width": width, "height": height,
            "state": "staged_awaiting_gpu",
        }
        metadata_path = root / (ident + ".stage.json")
        try:
            fd, tempname = tempfile.mkstemp(dir=root, prefix=".picm-stage-", suffix=".tmp")
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as dest:
                    json.dump(metadata, dest, ensure_ascii=False)
                    dest.flush()
                    os.fsync(dest.fileno())
                os.replace(tempname, metadata_path)
            finally:
                if os.path.exists(tempname):
                    os.unlink(tempname)
        except Exception:
            filename.unlink(missing_ok=True)
            raise
    result = JsonResponse({
        "id": ident, "state": "staged_awaiting_gpu",
        "message": "Reference received privately. The selected GPU model is not yet connected.",
        "mode": mode, "width": width, "height": height,
        "expires_in_seconds": PICM_REFERENCE_TTL_SECONDS,
    }, status=202)
    result["Cache-Control"] = "no-store"
    return result


@never_cache
@require_GET
def picm_reference_status(request, ident):
    """Only the image owner can view its preparation state."""
    if not request.user.is_authenticated:
        return unauthenticated()
    if not UUID_RE.fullmatch(ident):
        raise Http404
    with locked() as root:
        path = root / (ident + ".stage.json")
        if not path.is_file() or path.is_symlink():
            raise Http404
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("user_id") != request.user.pk:
            raise Http404
        if time.time() - float(data["created"]) >= PICM_REFERENCE_TTL_SECONDS:
            return JsonResponse({"state": "expired"}, status=410)
        result = JsonResponse({"id": ident, "state": data["state"],
                               "mode": data["mode"], "width": data["width"],
                               "height": data["height"]})
        result["Cache-Control"] = "no-store"
        return result
