#!/usr/bin/env python3
"""Owner-gated two-public-file backup and private isolated restoration.

All cPanel filesystem operations are relative to pinned O_NOFOLLOW/O_DIRECTORY
file descriptors. No live writes, DB access, Passenger action or TRX payment.
A successful result proves TWO public files only, never full-site recoverability.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys

HOME = Path("/home/zomorod2")
ROOT = HOME / "mojplaywin.com"
VAULT = HOME / ".mojprop-static-restore-evidence"
PUBLIC_FILES = (("moj-prop", "index.html"), ("moj-prop", "catalog", "index.html"))
ID = re.compile(r"[1-9][0-9]{0,18}\Z")
QUANTITY = re.compile(r"[0-9]+\Z")
FLAGS = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
MAX_BYTES = 512_000
RESERVE_BYTES = 64 * 1024 * 1024
RESERVE_INODES = 32


def _fd_dir(parent: int, name: str, *, uid: int, private=False) -> int:
    fd = os.open(name, FLAGS, dir_fd=parent)
    try:
        st = os.fstat(fd)
        if st.st_uid != uid or not stat.S_ISDIR(st.st_mode):
            raise RuntimeError("untrusted directory identity")
        if st.st_mode & (0o077 if private else 0o002):
            raise RuntimeError("unsafe directory permissions")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _home_fd(home: Path, uid: int) -> int:
    if not home.is_absolute() or ".." in home.parts:
        raise ValueError("bad home path")
    fd = os.open("/", FLAGS)
    try:
        for part in home.parts[1:]:
            new = os.open(part, FLAGS, dir_fd=fd)
            os.close(fd)
            fd = new
        st = os.fstat(fd)
        if st.st_uid != uid or not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o002:
            raise RuntimeError("home tenant ownership invalid")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read(fd: int, name: str, uid: int, *, minimum=64) -> bytes:
    handle = os.open(name, os.O_RDONLY | NOFOLLOW | getattr(os, "O_CLOEXEC", 0), dir_fd=fd)
    try:
        before = os.fstat(handle)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != uid or before.st_nlink != 1
                or before.st_mode & 0o002 or not minimum <= before.st_size <= MAX_BYTES):
            raise RuntimeError("unsafe public/backup file")
        with os.fdopen(os.dup(handle), "rb") as src:
            body = src.read(MAX_BYTES + 1)
        after = os.fstat(handle)
        if len(body) != before.st_size or (after.st_ino, after.st_mtime_ns, after.st_size) != (
                before.st_ino, before.st_mtime_ns, before.st_size):
            raise RuntimeError("file changed while reading")
        return body
    finally:
        os.close(handle)


def _write(fd: int, name: str, body: bytes) -> tuple[int, int]:
    handle = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600, dir_fd=fd)
    created = os.fstat(handle)
    try:
        with os.fdopen(handle, "wb") as dest:
            dest.write(body)
            dest.flush()
            os.fsync(dest.fileno())
        return created.st_dev, created.st_ino
    except BaseException:
        # O_EXCL succeeded, so only remove OUR newly created inode. Never
        # delete an unrelated file substituted at the same private path.
        try:
            current = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISREG(current.st_mode) and (
                    current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            pass
        raise


def _mkdir(fd: int, name: str, uid: int, *, unique=False) -> int:
    if unique:
        os.mkdir(name, 0o700, dir_fd=fd)
    else:
        try:
            os.mkdir(name, 0o700, dir_fd=fd)
        except FileExistsError:
            pass
    return _fd_dir(fd, name, uid=uid, private=True)


def _quantity(token: str) -> int:
    # quota(1) WITHOUT -s reports exact integer KiB, not rounded human
    # suffixes. Reject every suffix/asterisk/unrecognized token.
    if not QUANTITY.fullmatch(token):
        raise RuntimeError("unrecognized or rounded quota units")
    return int(token) * 1024


def _quota_evidence(home_fd: int, owner: str, needed: int) -> bool:
    """Require bounded OS quota report AND filesystem bytes/inodes; fail closed."""
    disk = os.fstatvfs(home_fd)
    if disk.f_bavail * disk.f_frsize < needed + RESERVE_BYTES or disk.f_favail < RESERVE_INODES:
        return False
    try:
        report = subprocess.run(
            ["quota", "-wvu", owner], timeout=6, check=True, capture_output=True, text=True,
            env={"LC_ALL": "C", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    observed = 0
    for raw in report.splitlines():
        cols = raw.split()
        # Linux quota -wvu (NOT -s) prints exact 1-KiB blocks and raw
        # inode counts; -s human-readable rounding is UNSAFE at reserve
        # boundaries. Grace/soft-limit anomalies are refused.
        if not cols or not cols[0].startswith("/dev/"):
            continue
        if len(cols) != 7:
            return False
        try:
            space_used = _quantity(cols[1])
            space_soft = _quantity(cols[2])
            space_hard = _quantity(cols[3])
            inode_used, inode_soft, inode_hard = [int(v) for v in cols[4:7]]
        except (ValueError, RuntimeError):
            return False
        # zero is OS quota's "unlimited" setting, NOT proof of additional space:
        # the statvfs cap above must still pass.
        for upper in (space_soft, space_hard):
            if upper and upper - space_used < needed + RESERVE_BYTES:
                return False
        for upper in (inode_soft, inode_hard):
            if upper and upper - inode_used < RESERVE_INODES:
                return False
        observed += 1
    return observed > 0


def audit_and_restore(*, home: Path = HOME, root: Path = ROOT,
                      vault: Path = VAULT, owner: str = "zomorod2",
                      run_id: str, approval_id: str,
                      quota_probe=None) -> dict:
    if not ID.fullmatch(run_id) or not ID.fullmatch(approval_id):
        raise ValueError("invalid run/authorization id")
    if root != home / "mojplaywin.com" or vault != home / ".mojprop-static-restore-evidence":
        raise ValueError("out-of-scope target")
    uid = os.geteuid()
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise RuntimeError("openat nofollow/directory capability unavailable")
    if pwd.getpwuid(uid).pw_name != owner:
        raise RuntimeError("unauthorized tenant identity")

    hfd = _home_fd(home, uid)
    try:
        rootfd = _fd_dir(hfd, "mojplaywin.com", uid=uid)
        try:
            propfd = _fd_dir(rootfd, "moj-prop", uid=uid)
            try:
                catfd = _fd_dir(propfd, "catalog", uid=uid)
                try:
                    source_dirs = (propfd, catfd)
                    originals = tuple(_read(fd, "index.html", uid) for fd in source_dirs)
                    need = 3 * sum(map(len, originals)) + 8 * 4096
                    acceptable = (quota_probe(hfd, owner, need) if quota_probe
                                  else _quota_evidence(hfd, owner, need))
                    if acceptable is not True:
                        raise RuntimeError("tenant quota not independently established")
                    # Pin the vault fd BEFORE any write; renamed/symlinked
                    # pathnames cannot redirect mkdir/openat to a live site.
                    # Consume authorization in tenant HOME, outside the
                    # swappable vault name. O_EXCL + fsync(home descriptor)
                    # makes the marker durable across process/crash replay.
                    _write(hfd, ".mojprop-c28-approval-" + approval_id + ".used", b"CONSUMED\n")
                    os.fsync(hfd)
                    vfd = _mkdir(hfd, ".mojprop-static-restore-evidence", uid)
                    try:
                        runfd = None
                        bfd = None
                        restorefd = None
                        completed = False
                        try:
                            runfd = _mkdir(vfd, run_id, uid, unique=True)
                            bfd = _mkdir(runfd, "backup", uid, unique=True)
                            restorefd = _mkdir(runfd, "isolated-restore", uid, unique=True)
                            checksums = {}
                            created_entries = []
                            for i, body in enumerate(originals):
                                name = "file-" + str(i) + ".bin"
                                identity = _write(bfd, name, body)
                                created_entries.append((bfd, name, identity))
                                persisted = _read(bfd, name, uid)
                                if persisted != body:
                                    raise RuntimeError("source backup mismatch")
                                identity = _write(restorefd, name, persisted)
                                created_entries.append((restorefd, name, identity))
                                restored = _read(restorefd, name, uid)
                                digest = hashlib.sha256(body).hexdigest()
                                if hashlib.sha256(restored).hexdigest() != digest:
                                    raise RuntimeError("restore digest mismatch")
                                # Relative to pinned source *directory handles*;
                                # no path-based read following replaced ancestor.
                                if hashlib.sha256(_read(source_dirs[i], "index.html", uid)).hexdigest() != digest:
                                    raise RuntimeError("public source changed")
                                checksums[name] = digest
                            manifest = {"schema": "mojprop.static.restore.evidence.v2",
                                        "run_id": run_id, "approval_id": approval_id,
                                        "sha256": checksums,
                                        "isolated_two_file_restore": True,
                                        "live_files_modified": False,
                                        "db_backup_or_restore": False,
                                        "tenant_isolation_proven": False,
                                        "release_permitted": False,
                                        "payment_permitted": False}
                            identity = _write(runfd, "manifest.json", json.dumps(manifest, sort_keys=True).encode())
                            created_entries.append((runfd, "manifest.json", identity))
                            completed = True
                        finally:
                            if not completed and runfd is not None:
                                # Reclaim ONLY files whose exclusive creation
                                # returned a particular inode identity. A file
                                # injected after directory creation but before
                                # our O_EXCL is never eligible for deletion.
                                for child_fd, filename, identity in reversed(locals().get("created_entries", [])):
                                    try:
                                        current = os.stat(filename, dir_fd=child_fd, follow_symlinks=False)
                                    except FileNotFoundError:
                                        continue
                                    if stat.S_ISREG(current.st_mode) and (
                                            current.st_dev, current.st_ino) == identity:
                                        os.unlink(filename, dir_fd=child_fd)
                                    else:
                                        raise RuntimeError("private partial file replaced; cannot clean safely")
                            if restorefd is not None:
                                os.close(restorefd)
                            if bfd is not None:
                                os.close(bfd)
                            if not completed and runfd is not None:
                                for child in ("backup", "isolated-restore"):
                                    try:
                                        os.rmdir(child, dir_fd=runfd)
                                    except FileNotFoundError:
                                        pass
                                os.rmdir(run_id, dir_fd=vfd)
                            if runfd is not None:
                                os.close(runfd)
                    finally:
                        os.close(vfd)
                finally:
                    os.close(catfd)
            finally:
                os.close(propfd)
        finally:
            os.close(rootfd)
    finally:
        os.close(hfd)
    return {"schema": "mojprop.static.restore.evidence.v2", "private_file_backup_count": 2,
            "isolated_two_file_restore": True, "live_files_modified": False,
            "database_backup_or_restore": False, "all_site_backup_proven": False,
            "subsite_isolation_proven": False, "release_permitted": False,
            "payment_permitted": False, "revenue_proven": False}


def main() -> int:
    try:
        report = audit_and_restore(run_id=sys.argv[1], approval_id=sys.argv[2])
    except (IndexError, OSError, ValueError, RuntimeError, KeyError) as error:
        print(json.dumps({"schema": "mojprop.static.restore.evidence.v2",
                          "error_class": type(error).__name__,
                          "isolated_two_file_restore": False, "release_permitted": False,
                          "payment_permitted": False}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
