#!/usr/bin/env python3
"""Bounded, duplicate-rejecting, no-clobber local JSON I/O for ONE Mojtaba.bot.ai.

No network, customer database, invoices, payments or background execution.
Use only for PII-free commercial metadata and publicly labelled synthetic data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

MAX_INPUT_BYTES = 65536
MAX_OUTPUT_BYTES = 262144


def _checked_path(raw: Path) -> Path:
    if not isinstance(raw, Path):
        raw = Path(raw)
    if any(piece == ".." for piece in raw.parts):
        raise ValueError("PARENT_TRAVERSAL_DENIED")
    path = raw.absolute()
    # Every ancestor is checked, not just the final input/output component.
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError("SYMLINK_PATH_DENIED")
    return path


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY_REJECTED")
        result[key] = value
    return result


def _no_constants(value):
    raise ValueError("NONFINITE_JSON_CONSTANT_REJECTED")


def read_json(raw: Path, *, limit: int = MAX_INPUT_BYTES) -> dict:
    """Read a stable regular file using O_NOFOLLOW and an explicit byte ceiling."""
    if type(limit) is not int or not 0 < limit <= MAX_INPUT_BYTES:
        raise ValueError("INVALID_INPUT_LIMIT")
    path = _checked_path(raw)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("INPUT_NOT_SINGLE_REGULAR_FILE")
        if not 0 < before.st_size <= limit:
            raise ValueError("INPUT_SIZE_INVALID")
        raw_bytes = bytearray()
        while len(raw_bytes) <= limit:
            part = os.read(fd, min(8192, limit + 1 - len(raw_bytes)))
            if not part:
                break
            raw_bytes.extend(part)
        after = os.fstat(fd)
        if (len(raw_bytes) != before.st_size or len(raw_bytes) > limit
                or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ino != after.st_ino):
            raise ValueError("INPUT_MODIFIED_OR_OVERSIZED")
    finally:
        os.close(fd)
    try:
        result = json.loads(bytes(raw_bytes).decode("utf-8"),
                            object_pairs_hook=_unique_pairs,
                            parse_constant=_no_constants)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("INPUT_INVALID_JSON") from exc
    if type(result) is not dict:
        raise ValueError("INPUT_MUST_BE_OBJECT")
    return result


def create_private_json(raw_target: Path, data: dict, *, input_path: Path | None = None) -> None:
    """Create a NEW 0600 JSON atomically with O_EXCL; never overwrite any file."""
    target = _checked_path(raw_target)
    if not target.parent.is_dir():
        raise ValueError("OUTPUT_PARENT_INVALID")
    if input_path is not None and target == _checked_path(input_path):
        raise ValueError("INPUT_OVERWRITE_DENIED")
    if type(data) is not dict:
        raise ValueError("OUTPUT_MUST_BE_OBJECT")
    try:
        payload = (json.dumps(data, ensure_ascii=False, sort_keys=True,
                              indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("INVALID_OUTPUT_DATA") from exc
    if len(payload) > MAX_OUTPUT_BYTES:
        raise ValueError("OUTPUT_EXCEEDS_SIZE_BOUND")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, stat.S_IRUSR | stat.S_IWUSR)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # An incomplete output must not be represented as a valid report.
        # Deliberately retain the exclusively-created path for forensic review.
        raise
