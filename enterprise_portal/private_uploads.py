"""Private, non-public evidence store for Zomorod office correspondence.

No file is served from MEDIA_URL or public_html. Allowed formats are PDF,
PNG, and JPEG up to 8 MiB. Every download re-verifies the saved SHA-256.
"""
import hashlib
import os
import re
import stat
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.utils.http import content_disposition_header

from .models import OfficeAttachment

MAX_BYTES = 8 * 1024 * 1024
MAGIC = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}
SAFE_KEY = re.compile(r"^[a-f0-9]{32}\.(?:pdf|png|jpg)$")


def _private_root(*, create=False):
    default = Path(settings.BASE_DIR).parent / ".private/zomorod-business/office-files"
    root = Path(getattr(settings, "COMPANY_OFFICE_ATTACHMENT_ROOT", default))
    if not root.is_absolute() or "public_html" in root.parts or root == Path("/"):
        raise RuntimeError("Unsafe office attachment storage directory")
    # Reject redirects through an attacker-controlled symlink on the private path.
    for candidate in (root, root.parent, root.parent.parent):
        if candidate.is_symlink():
            raise RuntimeError("Symlinked office attachment directory")
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not root.is_dir() or not stat.S_ISDIR(root.stat().st_mode):
        raise RuntimeError("Private attachment directory is not available")
    if root.stat().st_mode & 0o077:
        raise RuntimeError("Private attachment directory permissions are too broad")
    return root


def _validated_file(upload):
    name = str(getattr(upload, "name", "")).replace("\\", "/").split("/")[-1].strip()
    if not name or len(name) > 180 or name.startswith("."):
        raise ValidationError("نام فایل پیوست نامعتبر است.")
    ext = Path(name).suffix.lower()
    if ext not in MAGIC:
        raise ValidationError("تنها PDF، PNG و JPEG برای دبیرخانه پذیرفته می‌شوند.")
    if upload.size is not None and upload.size > MAX_BYTES:
        raise ValidationError("حجم فایل بیش از ۸ مگابایت است.")
    upload.seek(0)
    marker = upload.read(12)
    upload.seek(0)
    content_type, expected = MAGIC[ext]
    if not marker.startswith(expected):
        raise ValidationError("نوع واقعی فایل با پسوند آن یکسان نیست.")
    return name, content_type, ".jpg" if ext == ".jpeg" else ext


def _path_for(key, *, create=False):
    if not SAFE_KEY.fullmatch(str(key)):
        raise Http404("شناسه فایل نامعتبر است.")
    return _private_root(create=create) / key


def store_attachment(letter, actor, upload):
    """Save a single new immutable blob and metadata; remove our blob on failure."""
    original, content_type, ext = _validated_file(upload)
    key = uuid.uuid4().hex + ext
    target = _path_for(key, create=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    digest = hashlib.sha256()
    length = 0
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            for part in upload.chunks():
                length += len(part)
                if length > MAX_BYTES:
                    raise ValidationError("حجم پیوست بیش از حد مجاز است.")
                digest.update(part)
                output.write(part)
            output.flush()
            os.fsync(output.fileno())
        if length == 0:
            raise ValidationError("فایل پیوست خالی است.")
        return OfficeAttachment.objects.create(
            letter=letter, uploaded_by=actor, storage_key=key,
            original_name=original, content_type=content_type,
            size_bytes=length, sha256=digest.hexdigest(),
        )
    except BaseException:
        try:
            target.unlink()
        except OSError:
            pass
        raise


def remove_only_new_attachment(key):
    """Rollback cleanup only for an exact UUID file created by this request."""
    if not SAFE_KEY.fullmatch(str(key)):
        return
    try:
        _path_for(key).unlink()
    except OSError:
        pass


def download_attachment(record):
    target = _path_for(record.storage_key)
    fd = None
    try:
        fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size != record.size_bytes or meta.st_size > MAX_BYTES:
            raise Http404("فایل پیوست قابل بازیابی نیست.")
        with os.fdopen(fd, "rb") as source:
            fd = None
            data = source.read(MAX_BYTES + 1)
        if len(data) != record.size_bytes or hashlib.sha256(data).hexdigest() != record.sha256:
            raise Http404("یکپارچگی فایل پیوست تأیید نشد.")
    except OSError as exc:
        raise Http404("فایل پیوست پیدا نشد.") from exc
    finally:
        if fd is not None:
            os.close(fd)
    response = HttpResponse(data, content_type=record.content_type)
    response["Content-Disposition"] = content_disposition_header(True, record.original_name)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Referrer-Policy"] = "same-origin"
    return response
