#!/usr/bin/env python3
"""Fail-closed public homepage file invariant for Zomorod Melal.

Only reads the public homepage document, .htaccess, and all files under
public_html/assets and public_html/static. No private source, records,
file names or asset contents are emitted in output.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import sys

PUBLIC_ROOT = Path("/home/zomorod2/public_html")
REQUIRED_FILES = (".htaccess", "index.html")
ASSET_DIRS = ("assets", "static")
MAX_FILES = 2000
MAX_TOTAL_BYTES = 512 * 1024 * 1024
BLOCK_SIZE = 1024 * 1024


class ScopeError(RuntimeError):
    pass


def compute_fingerprint(root: Path = PUBLIC_ROOT) -> tuple[str, int, int]:
    if root.is_symlink() or not root.is_dir():
        raise ScopeError("INVALID_PUBLIC_ROOT")
    if os.geteuid() == 0 and root == PUBLIC_ROOT:
        raise ScopeError("ROOT_USER_NOT_ALLOWED")
    if root == PUBLIC_ROOT and root.stat().st_uid != os.geteuid():
        raise ScopeError("UNTRUSTED_PUBLIC_ROOT_OWNER")

    paths: list[Path] = []
    for name in REQUIRED_FILES:
        p = root / name
        if p.is_symlink() or not p.is_file():
            raise ScopeError("REQUIRED_ENTRY_MISSING_OR_SYMLINK")
        paths.append(p)
    for dirname in ASSET_DIRS:
        directory = root / dirname
        if directory.is_symlink() or not directory.is_dir():
            raise ScopeError("ASSET_DIRECTORY_MISSING_OR_SYMLINK")
        for parent, dirs, filenames in os.walk(directory, followlinks=False):
            dirs.sort()
            filenames.sort()
            for name in dirs:
                candidate = Path(parent) / name
                if candidate.is_symlink():
                    raise ScopeError("ASSET_DIRECTORY_SYMLINK")
            for name in filenames:
                candidate = Path(parent) / name
                if candidate.is_symlink() or not candidate.is_file():
                    raise ScopeError("ASSET_FILE_UNSAFE")
                paths.append(candidate)
                if len(paths) > MAX_FILES:
                    raise ScopeError("ASSET_FILE_LIMIT")

    digest = hashlib.sha256()
    cumulative = 0
    for p in sorted(paths, key=lambda x: x.relative_to(root).as_posix()):
        rel = p.relative_to(root).as_posix()
        if not rel or rel.startswith("/") or ".." in p.relative_to(root).parts:
            raise ScopeError("UNSAFE_RELATIVE_PATH")
        before = p.stat()
        if not stat.S_ISREG(before.st_mode):
            raise ScopeError("NON_REGULAR_ASSET")
        if before.st_size < 0 or before.st_size > MAX_TOTAL_BYTES:
            raise ScopeError("ASSET_TOO_LARGE")
        cumulative += before.st_size
        if cumulative > MAX_TOTAL_BYTES:
            raise ScopeError("TOTAL_ASSET_BYTES_LIMIT")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(p, flags)
        with os.fdopen(fd, "rb") as source:
            actual = os.fstat(source.fileno())
            if not stat.S_ISREG(actual.st_mode) or (
                actual.st_ino != before.st_ino
                or actual.st_dev != before.st_dev
                or actual.st_size != before.st_size
            ):
                raise ScopeError("ASSET_CHANGED_DURING_SCAN")
            digest.update(rel.encode("utf-8", errors="strict") + b"\0")
            while True:
                part = source.read(BLOCK_SIZE)
                if not part:
                    break
                digest.update(part)
            after = os.fstat(source.fileno())
            if (after.st_mtime_ns != actual.st_mtime_ns
                    or after.st_size != actual.st_size
                    or after.st_ctime_ns != actual.st_ctime_ns):
                raise ScopeError("ASSET_CHANGED_DURING_READ")
            digest.update(b"\0")
    return digest.hexdigest(), len(paths), cumulative


def main() -> None:
    if len(sys.argv) not in (2, 3):
        raise SystemExit(2)
    op = sys.argv[1]
    if op == "capture" and len(sys.argv) == 2:
        pass
    elif op == "verify" and len(sys.argv) == 3 and re.fullmatch(r"[0-9a-f]{64}", sys.argv[2]):
        pass
    else:
        raise SystemExit(2)
    try:
        fingerprint, files, total_bytes = compute_fingerprint()
    except (ScopeError, OSError, ValueError, UnicodeError) as error:
        label = type(error).__name__ if not isinstance(error, ScopeError) else str(error)
        print("PUBLIC_FILES_GUARD=" + label, file=sys.stderr)
        raise SystemExit(5) from None
    if op == "capture":
        print(fingerprint)
    elif fingerprint != sys.argv[2]:
        print("PUBLIC_FILES_GUARD=PUBLIC_SURFACE_DRIFT_ROLLBACK", file=sys.stderr)
        raise SystemExit(5)
    else:
        print("PUBLIC_HOMEPAGE_FILES_UNCHANGED=VERIFIED")
    print(f"PUBLIC_FILES_AUDITED_COUNT={files}", file=sys.stderr)
    print(f"PUBLIC_FILES_AUDITED_BYTES={total_bytes}", file=sys.stderr)


if __name__ == "__main__":
    main()
