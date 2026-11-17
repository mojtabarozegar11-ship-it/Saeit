#!/usr/bin/env python3
"""Additive MOJ-PROP-01 informational sidecar, never replaces owner site pages.

This installer is scoped to /moj-prop/plan1/index.html ONLY. It cannot touch
/moj-prop/index.html, /moj-prop/contact/, customer records or databases.
No checkout, broker or capital funding is enabled. A separate owner-only
workflow enforces independently reviewed restore evidence before install.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

HOME = Path("/home/zomorod2")
DOCROOT = HOME / "mojplaywin.com"
PARENT = DOCROOT / "moj-prop"
SIDE = "plan1"
SOURCE_REL = Path("templates/moj-prop-plan1-sidecar/index.html")
SOURCE_GIT_BLOB = "a16e69b6a18350e6919317dba8dbd8b50f49b90a"
MAX_HTML_BYTES = 131072
MANIFEST_SCHEMA = "mojprop.plan1.additive.sidecar.v1"
REQUIRED_ENV = (
    "MOJPROP_SIDECAR_RELEASE_APPROVED",
    "MOJPROP_FULL_DB_APP_MEDIA_RESTORE_VERIFIED",
    "MOJPROP_PASSENGER_TENANT_ISOLATION_VERIFIED",
    "MOJPROP_SIDECAR_SOURCE_REVIEWED",
)


def run_id(value: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[0-9]{1,20}", value):
        raise ValueError("Untrusted run identity")
    return value


def safe_directory(path: Path, uid: int | None = None) -> bool:
    owner = os.geteuid() if uid is None else uid
    try:
        s = path.lstat()
        return (stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode)
                and s.st_uid == owner and s.st_mode & 0o022 == 0)
    except OSError:
        return False


def safe_regular(path: Path, owner: int, *, size: int = MAX_HTML_BYTES) -> bool:
    try:
        s = path.lstat()
        return (stat.S_ISREG(s.st_mode) and not stat.S_ISLNK(s.st_mode)
                and s.st_uid == owner and s.st_nlink == 1
                and s.st_mode & 0o022 == 0 and 0 < s.st_size <= size)
    except OSError:
        return False


def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def staged_source(identity: str, home: Path = HOME) -> bytes:
    directory = home / (".mojprop-plan1-sidecar-stage-" + run_id(identity))
    if not safe_directory(directory):
        raise RuntimeError("Unsafe private staged root")
    for component in ("templates", "moj-prop-plan1-sidecar"):
        directory = directory / component
        if not safe_directory(directory):
            raise RuntimeError("Unsafe staged file ancestor")
    file = directory / "index.html"
    if not safe_regular(file, os.geteuid()):
        raise RuntimeError("Untrusted staged source file")
    # Read with O_NOFOLLOW. The immutable reviewed Git blob binds exact bytes.
    fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        initial = os.fstat(fd)
        with os.fdopen(fd, "rb", closefd=False) as f:
            data = f.read(MAX_HTML_BYTES + 1)
        later = os.fstat(fd)
        if ((initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns)
                != (later.st_dev, later.st_ino, later.st_size, later.st_mtime_ns)):
            raise RuntimeError("Staged source changed during read")
    finally:
        os.close(fd)
    if git_blob_id(data) != SOURCE_GIT_BLOB:
        raise RuntimeError("Source is not reviewed immutable Plan1 sidecar")
    if not data.lstrip().startswith(b"<!doctype html>"):
        raise RuntimeError("Unrecognized source document")
    return data


def verify_parent(parent: Path = PARENT) -> int:
    owner = os.geteuid()
    for path in (parent.parent.parent, parent.parent, parent):
        if not safe_directory(path, owner):
            raise RuntimeError("Untrusted current website parent")
    fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    observed = os.fstat(fd)
    expected = parent.lstat()
    if (observed.st_dev, observed.st_ino) != (expected.st_dev, expected.st_ino):
        os.close(fd)
        raise RuntimeError("Site root changed during open")
    return fd


def status_at_parent(parent_fd: int, data: bytes) -> str:
    """Never follow a symlink, accept owner files, or authorize an overwrite."""
    try:
        entry = os.stat(SIDE, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return "absent"
    if (not stat.S_ISDIR(entry.st_mode) or entry.st_uid != os.geteuid()
            or entry.st_mode & 0o022):
        return "blocked_existing_directory"
    try:
        fd = os.open(SIDE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                     dir_fd=parent_fd)
    except OSError:
        return "blocked_existing_directory"
    try:
        if (os.fstat(fd).st_ino, os.fstat(fd).st_dev) != (entry.st_ino, entry.st_dev):
            return "blocked_existing_directory"
        if os.listdir(fd) != ["index.html"]:
            return "blocked_existing_directory"
        item = os.stat("index.html", dir_fd=fd, follow_symlinks=False)
        if (not stat.S_ISREG(item.st_mode) or item.st_uid != os.geteuid()
                or item.st_nlink != 1 or item.st_mode & 0o022
                or item.st_size != len(data)):
            return "blocked_existing_source"
        item_fd = os.open("index.html", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        try:
            content = os.read(item_fd, MAX_HTML_BYTES + 1)
            after = os.fstat(item_fd)
            if (item.st_dev, item.st_ino, item.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_mtime_ns):
                return "blocked_existing_source"
        finally:
            os.close(item_fd)
        if content != data:
            return "blocked_existing_source"
        return "already_identical"
    except (OSError, ValueError):
        return "blocked_existing_source"
    finally:
        os.close(fd)


def inspect(identity: str, *, home: Path = HOME, parent: Path = PARENT) -> dict:
    data = staged_source(identity, home)
    fd = verify_parent(parent)
    try:
        state = status_at_parent(fd, data)
    finally:
        os.close(fd)
    return {
        "schema": MANIFEST_SCHEMA,
        "source_exact_git_blob_verified": True,
        "existing_owner_home_contact_preserved": True,
        "destination_status": state,
        "can_add_without_overwriting": state in ("absent", "already_identical"),
        "read_only": True,
        "payment_or_customer_data_enabled": False,
        "full_restore_independently_observed_by_this_code": False,
    }


def install(identity: str, *, home: Path = HOME, parent: Path = PARENT,
            authorization: dict[str, str] | None = None) -> dict:
    """Manual owner-release-only. New path via O_EXCL+link, never os.replace."""
    flags = os.environ if authorization is None else authorization
    if any(flags.get(key) != "true" for key in REQUIRED_ENV):
        raise RuntimeError("Independent restore and owner release approvals absent")
    data = staged_source(identity, home)
    fd = verify_parent(parent)
    created = False
    try:
        state = status_at_parent(fd, data)
        if state == "already_identical":
            return {"schema": MANIFEST_SCHEMA, "status": "already_identical",
                    "existing_owner_home_contact_preserved": True,
                    "customer_post_or_trx_payment": False}
        if state != "absent":
            raise RuntimeError("Existing owner Plan1 sidecar cannot be overwritten")
        # The only new path is SIDE/index.html. Never edit another page.
        os.mkdir(SIDE, mode=0o755, dir_fd=fd)
        created = True
        sfd = os.open(SIDE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                      dir_fd=fd)
        try:
            tmp = ".plan1-" + run_id(identity) + ".partial"
            tfd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=sfd)
            try:
                with os.fdopen(tfd, "wb", closefd=True) as target:
                    target.write(data)
                    target.flush()
                    os.fsync(target.fileno())
                # Link requires destination not to exist; NO REPLACE of owner bytes.
                os.link(tmp, "index.html", src_dir_fd=sfd, dst_dir_fd=sfd,
                        follow_symlinks=False)
                os.chmod("index.html", 0o644, dir_fd=sfd)
                os.unlink(tmp, dir_fd=sfd)  # only our new private-mode temp file
                if status_at_parent(fd, data) != "already_identical":
                    raise RuntimeError("New page failed exact readback verification")
            except Exception:
                # Never delete/modify any existing owner site file; a failed
                # new-route operation requires a deliberate owner-safe recovery.
                raise
        finally:
            os.close(sfd)
        return {"schema": MANIFEST_SCHEMA, "status": "created_new_path_only",
                "existing_owner_home_contact_preserved": True,
                "customer_post_or_trx_payment": False}
    finally:
        os.close(fd)


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("preflight", "install"):
        raise SystemExit("Only preflight or explicit manual install with run ID allowed")
    mode, identity = sys.argv[1:]
    output = inspect(identity) if mode == "preflight" else install(identity)
    print("MOJPROP_PLAN1_SIDECAR=" + json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
