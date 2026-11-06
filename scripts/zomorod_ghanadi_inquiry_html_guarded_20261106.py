#!/usr/bin/env python3
"""Guarded release of ONLY the Ghanadi landing page, with private rollback.

This code is packed with the reviewed HTML in GitHub Actions and executed as
the existing unprivileged cPanel account. It never changes any other page,
database, PHP engine, or subsite.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

HTML_BASE64 = None  # Packed with the exact reviewed HTML by GitHub Actions.
ORIGINAL_SHA = '32361747bb8bacc0f3098dd6420406a4ece73d78d564c815e07a9ae7d11650f2'
HOME = Path('/home/zomorod2')
TARGET = HOME / 'public_html/ghanadi/index.html'
BACKUP_ROOT = HOME / '.backups/ghanadi-inquiry-20261106'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate() -> bytes:
    if not isinstance(HTML_BASE64, str):
        raise RuntimeError('HTML_RELEASE_NOT_PACKED')
    data = base64.b64decode(HTML_BASE64, validate=True)
    if not (b'<form id="inquiryPanel"' in data and
            b'/ask-master/index.php?service=1' in data and
            b'csrf_missing' in data and
            b"submission.submit();" in data and
            b'<input id="inquiryEmail"' in data):
        raise RuntimeError('HTML_RELEASE_CONTRACT_INVALID')
    if not 15000 < len(data) < 200000:
        raise RuntimeError('HTML_SIZE_INVALID')
    return data


def host_guard() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError('CPANEL_ACCOUNT_MISMATCH')
    for path in (HOME / 'public_html', TARGET.parent, TARGET):
        if path.is_symlink() or not path.exists():
            raise RuntimeError('TARGET_MISSING_OR_SYMLINK:' + str(path))
    if not TARGET.is_file() or not os.access(TARGET.parent, os.W_OK):
        raise RuntimeError('TARGET_NOT_REGULAR_WRITABLE_FILE')


def private_backup(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{6,20}', run_id):
        raise RuntimeError('INVALID_RELEASE_ID')
    return BACKUP_ROOT / run_id / 'index.html.original'


def atomic_replace(data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=TARGET.parent, prefix='.zm-ghanadi-', delete=False) as f:
            temporary = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, TARGET)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def public_matches(expected: str) -> bool:
    request = Request(
        'https://zomorodmelal.ir/ghanadi/?zm_ghanadi_guard=' + str(time.time_ns()),
        headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache',
                 'User-Agent': 'ZM-Ghanadi-Guarded-Release/1.0'},
    )
    with urlopen(request, timeout=18) as response:
        return response.status == 200 and digest(response.read(200_001)) == expected


def main(mode: str, run_id: str) -> None:
    desired = candidate()
    desired_sha = digest(desired)
    if mode == 'selftest':
        if desired_sha == ORIGINAL_SHA:
            raise RuntimeError('RELEASE_HAS_NO_DIFFERENCE')
        print('GHANADI_HTML_SOURCE_VALID=' + desired_sha)
        return

    host_guard()
    backup = private_backup(run_id)
    before = TARGET.read_bytes()
    if mode == 'preview':
        if digest(before) != ORIGINAL_SHA or backup.exists():
            raise RuntimeError('LIVE_BASELINE_CHANGED_ABORT')
        print('GHANADI_SINGLE_FILE_PREFLIGHT=READY')
    elif mode == 'publish':
        if digest(before) != ORIGINAL_SHA or backup.exists():
            raise RuntimeError('LIVE_BASELINE_CHANGED_ABORT')
        backup.parent.mkdir(parents=True, mode=0o700, exist_ok=False)
        with backup.open('xb') as f:
            f.write(before)
            f.flush()
            os.fsync(f.fileno())
        backup.chmod(0o600)
        atomic_replace(desired)
        if digest(TARGET.read_bytes()) != desired_sha:
            raise RuntimeError('ORIGIN_PUBLISHED_HASH_MISMATCH')
        print('GHANADI_SINGLE_FILE_PUBLISHED=' + desired_sha)
    elif mode == 'verify':
        if not backup.is_file() or digest(backup.read_bytes()) != ORIGINAL_SHA:
            raise RuntimeError('ROLLBACK_BACKUP_NOT_VERIFIED')
        if digest(before) != desired_sha:
            raise RuntimeError('ORIGIN_HTML_NOT_UPDATED')
        for attempt in range(6):
            try:
                if public_matches(desired_sha):
                    print('GHANADI_PUBLIC_HTML_VERIFIED=' + desired_sha)
                    return
            except Exception:
                pass
            if attempt < 5:
                time.sleep(4)
        raise RuntimeError('PUBLIC_HTML_NOT_UPDATED')
    elif mode == 'rollback':
        if not backup.is_file() or digest(backup.read_bytes()) != ORIGINAL_SHA:
            raise RuntimeError('ORIGINAL_BACKUP_UNAVAILABLE')
        if digest(before) != desired_sha:
            raise RuntimeError('CONCURRENT_CHANGE_REFUSE_ROLLBACK')
        atomic_replace(backup.read_bytes())
        if digest(TARGET.read_bytes()) != ORIGINAL_SHA:
            raise RuntimeError('ROLLBACK_HASH_MISMATCH')
        print('GHANADI_SINGLE_FILE_ROLLED_BACK=' + ORIGINAL_SHA)
    else:
        raise RuntimeError('UNRECOGNIZED_RELEASE_MODE')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('USAGE: release.py selftest|preview|publish|verify|rollback RUN_ID')
    main(sys.argv[1], sys.argv[2])
