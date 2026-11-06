#!/usr/bin/env python3
"""Single-file cPanel release with exact live SHA guard and retained rollback.

The runner injects public/mohammad/app.js as base64; this script then runs
under the existing zomorod2 account. It never writes the site's HTML, PHP,
Passenger configuration, database or any other subsite file.
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

JS_BASE64 = None  # Replaced with the exact reviewed JS bytes on the runner.
ORIGINAL_SHA = '2d365f372abe8405a9afb196e64ec097c3b571c72438b8c655fbe46d0c9c874e'
HOME = Path('/home/zomorod2')
TARGET = HOME / 'public_html/mohammad/app.js'
BACKUP_ROOT = HOME / '.backups/mohammad-inquiry-js-20261106'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content() -> bytes:
    if not isinstance(JS_BASE64, str):
        raise RuntimeError('JS_RELEASE_CONTENT_NOT_PACKED')
    data = base64.b64decode(JS_BASE64, validate=True)
    if not (b'/ask-master/index.php' in data and b'csrf_missing' in data and
            b'response_format' not in data and b'new Blob(' not in data):
        raise RuntimeError('JS_RELEASE_CONTRACT_INVALID')
    return data


def guard_host() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError('CPANEL_ACCOUNT_MISMATCH')
    for path in (HOME / 'public_html', TARGET.parent, TARGET):
        if path.is_symlink() or not path.exists():
            raise RuntimeError('RELEASE_TARGET_MISSING_OR_SYMLINK:' + str(path))
    if not TARGET.is_file() or not os.access(TARGET.parent, os.W_OK):
        raise RuntimeError('TARGET_NOT_REGULAR_WRITABLE_FILE')


def backup_path(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{6,20}', run_id):
        raise RuntimeError('INVALID_RELEASE_ID')
    return BACKUP_ROOT / run_id / 'app.js.original'


def replace(data: bytes) -> None:
    filename = None
    try:
        with tempfile.NamedTemporaryFile(dir=TARGET.parent, prefix='.zm-inquiry-', delete=False) as handle:
            filename = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(filename, 0o644)
        os.replace(filename, TARGET)
        filename = None
    finally:
        if filename and os.path.exists(filename):
            os.unlink(filename)


def live_matches(expected: str) -> bool:
    url = 'https://zomorodmelal.ir/mohammad/app.js?zm_js_guard=' + str(time.time_ns())
    request = Request(url, headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache',
                                   'User-Agent': 'ZM-Mohammad-Single-File-Release/1.0'})
    with urlopen(request, timeout=18) as response:
        return response.status == 200 and digest(response.read(100_000)) == expected


def main(mode: str, run_id: str) -> None:
    candidate = content()
    desired = digest(candidate)
    if mode == 'selftest':
        if desired == ORIGINAL_SHA:
            raise RuntimeError('NO_RELEASE_CHANGE')
        print('JS_SOURCE_VALID=' + desired)
        return
    guard_host()
    previous = backup_path(run_id)
    before = TARGET.read_bytes()
    if mode == 'preview':
        if digest(before) != ORIGINAL_SHA or previous.exists():
            raise RuntimeError('LIVE_BASELINE_CHANGED_ABORT')
        print('JS_SINGLE_FILE_PREFLIGHT=READY')
    elif mode == 'publish':
        if digest(before) != ORIGINAL_SHA or previous.exists():
            raise RuntimeError('LIVE_BASELINE_CHANGED_ABORT')
        previous.parent.mkdir(parents=True, mode=0o700, exist_ok=False)
        with previous.open('xb') as saved:
            saved.write(before)
            saved.flush()
            os.fsync(saved.fileno())
        previous.chmod(0o600)
        replace(candidate)
        if digest(TARGET.read_bytes()) != desired:
            raise RuntimeError('PUBLISHED_SHA_MISMATCH')
        print('JS_SINGLE_FILE_PUBLISHED=' + desired)
    elif mode == 'verify':
        if not previous.is_file() or digest(previous.read_bytes()) != ORIGINAL_SHA:
            raise RuntimeError('ROLLBACK_BACKUP_NOT_VERIFIED')
        if digest(before) != desired:
            raise RuntimeError('ORIGIN_JS_NOT_UPDATED')
        for attempt in range(6):
            try:
                if live_matches(desired):
                    print('JS_SINGLE_FILE_LIVE_VERIFIED=' + desired)
                    return
            except Exception:
                pass
            if attempt < 5:
                time.sleep(4)
        raise RuntimeError('PUBLIC_JS_NOT_UPDATED')
    elif mode == 'rollback':
        if not previous.is_file() or digest(previous.read_bytes()) != ORIGINAL_SHA:
            raise RuntimeError('ORIGINAL_BACKUP_UNAVAILABLE')
        if digest(before) != desired:
            raise RuntimeError('CONCURRENT_CHANGE_REFUSE_ROLLBACK')
        replace(previous.read_bytes())
        if digest(TARGET.read_bytes()) != ORIGINAL_SHA:
            raise RuntimeError('ROLLBACK_SHA_MISMATCH')
        print('JS_SINGLE_FILE_ROLLED_BACK=' + ORIGINAL_SHA)
    else:
        raise RuntimeError('UNRECOGNIZED_MODE')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('USAGE: release.py selftest|preview|publish|verify|rollback RUN_ID')
    main(sys.argv[1], sys.argv[2])
