#!/usr/bin/env python3
"""Guarded consolidation of the independent Mojtaba personal homepage.

Only its home.html is writable. Ten *identical* sections retained on the
dedicated Journal page are removed from Home; original posts and media remain.
The already-reviewed two-portrait/one-introduction patch is reused.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
REL = "templates/personal_site/core/home.html"
BACKUP_ROOT = Path("/home/zomorod2/.backups/mojtaba-home-consolidation")
DUPLICATE_IDS = (
    "mpw-journal-longform-index-20261016",
    "mpw-journal-advanced-index-20261016",
    "mpw-website-ten-index-20261016",
    "mpw-vancouver-collab-photo-ten-20261016",
    "mpw-vancouver-enterprise-20-index-20261016",
    "mpw-vancouver-enterprise-20-series2-index-20261016",
    "mpw-mojtaba-twenty-image-essays-20261016",
    "mpw-photoessay-reading-guides-20261016",
    "mpw-enterprise-collaboration-brief-20261016",
    "mpw-five-smart-web-portraits-20261016",
)
PRESERVE_IDS = (
    "mpw-primary-personal-profile-20261016",
    "hero-title",
    "mpw-social-central-hub-20261026",
    "mpw-complete-standard-20261019-toc",
    "owner-original-gallery-20261015",
)
SECTION_TAG = re.compile(r"</?section\b[^>]*>", re.I)
HERO_SCRIPT = Path(__file__).with_name("mojtaba_home_two_portraits_one_intro_20261020.py")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def section_span(document: str, ident: str) -> tuple[int, int]:
    opening = re.compile(
        r'<section\b[^>]*\bid=["\']' + re.escape(ident) + r'["\'][^>]*>',
        re.I,
    )
    matches = list(opening.finditer(document))
    if len(matches) != 1:
        raise ValueError("Expected exactly one section: " + ident)
    match = matches[0]
    depth = 1
    for token in SECTION_TAG.finditer(document, match.end()):
        depth += -1 if token.group().startswith("</") else 1
        if depth == 0:
            return match.start(), token.end()
    raise ValueError("Unclosed section: " + ident)


def section_text(document: str, ident: str) -> str:
    start, end = section_span(document, ident)
    return document[start:end]


def assert_duplicate_equivalence(home_html: str, journal_html: str) -> None:
    for ident in DUPLICATE_IDS:
        if section_text(home_html, ident) != section_text(journal_html, ident):
            raise ValueError("Journal differs from homepage; preserve both: " + ident)


def remove_duplicate_sections(source: str) -> tuple[str, int]:
    bounds = sorted((section_span(source, ident) + (ident,) for ident in DUPLICATE_IDS))
    for left, right in zip(bounds, bounds[1:]):
        if left[1] > right[0]:
            raise ValueError("Nested or overlapping duplicate sections: " + left[2] + "/" + right[2])
    removed = sum(end - start for start, end, _ in bounds)
    if removed < 75000:
        raise ValueError("Current template size differs from audited duplicate sections")
    updated = source
    for start, end, _ in reversed(bounds):
        updated = updated[:start] + updated[end:]
    for ident in DUPLICATE_IDS:
        if ident in updated:
            raise ValueError("Duplicate section remains: " + ident)
    for ident in PRESERVE_IDS:
        if source.count('id="' + ident + '"') != 1 or updated.count('id="' + ident + '"') != 1:
            raise ValueError("Protected section changed: " + ident)
    if updated.count("{%") != source.count("{%") or updated.count("{{") != source.count("{{"):
        raise ValueError("Django template syntax changed by section deletion")
    return updated, removed


def hero_patch(source: str) -> str:
    if not HERO_SCRIPT.is_file() or HERO_SCRIPT.is_symlink():
        raise ValueError("Reviewed one-introduction transformation not staged")
    spec = importlib.util.spec_from_file_location("mojtaba_one_intro", HERO_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    if module.MARK in source:
        if "PROFESSIONAL PROFILE" in source:
            raise ValueError("Partial existing hero consolidation")
        return source
    return module.patch(source)


def plan(source: str) -> tuple[str, int]:
    new, removed = remove_duplicate_sections(source)
    new = hero_patch(new)
    if len(new) >= len(source) - 60000:
        raise ValueError("Homepage did not shrink sufficiently")
    if '<h1 id="hero-title"' not in new or new.count('id="hero-title"') != 1:
        raise ValueError("One accessible H1 must remain")
    if "PROFESSIONAL PROFILE" in new:
        raise ValueError("Duplicate introductory copy remains")
    return new, removed


def target() -> Path:
    if APP.is_symlink() or not (APP / "manage.py").is_file():
        raise ValueError("Independent personal Django app identity mismatch")
    path = APP / REL
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise ValueError("Unsafe personal homepage path")
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
    j = client.get("/mojtaba.roozegar/blog/", secure=True)
    if h.status_code != 200 or j.status_code != 200:
        raise ValueError("Personal homepage or Journal not healthy")
    assert_duplicate_equivalence(
        h.content.decode("utf-8", "replace"),
        j.content.decode("utf-8", "replace"),
    )


def atomic_replace(path: Path, data: bytes) -> None:
    fd, staged = tempfile.mkstemp(prefix=".mojtaba-home-consolidate-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), stat.S_IMODE(path.stat().st_mode))
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staged, path)
    finally:
        if os.path.lexists(staged):
            os.unlink(staged)


def backup_dir(run_id: str) -> Path:
    if not re.fullmatch(r"[0-9]{6,24}", run_id):
        raise ValueError("Invalid workflow run identifier")
    return BACKUP_ROOT / run_id


def install(run_id: str) -> None:
    path = target()
    before = path.read_bytes()
    after, removed = plan(before.decode("utf-8"))
    django_preflight(after)
    new_data = after.encode("utf-8")
    backup = backup_dir(run_id)
    if backup.exists() or backup.is_symlink():
        raise ValueError("Backup path collision")
    backup.mkdir(parents=True, mode=0o700)
    original = backup / "home.before"
    with original.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(before)
        handle.flush()
        os.fsync(handle.fileno())
    manifest = {
        "target": str(path),
        "before_sha256": digest(before),
        "after_sha256": digest(new_data),
        "source_bytes": len(before),
        "result_bytes": len(new_data),
        "duplicate_template_bytes_removed": removed,
        "removed_section_ids": list(DUPLICATE_IDS),
    }
    (backup / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    (backup / "manifest.json").chmod(0o600)
    if original.read_bytes() != before or digest(path.read_bytes()) != digest(before):
        raise ValueError("Backup verification or concurrent edit failure")
    atomic_replace(path, new_data)
    if digest(path.read_bytes()) != digest(new_data):
        raise ValueError("Post-write content hash failure")
    print("MOJTABA_HOME_INSTALLED=YES", flush=True)
    print("MOJTABA_REMOVED_TEMPLATE_BYTES=" + str(removed), flush=True)
    print("MOJTABA_BACKUP=" + str(backup), flush=True)


def rollback(run_id: str) -> None:
    path = target()
    backup = backup_dir(run_id)
    if backup.is_symlink() or not (backup / "manifest.json").is_file():
        raise ValueError("Rollback backup missing")
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    old = (backup / "home.before").read_bytes()
    now = path.read_bytes()
    if (manifest["target"] != str(path) or
        digest(old) != manifest["before_sha256"] or
        digest(now) not in (manifest["before_sha256"], manifest["after_sha256"])):
        raise ValueError("Rollback refused because source changed")
    if digest(now) == manifest["after_sha256"]:
        atomic_replace(path, old)
    if digest(path.read_bytes()) != manifest["before_sha256"]:
        raise ValueError("Rollback verification failed")
    print("MOJTABA_HOME_ROLLBACK=VERIFIED", flush=True)


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
    path = target()
    before = path.read_text(encoding="utf-8")
    after, removed = plan(before)
    django_preflight(after)
    print("MOJTABA_HOME_PREFLIGHT=PASS", flush=True)
    print("MOJTABA_DUPLICATE_SECTIONS=" + str(len(DUPLICATE_IDS)), flush=True)
    print("MOJTABA_PRESERVED_JOURNAL=YES", flush=True)
    print("MOJTABA_CANDIDATE_TEMPLATE_BYTES_REMOVED=" + str(removed), flush=True)
    if args.action == "install":
        if not args.run_id:
            parser.error("--run-id is required")
        install(args.run_id)


if __name__ == "__main__":
    main()
