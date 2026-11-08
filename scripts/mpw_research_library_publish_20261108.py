#!/usr/bin/env python3
"""Guarded, one-time cPanel publisher for the versioned MojPlayWin research library.

This helper is meant to run as the existing authorized cPanel account, *not*
from GitHub Actions. It never changes Passenger, Django, .htaccess, payments,
mail or existing site files. Rollback quarantines only its unchanged version.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pwd
import re
import shutil
import stat
import sys
import zipfile
from pathlib import Path

HOME = Path("/home/zomorod2")
SITE = HOME / "mojplaywin.com"
EDITORIAL = SITE / "mpw-editorial"
PARENT = EDITORIAL / "research-library"
TARGET = PARENT / "20261108-c4"
PRIVATE = HOME / ".mpw-research-release-c4"
RELEASE = "MPW-RESEARCH-C4-20261108"
EXACT_FILES = frozenset({
    "index.html",
    "books/30-evidence-methods/index.html",
    "books/30-evidence-methods/book.pdf",
    "learning/research-project-guide/index.html",
    "learning/twenty-research-projects/index.html",
    "learning/twenty-research-projects/workbook.pdf",
    "learning/twenty-research-projects/worksheets/index.html",
    "release.json",
} | {f"learning/twenty-research-projects/worksheets/{i:02d}/index.html" for i in range(1, 21)})


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def owned(path: Path, directory: bool | None = None) -> bool:
    if path.is_symlink() or not path.exists():
        return False
    info = path.lstat()
    if info.st_uid != os.getuid():
        return False
    if directory is True and not stat.S_ISDIR(info.st_mode):
        return False
    if directory is False and not stat.S_ISREG(info.st_mode):
        return False
    return True


def authorized_user() -> bool:
    return pwd.getpwuid(os.getuid()).pw_name == "zomorod2"


def preflight() -> None:
    if not authorized_user():
        raise RuntimeError("CPANEL_OWNER_IDENTITY_REQUIRED")
    for p in (HOME, SITE, EDITORIAL):
        if not owned(p, True):
            raise RuntimeError(f"RELEASE_PARENT_NOT_OWNED: {p}")
    for p in (SITE / ".htaccess", SITE / "passenger_wsgi.py"):
        if not owned(p, False):
            raise RuntimeError(f"PROTECTED_SITE_FILE_MISSING_OR_NOT_OWNED: {p}")
    if PARENT.exists() or PARENT.is_symlink():
        if not owned(PARENT, True):
            raise RuntimeError("RELEASE_PARENT_COLLISION")
    if TARGET.exists() or TARGET.is_symlink():
        raise RuntimeError("VERSION_ALREADY_PRESENT_REFUSE_OVERWRITE")
    if PRIVATE.exists() or PRIVATE.is_symlink():
        if not owned(PRIVATE, True):
            raise RuntimeError("PRIVATE_RELEASE_DIR_NOT_OWNED")


def verify_zip(package: Path) -> dict:
    if not owned(package, False) or not package.resolve().is_relative_to(HOME):
        raise RuntimeError("ZIP_MUST_BE_OWNED_INSIDE_CPANEL_HOME")
    if package.stat().st_size > 2_000_000:
        raise RuntimeError("ZIP_EXCEEDS_RELEASE_LIMIT")
    with zipfile.ZipFile(package, "r") as z:
        if set(z.namelist()) != EXACT_FILES or len(z.infolist()) != len(EXACT_FILES):
            raise RuntimeError("WRONG_OR_DUPLICATE_ARCHIVE_FILES")
        for info in z.infolist():
            if info.is_dir() or info.filename.startswith("/") or ".." in Path(info.filename).parts:
                raise RuntimeError("UNSAFE_ARCHIVE_PATH")
            if stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF):
                raise RuntimeError("SYMLINK_ENTRY_REFUSED")
            if info.file_size > 300_000:
                raise RuntimeError("ARCHIVE_ENTRY_TOO_LARGE")
        if z.testzip() is not None:
            raise RuntimeError("ARCHIVE_CRC_FAILURE")
        manifest = json.loads(z.read("release.json"))
        if manifest.get("release_id") != RELEASE or manifest.get("public_root") != "/mpw-editorial/research-library/20261108-c4/":
            raise RuntimeError("RELEASE_IDENTITY_MISMATCH")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != EXACT_FILES - {"release.json"}:
            raise RuntimeError("MANIFEST_FILE_SET_MISMATCH")
        for path, info in files.items():
            data = z.read(path)
            if len(data) != info.get("bytes") or digest(data) != info.get("sha256"):
                raise RuntimeError(f"HASH_OR_SIZE_MISMATCH: {path}")
        return {"package_sha256": digest(package.read_bytes()), "files": files, "manifest_sha256": digest(z.read("release.json"))}


def verify_directory(root: Path, expected: dict) -> None:
    if not owned(root, True):
        raise RuntimeError("RELEASE_DIR_NOT_OWNED")
    observed = set()
    for base, dirs, files in os.walk(root, followlinks=False):
        basepath = Path(base)
        if not owned(basepath, True):
            raise RuntimeError("RELEASE_SUBDIR_NOT_OWNED")
        for d in dirs:
            if not owned(basepath / d, True):
                raise RuntimeError("RELEASE_DIR_COLLISION")
        for f in files:
            p = basepath / f
            if not owned(p, False):
                raise RuntimeError("RELEASE_FILE_COLLISION")
            observed.add(p.relative_to(root).as_posix())
    if observed != EXACT_FILES:
        raise RuntimeError("RELEASE_FILES_CHANGED")
    for path, info in expected["files"].items():
        p = root / path
        if p.stat().st_size != info["bytes"] or digest(p.read_bytes()) != info["sha256"]:
            raise RuntimeError("DEPLOYED_HASH_CHANGED")
    if digest((root / "release.json").read_bytes()) != expected["manifest_sha256"]:
        raise RuntimeError("DEPLOYED_MANIFEST_CHANGED")


def validate_run(run: str) -> None:
    if not re.fullmatch(r"[0-9]{8,20}", run):
        raise RuntimeError("INVALID_RUN_ID")


def install(package: Path, run: str) -> None:
    validate_run(run)
    preflight()
    if not PRIVATE.exists():
        PRIVATE.mkdir(mode=0o700)
    if not owned(PRIVATE, True):
        raise RuntimeError("PRIVATE_DIR_OWNERSHIP_CHANGED")
    stage = PRIVATE / f"stage-{run}"
    receipt = PRIVATE / f"receipt-{run}.json"
    if stage.exists() or stage.is_symlink() or receipt.exists() or receipt.is_symlink():
        raise RuntimeError("RUN_ALREADY_USED")
    with open(PRIVATE / "exclusive.lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        preflight()
        verified = verify_zip(package)
        if not PARENT.exists():
            PARENT.mkdir(mode=0o755)
        if not owned(PARENT, True) or PARENT.stat().st_dev != PRIVATE.stat().st_dev:
            raise RuntimeError("NON_ATOMIC_OR_FOREIGN_PARENT")
        stage.mkdir(mode=0o700)
        with zipfile.ZipFile(package) as z:
            for name in sorted(EXACT_FILES):
                p = stage / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(z.read(name))
                os.chmod(p, 0o644)
        for p in sorted(stage.rglob("*")):
            if p.is_dir():
                os.chmod(p, 0o755)
        os.chmod(stage, 0o755)
        verify_directory(stage, verified)
        data = {"release": RELEASE, "run": run, "target": str(TARGET), **verified}
        with open(receipt, "x", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(receipt, 0o600)
        if TARGET.exists() or TARGET.is_symlink():
            raise RuntimeError("CONCURRENT_TARGET_COLLISION")
        os.replace(stage, TARGET)
        verify_directory(TARGET, verified)
        print("RESEARCH_BOOKS_ATOMIC_RELEASE_PASS", json.dumps({"target": str(TARGET), "run": run, "count": len(EXACT_FILES) - 1}, sort_keys=True))


def rollback(run: str) -> None:
    validate_run(run)
    if not authorized_user() or not owned(PRIVATE, True):
        raise RuntimeError("CPANEL_OWNER_OR_RECEIPT_DIR_REQUIRED")
    receipt = PRIVATE / f"receipt-{run}.json"
    if not owned(receipt, False):
        raise RuntimeError("RUN_RECEIPT_MISSING")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if (data.get("release"), data.get("run"), data.get("target")) != (RELEASE, run, str(TARGET)):
        raise RuntimeError("RECEIPT_IDENTITY_MISMATCH")
    with open(PRIVATE / "exclusive.lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not TARGET.exists() or TARGET.is_symlink():
            raise RuntimeError("TARGET_MISSING_OR_CHANGED")
        verify_directory(TARGET, data)
        quarantine = PRIVATE / f"quarantined-{run}"
        if quarantine.exists() or quarantine.is_symlink():
            raise RuntimeError("QUARANTINE_COLLISION")
        os.replace(TARGET, quarantine)
        print("RESEARCH_BOOKS_ROLLBACK_QUARANTINED", str(quarantine))


def main(argv: list[str]) -> None:
    if len(argv) not in (2, 3) or argv[0] not in ("preflight", "install", "rollback"):
        raise SystemExit("usage: publisher.py preflight ZIP | install ZIP RUNID | rollback RUNID")
    action = argv[0]
    if action == "preflight" and len(argv) == 2:
        preflight()
        verified = verify_zip(Path(argv[1]))
        print("RESEARCH_BOOKS_PREFLIGHT_PASS", verified["package_sha256"])
    elif action == "install" and len(argv) == 3:
        install(Path(argv[1]), argv[2])
    elif action == "rollback" and len(argv) == 2:
        rollback(argv[1])
    else:
        raise SystemExit("invalid argument count")


if __name__ == "__main__":
    main(sys.argv[1:])
