#!/usr/bin/env python3
"""One-route Zomorod Persian author restoration, with exact-byte rollback.

Called only on the verified cPanel account by the guarded GitHub workflow.
Never modifies the site homepage, Django app, or any unrelated redirect.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


HOME = Path("/home/zomorod2")
WEB = HOME / "public_html"
HTACCESS = WEB / ".htaccess"
TARGET = WEB / "authors/mojtaba-rozegar/index.html"
PHOTO = WEB / "static/site/zomorod-about/ceo-mojtaba-rozegar.webp"
STAGE_ROOT = HOME / ".private-zm-author-route"
REDIRECT = (
    b"RedirectMatch 301 ^/authors/mojtaba-rozegar/?$ "
    b"https://zomorodmelal.ir/en/authors/mojtaba-rozegar/"
)
OLD_SOURCE_SHA256 = (
    "6fc1f571f9bb27bf314b3d6804d39f029fcaca228f724e40652e13e705fbbd10"
)
PASSENGER_ANCHOR = b'PassengerAppRoot "/home/zomorod2/Saeit"'
PROFILE_MARKER = b'id="profile-name"'


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def without_exact_redirect(blob: bytes) -> bytes:
    """Remove one verified mod_alias rule, keeping every other byte."""
    lines = blob.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.rstrip(b"\r\n") == REDIRECT]
    if len(matches) != 1:
        raise ValueError("EXPECTED_ONE_EXISTING_AUTHOR_REDIRECT")
    # The original release prepended this rule. Require identical placement.
    if matches[0] != 0:
        raise ValueError("AUTHOR_REDIRECT_MOVED_FROM_ORIGINAL_POSITION")
    return b"".join(lines[:matches[0]] + lines[matches[0] + 1:])


def safe_paths(run: str) -> Path:
    if not re.fullmatch(r"[0-9]{6,24}", run):
        raise ValueError("INVALID_RUN_ID")
    if Path.home() != HOME:
        raise ValueError("CPANEL_ACCOUNT_MISMATCH")
    stage = STAGE_ROOT / run
    for path in (HOME, WEB, HTACCESS, TARGET.parent, TARGET, PHOTO, STAGE_ROOT, stage):
        if path.is_symlink():
            raise ValueError("SYMLINK_BLOCKED:" + str(path))
    if not WEB.is_dir() or not HTACCESS.is_file() or not PHOTO.is_file():
        raise ValueError("SITE_OR_REAL_PORTRAIT_MISSING")
    if not stage.is_dir():
        raise ValueError("STAGING_DIRECTORY_MISSING")
    return stage


def atomic_write(path: Path, blob: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".author-atomic-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def install(run: str, want: str) -> None:
    stage = safe_paths(run)
    if not re.fullmatch(r"[0-9a-f]{64}", want):
        raise ValueError("INVALID_EXPECTED_SHA")
    candidate = stage / "source.html"
    manifest = stage / "profile-route-manifest.json"
    if not candidate.is_file() or candidate.is_symlink() or manifest.exists():
        raise ValueError("SOURCE_OR_MANIFEST_CONFLICT")
    new_page = candidate.read_bytes()
    if digest(new_page) != want or PROFILE_MARKER not in new_page:
        raise ValueError("CANDIDATE_HASH_OR_IDENTITY_MISMATCH")
    if not new_page.strip().endswith(b"</html>"):
        raise ValueError("CANDIDATE_INCOMPLETE")

    original_ht = HTACCESS.read_bytes()
    if PASSENGER_ANCHOR not in original_ht:
        raise ValueError("HOST_APP_MAPPING_DRIFT")
    new_ht = without_exact_redirect(original_ht)
    existing_page = TARGET.read_bytes() if TARGET.is_file() else None
    if TARGET.exists() and existing_page is None:
        raise ValueError("AUTHOR_DEST_NOT_A_REGULAR_FILE")
    if existing_page is not None and digest(existing_page) not in (want, OLD_SOURCE_SHA256):
        raise ValueError("AUTHOR_DEST_UNKNOWN_CONTENT")
    if digest(HTACCESS.read_bytes()) != digest(original_ht):
        raise ValueError("CONCURRENT_HTACCESS_CHANGE")

    atomic_write(stage / "htaccess.before", original_ht, 0o600)
    if existing_page is not None:
        atomic_write(stage / "profile.before", existing_page, 0o600)
    record = {
        "run": run, "had_page": existing_page is not None,
        "ht_before": digest(original_ht), "ht_after": digest(new_ht),
        "page_before": digest(existing_page) if existing_page is not None else None,
        "page_after": want,
    }
    atomic_write(
        manifest, json.dumps(record, sort_keys=True).encode("ascii"), 0o600
    )
    try:
        if (existing_page is None or digest(existing_page) != want):
            atomic_write(TARGET, new_page, 0o644)
        if digest(TARGET.read_bytes()) != want:
            raise ValueError("PROFILE_WRITE_FAILED")
        if digest(HTACCESS.read_bytes()) != digest(original_ht):
            raise ValueError("CONCURRENT_HTACCESS_CHANGE_BEFORE_COMMIT")
        atomic_write(HTACCESS, new_ht, HTACCESS.stat().st_mode & 0o777)
        if digest(HTACCESS.read_bytes()) != digest(new_ht):
            raise ValueError("REDIRECT_REMOVAL_FAILED")
        print("ZM_PERSIAN_AUTHOR_CONTENT_AND_REDIRECT_FIXED=PASS")
        print("ZM_PERSIAN_AUTHOR_ROLLBACK_MANIFEST=" + str(manifest))
    except Exception:
        rollback(run)
        raise


def rollback(run: str) -> None:
    stage = safe_paths(run)
    manifest = stage / "profile-route-manifest.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise ValueError("ROLLBACK_MANIFEST_MISSING")
    record = json.loads(manifest.read_text(encoding="ascii"))
    if record["run"] != run:
        raise ValueError("ROLLBACK_RUN_MISMATCH")
    saved_ht = (stage / "htaccess.before").read_bytes()
    if digest(saved_ht) != record["ht_before"]:
        raise ValueError("ROLLBACK_BACKUP_MISMATCH")
    current_ht = HTACCESS.read_bytes()
    if digest(current_ht) not in (record["ht_before"], record["ht_after"]):
        raise ValueError("ROLLBACK_CONCURRENT_HTACCESS_CHANGE")
    if TARGET.is_symlink():
        raise ValueError("ROLLBACK_PROFILE_SYMLINK")
    current_page = TARGET.read_bytes() if TARGET.is_file() else None
    if current_page is None and record["had_page"]:
        raise ValueError("ROLLBACK_ORIGINAL_PROFILE_MISSING")
    if current_page is not None and digest(current_page) not in (
        record["page_after"], record["page_before"]
    ):
        raise ValueError("ROLLBACK_CONCURRENT_PROFILE_CHANGE")
    if record["had_page"]:
        saved_page = (stage / "profile.before").read_bytes()
        if digest(saved_page) != record["page_before"]:
            raise ValueError("ROLLBACK_PROFILE_BACKUP_MISMATCH")
        if digest(current_page) != record["page_before"]:
            atomic_write(TARGET, saved_page, 0o644)
    elif current_page is not None and digest(current_page) == record["page_after"]:
        TARGET.unlink()
    if digest(current_ht) != record["ht_before"]:
        atomic_write(HTACCESS, saved_ht, HTACCESS.stat().st_mode & 0o777)
    if HTACCESS.read_bytes() != saved_ht:
        raise ValueError("ROLLBACK_HTACCESS_VERIFY_FAILED")
    print("ZM_PERSIAN_AUTHOR_SCOPE_ROLLBACK=PASS")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "install":
        install(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: release.py install RUN_ID SHA | rollback RUN_ID")
