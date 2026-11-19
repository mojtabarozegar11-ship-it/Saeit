"""Read-only equivalence diagnostic for the two fixed owner-local backup files.
No raw content, paths, digests, writes, deletes, extraction or restore.
"""
import gzip
import hashlib
import json
import os
import pwd
import stat
import time
from pathlib import Path

HOME = Path("/home/zomorod2")
RAW_ROOT = HOME / "Saeit-staging" / "backups"
RAW_ID = "631f2edc066491c2"
RAW_SIZE = 17901606016
RAW_MTIME = 1795033731
SECOND_GROUP = "012feef8bce02780"
SECOND_ID = "a0527a9d8e6018a2"
SECOND_SIZE = 2314043690
SECOND_MTIME = 1795077682
MAX_SECONDS = 210
BLOCK = 1024 * 1024


def token(value):
    return hashlib.sha256(os.fsencode(str(value))).hexdigest()[:16]


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def locate(root, wanted, size, mtime, budget):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or root.resolve() != root:
        return None
    root_stat = root.lstat()
    if root_stat.st_uid != os.geteuid():
        return None
    stack = [root]
    matches = []
    count = 0
    while stack and time.monotonic() < budget:
        parent = stack.pop()
        try:
            with os.scandir(parent) as entries:
                for entry in entries:
                    count += 1
                    if count > 25000 or time.monotonic() >= budget:
                        return None
                    current = entry.stat(follow_symlinks=False)
                    if current.st_uid != os.geteuid() or stat.S_ISLNK(current.st_mode):
                        continue
                    path = Path(entry.path)
                    if stat.S_ISDIR(current.st_mode):
                        if current.st_dev == root_stat.st_dev:
                            stack.append(path)
                    elif (stat.S_ISREG(current.st_mode)
                          and current.st_size == size
                          and int(current.st_mtime) == mtime
                          and token(path.relative_to(HOME)) == wanted):
                        matches.append((path, current))
        except OSError:
            return None
    return matches[0] if len(matches) == 1 else None


def open_stable(pair):
    path, expected = pair
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        stream = os.fdopen(fd, "rb")
        actual = os.fstat(stream.fileno())
        if identity(actual) != identity(expected) or not stat.S_ISREG(actual.st_mode):
            stream.close()
            return None
        return stream
    except OSError:
        return None


def digest(stream, limit, deadline):
    result = hashlib.sha256()
    total = 0
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError
        block = stream.read(BLOCK)
        if not block:
            return total, result.digest()
        total += len(block)
        if total > limit:
            raise ValueError
        result.update(block)


def audit():
    result = {
        "schema": "mpw.backup.equivalence.readonly.v2",
        "read_only": True,
        "raw_content_disclosed": False,
        "files_deleted": False,
        "restore_verified": False,
        "safe_to_delete": False,
        "equivalent": False,
        "error_category": None,
    }
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        result["error_category"] = "WRONG_ACCOUNT"
        return result

    deadline = time.monotonic() + MAX_SECONDS
    try:
        roots = [
            path for path in HOME.iterdir()
            if token(path.name) == SECOND_GROUP and not path.is_symlink()
        ]
        raw = locate(RAW_ROOT, RAW_ID, RAW_SIZE, RAW_MTIME, deadline)
        second = locate(roots[0], SECOND_ID, SECOND_SIZE, SECOND_MTIME, deadline) if len(roots) == 1 else None
        result["raw_identified"] = raw is not None
        result["second_identified"] = second is not None
        if not raw or not second:
            result["error_category"] = "FIXED_PAIR_NOT_IDENTIFIED"
            return result

        second_stream = open_stable(second)
        if second_stream is None:
            result["error_category"] = "SECOND_IDENTITY_CHANGED_OR_OPEN_FAILED"
            return result
        try:
            header = second_stream.read(4096)
            result["second_gzip_magic"] = header.startswith(b"\x1f\x8b")
            result["second_plain_sql_marker"] = b"-- MySQL dump" in header or b"-- MariaDB dump" in header
            if not result["second_gzip_magic"]:
                result["error_category"] = "SECOND_NOT_GZIP"
                return result
            second_stream.seek(0)
            try:
                with gzip.GzipFile(fileobj=second_stream) as decoded:
                    decompressed_size, second_digest = digest(decoded, RAW_SIZE, deadline)
            except (OSError, EOFError, gzip.BadGzipFile, ValueError):
                result["error_category"] = "GZIP_DECODE_FAILED"
                return result
            result["decompressed_size"] = decompressed_size
            if decompressed_size != RAW_SIZE:
                result["error_category"] = "DECOMPRESSED_SIZE_MISMATCH"
                return result
        finally:
            second_after = os.fstat(second_stream.fileno())
            second_stream.close()

        raw_stream = open_stable(raw)
        if raw_stream is None:
            result["error_category"] = "RAW_IDENTITY_CHANGED_OR_OPEN_FAILED"
            return result
        try:
            raw_size, raw_digest = digest(raw_stream, RAW_SIZE, deadline)
            raw_after = os.fstat(raw_stream.fileno())
        except TimeoutError:
            result["error_category"] = "DIGEST_TIME_BUDGET"
            return result
        except ValueError:
            result["error_category"] = "RAW_SIZE_BOUND_EXCEEDED"
            return result
        finally:
            raw_stream.close()

        result["raw_stream_size"] = raw_size
        unchanged = identity(raw_after) == identity(raw[1]) and identity(second_after) == identity(second[1])
        result["pair_unchanged"] = unchanged
        result["equivalent"] = unchanged and raw_size == decompressed_size and raw_digest == second_digest
        if result["equivalent"]:
            result["error_category"] = "NONE"
        elif not unchanged:
            result["error_category"] = "IDENTITY_CHANGED_DURING_READ"
        else:
            result["error_category"] = "CONTENT_DIGEST_MISMATCH"
        return result
    except TimeoutError:
        result["error_category"] = "LOCATE_OR_DIGEST_TIME_BUDGET"
        return result
    except OSError:
        result["error_category"] = "READ_ONLY_FILESYSTEM_ERROR"
        return result


if __name__ == "__main__":
    print("MPW_BACKUP_EQUIVALENCE_READONLY=" + json.dumps(audit(), sort_keys=True), flush=True)
