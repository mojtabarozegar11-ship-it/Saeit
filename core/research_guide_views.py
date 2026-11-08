"""Fail-closed public Django route for hash-approved Zomorod Melal research guides.

Static cPanel files alone are not public Django routes on Passenger deployments.
Only exact author/editor-approved source bytes and a matching publisher journal
may be served. The publishing script creates the journal; this view never writes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET

MANIFEST = "content/zomorod-research-guides/publication-manifest-20261108.json"
SOURCE_RE = re.compile(r"content/zomorod-research-guides/[a-z0-9-]+\.md\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
RELEASE_RE = re.compile(r"ZM-RESEARCH-GUIDES-[A-Z0-9-]+\Z")
PUBLIC_HOSTS = frozenset({"zomorodmelal.ir", "www.zomorodmelal.ir"})
MAX_FILE_BYTES = 2_000_000


def _safe_read(root: Path, relative: str) -> bytes:
    """No symlinks, path escapes, directories or unbounded file loads."""
    if not root.is_dir() or root.is_symlink():
        raise Http404
    base = root.resolve(strict=True)
    item = base / relative
    if not item.resolve().is_relative_to(base) or not item.is_file():
        raise Http404
    candidate = item
    while candidate != base:
        if candidate.is_symlink():
            raise Http404
        candidate = candidate.parent
    if item.stat().st_size > MAX_FILE_BYTES:
        raise Http404
    return item.read_bytes()


def _load_public_file(slug: str, *, require_verified: bool = False) -> tuple[bytes, str]:
    """Return exact public HTML and release state, or reject without disclosure."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise Http404
    configured_root = os.environ.get("ZOMOROD_RESEARCH_GUIDES_WEB_ROOT", "")
    if not configured_root:
        raise Http404
    web_root = Path(configured_root)
    source_root = Path(settings.BASE_DIR)
    try:
        manifest = json.loads(_safe_read(source_root, MANIFEST))
        if manifest.get("site") != "https://zomorodmelal.ir":
            raise Http404
        release = manifest.get("release_id")
        if not isinstance(release, str) or not RELEASE_RE.fullmatch(release):
            raise Http404
        wanted = "https://zomorodmelal.ir/research/guides/" + slug + "/"
        approved = [g for g in manifest.get("guides", [])
                    if isinstance(g, dict) and g.get("desired_url") == wanted]
        if len(approved) != 1 or approved[0].get("status") != "APPROVED_FOR_SITE":
            raise Http404
        guide = approved[0]
        source_path = guide.get("source_path", "")
        if not isinstance(source_path, str) or not SOURCE_RE.fullmatch(source_path):
            raise Http404
        expected_source_sha = guide.get("approved_source_sha256", "")
        if not isinstance(expected_source_sha, str) or not SHA_RE.fullmatch(expected_source_sha):
            raise Http404
        source = _safe_read(source_root, source_path)
        if hashlib.sha256(source).hexdigest() != expected_source_sha:
            raise Http404

        state_default = web_root.parent / ".backups" / "zomorod-research-guides"
        state_root = Path(os.environ.get("ZOMOROD_RESEARCH_GUIDES_STATE_ROOT", str(state_default)))
        journal = json.loads(_safe_read(state_root, release + "/journal.json"))
        state = journal.get("state")
        if journal.get("release_id") != release or state not in ("installed_unverified", "live_verified"):
            raise Http404
        if require_verified and state != "live_verified":
            raise Http404
        relative_html = "research/guides/" + slug + "/index.html"
        expected_html_sha = journal.get("created", {}).get(relative_html, "")
        if not isinstance(expected_html_sha, str) or not SHA_RE.fullmatch(expected_html_sha):
            raise Http404
        html_bytes = _safe_read(web_root, relative_html)
        if hashlib.sha256(html_bytes).hexdigest() != expected_html_sha:
            raise Http404
        return html_bytes, state
    except (OSError, ValueError, TypeError, AttributeError, KeyError, UnicodeError):
        raise Http404 from None


@require_GET
def research_guide(request, slug: str):
    """Django/Passenger endpoint, with no unapproved publishing side effects."""
    if request.get_host().split(":")[0].lower() not in PUBLIC_HOSTS:
        raise Http404
    payload, state = _load_public_file(slug)
    response = HttpResponse(payload, content_type="text/html; charset=utf-8")
    response["X-Content-Type-Options"] = "nosniff"
    if state == "installed_unverified":
        response["X-Robots-Tag"] = "noindex, nofollow"
        response["Cache-Control"] = "no-store"
    else:
        response["Cache-Control"] = "public, max-age=300"
    return response


def verified_guide_paths() -> list[str]:
    """Only publicly verified, hash-matching paths can enter sitemap.xml."""
    try:
        manifest = json.loads(_safe_read(Path(settings.BASE_DIR), MANIFEST))
        if manifest.get("site") != "https://zomorodmelal.ir":
            return []
        paths: list[str] = []
        for guide in manifest.get("guides", []):
            if not isinstance(guide, dict):
                continue
            url = guide.get("desired_url", "")
            m = re.fullmatch(
                r"https://zomorodmelal\.ir/research/guides/([a-z0-9]+(?:-[a-z0-9]+)*)/", str(url)
            )
            if m:
                try:
                    _load_public_file(m.group(1), require_verified=True)
                except Http404:
                    continue
                paths.append("/research/guides/" + m.group(1) + "/")
        return paths
    except (OSError, ValueError, TypeError, UnicodeError):
        return []
