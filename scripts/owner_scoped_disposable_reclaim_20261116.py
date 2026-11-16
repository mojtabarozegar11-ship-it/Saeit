#!/usr/bin/env python3
"""One-shot, fail-closed production disk reclamation of strictly disposable targets.

Only the two hard-coded owner accounts are supported. No database, backup, live
application, cron, package installation or service is modified. The tool reports
measured bytes and exits nonzero on any ambiguity; --apply requires a separate
workflow-provided one-use environment permit.
"""
import argparse
import fcntl
import hashlib
import os
import pwd
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

VPS_UID_NAME = "githubops"
HOST_UID_NAME = "zomorod2"
AGE_SECONDS = 14 * 86400
VPS_PREFIXES = (".qa1000-supply-", ".stage4-readonly-", ".factory-audit-")
SAFE_EXTENSIONS = (".tmp", ".temp", ".log", ".pyc")
CPANEL_ARCHIVE_SIZE = (40_000_000, 80_000_000)
CPANEL_ARCHIVE_REL = ".cache/dc-node-setup/node.tar.gz"


def die(tag):
    raise SystemExit("DISK_CLEANUP_STOP=" + tag)


def owner_dir(path, uid):
    if path.is_symlink() or not path.is_dir():
        die("ROOT_NOT_PLAIN_DIRECTORY")
    meta = path.lstat()
    if meta.st_uid != uid or not stat.S_ISDIR(meta.st_mode):
        die("ROOT_WRONG_OWNER")
    return meta


def free_bytes(path):
    s = os.statvfs(path)
    return s.f_bavail * s.f_frsize


def process_references(uid, candidates):
    """Reject a target referenced by any owner process; fail closed on unreadable proc."""
    candidates = [str(p) for p in candidates]
    if not candidates:
        return False
    errors = 0
    references = False
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != uid:
                continue
        except FileNotFoundError:
            continue
        except OSError:
            errors += 1
            continue
        links = []
        for part in ("cwd", "exe"):
            try:
                links.append(os.readlink(proc / part))
            except FileNotFoundError:
                pass
            except OSError:
                errors += 1
        try:
            fds = list((proc / "fd").iterdir())
        except FileNotFoundError:
            fds = []
        except OSError:
            errors += 1
            fds = []
        for fd in fds:
            try:
                links.append(os.readlink(fd))
            except FileNotFoundError:
                pass
            except OSError:
                errors += 1
        for ref in links:
            if any(ref == p or ref.startswith(p + "/") or ref.startswith(p + " (deleted)") for p in candidates):
                references = True
    if errors:
        die("PROCESS_VISIBILITY_INCOMPLETE")
    return references


def command_references(uid, candidates):
    """Check cron AND process argv, in addition to cwd and fd references."""
    cron = subprocess.run(["crontab", "-l"], text=True, capture_output=True, timeout=15)
    if cron.returncode and "no crontab for" not in cron.stderr.lower():
        die("CRON_NOT_READABLE")
    ps = subprocess.run(["ps", "-u", str(uid), "-o", "args="],
                        text=True, capture_output=True, timeout=15)
    if ps.returncode:
        die("PROCESS_ARGS_NOT_READABLE")
    combined = cron.stdout + "\n" + ps.stdout
    return any(str(p) in combined or p.name in combined for p in candidates)


def safe_tree(path, uid, root_dev):
    count = 0
    size = 0
    for base, dirs, files in os.walk(path, topdown=True, followlinks=False):
        for name in list(dirs) + files:
            entry = Path(base) / name
            s = entry.lstat()
            if s.st_uid != uid or s.st_dev != root_dev or s.st_nlink != 1:
                return None
            if stat.S_ISLNK(s.st_mode):
                return None
            if stat.S_ISDIR(s.st_mode):
                continue
            if not stat.S_ISREG(s.st_mode):
                return None
            if (not name.endswith(SAFE_EXTENSIONS)
                    or any(marker in name.lower() for marker in
                           ("backup", "database", "payment", "invoice", "secret", "key", "order", "receipt"))):
                return None
            count += 1
            size += s.st_size
            if count > 3000 or size > 2_000_000_000:
                return None
    return count, size


def reclaim_vps(apply):
    if pwd.getpwuid(os.geteuid()).pw_name != VPS_UID_NAME:
        die("VPS_IDENTITY")
    home = Path("/home/githubops")
    root = home / "factory-runtime"
    ops = root / "operations"
    root_meta = owner_dir(root, os.geteuid())
    owner_dir(ops, os.geteuid())
    lock_path = ops / "master-agent" / "activation.lock"
    if lock_path.is_symlink() or not lock_path.is_file() or lock_path.stat().st_uid != os.geteuid():
        die("EXISTING_FACTORY_LOCK_NOT_VERIFIED")
    # Open existing lock without creating or truncating it.
    with lock_path.open("rb") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            die("FACTORY_LOCK_BUSY")
        before = free_bytes(root)
        cutoff = time.time() - AGE_SECONDS
        approved = []
        total_logical = 0
        skipped = 0
        for path in ops.iterdir():
            if not path.name.startswith(VPS_PREFIXES):
                continue
            if path.is_symlink() or not path.is_dir():
                skipped += 1
                continue
            st = path.lstat()
            if st.st_uid != os.geteuid() or st.st_dev != root_meta.st_dev or st.st_mtime >= cutoff:
                skipped += 1
                continue
            scanned = safe_tree(path, os.geteuid(), root_meta.st_dev)
            if scanned is None:
                skipped += 1
                continue
            if command_references(os.geteuid(), [path]) or process_references(os.geteuid(), [path]):
                skipped += 1
                continue
            if st.st_ino != path.lstat().st_ino:
                die("VPS_TARGET_CHANGED")
            approved.append((path, st.st_ino))
            total_logical += scanned[1]
        print("VPS_DISPOSABLE_CANDIDATES=" + str(len(approved)), flush=True)
        print("VPS_SKIPPED_UNVERIFIED=" + str(skipped), flush=True)
        print("VPS_DISPOSABLE_LOGICAL_BYTES=" + str(total_logical), flush=True)
        print("VPS_FREE_BYTES_BEFORE=" + str(before), flush=True)
        completed = 0
        if apply:
            for path, inode in approved:
                if path.is_symlink() or path.lstat().st_ino != inode:
                    die("VPS_TARGET_RACE")
                if command_references(os.geteuid(), [path]) or process_references(os.geteuid(), [path]):
                    die("VPS_REFERENCED_DURING_DELETE")
                if safe_tree(path, os.geteuid(), root_meta.st_dev) is None:
                    die("VPS_CONTENT_CHANGED")
                shutil.rmtree(path)
                completed += 1
        after = free_bytes(root)
        print("VPS_CLEANUP_APPLIED=" + str(apply).lower(), flush=True)
        print("VPS_DISPOSABLE_REMOVED_COUNT=" + str(completed), flush=True)
        print("VPS_FREE_BYTES_AFTER=" + str(after), flush=True)
        print("VPS_BACKUPS_DATABASES_SERVICES_UNTOUCHED=true", flush=True)
        return 0


def reclaim_cpanel(apply):
    if pwd.getpwuid(os.geteuid()).pw_name != HOST_UID_NAME:
        die("CPANEL_IDENTITY")
    uid = os.geteuid()
    home = Path("/home/zomorod2")
    owner_dir(home, uid)
    cache = home / ".cache"
    leaf = cache / "dc-node-setup"
    owner_dir(cache, uid)
    owner_dir(leaf, uid)
    archive = home / CPANEL_ARCHIVE_REL
    before = free_bytes(home)
    print("CPANEL_FREE_BYTES_BEFORE=" + str(before), flush=True)
    if not archive.exists():
        print("CPANEL_DISPOSABLE_ARCHIVE=ALREADY_ABSENT", flush=True)
        print("CPANEL_CLEANUP_APPLIED=false", flush=True)
        print("CPANEL_BACKUPS_DATABASES_SERVICES_UNTOUCHED=true", flush=True)
        return 0
    s = archive.lstat()
    if (not stat.S_ISREG(s.st_mode) or s.st_uid != uid or s.st_nlink != 1
            or not CPANEL_ARCHIVE_SIZE[0] <= s.st_size <= CPANEL_ARCHIVE_SIZE[1]
            or time.time() - s.st_mtime < 72 * 3600):
        die("CPANEL_ARCHIVE_UNVERIFIED")
    checksum = leaf / "SHASUMS256.txt"
    if (checksum.is_symlink() or not checksum.is_file() or
            checksum.stat().st_uid != uid):
        die("CPANEL_DOWNLOAD_CHECKSUM_MISSING")
    if command_references(uid, [archive]) or process_references(uid, [archive]):
        die("CPANEL_ARCHIVE_IN_USE")
    print("CPANEL_DISPOSABLE_ARCHIVE_BYTES=" + str(s.st_size), flush=True)
    if apply:
        current = archive.lstat()
        if current.st_ino != s.st_ino or current.st_size != s.st_size:
            die("CPANEL_ARCHIVE_CHANGED")
        if command_references(uid, [archive]) or process_references(uid, [archive]):
            die("CPANEL_ARCHIVE_REOPENED")
        archive.unlink()
    print("CPANEL_CLEANUP_APPLIED=" + str(apply).lower(), flush=True)
    print("CPANEL_FREE_BYTES_AFTER=" + str(free_bytes(home)), flush=True)
    print("CPANEL_BACKUPS_DATABASES_SERVICES_UNTOUCHED=true", flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=("vps", "cpanel"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and os.environ.get("OWNER_ONE_USE_DISK_CLEANUP_PERMIT") != "20261116-VERIFIED-DISPOSABLE-ONLY":
        die("OWNER_PERMIT_REQUIRED")
    print("CLEANUP_TARGET=" + args.target, flush=True)
    print("CLEANUP_DATE_UTC=" + time.strftime("%Y-%m-%d", time.gmtime()), flush=True)
    if args.target == "vps":
        return reclaim_vps(args.apply)
    return reclaim_cpanel(args.apply)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        die("RUNTIME_CHECK_" + type(e).__name__)
