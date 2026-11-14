"""Fail-closed local, anonymized I/O for one-bot pre-sale qualification.

No customer emails, payments or real orders are read or written by this module.
A caller must validate strict allowlisted fields before exporting any output.
"""
import json
import os
from pathlib import Path
import stat

MAX_BYTES = 65536
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 4096


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key rejected")
        result[key] = value
    return result


def reject_nonfinite(value):
    raise ValueError("non-finite JSON number rejected")


def _enforce_document_shape(root):
    # JSON can be deeply nested even if the interpreter accepts it.
    # Iterative traversal avoids recursive risk and bounds processing cost.
    pending = [(root, 0)]
    nodes = 0
    while pending:
        current, depth = pending.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise ValueError("JSON nesting or field-count limit exceeded")
        if isinstance(current, dict):
            pending.extend((v, depth + 1) for v in current.values())
        elif isinstance(current, list):
            pending.extend((v, depth + 1) for v in current)


def read_strict_json(path, *, max_bytes=MAX_BYTES):
    """Open regular input without following links; reject ambiguous JSON."""
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("invalid input size policy")
    src = Path(path)
    if src.is_symlink():
        raise ValueError("intake symlink rejected")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(src, flags)
    except OSError as exc:
        raise ValueError("intake file inaccessible") from exc
    with os.fdopen(fd, "rb") as handle:
        meta = os.fstat(handle.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > max_bytes:
            raise ValueError("intake must be a regular file at most 64 KiB")
        raw = handle.read(max_bytes + 1)
        after = os.fstat(handle.fileno())
        if (len(raw) != meta.st_size or after.st_size != meta.st_size
                or after.st_mtime_ns != meta.st_mtime_ns
                or after.st_ctime_ns != meta.st_ctime_ns):
            raise ValueError("intake changed during read")
    if len(raw) > max_bytes:
        raise ValueError("intake exceeds maximum length")
    try:
        result = json.loads(raw.decode("utf-8"),
                            object_pairs_hook=reject_duplicate_keys,
                            parse_constant=reject_nonfinite)
        _enforce_document_shape(result)
        return result
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid or ambiguous JSON intake") from exc


def write_new_anonymized_json(path, content):
    """Never overwrite a file, follow a symlink, or persist private input."""
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_BYTES:
        raise ValueError("invalid sanitized output")
    dest = Path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(dest, flags, 0o600)
    except OSError as exc:
        raise ValueError("refusing to overwrite an existing or unsafe output") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
