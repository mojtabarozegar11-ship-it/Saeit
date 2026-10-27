#!/usr/bin/env python3
"""Deduplicate Mojtaba's gallery-only image assets from the personal homepage.

Touch exactly one independent Django template. The ten gallery pictures and the
three copies of the same supplementary portrait must already be present in the
dedicated Gallery before any homepage markup is replaced. A SHA256-verified
backup and reversible atomic replacement protect the active site.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
REL = "templates/personal_site/core/home.html"
BACKUP_ROOT = Path("/home/zomorod2/.backups/mojtaba-gallery-consolidation")
GALLERY_ID = "owner-original-gallery-20261015"
PORTRAITS_ID = "mpw-personal-home-sport-white-20261018"
NEW_ID = "mpw-gallery-preview-20261027"
PRESERVE_IDS = (
    "mpw-primary-personal-profile-20261016",
    "mpw-two-profile-portraits-20261020",
    "mpw-social-central-hub-20261026",
    "hero-title",
    "mpw-fifty-editorials-20261015",
    "mpw-academic-profile-20261016",
    "mpw-personal-expanded-20261016",
)
SECTION_TAG = re.compile(r"</?section\b[^>]*>", re.I)
GALLERY_PREVIEW = """
<section id="mpw-gallery-preview-20261027" aria-labelledby="mpw-gallery-preview-title-20261027" style="box-sizing:border-box;max-width:1180px;margin:48px auto;padding:clamp(28px,5vw,58px);border:1px solid #a78c59;border-radius:20px;background:linear-gradient(130deg,#101a29 5%,#1b2b40 100%);color:#f3ece1">
  <p style="font-size:0.75rem;letter-spacing:0.2em;color:#d7b879;text-transform:uppercase;margin:0 0 16px">The personal photo archive</p>
  <h2 id="mpw-gallery-preview-title-20261027" style="font-size:clamp(1.75rem,3.8vw,2.9rem);line-height:1.15;max-width:720px;color:#fff7ec;margin:0 0 20px">Portraits, heritage and the journey behind the work.</h2>
  <p style="font-size:1.05rem;line-height:1.85;max-width:710px;color:#d8e0e7;margin:0 0 28px">A curated collection of original photographs and personal perspectives, connecting a background in agricultural economics and enterprise with current research and creative work.</p>
  <a href="/mojtaba.roozegar/gallery/" style="display:inline-block;color:#101a29;background:#ddbf83;border-radius:8px;padding:14px 22px;text-decoration:none;font-weight:700">Explore the complete photo gallery &rarr;</a>
</section>
"""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def section_span(document: str, ident: str) -> tuple[int, int]:
    opening = re.compile(
        r'<section\b[^>]*\bid=["\']' + re.escape(ident) + r'["\'][^>]*>', re.I
    )
    matches = list(opening.finditer(document))
    if len(matches) != 1:
        raise ValueError("Expected exactly one gallery section: " + ident)
    match = matches[0]
    depth = 1
    for token in SECTION_TAG.finditer(document, match.end()):
        depth += -1 if token.group().startswith("</") else 1
        if depth == 0:
            return match.start(), token.end()
    raise ValueError("Unclosed gallery section: " + ident)


def section_text(document: str, ident: str) -> str:
    start, end = section_span(document, ident)
    return document[start:end]


class ImgCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.srcs: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag != "img":
            return
        src = dict(attrs).get("src", "")
        if src:
            self.srcs.append(src)


def image_sources(document: str) -> list[str]:
    parser = ImgCollector()
    parser.feed(document)
    return parser.srcs


def assert_gallery_retains_images(home_html: str, gallery_html: str) -> None:
    original = image_sources(section_text(home_html, GALLERY_ID))
    repeated = image_sources(section_text(home_html, PORTRAITS_ID))
    published = set(image_sources(gallery_html))
    if len(original) != 10 or len(set(original)) != 10:
        raise ValueError("Original homepage gallery changed; refuse consolidation")
    if len(repeated) != 3 or len(set(repeated)) != 1:
        raise ValueError("Three-copy repeated portrait changed; refuse consolidation")
    if not (set(original) | set(repeated)).issubset(published):
        raise ValueError("Gallery is missing an image used on the homepage")


def plan(source: str) -> tuple[str, int]:
    if NEW_ID in source:
        raise ValueError("Gallery preview already installed; no second mutation")
    bounds = sorted((
        section_span(source, GALLERY_ID) + (GALLERY_ID,),
        section_span(source, PORTRAITS_ID) + (PORTRAITS_ID,),
    ))
    if bounds[0][1] > bounds[1][0]:
        raise ValueError("Unexpected overlapping sections")
    updated = source
    removed = sum(end - start for start, end, _ in bounds)
    for start, end, ident in reversed(bounds):
        updated = updated[:start] + (GALLERY_PREVIEW if ident == GALLERY_ID else "") + updated[end:]
    if removed < 5000 or len(updated) >= len(source):
        raise ValueError("Gallery consolidation would not materially reduce markup")
    for ident in (GALLERY_ID, PORTRAITS_ID):
        if 'id="' + ident + '"' in updated:
            raise ValueError("Duplicated gallery section remains: " + ident)
    if updated.count('id="' + NEW_ID + '"') != 1:
        raise ValueError("Exactly one gallery preview is required")
    for ident in PRESERVE_IDS:
        token = 'id="' + ident + '"'
        if source.count(token) != 1 or updated.count(token) != 1:
            raise ValueError("Protected homepage section changed: " + ident)
    return updated, removed


def target() -> Path:
    if APP.is_symlink() or not (APP / "manage.py").is_file():
        raise ValueError("Independent personal Django app identity mismatch")
    path = APP / REL
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise ValueError("Unsafe home template path")
    return path


def django_preflight(after: str) -> None:
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.template import engines
    engines["django"].engine.from_string(after)
    from django.test import Client
    client = Client(HTTP_HOST="mojplaywin.com")
    h = client.get("/mojtaba.roozegar/", secure=True)
    g = client.get("/mojtaba.roozegar/gallery/", secure=True)
    if h.status_code != 200 or g.status_code != 200:
        raise ValueError("Home or complete Gallery not healthy")
    assert_gallery_retains_images(
        h.content.decode("utf8", "replace"),
        g.content.decode("utf8", "replace"),
    )


def atomic_replace(path: Path, data: bytes) -> None:
    fd, temp = tempfile.mkstemp(prefix=".mojtaba-gallery-consolidation-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            os.fchmod(out.fileno(), stat.S_IMODE(path.stat().st_mode))
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def backup_dir(run_id: str) -> Path:
    if not re.fullmatch(r"[0-9]{6,24}", run_id):
        raise ValueError("Invalid run id")
    return BACKUP_ROOT / run_id


def install(run_id: str) -> None:
    path = target()
    before = path.read_bytes()
    after, removed = plan(before.decode("utf8"))
    django_preflight(after)
    new_data = after.encode("utf8")
    folder = backup_dir(run_id)
    if folder.exists() or folder.is_symlink():
        raise ValueError("Backup path collision")
    folder.mkdir(parents=True, mode=0o700)
    original = folder / "home.before"
    with original.open("xb") as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(before)
        out.flush()
        os.fsync(out.fileno())
    manifest = {
        "target": str(path),
        "before_sha256": digest(before),
        "after_sha256": digest(new_data),
        "before_bytes": len(before),
        "after_bytes": len(new_data),
        "removed_section_bytes": removed,
        "section_ids": [GALLERY_ID, PORTRAITS_ID],
    }
    details = folder / "manifest.json"
    details.write_text(json.dumps(manifest, sort_keys=True), encoding="utf8")
    details.chmod(0o600)
    if original.read_bytes() != before or digest(path.read_bytes()) != digest(before):
        raise ValueError("Backup verification or concurrent change failure")
    atomic_replace(path, new_data)
    if digest(path.read_bytes()) != digest(new_data):
        raise ValueError("Post-write hash mismatch")
    print("MOJTABA_GALLERY_INSTALLED=YES", flush=True)
    print("MOJTABA_GALLERY_REMOVED_BYTES=" + str(removed), flush=True)
    print("MOJTABA_GALLERY_BACKUP=" + str(folder), flush=True)


def rollback(run_id: str) -> None:
    path = target()
    folder = backup_dir(run_id)
    if folder.is_symlink() or not (folder / "manifest.json").is_file():
        raise ValueError("Rollback manifest missing")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf8"))
    old = (folder / "home.before").read_bytes()
    current = path.read_bytes()
    if (
        manifest["target"] != str(path)
        or digest(old) != manifest["before_sha256"]
        or digest(current) not in (manifest["before_sha256"], manifest["after_sha256"])
    ):
        raise ValueError("Rollback refused because the live source changed")
    if digest(current) == manifest["after_sha256"]:
        atomic_replace(path, old)
    if digest(path.read_bytes()) != manifest["before_sha256"]:
        raise ValueError("Rollback verification failed")
    print("MOJTABA_GALLERY_ROLLBACK=VERIFIED", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "install", "rollback"))
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.action == "rollback":
        if not args.run_id:
            parser.error("--run-id is required")
        rollback(args.run_id)
        return
    before = target().read_text(encoding="utf8")
    after, removed = plan(before)
    django_preflight(after)
    print("MOJTABA_GALLERY_PREFLIGHT=PASS", flush=True)
    print("MOJTABA_GALLERY_CANDIDATE_REMOVED_BYTES=" + str(removed), flush=True)
    if args.action == "install":
        if not args.run_id:
            parser.error("--run-id is required")
        install(args.run_id)


if __name__ == "__main__":
    main()
