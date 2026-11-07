#!/usr/bin/env python3
"""Fail-closed, single-asset repair of a stale MojPlayWin staging manifest.

Only the absent source JPEG, its two collected copies and staticfiles.json may
change. The backup journal is retained for an independent rollback. No DB,
email, payment, deployment sync or Passenger restart is performed.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
import types
from pathlib import Path

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
PUBLIC = HOME / "mojplaywin.com"
SOURCE = APP / "core/static/site/mojplaywin-header-emblem.jpg"
COLLECTED = APP / "staticfiles/site/mojplaywin-header-emblem.jpg"
MANIFEST = APP / "staticfiles/staticfiles.json"
BACKUP_ROOT = HOME / ".backups/mpw-staging-header-manifest-20261107"
ASSET_NAME = "site/mojplaywin-header-emblem.jpg"
EXPECTED_GIT_BLOB = "bfd6977e82b6623b67edbbbc00a60e25cd56f810"
EXPECTED_STORE_PREFIX = "337bd51a2390578d"
EXPECTED_STORE_LENGTH = 15919
MIN_FREE_BYTES = 512 * 1024 * 1024


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob_id(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def image_hashed_name(raw: bytes) -> str:
    return "site/mojplaywin-header-emblem." + hashlib.md5(raw).hexdigest()[:12] + ".jpg"


def update_manifest(raw: bytes, image: bytes) -> bytes:
    """Replicate Django 5.2's manifest hash while retaining *all* old paths."""
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("version") not in ("1.0", "1.1"):
        raise RuntimeError("MANIFEST_VERSION_REFUSED")
    paths = data.get("paths")
    if not isinstance(paths, dict) or ASSET_NAME in paths:
        raise RuntimeError("MANIFEST_ENTRY_DRIFT")
    css = paths.get("site/mojplaywin.css")
    if not isinstance(css, str) or not css.startswith("site/mojplaywin.") or not css.endswith(".css"):
        raise RuntimeError("CSS_MANIFEST_BASELINE_DRIFT")
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in paths.items()):
        raise RuntimeError("MANIFEST_TYPES_REFUSED")
    newpaths = dict(paths)
    newpaths[ASSET_NAME] = image_hashed_name(image)
    data["paths"] = newpaths
    # Django ManifestFilesMixin.save_manifest() uses file_hash() on the JSON
    # encoding of the sorted (original, hashed) pairs, truncating MD5 to 12.
    data["hash"] = hashlib.md5(json.dumps(sorted(newpaths.items())).encode()).hexdigest()[:12]
    return json.dumps(data, separators=(",", ":")).encode("utf-8")


def checked_file(path: Path, *, max_bytes: int | None = None) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("UNSAFE_EXPECTED_FILE")
    if max_bytes is not None and path.stat().st_size > max_bytes:
        raise RuntimeError("FILE_TOO_LARGE")
    return path.read_bytes()


def atomic_write(path: Path, raw: bytes, *, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix=".mpw-header-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def exclusive_create(path: Path, raw: bytes) -> None:
    with path.open("xb") as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    if path.is_symlink() or path.read_bytes() != raw:
        raise RuntimeError("CREATED_FILE_READBACK_FAILED")


def safety_preflight() -> bytes:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_CPANEL_ACCOUNT")
    for path in (HOME, APP, PUBLIC, APP / "core", APP / "core/static",
                 SOURCE.parent, APP / "staticfiles", COLLECTED.parent):
        if path.is_symlink() or not path.is_dir():
            raise RuntimeError("APPLICATION_ROOT_DRIFT")
    passenger = PUBLIC / "passenger_wsgi.py"
    if "Saeit-staging" not in checked_file(passenger, max_bytes=40_000).decode("utf-8", "replace"):
        raise RuntimeError("PASSENGER_ROOT_NOT_VERIFIED")
    view = checked_file(APP / "core/mojplaywin_views.py", max_bytes=100_000)
    if len(view) != EXPECTED_STORE_LENGTH or not sha256(view).startswith(EXPECTED_STORE_PREFIX):
        raise RuntimeError("STAGING_STORE_VIEW_DRIFT")
    if (APP / "core/commerce_funnel.py").exists():
        raise RuntimeError("STAGING_OPTIONAL_MODULE_DRIFT")
    if os.statvfs(APP).f_bavail * os.statvfs(APP).f_frsize < MIN_FREE_BYTES:
        raise RuntimeError("FREE_SPACE_BELOW_SAFE_MINIMUM")
    for path in (SOURCE, COLLECTED):
        if path.exists() or path.is_symlink():
            raise RuntimeError("ASSET_ALREADY_EXISTS_REFUSED")
    if list(COLLECTED.parent.glob("mojplaywin-header-emblem.*.jpg")):
        raise RuntimeError("UNTRACKED_HASHED_ASSET_REFUSED")
    old = checked_file(MANIFEST, max_bytes=3_000_000)
    existing = json.loads(old).get("paths", {})
    css_hashed = existing.get("site/mojplaywin.css", "")
    if not isinstance(css_hashed, str) or "/" in css_hashed[5:] or ".." in css_hashed:
        raise RuntimeError("CSS_MANIFEST_PATH_UNSAFE")
    if not (APP / "staticfiles" / css_hashed).is_file():
        raise RuntimeError("CSS_MANIFEST_TARGET_MISSING")
    return old


def verify_fresh_django_render() -> None:
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    import django
    django.setup()
    from django.conf import settings
    if Path(settings.STATIC_ROOT) != APP / "staticfiles":
        raise RuntimeError("RUNTIME_STATIC_ROOT_DRIFT")
    from django.test import RequestFactory
    from django.contrib.auth.models import AnonymousUser
    from core.mojplaywin_views import store
    from unittest.mock import patch
    request = RequestFactory().get("/store/", secure=True, HTTP_HOST="mojplaywin.com")
    request.user = AnonymousUser()
    stub = types.ModuleType("core.commerce_funnel")
    stub.record_funnel_event = lambda *args, **kwargs: None
    with patch.dict(sys.modules, {"core.commerce_funnel": stub}):
        response = store(request)
    if response.status_code != 200 or len(response.content) < 2000:
        raise RuntimeError("FRESH_STAGING_RENDER_FAILED")
    for needle in (b"/store/product/72/checkout/", b"/store/product/225/checkout/",
                   b"/store/product/879/"):
        if needle not in response.content:
            raise RuntimeError("STAGING_PRODUCT_CTA_MISSING")


def journal_paths(run_id: str) -> tuple[Path, Path, Path]:
    if not re.fullmatch(r"[0-9]{8,12}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    directory = BACKUP_ROOT / run_id
    return directory, directory / "original-staticfiles.json", directory / "journal.json"


def rollback_journal(run_id: str) -> None:
    directory, original_path, journal_path = journal_paths(run_id)
    for root in (HOME, APP, APP / "staticfiles", COLLECTED.parent,
                 BACKUP_ROOT.parent, BACKUP_ROOT, directory):
        if root.is_symlink() or not root.is_dir():
            raise RuntimeError("ROLLBACK_ROOT_DRIFT")
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError("BACKUP_DIRECTORY_MISSING")
    info = json.loads(checked_file(journal_path, max_bytes=5_000))
    if (not isinstance(info, dict) or
            not re.fullmatch(r"site/mojplaywin-header-emblem\.[0-9a-f]{12}\.jpg",
                             str(info.get("hashed_name", "")))):
        raise RuntimeError("BACKUP_JOURNAL_DRIFT")
    original = checked_file(original_path, max_bytes=3_000_000)
    if sha256(original) != info["original_sha256"]:
        raise RuntimeError("BACKUP_INTEGRITY_FAILED")
    current = checked_file(MANIFEST, max_bytes=3_000_000)
    if sha256(current) not in (info["original_sha256"], info["updated_sha256"]):
        raise RuntimeError("CONCURRENT_MANIFEST_CHANGE_REFUSED")
    files = (SOURCE, COLLECTED, APP / "staticfiles" / info["hashed_name"])
    for path in files:
        if path.is_symlink():
            raise RuntimeError("ROLLBACK_SYMLINK_REFUSED")
        if path.exists() and sha256(checked_file(path, max_bytes=200_000)) != info["image_sha256"]:
            raise RuntimeError("CONCURRENT_ASSET_CHANGE_REFUSED")
    if sha256(current) != info["original_sha256"]:
        atomic_write(MANIFEST, original, mode=info["manifest_mode"])
    for path in files:
        if path.exists():
            path.unlink()
    print("MPW_STAGING_HEADER_ROLLBACK=COMPLETE;DATABASE_WRITE=NO;RESTART=NO")


def apply(run_id: str, payload: str) -> None:
    if len(payload) > 100_000:
        raise RuntimeError("PAYLOAD_TOO_LARGE")
    image = base64.b64decode(payload, validate=True)
    if git_blob_id(image) != EXPECTED_GIT_BLOB:
        raise RuntimeError("SOURCE_ASSET_HASH_MISMATCH")
    old = safety_preflight()
    updated = update_manifest(old, image)
    hashed_name = image_hashed_name(image)
    hashed_path = APP / "staticfiles" / hashed_name
    if hashed_path.exists() or hashed_path.is_symlink():
        raise RuntimeError("HASHED_ASSET_ALREADY_EXISTS")
    directory, original_path, journal_path = journal_paths(run_id)
    if BACKUP_ROOT.parent.is_symlink() or BACKUP_ROOT.is_symlink():
        raise RuntimeError("BACKUP_ROOT_SYMLINK_REFUSED")
    BACKUP_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.exists() or directory.is_symlink():
        raise RuntimeError("RUN_ID_ALREADY_USED")
    directory.mkdir(mode=0o700)
    old_mode = stat.S_IMODE(MANIFEST.stat().st_mode)
    info = {
        "original_sha256": sha256(old),
        "updated_sha256": sha256(updated),
        "image_sha256": sha256(image),
        "hashed_name": hashed_name,
        "manifest_mode": old_mode,
        "status": "backup_created;rollback_available",
    }
    exclusive_create(original_path, old)
    exclusive_create(journal_path, json.dumps(info, sort_keys=True).encode())
    try:
        if checked_file(MANIFEST, max_bytes=3_000_000) != old:
            raise RuntimeError("CONCURRENT_MANIFEST_EDIT_REFUSED")
        for path in (SOURCE, COLLECTED, hashed_path):
            exclusive_create(path, image)
        atomic_write(MANIFEST, updated, mode=old_mode)
        if checked_file(MANIFEST, max_bytes=3_000_000) != updated:
            raise RuntimeError("MANIFEST_READBACK_FAILED")
        verify_fresh_django_render()
    except BaseException:
        rollback_journal(run_id)
        raise
    print("MPW_STAGING_HEADER_ASSET_MANIFEST=PASS;FRESH_DJANGO_RENDER=PASS;BACKUP=VERIFIED;RESTART=NO")


def main() -> None:
    if len(sys.argv) < 3:
        raise RuntimeError("INVALID_ARGS")
    mode, run_id = sys.argv[1:3]
    # This file is always streamed to python -B - on the pinned cPanel account.
    if mode == "apply" and len(sys.argv) == 4:
        apply(run_id, sys.argv[3])
    elif mode == "rollback" and len(sys.argv) == 3:
        if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
            raise RuntimeError("WRONG_CPANEL_ACCOUNT")
        rollback_journal(run_id)
    else:
        raise RuntimeError("INVALID_MODE")


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        print("MPW_STAGING_HEADER_REPAIR=BLOCKED;ERROR_CLASS=" + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
