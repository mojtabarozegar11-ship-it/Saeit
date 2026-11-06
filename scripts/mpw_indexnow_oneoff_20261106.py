#!/usr/bin/env python3
"""Publish one IndexNow domain ownership TXT for one changed public URL.

No user, lead, checkout or payment data is accessed. This is a one-time
verification file, not a persistent scheduler or a new application runtime.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import sys


ROOT = Path('/home/zomorod2/mojplaywin.com')
KEY = 'fa0cd1f147d5dc00d1e02b5f8d2f8c94'
TARGET = ROOT / (KEY + '.txt')
AUDIT = Path('/home/zomorod2/.local/share/mpw-indexnow-oneoff')
PAYLOAD = (KEY + '\n').encode('ascii')


def guard() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('Unexpected hosting account')
    if ROOT.is_symlink() or ROOT.resolve() != ROOT or not ROOT.is_dir():
        raise RuntimeError('Unexpected MojPlayWin document root')
    if ROOT.stat().st_uid != os.geteuid():
        raise RuntimeError('Document root owner mismatch')
    if AUDIT.is_symlink() or AUDIT.parent.is_symlink() or TARGET.is_symlink():
        raise RuntimeError('Unsafe verification path')


def marker_path(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{8,20}', run_id):
        raise RuntimeError('Invalid release id')
    return AUDIT / (run_id + '.marker')


def run(operation: str, run_id: str = '') -> None:
    if operation == 'selftest':
        assert len(KEY) == 32 and all(c in '0123456789abcdef' for c in KEY)
        assert TARGET.name == KEY + '.txt' and PAYLOAD.strip().decode() == KEY
        print('MPW_INDEXNOW_SELFTEST=PASS')
        return
    guard()
    if operation == 'preflight':
        if TARGET.exists() or TARGET.is_symlink():
            raise RuntimeError('An IndexNow file already exists at this exact target')
        print('MPW_INDEXNOW_PREFLIGHT=PASS')
        return
    marker = marker_path(run_id)
    if operation == 'publish':
        if TARGET.exists() or TARGET.is_symlink():
            raise RuntimeError('Existing key file must not be overwritten')
        AUDIT.mkdir(parents=True, mode=0o700, exist_ok=True)
        if stat.S_IMODE(AUDIT.stat().st_mode) != 0o700:
            raise RuntimeError('Private audit folder mode invalid')
        if marker.exists() or marker.is_symlink():
            raise RuntimeError('Release id has already been used')
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write((hashlib.sha256(PAYLOAD).hexdigest() + '\n').encode())
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(PAYLOAD)
            stream.flush()
            os.fsync(stream.fileno())
        if TARGET.read_bytes() != PAYLOAD:
            raise RuntimeError('Verification file content mismatch')
        print('MPW_INDEXNOW_PUBLISHED=PASS')
        return
    if operation == 'rollback':
        if not marker.is_file() or marker.is_symlink():
            raise RuntimeError('No release marker found')
        if not TARGET.is_file() or TARGET.is_symlink() or TARGET.read_bytes() != PAYLOAD:
            raise RuntimeError('Verification file changed; refusing cleanup')
        if marker.read_text().strip() != hashlib.sha256(PAYLOAD).hexdigest():
            raise RuntimeError('Private release marker invalid')
        TARGET.unlink()
        print('MPW_INDEXNOW_ROLLBACK=PASS')
        return
    raise RuntimeError('Expected selftest, preflight, publish or rollback')


if __name__ == '__main__':
    run(*sys.argv[1:])
