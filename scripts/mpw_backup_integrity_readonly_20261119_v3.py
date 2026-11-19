"""Read-only system-gzip integrity diagnostic for the fixed 2.31GB backup.
No extraction, temporary files, content output, writes, deletes or transfer.
"""
import hashlib
import json
import os
import pwd
import stat
import subprocess
import time
from pathlib import Path

HOME = Path("/home/zomorod2")
SECOND_GROUP = "012feef8bce02780"
SECOND_ID = "a0527a9d8e6018a2"
SECOND_SIZE = 2314043690
SECOND_MTIME = 1795077682
MAX_SECONDS = 360
BLOCK = 1024 * 1024


def token(value):
    return hashlib.sha256(os.fsencode(str(value))).hexdigest()[:16]


def ident(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def locate(root, deadline):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or root.resolve() != root:
        return None
    root_stat = root.lstat()
    if root_stat.st_uid != os.geteuid():
        return None
    stack = [root]
    matches = []
    count = 0
    while stack and time.monotonic() < deadline:
        parent = stack.pop()
        try:
            with os.scandir(parent) as entries:
                for entry in entries:
                    count += 1
                    if count > 50000 or time.monotonic() >= deadline:
                        return None
                    current = entry.stat(follow_symlinks=False)
                    if current.st_uid != os.geteuid() or stat.S_ISLNK(current.st_mode):
                        continue
                    path = Path(entry.path)
                    if stat.S_ISDIR(current.st_mode):
                        if current.st_dev == root_stat.st_dev:
                            stack.append(path)
                    elif (stat.S_ISREG(current.st_mode)
                          and current.st_size == SECOND_SIZE
                          and int(current.st_mtime) == SECOND_MTIME
                          and token(path.relative_to(HOME)) == SECOND_ID):
                        matches.append((path, current))
        except OSError:
            return None
    return matches[0] if len(matches) == 1 else None


def result_base():
    return {
        "schema": "mpw.backup.integrity.readonly.v3",
        "read_only": True,
        "raw_content_disclosed": False,
        "temporary_files_created": False,
        "files_deleted": False,
        "extraction_performed": False,
        "safe_to_delete": False,
        "integrity_proven": False,
        "error_category": None,
    }


def main():
    out = result_base()
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        out["error_category"] = "WRONG_ACCOUNT"
        return out
    deadline = time.monotonic() + MAX_SECONDS
    roots = [p for p in HOME.iterdir() if token(p.name) == SECOND_GROUP and not p.is_symlink()]
    pair = locate(roots[0], deadline) if len(roots) == 1 else None
    out["file_identified"] = pair is not None
    if pair is None:
        out["error_category"] = "FIXED_FILE_NOT_IDENTIFIED"
        return out
    path, expected = pair
    try:
        before = path.stat()
    except OSError:
        out["error_category"] = "STAT_FAILED"
        return out
    if ident(before) != ident(expected):
        out["error_category"] = "IDENTITY_CHANGED_BEFORE_TEST"
        return out
    out["compressed_bytes"] = before.st_size
    if not hasattr(subprocess, "run"):
        out["error_category"] = "SUBPROCESS_UNAVAILABLE"
        return out
    try:
        test = subprocess.run(
            ["gzip", "-t", "--", str(path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=MAX_SECONDS,
        )
    except FileNotFoundError:
        out["error_category"] = "SYSTEM_GZIP_UNAVAILABLE"
        return out
    except subprocess.TimeoutExpired:
        out["error_category"] = "SYSTEM_GZIP_TEST_TIMEOUT"
        return out
    except OSError:
        out["error_category"] = "SYSTEM_GZIP_TEST_OS_ERROR"
        return out
    out["system_gzip_test_returncode"] = test.returncode
    if test.returncode != 0:
        out["error_category"] = "SYSTEM_GZIP_TEST_FAILED"
        return out

    try:
        proc = subprocess.Popen(
            ["gzip", "-cd", "--", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        assert proc.stdout is not None
        digest = hashlib.sha256()
        total = 0
        while True:
            if time.monotonic() >= deadline:
                proc.kill()
                proc.wait()
                out["error_category"] = "SYSTEM_GZIP_STREAM_TIMEOUT"
                return out
            block = proc.stdout.read(BLOCK)
            if not block:
                break
            total += len(block)
            digest.update(block)
        returncode = proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait()
        except Exception:
            pass
        out["error_category"] = "SYSTEM_GZIP_STREAM_TIMEOUT"
        return out
    except OSError:
        out["error_category"] = "SYSTEM_GZIP_STREAM_OS_ERROR"
        return out

    out["decompressed_bytes"] = total
    out["system_gzip_stream_returncode"] = returncode
    out["decompressed_sha256_prefix"] = digest.hexdigest()[:16]
    if returncode != 0:
        out["error_category"] = "SYSTEM_GZIP_STREAM_FAILED"
        return out
    try:
        after = path.stat()
    except OSError:
        out["error_category"] = "STAT_FAILED_AFTER_TEST"
        return out
    out["file_unchanged"] = ident(after) == ident(before)
    if not out["file_unchanged"]:
        out["error_category"] = "IDENTITY_CHANGED_DURING_TEST"
        return out
    out["integrity_proven"] = True
    out["error_category"] = "NONE"
    return out


if __name__ == "__main__":
    print("MPW_BACKUP_INTEGRITY_READONLY=" + json.dumps(main(), sort_keys=True), flush=True)
