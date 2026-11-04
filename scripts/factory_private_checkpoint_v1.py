#!/usr/bin/env python3
"""Fail-closed, read-only-source checkpoint for the isolated VPS factory.

This intentionally has no restore command. Replacing live state requires an
operator to establish that no legitimate intervening writes will be lost.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tarfile
import tempfile
from typing import BinaryIO


SCHEMA = "saeit.factory.private-checkpoint.v1"
ARCHIVE = "private-state.tar.gz"
DB_COPY = "factory-state.sqlite3"
MANIFEST = "manifest.json"


def _regular_file(path: Path) -> None:
    _no_symlink_components(path)
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError(f"CHECKPOINT_NOT_REGULAR_FILE:{path.name}")


def _safe_directory(path: Path) -> None:
    _no_symlink_components(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"CHECKPOINT_UNSAFE_DIRECTORY:{path.name}")


def _no_symlink_components(path: Path) -> None:
    if any(component.is_symlink() for component in (path, *path.parents)):
        raise ValueError("CHECKPOINT_SYMLINK_IN_PATH")


def _hash_file(path: Path) -> str:
    _regular_file(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for piece in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(piece)
    return digest.hexdigest()


def _files_in_private(private: Path, cap_bytes: int) -> tuple[list[Path], int]:
    files: list[Path] = []
    size = 0
    for folder, dirs, names in os.walk(private, topdown=True, followlinks=False):
        dirs.sort()
        names.sort()
        for name in dirs:
            _safe_directory(Path(folder) / name)
        for name in names:
            path = Path(folder) / name
            _regular_file(path)
            size += path.stat().st_size
            if size > cap_bytes:
                raise ValueError("CHECKPOINT_SOURCE_LIMIT_EXCEEDED")
            files.append(path)
            if len(files) > 100_000:
                raise ValueError("CHECKPOINT_TOO_MANY_FILES")
    if not files:
        raise ValueError("CHECKPOINT_PRIVATE_SOURCE_EMPTY")
    return files, size


class _DigestingReader:
    def __init__(self, stream: BinaryIO):
        self.stream = stream
        self.hasher = hashlib.sha256()

    def read(self, length: int = -1) -> bytes:
        value = self.stream.read(length)
        self.hasher.update(value)
        return value


def _sqlite_copy(source_path: Path, destination: Path) -> None:
    _regular_file(source_path)
    with closing(sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(destination)) as target:
            source.backup(target, pages=512, sleep=0.05)
            target.commit()
            row = target.execute("PRAGMA integrity_check").fetchone()
            if row != ("ok",):
                raise ValueError("CHECKPOINT_SQLITE_INTEGRITY_FAILURE")
    destination.chmod(0o600)


def snapshot(db: Path, private: Path, destination: Path, max_source_mib: int) -> dict:
    _regular_file(db)
    _safe_directory(private)
    _safe_directory(destination.parent)
    if destination.exists() or destination.is_symlink():
        raise ValueError("CHECKPOINT_DESTINATION_ALREADY_EXISTS")
    if destination.parent == private or private in destination.parents:
        raise ValueError("CHECKPOINT_DESTINATION_INSIDE_SOURCE")
    if db == private or private in db.parents:
        raise ValueError("CHECKPOINT_DB_MUST_BE_SEPARATE")
    if max_source_mib < 1 or max_source_mib > 4096:
        raise ValueError("CHECKPOINT_UNSAFE_SIZE_CAP")
    cap = max_source_mib * 1024 * 1024
    files, total_bytes = _files_in_private(private, cap)
    db_bytes = db.stat().st_size
    if db_bytes + total_bytes > cap:
        raise ValueError("CHECKPOINT_SOURCE_LIMIT_EXCEEDED")
    required_free = 2 * (db_bytes + total_bytes) + 64 * 1024 * 1024
    if shutil.disk_usage(destination.parent).free < required_free:
        raise ValueError("CHECKPOINT_INSUFFICIENT_FREE_SPACE")

    with tempfile.TemporaryDirectory(
        prefix=".checkpoint-staging-", dir=destination.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        os.chmod(temporary, 0o700)
        copied_db = temporary / DB_COPY
        _sqlite_copy(db, copied_db)
        inventory: list[dict] = []
        archive_path = temporary / ARCHIVE
        with tarfile.open(archive_path, "w:gz", compresslevel=1) as archive:
            for source_file in files:
                relative = source_file.relative_to(private).as_posix()
                if relative.startswith("/") or ".." in PurePosixPath(relative).parts:
                    raise ValueError("CHECKPOINT_UNSAFE_RELATIVE_PATH")
                with source_file.open("rb") as stream:
                    before = os.fstat(stream.fileno())
                    if not stat.S_ISREG(before.st_mode):
                        raise ValueError("CHECKPOINT_SOURCE_TYPE_CHANGED")
                    item = tarfile.TarInfo(relative)
                    item.size = before.st_size
                    item.mode = 0o600
                    item.uid = item.gid = 0
                    item.uname = item.gname = ""
                    item.mtime = int(before.st_mtime)
                    reader = _DigestingReader(stream)
                    archive.addfile(item, reader)
                    after = os.fstat(stream.fileno())
                    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                        after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns
                    ):
                        raise ValueError("CHECKPOINT_SOURCE_CHANGED_DURING_COPY")
                    inventory.append(
                        {"path": relative, "size": item.size, "sha256": reader.hasher.hexdigest()}
                    )
        archive_path.chmod(0o600)
        manifest = {
            "schema": SCHEMA,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "db_sha256": _hash_file(copied_db),
            "archive_sha256": _hash_file(archive_path),
            "file_count": len(inventory),
            "uncompressed_bytes": total_bytes,
            "files": inventory,
            "scope": "isolated SQLite + factory private directory; no external workloads",
            "independent_offhost_copy_verified": False,
            "auto_restore_authorized": False,
        }
        manifest_path = temporary / MANIFEST
        with manifest_path.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
        manifest_path.chmod(0o600)
        verify(temporary)
        temporary.rename(destination)
        return manifest


def verify(checkpoint: Path) -> dict:
    _safe_directory(checkpoint)
    manifest_path = checkpoint / MANIFEST
    db_path = checkpoint / DB_COPY
    archive_path = checkpoint / ARCHIVE
    for path in (manifest_path, db_path, archive_path):
        _regular_file(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError("CHECKPOINT_WRONG_SCHEMA")
    if manifest.get("independent_offhost_copy_verified") is not False:
        raise ValueError("CHECKPOINT_OFFHOST_CLAIM_NOT_ALLOWED")
    if manifest.get("auto_restore_authorized") is not False:
        raise ValueError("CHECKPOINT_AUTO_RESTORE_FORBIDDEN")
    if _hash_file(db_path) != manifest.get("db_sha256"):
        raise ValueError("CHECKPOINT_DB_DIGEST_MISMATCH")
    if _hash_file(archive_path) != manifest.get("archive_sha256"):
        raise ValueError("CHECKPOINT_ARCHIVE_DIGEST_MISMATCH")
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("CHECKPOINT_DB_CORRUPT")
    inventory = manifest.get("files")
    if not isinstance(inventory, list) or not inventory:
        raise ValueError("CHECKPOINT_INVALID_FILE_LIST")
    seen = set()
    total = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) != len(inventory):
            raise ValueError("CHECKPOINT_ARCHIVE_MEMBER_COUNT_MISMATCH")
        for item, record in zip(members, inventory):
            if not isinstance(record, dict) or not item.isfile():
                raise ValueError("CHECKPOINT_NONFILE_MEMBER")
            name = item.name
            if (name.startswith("/") or ".." in PurePosixPath(name).parts
                    or name in seen or name != record.get("path")
                    or item.size != record.get("size")):
                raise ValueError("CHECKPOINT_UNSAFE_MEMBER")
            seen.add(name)
            total += item.size
            digest = hashlib.sha256()
            with archive.extractfile(item) as stream:
                for piece in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(piece)
            if digest.hexdigest() != record.get("sha256"):
                raise ValueError("CHECKPOINT_FILE_DIGEST_MISMATCH")
    if manifest.get("file_count") != len(inventory) or manifest.get("uncompressed_bytes") != total:
        raise ValueError("CHECKPOINT_INVENTORY_MISMATCH")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="operation", required=True)
    create = subcommands.add_parser("snapshot")
    create.add_argument("--db", type=Path, required=True)
    create.add_argument("--private", type=Path, required=True)
    create.add_argument("--destination", type=Path, required=True)
    create.add_argument("--max-source-mib", type=int, default=512)
    check = subcommands.add_parser("verify")
    check.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()
    if args.operation == "snapshot":
        result = snapshot(args.db, args.private, args.destination, args.max_source_mib)
    else:
        result = verify(args.checkpoint)
    print(
        "F01_PRIVATE_CHECKPOINT_VERIFIED=PASS "
        f"FILES={result['file_count']} "
        "OFFHOST_VERIFIED=NO AUTO_RESTORE=NO"
    )


if __name__ == "__main__":
    main()
