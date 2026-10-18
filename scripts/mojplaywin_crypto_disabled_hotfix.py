#!/usr/bin/env python3
"""Update ONLY the existing MojPlayWin isolated PHP gateway while payments are off.

No shared Django settings, production DB or child application writes. Existing
file byte-for-byte matching is required. Keep a private, immutable backup of
both files, and use same-directory atomic replaces. Fail closed if enabled.
"""
import hashlib
import os
from pathlib import Path
import sys

DOCROOT = Path("/home/zomorod2/mojplaywin.com")
TARGET = DOCROOT / "checkout" / "crypto"
PRIVATE = Path("/home/zomorod2/.mojplaywin-crypto-payments-v1")
FILES = ("index.php", "bootstrap.php")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ensure_safe_dir(path):
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("Expected non-symlink directory is missing.")


def exclusive_write(path, contents, mode):
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())


def atomic_update(path, contents, label):
    tmp = path.with_name(".moj-crypto-hotfix-" + label)
    if tmp.exists() or tmp.is_symlink():
        raise RuntimeError("Unclean temporary file from earlier run.")
    try:
        exclusive_write(tmp, contents, 0o644)
        os.replace(tmp, path)
    finally:
        if tmp.exists() and not tmp.is_symlink():
            tmp.unlink()


def hotfix(stage, identifier):
    for d in (DOCROOT, TARGET.parent, TARGET, PRIVATE, stage):
        ensure_safe_dir(d)
    if (PRIVATE / "enabled.flag").exists() or (PRIVATE / "enabled.flag").is_symlink():
        raise RuntimeError("Payments appear enabled; no live code edits permitted.")
    existing = {}
    desired = {}
    for name in FILES:
        old_file = stage / ("old_" + name)
        new_file = stage / name
        actual_file = TARGET / name
        if any(p.is_symlink() or not p.is_file() for p in (old_file, new_file, actual_file)):
            raise RuntimeError("Unexpected file or symlink.")
        old, new, live = old_file.read_bytes(), new_file.read_bytes(), actual_file.read_bytes()
        if not (old.startswith(b"<?php") and new.startswith(b"<?php") and len(new) < 150_000):
            raise RuntimeError("Invalid PHP source.")
        if live != old and live != new:
            raise RuntimeError("Live PHP does not match either reviewed source; refusing changes.")
        existing[name] = old
        desired[name] = new
    backup = PRIVATE / ("hotfix-backup-" + identifier)
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Backup destination already exists; refusing overwrite.")
    backup.mkdir(mode=0o700)
    try:
        for name in FILES:
            exclusive_write(backup / name, existing[name], 0o600)
    except Exception:
        for p in backup.iterdir():
            p.unlink()
        backup.rmdir()
        raise
    updated = []
    try:
        for name in FILES:
            dest = TARGET / name
            if dest.read_bytes() != desired[name]:
                atomic_update(dest, desired[name], identifier + "-" + name)
                updated.append(name)
        for name in FILES:
            if (TARGET / name).read_bytes() != desired[name]:
                raise RuntimeError("Gateway source verification failed.")
    except BaseException:
        for name in reversed(updated):
            atomic_update(TARGET / name, existing[name], identifier + "-rollback-" + name)
        raise
    print("MOJPLAYWIN_GATEWAY_DISABLED_HOTFIX_VERIFIED=true")
    print("MOJPLAYWIN_GATEWAY_FILES_UPDATED=" + str(len(updated)))
    print("MOJPLAYWIN_GATEWAY_BACKUP_CREATED=true")
    print("MOJPLAYWIN_CHILD_SITES_OR_DJANGO_CHANGED=false")
    print("MOJPLAYWIN_PAYMENTS_ENABLED=false")


if __name__ == "__main__":
    if len(sys.argv) != 3 or not sys.argv[2].isdigit() or not (1 <= len(sys.argv[2]) <= 20):
        raise SystemExit("usage: hotfix.py /private/stage run-id")
    hotfix(Path(sys.argv[1]), sys.argv[2])
