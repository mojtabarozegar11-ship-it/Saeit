#!/usr/bin/env python3
"""Precisely bounded cPanel release of SIX static sales pages, no database writes.

Run only through the fingerprint-pinned workflow on the company cPanel account.
Canary proves that the web server serves physical files; rollback touches only
files introduced by this release and refuses changed/unexpected content.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tarfile

CODES = ("AGR-01", "RS-01", "RS-02", "RS-03", "WEB-01", "SEO-01")
ROOT = Path.home() / "public_html"
SERVICES = ROOT / "services"
SCOPE = SERVICES / "scope"
CANARY = SCOPE / "_c13_probe_20261114"
CANARY_DATA = b"ZM_C13_STATIC_ROUTING_PROOF_20261114\n"
MANIFEST = SCOPE / ".c13-release-sha256"
MAX_FILE = 96 * 1024
MAX_ALL = 768 * 1024

def fail(message: str, code: int = 64) -> None:
    print("ZM_C13_RELEASE_STATE=" + message)
    raise SystemExit(code)

def existing(path: Path) -> bool:
    return path.exists() or path.is_symlink()

def safe_owned_dir(path: Path) -> bool:
    try:
        s = path.stat()
        return (not path.is_symlink() and stat.S_ISDIR(s.st_mode)
                and s.st_uid == os.getuid())
    except OSError:
        return False

def root_guard() -> None:
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        fail("WRONG_CPANEl_USER")
    if not safe_owned_dir(ROOT) or not safe_owned_dir(SERVICES):
        fail("UNSAFE_PUBLIC_ROOT")
    if SCOPE.is_symlink():
        fail("SYMLINK_TARGET_REFUSED")

def create_file(path: Path, payload: bytes, mode=0o644) -> None:
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        with os.fdopen(fd, "wb", closefd=True) as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise

def canary_create() -> None:
    root_guard()
    if existing(SCOPE):
        fail("SCOPE_ALREADY_EXISTS")
    SCOPE.mkdir(mode=0o755)
    try:
        CANARY.mkdir(mode=0o755)
        create_file(CANARY / "index.html", CANARY_DATA)
    except Exception:
        try:
            (CANARY / "index.html").unlink(missing_ok=True)
            CANARY.rmdir()
            SCOPE.rmdir()
        except OSError:
            pass
        raise
    print("ZM_C13_CANARY_CREATED=true")

def canary_remove() -> None:
    root_guard()
    file = CANARY / "index.html"
    if not safe_owned_dir(SCOPE) or not safe_owned_dir(CANARY):
        fail("CANARY_PARENT_MISSING")
    if file.is_symlink() or not file.is_file() or file.read_bytes() != CANARY_DATA:
        fail("CANARY_CHANGED_ROLLBACK_REFUSED")
    if set(p.name for p in CANARY.iterdir()) != {"index.html"}:
        fail("CANARY_UNEXPECTED_FILES")
    if set(p.name for p in SCOPE.iterdir()) != {CANARY.name}:
        fail("SCOPE_UNEXPECTED_FILES")
    file.unlink()
    CANARY.rmdir()
    SCOPE.rmdir()
    print("ZM_C13_CANARY_REMOVED=true")

def read_archive() -> dict[str, bytes]:
    expected = {code + "/index.html" for code in CODES}
    result = {}
    total = 0
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as stream:
        for part in stream:
            name = part.name.removeprefix("./")
            if part.isdir() and name in ("", "."):
                continue
            if part.isdir() and name.rstrip("/") in CODES:
                continue
            if not part.isfile() or name not in expected or name in result:
                fail("TAR_PATH_NOT_ALLOWLISTED")
            if part.size <= 100 or part.size > MAX_FILE:
                fail("TAR_CONTENT_SIZE_REFUSED")
            total += part.size
            if total > MAX_ALL:
                fail("TAR_TOTAL_SIZE_REFUSED")
            reader = stream.extractfile(part)
            if reader is None:
                fail("TAR_MEMBER_UNREADABLE")
            data = reader.read(MAX_FILE + 1)
            if len(data) != part.size:
                fail("TAR_BYTES_MISMATCH")
            code = name.split("/", 1)[0]
            if not data.startswith(b"<!doctype html>") or code.encode() not in data:
                fail("INVALID_SERVICE_HTML")
            if b"scope-primary-cta" not in data or b"/ask-master/index.php?service=1" not in data:
                fail("CANONICAL_CTA_MISSING")
            if b"<form" in data.lower():
                fail("SHADOW_FORM_REFUSED")
            result[name] = data
    if set(result) != expected:
        fail("INCOMPLETE_SIX_PAGE_ARCHIVE")
    return result

def apply() -> None:
    root_guard()
    if existing(SCOPE):
        fail("SCOPE_ALREADY_EXISTS")
    pages = read_archive()
    hashes = {code: hashlib.sha256(pages[code + "/index.html"]).hexdigest()
              for code in CODES}
    SCOPE.mkdir(mode=0o755)
    try:
        for code in CODES:
            target = SCOPE / code
            target.mkdir(mode=0o755)
            create_file(target / "index.html", pages[code + "/index.html"])
        manifest = ("ZM_C13_RELEASE_V1\n" + "".join(
            f"{code} {hashes[code]}\n" for code in CODES
        )).encode("ascii")
        create_file(MANIFEST, manifest, mode=0o600)
    except Exception:
        # Only SCOPE was newly created by this invocation, and only
        # precise files and directories from our six-code allowlist are touched.
        for code in CODES:
            p = SCOPE / code
            f = p / "index.html"
            if not f.is_symlink() and f.is_file():
                f.unlink()
            if p.is_dir() and not p.is_symlink():
                p.rmdir()
        if MANIFEST.is_file() and not MANIFEST.is_symlink():
            MANIFEST.unlink()
        SCOPE.rmdir()
        raise
    print("ZM_C13_STATIC_PAGES_INSTALLED=6")
    print("ZM_C13_SOURCE_OF_TRUTH=EXISTING_SIX_SERVICE_CATALOGUE")

def rollback() -> None:
    root_guard()
    if not safe_owned_dir(SCOPE) or not MANIFEST.is_file() or MANIFEST.is_symlink():
        fail("UNVERIFIABLE_RELEASE_NO_DELETE")
    lines = MANIFEST.read_text("ascii").splitlines()
    if lines[0:1] != ["ZM_C13_RELEASE_V1"] or len(lines) != 7:
        fail("BAD_RELEASE_MANIFEST_NO_DELETE")
    expected = {}
    for code, line in zip(CODES, lines[1:]):
        parts = line.split()
        if len(parts) != 2 or parts[0] != code or not re.fullmatch("[a-f0-9]{64}", parts[1]):
            fail("BAD_RELEASE_HASH_NO_DELETE")
        expected[code] = parts[1]
    if set(x.name for x in SCOPE.iterdir()) != set(CODES) | {MANIFEST.name}:
        fail("SCOPE_CHANGED_NO_DELETE")
    for code in CODES:
        path = SCOPE / code
        if not safe_owned_dir(path) or set(p.name for p in path.iterdir()) != {"index.html"}:
            fail("PAGE_DIRECTORY_CHANGED_NO_DELETE")
        page = path / "index.html"
        if page.is_symlink() or not page.is_file():
            fail("PAGE_CHANGED_NO_DELETE")
        if hashlib.sha256(page.read_bytes()).hexdigest() != expected[code]:
            fail("PAGE_HASH_CHANGED_NO_DELETE")
    for code in CODES:
        path = SCOPE / code
        (path / "index.html").unlink()
        path.rmdir()
    MANIFEST.unlink()
    SCOPE.rmdir()
    print("ZM_C13_ONLY_MANAGED_STATIC_PAGES_ROLLED_BACK=6")

def main() -> None:
    os.umask(0o022)
    if len(sys.argv) != 2:
        fail("EXACT_MODE_REQUIRED")
    operations = {
        "canary_create": canary_create,
        "canary_remove": canary_remove,
        "apply": apply,
        "rollback": rollback,
    }
    if sys.argv[1] not in operations:
        fail("MODE_NOT_ALLOWLISTED")
    operations[sys.argv[1]]()

if __name__ == "__main__":
    main()
