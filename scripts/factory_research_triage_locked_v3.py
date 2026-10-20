#!/usr/bin/env python3
"""Non-overlapping private research triage entry point for V3.

This wrapper calls the existing evidence triage; it never changes factory
approval, store listings, payments, or the production scheduler.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import stat

from factory_research_triage import snapshot


def locked_snapshot(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("V3_TRIAGE_ROOT_UNSAFE")
    ledger = root / "research-rework"
    if ledger.is_symlink() or not ledger.is_dir():
        raise RuntimeError("V3_TRIAGE_LEDGER_UNSAFE")
    inbox = root / "research-triage"
    if inbox.is_symlink():
        raise RuntimeError("V3_TRIAGE_INBOX_SYMLINK")
    inbox.mkdir(mode=0o700, exist_ok=True)
    if inbox.is_symlink() or not inbox.is_dir():
        raise RuntimeError("V3_TRIAGE_INBOX_UNSAFE")
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("V3_TRIAGE_NOFOLLOW_UNAVAILABLE")
    lock = inbox / ".v3-research-triage.lock"
    if lock.is_symlink():
        raise RuntimeError("V3_TRIAGE_LOCK_SYMLINK")
    fd = os.open(str(lock), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a+b") as mutex:
        if not stat.S_ISREG(os.fstat(mutex.fileno()).st_mode):
            raise RuntimeError("V3_TRIAGE_LOCK_NOT_REGULAR")
        os.fchmod(mutex.fileno(), 0o600)
        try:
            fcntl.flock(mutex.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("V3_TRIAGE_ALREADY_RUNNING") from exc
        return snapshot(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = locked_snapshot(args.out)
    print("V3_PRIVATE_RESEARCH_TRIAGE=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
