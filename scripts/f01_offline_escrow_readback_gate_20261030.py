#!/usr/bin/env python3
"""Read-only local SHA-256 comparison of two separately supplied escrow files.

Does not touch VPS, decrypt files, certify off-host provenance or authorize factory
stop, cron changes, backup, restore, restart, deployment or any release.
"""
import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path

MAX_BYTES = 8 * 1024**3
HEX64 = re.compile(r"[0-9a-fA-F]{64}\Z")

class Blocked(Exception):
    pass


def digest_regular(path):
    # Walk each path component without following symlinks, including parents.
    parts = Path(os.path.abspath(path)).parts
    dirflags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    leaf_flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    parent = os.open('/', dirflags)
    try:
        for part in parts[1:-1]:
            nxt = os.open(part, dirflags, dir_fd=parent)
            os.close(parent)
            parent = nxt
        fd = os.open(parts[-1], leaf_flags, dir_fd=parent)
    finally:
        os.close(parent)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or not 32 <= meta.st_size <= MAX_BYTES:
            raise Blocked('UNSAFE_OR_INVALID_FILE')
        h = hashlib.sha256()
        with os.fdopen(fd, 'rb', closefd=False) as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
        after = os.fstat(fd)
        if (meta.st_dev, meta.st_ino, meta.st_size, meta.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise Blocked('FILE_CHANGED_DURING_HASH')
        return h.hexdigest(), (meta.st_dev, meta.st_ino), meta.st_size
    finally:
        os.close(fd)


def verify(escrow, readback, expected_sha256):
    if not isinstance(expected_sha256, str) or not HEX64.fullmatch(expected_sha256):
        raise Blocked('EXPECTED_SHA256_REQUIRED')
    try:
        a, aid, size = digest_regular(escrow)
        b, bid, readback_size = digest_regular(readback)
    except (OSError, ValueError) as exc:
        raise Blocked('INPUT_UNAVAILABLE_OR_LINKED') from exc
    if aid == bid:
        raise Blocked('SAME_FILE_NOT_INDEPENDENT_READBACK')
    if a != expected_sha256.lower() or b != a or size != readback_size:
        raise Blocked('HASH_OR_SIZE_MISMATCH')
    return {'schema':'f01.escrow.readback.v1','status':'TWO_LOCAL_COPIES_HASH_MATCH',
            'sha256':a,'bytes':size,'offhost_provenance_verified':False,
            'factory_stop_verified':False,'production_backup_verified':False,
            'deployment_authorized':False,'vps_mutation_performed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--escrow',required=True)
    p.add_argument('--readback',required=True)
    p.add_argument('--expected-sha256',required=True)
    args=p.parse_args()
    try:
        result=verify(args.escrow,args.readback,args.expected_sha256)
        code=0
    except Blocked as exc:
        result={'schema':'f01.escrow.readback.v1','status':'NO_GO','reason':str(exc),
                'offhost_provenance_verified':False,'factory_stop_verified':False,
                'production_backup_verified':False,'deployment_authorized':False,
                'vps_mutation_performed':False}
        code=2
    print(json.dumps(result,sort_keys=True))
    return code


if __name__=='__main__':
    raise SystemExit(main())
