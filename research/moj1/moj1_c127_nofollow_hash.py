#!/usr/bin/env python3
"""Offline, read-only, fail-closed file SHA256 verifier for a frozen checkout.
Candidate handoff to F owner; not a contract security audit or release approval.
POSIX-only. Path lookup is anchored to a real directory descriptor.
Root ancestor replacement races require a stronger trusted-checkout boundary.
"""
import hashlib
import os
import pathlib
import re
import stat

HEX64 = re.compile(r'^[0-9a-f]{64}$')

def checked_hash(root, entry):
    if not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        raise ValueError('platform lacks nofollow directory opens')
    if not isinstance(entry, dict):
        raise ValueError('manifest entry must be an object')
    rel, expected = entry.get('path'), entry.get('sha256')
    if not isinstance(rel, str) or not rel or '\\' in rel or rel.startswith('/'):
        raise ValueError('invalid relative path')
    parts = rel.split('/')
    if any(x in ('', '.', '..') for x in parts):
        raise ValueError('noncanonical relative path')
    if not isinstance(expected, str) or not HEX64.fullmatch(expected):
        raise ValueError('invalid lowercase sha256')
    root = pathlib.Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('symlinked checkout root or ancestor')
    descriptors = []
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        for part in parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0), dir_fd=fd)
        descriptors.append(fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('not a regular file')
        h = hashlib.sha256()
        with os.fdopen(os.dup(fd), 'rb', closefd=True) as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(block)
        if h.hexdigest() != expected:
            raise ValueError('digest mismatch')
        return rel
    except OSError as exc:
        raise ValueError(f'unsafe or unreadable path: {exc.strerror}') from exc
    finally:
        for fd in reversed(descriptors):
            os.close(fd)
