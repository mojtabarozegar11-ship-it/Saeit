#!/usr/bin/env python3
"""Prepare a writable private SKU 879 rework tree from an immutable, hash-pinned copy.

Never changes the original archive, store product, release/rights flags, or QA grade.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

SOURCE_SHA = "20894f2de0228318c0e96ba407c2bd4aa98b62ba2f3f2f2fbca53987c9276783"
ROOT = Path("/home/githubops/factory-runtime/private/autonomous-product-cycle/design-intake/mpw-live-three-sku-qa")
MAX_EXPANDED = 512 * 1024 * 1024
MAX_MEMBER = 100 * 1024 * 1024


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def private_dir(path):
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError("REWORK_SYMLINK_DIRECTORY")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("REWORK_INVALID_DIRECTORY")
    os.chmod(path, 0o700)


def extract(archive, target):
    """Bounded ZIP extraction; no traversal, links, duplicate paths or special files."""
    if not zipfile.is_zipfile(archive):
        raise RuntimeError("REWORK_NOT_ZIP")
    manifest = []
    seen = set()
    total = 0
    with zipfile.ZipFile(archive) as package:
        members = package.infolist()
        if not 0 < len(members) <= 2000 or package.testzip() is not None:
            raise RuntimeError("REWORK_BAD_ZIP")
        for info in members:
            name = info.filename
            p = PurePosixPath(name)
            mode = (info.external_attr >> 16) & 0o170000
            if (not name or name.startswith("/") or "\\" in name or
                    "." in p.parts or ".." in p.parts or name in seen or
                    mode not in (0, stat.S_IFDIR, stat.S_IFREG)):
                raise RuntimeError("REWORK_UNSAFE_ZIP_MEMBER")
            seen.add(name)
            if info.file_size > MAX_MEMBER:
                raise RuntimeError("REWORK_MEMBER_TOO_LARGE")
            total += info.file_size
            if total > MAX_EXPANDED:
                raise RuntimeError("REWORK_EXPANSION_LIMIT")
            destination = target.joinpath(*p.parts)
            if info.is_dir():
                private_dir(destination)
                continue
            private_dir(destination.parent)
            with package.open(info) as reader, destination.open("xb") as output:
                size = 0
                while True:
                    block = reader.read(1048576)
                    if not block:
                        break
                    size += len(block)
                    if size > info.file_size or size > MAX_MEMBER:
                        raise RuntimeError("REWORK_SIZE_MISMATCH")
                    output.write(block)
            if size != info.file_size:
                raise RuntimeError("REWORK_SIZE_MISMATCH")
            os.chmod(destination, 0o600)
            manifest.append({"path": name, "size": size, "sha256": sha(destination)})
    if not any(PurePosixPath(row["path"]).name.lower() == "index.html" for row in manifest):
        raise RuntimeError("REWORK_INDEX_MISSING")
    return sorted(manifest, key=lambda x: x["path"])


def write_once(path, content):
    if path.is_symlink():
        raise RuntimeError("REWORK_UNSAFE_RECEIPT")
    fd, temp = tempfile.mkstemp(prefix=".receipt-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        try:
            os.link(temp, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != content:
                raise RuntimeError("REWORK_RECEIPT_CONFLICT")
    finally:
        os.unlink(temp)


def prepare(root=ROOT, source_sha=SOURCE_SHA, min_free_bytes=2 * 1024 ** 3):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("REWORK_PRIVATE_ROOT_REQUIRED")
    original = root / "copies" / "879" / (source_sha + ".bin")
    if original.is_symlink() or not original.is_file() or sha(original) != source_sha:
        raise RuntimeError("REWORK_SOURCE_HASH_MISMATCH")
    home = root / "quality1000-rework" / "879" / source_sha
    private_dir(home)
    lock = home / ".prepare.lock"
    if lock.is_symlink():
        raise RuntimeError("REWORK_LOCK_SYMLINK")
    with lock.open("a+b") as lock_file:
        os.chmod(lock, 0o600)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        dest = home / "writable-source"
        receipt = home / "source-baseline.json"
        if dest.exists() or dest.is_symlink():
            if (dest.is_symlink() or not dest.is_dir() or receipt.is_symlink() or
                    not receipt.is_file()):
                raise RuntimeError("REWORK_EXISTING_TREE_UNTRUSTED")
            record = json.loads(receipt.read_text(encoding="utf-8"))
            if record.get("source_sha256") != source_sha or record.get("schema") != "saeit.sku879.writable-rework.v1":
                raise RuntimeError("REWORK_BASELINE_INVALID")
            return {"status": "already_prepared", "source_preserved": sha(original) == source_sha,
                    "commercial_release_allowed": False, "quality1000_verified": False}
        if shutil.disk_usage(home).free < min_free_bytes + min(original.stat().st_size * 5, MAX_EXPANDED):
            raise RuntimeError("REWORK_DISK_RESERVE_LOW")
        stage = Path(tempfile.mkdtemp(prefix=".rework-stage-", dir=str(home)))
        os.chmod(stage, 0o700)
        try:
            files = extract(original, stage)
            record = {"schema": "saeit.sku879.writable-rework.v1",
                      "sku": 879, "source_sha256": source_sha, "source_immutable": True,
                      "files": files, "baseline_only": True, "quality1000_verified": False,
                      "commercial_release_allowed": False, "storefront_unchanged": True}
            raw = (json.dumps(record, sort_keys=True, indent=2) + "\n").encode("utf-8")
            if sha(original) != source_sha:
                raise RuntimeError("REWORK_SOURCE_CHANGED_DURING_COPY")
            # Same-volume rename and one-time receipt, never overwriting an existing tree.
            if dest.exists() or dest.is_symlink():
                raise RuntimeError("REWORK_DESTINATION_EXISTS")
            os.rename(stage, dest)
            write_once(receipt, raw)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        return {"status": "prepared", "source_preserved": sha(original) == source_sha,
                "file_count": len(files), "commercial_release_allowed": False,
                "quality1000_verified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["prepare"])
    args = parser.parse_args()
    if args.operation == "prepare":
        print("MPW_SKU879_REWORK=" + json.dumps(prepare(), sort_keys=True))


if __name__ == "__main__":
    main()
