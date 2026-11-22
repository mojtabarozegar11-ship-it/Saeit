#!/usr/bin/env python3
"""Read-only R01 artifact identity check; never evidence of field efficacy.

Usage: python research/irrigation_synthetic_audit/verify_frozen_manifest.py MANIFEST.json
Manifest: {"schema_version":1,"study":"R01","artifacts":[{"role":"input",
"path":"inputs/C.csv","sha256":"<64 lowercase hex>","bytes":123}, ...]}
Required roles: input, generator, config, output. No private data are published.
"""
import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

ROLES = {"input", "generator", "config", "output", "analysis", "table"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_ARTIFACTS = 10000


def _digest_anchored(root, parts, expected_size):
    """Open each path component relative to held directory FDs, without symlinks.

    A concurrent rename can change directory entries, but cannot redirect
    already-open descriptors to a different inode. Never write to artifacts.
    """
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
    fds = []
    try:
        parent = os.open(root, directory_flags)
        fds.append(parent)
        for component in parts[:-1]:
            parent = os.open(component, directory_flags, dir_fd=parent)
            fds.append(parent)
        fd = os.open(parts[-1], file_flags, dir_fd=parent)
        fds.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("artifact is not a regular file")
        if before.st_size != expected_size:
            raise ValueError("byte count mismatch")
        digest = hashlib.sha256()
        count = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            count += len(chunk)
            if count > expected_size:
                raise ValueError("artifact grew during read")
            digest.update(chunk)
        after = os.fstat(fd)
        if (count != expected_size or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ctime_ns != after.st_ctime_ns):
            raise ValueError("artifact changed during read")
        return digest.hexdigest()
    finally:
        for fd in reversed(fds):
            os.close(fd)


def verify(manifest_path):
    errors = []
    def check(ok, message):
        if not ok:
            errors.append(message)
        return bool(ok)

    manifest_path = Path(manifest_path)
    try:
        # Pin the manifest inode; a path check followed by open is racy.
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(manifest_path, flags)
        with os.fdopen(fd, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                return ["manifest must be a regular file"]
            if before.st_size > MAX_MANIFEST_BYTES:
                return ["manifest exceeds size limit"]
            raw = handle.read(MAX_MANIFEST_BYTES + 1)
            after = os.fstat(handle.fileno())
            if (before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or before.st_ctime_ns != after.st_ctime_ns):
                return ["manifest changed during read"]
        if len(raw) > MAX_MANIFEST_BYTES:
            return ["manifest exceeds size limit"]
        if len(raw) != before.st_size:
            return ["manifest short read; snapshot incomplete"]
        def reject_duplicate_keys(pairs):
            obj = {}
            for key, value in pairs:
                if key in obj:
                    raise ValueError("duplicate JSON key: " + key)
                obj[key] = value
            return obj
        def reject_nonfinite(token):
            # Python accepts NaN/Infinity by default although JSON forbids them.
            # Fail closed for scientific provenance metadata.
            raise ValueError("non-finite JSON constant: " + token)
        data = json.loads(raw, object_pairs_hook=reject_duplicate_keys,
                          parse_constant=reject_nonfinite)
    except (OSError, UnicodeError, ValueError) as exc:
        return ["manifest unreadable or invalid JSON: " + str(exc)]
    if not check(isinstance(data, dict), "root must be object"):
        return errors
    check(type(data.get("schema_version")) is int and data["schema_version"] == 1,
          "schema_version must be 1")
    check(data.get("study") == "R01", "study must be R01")
    artifacts = data.get("artifacts")
    if not check(isinstance(artifacts, list), "artifacts must be array"):
        return errors
    if not check(0 < len(artifacts) <= MAX_ARTIFACTS, "artifact count out of bounds"):
        return errors
    root = manifest_path.parent
    seen = set()
    roles = set()
    for i, item in enumerate(artifacts):
        tag = "artifacts[%d]" % i
        if not check(isinstance(item, dict), tag + " must be object"):
            continue
        role = item.get("role")
        role_valid = check(isinstance(role, str) and role in ROLES, tag + " invalid role")
        path = item.get("path")
        if not check(isinstance(path, str) and bool(path) and "\x00" not in path,
                     tag + " invalid path"):
            continue
        # Only canonical POSIX-relative artifact paths are allowed.
        if not check("\\" not in path and not path.startswith("/")
                     and all(p not in ("", ".", "..") for p in path.split("/")),
                     tag + " noncanonical or unsafe path"):
            continue
        if not check(path not in seen, tag + " duplicate path"):
            continue
        seen.add(path)
        size = item.get("bytes")
        if not check(type(size) is int and size >= 0, tag + " invalid byte count"):
            continue
        expected = item.get("sha256")
        if not check(isinstance(expected, str) and SHA.fullmatch(expected) is not None,
                     tag + " invalid SHA-256"):
            continue
        try:
            digest = _digest_anchored(root, path.split("/"), size)
            if check(digest == expected, tag + " SHA-256 mismatch") and role_valid:
                roles.add(role)
        except (OSError, ValueError) as exc:
            errors.append(tag + " inaccessible or invalid artifact: " + str(exc))
    for role in ("input", "generator", "config", "output"):
        check(role in roles, "missing " + role + " role")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    failures = verify(args.manifest)
    for failure in failures:
        print("FAIL:", failure, file=sys.stderr)
    if failures:
        print("BLOCKED: %d integrity violations" % len(failures), file=sys.stderr)
        return 1
    print("PASS: file identity only; model validity NOT established")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
