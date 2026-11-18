#!/usr/bin/env python3
"""Narrow, create-only Zomorod /b2b/ release with strict verified rollback.

NOT a site deploy runner. CLI exposes only --preflight (read-only).
Actual install/rollback require a separately reviewed owner executor to import
functions; neither action runs on GitHub PR or main branch automatically.
Never changes homepage, Django, database, cron or another directory.
"""
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys

from scripts.zomorod_b2b_static_package_20261118 import (
    PAGES, REVIEWED_GIT_BLOBS, _git_blob, archive_bytes, verify_archive,
)

HOME = Path("/home/zomorod2")
DOCUMENT_ROOT = HOME / "public_html"
RELEASE_NAME = ".zomorod-b2b-release.json"
AT_FDCWD = -100
RENAME_NOREPLACE = 1


def _safe_dir(path):
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("Missing or linked directory")
    meta = path.lstat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_mode & 0o022 or meta.st_uid != os.geteuid():
        raise RuntimeError("Unsafe directory mode")
    return meta.st_dev


def _verify_identity(home, require_owner):
    if require_owner and (home != HOME or pwd.getpwuid(os.geteuid()).pw_name != "zomorod2"):
        raise PermissionError("Not the pinned cPanel owner")
    _safe_dir(home)
    _safe_dir(home / "public_html")


def _target(home):
    return home / "public_html" / "b2b"


def _no_target(home):
    dest = _target(home)
    if dest.is_symlink() or dest.exists():
        raise FileExistsError("B2B route is already owned; overwrite prohibited")
    return dest


def preflight(home=HOME, require_owner=True):
    """No site writes. Presence of a path is NOT proof of HTTP or Passenger routing."""
    _verify_identity(home, require_owner)
    target = _target(home)
    return {
        "schema": "zomorod.b2b.create_only_release.v1",
        "read_only": True,
        "create_only_target_absent": not (target.is_symlink() or target.exists()),
        "site_modified": False,
        "backup_or_http_verified": False,
        "database_accessed": False,
        "payment_created": False,
        "target_scope": "public_html/b2b",
    }


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_new(path, content, mode=0o644):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
    with os.fdopen(fd, "wb") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())


def _rename_no_replace(source, destination):
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise RuntimeError("Atomic no-replace rename unavailable; no unsafe fallback")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    code = rename(AT_FDCWD, os.fsencode(source), AT_FDCWD, os.fsencode(destination), RENAME_NOREPLACE)
    if code:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))


def _check_sha(value):
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Invalid exact PR source commit")
    return value


def install_verified(home, source_root, source_sha, run_id, *, owner_authorization, require_owner=True):
    """Potential production write; no caller in PR. Owner authorization is NOT restore proof."""
    _verify_identity(home, require_owner)
    _check_sha(source_sha)
    if not re.fullmatch(r"[0-9]{7,20}", run_id):
        raise ValueError("Invalid release run ID")
    if owner_authorization != f"owner-create-only-b2b:{source_sha}:{run_id}":
        raise PermissionError("Missing explicit release-specific owner authorization")
    dest = _no_target(home)
    source_data = archive_bytes(source_root, source_sha)
    proof = verify_archive(source_data, source_sha)
    if _safe_dir(home) != _safe_dir(home / "public_html"):
        raise RuntimeError("Different filesystems; no atomic release possible")
    stage = home / (".zomorod-b2b-stage-" + run_id)
    if stage.exists() or stage.is_symlink():
        raise FileExistsError("Release ID already used")
    stage.mkdir(mode=0o700)
    (stage / "privacy").mkdir(mode=0o755)
    for member, relative in sorted(PAGES.items()):
        target = stage / member.removeprefix("b2b/")
        data = (source_root / relative).read_bytes()
        if len(data) != proof["files"][member]["size"] or hashlib.sha256(data).hexdigest() != proof["files"][member]["sha256"]:
            raise ValueError("Source bytes changed after packaging")
        _write_new(target, data)
    metadata = {
        "schema": proof["schema"], "commit": source_sha, "run": run_id,
        "files": proof["files"], "created_only": True,
    }
    _write_new(stage / RELEASE_NAME, (json.dumps(metadata,sort_keys=True)+"\n").encode())
    _fsync_dir(stage / "privacy")
    _fsync_dir(stage)
    stage.chmod(0o755)
    _no_target(home)
    _rename_no_replace(stage, dest)
    _fsync_dir(home / "public_html")
    verify_installed(home, source_sha, run_id, require_owner=require_owner)
    return {"created_only": True, "source_sha": source_sha, "run_id": run_id}


def verify_installed(home, source_sha, run_id, *, require_owner=True):
    _verify_identity(home, require_owner)
    dest = _target(home)
    _safe_dir(dest)
    _safe_dir(dest / "privacy")
    marker = dest / RELEASE_NAME
    if marker.is_symlink() or not marker.is_file():
        raise RuntimeError("No owned release marker")
    m = json.loads(marker.read_text(encoding="utf-8"))
    if m.get("commit") != _check_sha(source_sha) or m.get("run") != run_id or m.get("created_only") is not True:
        raise RuntimeError("Wrong release ownership")
    if {p.name for p in dest.iterdir()} != {"index.html","privacy",RELEASE_NAME}:
        raise RuntimeError("Unexpected public B2B file")
    if {p.name for p in (dest/"privacy").iterdir()} != {"index.html"}:
        raise RuntimeError("Unexpected privacy file")
    for member in sorted(PAGES):
        p = dest / member.removeprefix("b2b/")
        if p.is_symlink() or not p.is_file():
            raise RuntimeError("Missing or linked installed file")
        raw = p.read_bytes()
        if _git_blob(raw) != REVIEWED_GIT_BLOBS[member]:
            raise RuntimeError("Installed bytes differ from independently reviewed source")
        record = m["files"][member]
        if len(raw) != record["size"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise RuntimeError("Installed asset modified")
    return True


def rollback_verified(home, source_sha, run_id, *, owner_authorization, require_owner=True):
    """Remove ONLY these three created files and created directories, if byte-identical."""
    if owner_authorization != f"owner-rollback-b2b:{source_sha}:{run_id}":
        raise PermissionError("Missing separate rollback authorization")
    verify_installed(home, source_sha, run_id, require_owner=require_owner)
    dest = _target(home)
    (dest / "privacy" / "index.html").unlink()
    (dest / "privacy").rmdir()
    (dest / "index.html").unlink()
    (dest / RELEASE_NAME).unlink()
    dest.rmdir()
    _fsync_dir(home / "public_html")
    return {"rolled_back_only_owned_created_files": True}


if __name__ == "__main__":
    if sys.argv[1:] != ["--preflight"]:
        raise SystemExit("Only --preflight is permitted from CLI; NO SITE DEPLOY via this entrypoint.")
    print("ZOMOROD_B2B_CREATE_ONLY_PREFLIGHT="+json.dumps(preflight(),sort_keys=True))
