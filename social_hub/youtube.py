"""Resumable YouTube videos.insert, private local file only, no arbitrary URL fetch.

Security: uploads only explicitly approved local video under private MEDIA_ROOT.
The upstream session URL is allowed only on Google API upload hosts.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import re
import stat
from urllib.parse import urlsplit

from .adapters import Blocked, DispatchOutcome, Uncertain, Response

CHUNK_SIZE = 8 * 1024 * 1024

def checked_file(media_root, path):
    root = Path(media_root).resolve(strict=True)
    if not root.is_dir():
        raise Blocked("Private media root unavailable")
    candidate = Path(path)
    if ".." in candidate.parts:
        raise Blocked("Media path traversal forbidden")
    if not candidate.is_absolute():
        candidate = root / candidate
    # Reject symlinks in the entire provided path, not just the final file.
    tentative = candidate.absolute()
    if not tentative.is_relative_to(root):
        raise Blocked("Video outside private media root")
    for component in (root, *[root.joinpath(*tentative.relative_to(root).parts[:i])
                               for i in range(1, len(tentative.relative_to(root).parts) + 1)]):
        if component.is_symlink():
            raise Blocked("Video symlink or symlinked directory forbidden")
    try:
        real = tentative.resolve(strict=True)
    except (OSError, RuntimeError):
        raise Blocked("Video file missing or inaccessible") from None
    if not real.is_relative_to(root) or not stat.S_ISREG(real.stat().st_mode):
        raise Blocked("Video must be a regular private file")
    size = real.stat().st_size
    if not 1 <= size <= 2 * 1024**3:
        raise Blocked("Video file size out of configured range")
    return real, size

def _location(value):
    if not isinstance(value, str):
        raise Uncertain("YouTube resumable upload session missing")
    url = urlsplit(value)
    if (url.scheme != "https" or url.hostname not in
        {"www.googleapis.com", "www.google.com", "youtube.googleapis.com"}
        or url.username or url.password or url.port or not url.path.startswith("/upload/")):
        raise Uncertain("YouTube upload location not on official HTTPS endpoint")
    return value

def upload_video(account: dict, content: dict, token: str, transport, *, media_root: str) -> DispatchOutcome:
    if account.get("platform") != "youtube" or account.get("verified") is not True:
        raise Blocked("Unverified YouTube channel")
    video, size = checked_file(media_root, content.get("media_path", ""))
    title, desc = content.get("title"), content.get("text")
    if not isinstance(title, str) or not 1 <= len(title) <= 100:
        raise Blocked("YouTube video title required")
    if not isinstance(desc, str) or len(desc) > 5000:
        raise Blocked("YouTube description invalid")
    if content.get("privacy") not in ("private", "unlisted", "public"):
        raise Blocked("Explicit YouTube privacy selection required")
    if content.get("made_for_kids") not in (True, False):
        raise Blocked("Made-for-kids designation required")
    body = {
        "snippet": {"title": title, "description": desc, "categoryId": "22"},
        "status": {"privacyStatus": content["privacy"], "selfDeclaredMadeForKids": content["made_for_kids"]},
    }
    headers = {
        "Authorization": "Bearer " + token, "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size),
    }
    session = transport("POST",
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        body, headers)
    if session.status not in (200, 201):
        raise Uncertain("YouTube upload initialization failed")
    url = _location(session.headers.get("Location") or session.headers.get("location"))
    next_byte = 0
    with video.open("rb") as f:
        while next_byte < size:
            f.seek(next_byte)
            chunk = f.read(min(CHUNK_SIZE, size - next_byte))
            if not chunk:
                raise Uncertain("Video changed during upload")
            end = next_byte + len(chunk) - 1
            headers = {"Authorization": "Bearer " + token, "Content-Type": "video/mp4",
                       "Content-Range": "bytes " + str(next_byte) + "-" + str(end) + "/" + str(size)}
            response = transport("PUT", url, chunk, headers)
            if response.status in (200, 201):
                rid = response.payload.get("id")
                if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{6,40}", rid):
                    raise Uncertain("YouTube video ID absent")
                return DispatchOutcome("submitted", rid, "YouTube accepted video upload; privacy and processing status require separate confirmation")
            if response.status != 308:
                raise Uncertain("YouTube upload returned unexpected state")
            server_range = response.headers.get("Range") or response.headers.get("range")
            if server_range:
                match = re.fullmatch(r"bytes=0-([0-9]+)", server_range)
                if not match:
                    raise Uncertain("YouTube resumable position invalid")
                confirmed_end = int(match.group(1))
                if confirmed_end < next_byte - 1 or confirmed_end > end:
                    raise Uncertain("YouTube resumable offset inconsistent")
                next_byte = confirmed_end + 1
            else:
                if next_byte == 0:
                    # Some Google responses give no Range until the first chunk is accepted.
                    # Retrying here may be necessary but MUST NOT assume success.
                    raise Uncertain("No confirmed bytes in YouTube resumable session")
                raise Uncertain("Upload byte count not acknowledged")
    raise Uncertain("Video upload did not finish with a confirmed video ID")
