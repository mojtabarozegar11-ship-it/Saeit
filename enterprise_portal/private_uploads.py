"""Private, non-public evidence store for Zomorod office correspondence.

No file is served from MEDIA_URL or public_html. Allowed formats are PDF,
PNG, and JPEG up to 8 MiB. Every download re-verifies the saved SHA-256.
"""
from contextlib import contextmanager
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


def _private_root_path():
    """Validate the configured path without trusting any pathname lookup."""
    default = Path(settings.BASE_DIR).parent / ".private/zomorod-business/office-files"
    root = Path(getattr(settings, "COMPANY_OFFICE_ATTACHMENT_ROOT", default))
    if (not root.is_absolute() or "public_html" in root.parts
            or root == Path("/") or ".." in root.parts):
        raise RuntimeError("Unsafe office attachment storage directory")
    return root


@contextmanager
def _private_dir_fd(*, create=False):
    """Pin each ancestor with openat(O_NOFOLLOW), preventing path-swap escapes.

    Every file operation must use the yielded descriptor, never re-resolve the
    pathname after validation. Linux/cPanel support is required, fail closed.
    """
    root = _private_root_path()
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise RuntimeError("Private attachment storage requires secure directory descriptors")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    current_fd = os.open("/", flags)
    try:
        for component in root.parts[1:]:
            try:
                if create:
                    try:
                        os.mkdir(component, mode=0o700, dir_fd=current_fd)
                    except FileExistsError:
                        pass
                next_fd = os.open(component, flags, dir_fd=current_fd)
            except OSError as exc:
                raise RuntimeError("Symlinked or unavailable office attachment directory") from exc
            os.close(current_fd)
            current_fd = next_fd
        mode = os.fstat(current_fd).st_mode
        if not stat.S_ISDIR(mode) or mode & 0o077:
            raise RuntimeError("Private attachment directory permissions are too broad")
        yield current_fd
    finally:
        os.close(current_fd)


def _private_root(*, create=False):
    """Compatibility helper; file I/O must use _private_dir_fd instead."""
    root = _private_root_path()
    with _private_dir_fd(create=create):
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


def _validated_key(key):
    if not SAFE_KEY.fullmatch(str(key)):
        raise Http404("شناسه فایل نامعتبر است.")
    return str(key)


def store_attachment(letter, actor, upload):
    """Save an immutable blob through a pinned directory descriptor."""
    original, content_type, ext = _validated_file(upload)
    key = _validated_key(uuid.uuid4().hex + ext)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    digest = hashlib.sha256()
    length = 0
    with _private_dir_fd(create=True) as directory_fd:
        fd = os.open(key, flags, 0o600, dir_fd=directory_fd)
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
                os.unlink(key, dir_fd=directory_fd)
            except OSError:
                pass
            raise


def remove_only_new_attachment(key):
    """Rollback cleanup in the pinned private directory only."""
    if not SAFE_KEY.fullmatch(str(key)):
        return
    try:
        with _private_dir_fd() as directory_fd:
            os.unlink(str(key), dir_fd=directory_fd)
    except (OSError, RuntimeError):
        pass


def download_attachment(record):
    key = _validated_key(record.storage_key)
    with _private_dir_fd() as directory_fd:
        fd = None
        try:
            fd = os.open(key, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
            meta = os.fstat(fd)
            if (not stat.S_ISREG(meta.st_mode) or meta.st_size != record.size_bytes
                    or meta.st_size > MAX_BYTES or meta.st_mode & 0o077
                    or meta.st_nlink != 1):
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
