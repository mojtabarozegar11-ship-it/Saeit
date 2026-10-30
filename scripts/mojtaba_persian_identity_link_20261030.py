#!/usr/bin/env python3
"""Guarded visible Persian identity link for Mojtaba's personal homepage.

Only the existing independent personal homepage is changed. No redirects,
old-source removal, generated claims or changes to other site pages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
REL = "templates/personal_site/core/home.html"
BACKUP_ROOT = Path("/home/zomorod2/.backups/mojtaba-persian-link-20261030")
PERSIAN_URL = "https://zomorodmelal.ir/authors/mojtaba-rozegar/"
MARKER = 'id="mojtaba-current-persian-profile"'
HERO = re.compile(r'<p\s+class="hero-intro"[^>]*>.*?</p>', re.S)
PARAGRAPH = (
    '\n<p id="mojtaba-current-persian-profile" lang="fa" dir="rtl">'
    'نسخه فارسی و به‌روز معرفی مجتبی روزگار: '
    '<a href="https://zomorodmelal.ir/authors/mojtaba-rozegar/">'
    'زندگی‌نامه رسمی مجتبی روزگار</a>. '
    'اطلاعات کنونی درباره اقامت در ونکوور کانادا، سوابق علمی و فعالیت‌های حرفه‌ای.'
    '</p>\n'
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transform(source: str) -> str:
    if MARKER in source:
        raise ValueError("Persian homepage link already exists; no duplicate")
    matches = list(HERO.finditer(source))
    if len(matches) != 1:
        raise ValueError("Expected exactly one original hero-intro")
    hero = matches[0].group()
    if "Mojtaba Roozegar" not in hero or "مجتبی روزگار" not in hero:
        raise ValueError("Existing bilingual identity is missing")
    if "Vancouver, Canada" not in hero:
        raise ValueError("Current residence in original introduction changed")
    if source.count('id="hero-title"') != 1:
        raise ValueError("Existing personal H1 missing or duplicated")
    result = source[:matches[0].end()] + PARAGRAPH + source[matches[0].end():]
    if result.count(PERSIAN_URL) != source.count(PERSIAN_URL) + 1:
        raise ValueError("Unexpected Persian profile URL count")
    if result.count(MARKER) != 1:
        raise ValueError("Duplicate identity marker")
    return result


def target() -> Path:
    if APP.is_symlink() or not (APP / "manage.py").is_file():
        raise ValueError("Independent personal app not found")
    path = APP / REL
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise ValueError("Unsafe homepage target")
    return path


def candidate() -> tuple[Path, bytes, bytes]:
    path = target()
    before = path.read_bytes()
    after = transform(before.decode("utf-8")).encode("utf-8")
    if before == after:
        raise ValueError("No update produced")
    return path, before, after


def preflight(after: bytes) -> None:
    sys.path.insert(0, str(APP))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.template import engines
    engines["django"].engine.from_string(after.decode("utf-8"))
    from django.test import Client
    client = Client(HTTP_HOST="mojplaywin.com")
    for route in ("", "about/", "resume/", "blog/"):
        if client.get("/mojtaba.roozegar/" + route, secure=True).status_code != 200:
            raise ValueError("Personal baseline route failure: " + route)


def atomic_write(path: Path, data: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".mojtaba-fa-identity-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), stat.S_IMODE(path.stat().st_mode))
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def backup_path(run_id: str) -> Path:
    if not re.fullmatch(r"[0-9]{6,24}", run_id):
        raise ValueError("Invalid workflow run ID")
    return BACKUP_ROOT / run_id


def install(run_id: str) -> None:
    path, before, after = candidate()
    preflight(after)
    folder = backup_path(run_id)
    if folder.exists() or folder.is_symlink():
        raise ValueError("Backup location already exists")
    folder.mkdir(parents=True, mode=0o700)
    saved = folder / "home.before"
    with saved.open("xb") as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(before)
        output.flush()
        os.fsync(output.fileno())
    manifest = {"target": str(path), "before": digest(before), "after": digest(after)}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (folder / "manifest.json").chmod(0o600)
    if saved.read_bytes() != before or digest(path.read_bytes()) != digest(before):
        raise ValueError("Backup verification or concurrent edit failure")
    atomic_write(path, after)
    if digest(path.read_bytes()) != digest(after):
        raise ValueError("Post-write hash verification failed")
    print("PERSIAN_IDENTITY_LINK_INSTALLED=YES", flush=True)
    print("PERSIAN_IDENTITY_BACKUP=" + str(folder), flush=True)


def rollback(run_id: str) -> None:
    path = target()
    folder = backup_path(run_id)
    if folder.is_symlink() or not (folder / "manifest.json").is_file():
        raise ValueError("No valid backup available")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    before = (folder / "home.before").read_bytes()
    current = path.read_bytes()
    if (manifest["target"] != str(path) or
            digest(before) != manifest["before"] or
            digest(current) not in (manifest["before"], manifest["after"])):
        raise ValueError("Concurrent change; rollback refused")
    if digest(current) == manifest["after"]:
        atomic_write(path, before)
    if digest(path.read_bytes()) != manifest["before"]:
        raise ValueError("Rollback hash mismatch")
    print("PERSIAN_IDENTITY_ROLLBACK=VERIFIED", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "install", "rollback"))
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.action == "rollback":
        if not args.run_id:
            parser.error("--run-id required")
        rollback(args.run_id)
    elif args.action == "install":
        if not args.run_id:
            parser.error("--run-id required")
        install(args.run_id)
    else:
        _, before, after = candidate()
        preflight(after)
        print("PERSIAN_IDENTITY_PREFLIGHT=PASS", flush=True)
        print("PERSONAL_HOME_DELTA_BYTES=" + str(len(after)-len(before)), flush=True)


if __name__ == "__main__":
    main()
