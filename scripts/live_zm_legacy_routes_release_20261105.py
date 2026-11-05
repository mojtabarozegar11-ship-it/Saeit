#!/usr/bin/env python3
"""Atomic, reversible canonical redirects for three verified legacy routes."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from pathlib import Path


HOME = Path('/home/zomorod2')
TARGET = HOME / 'public_html/.htaccess'
BACKUPS = HOME / '.private/route-repair-backups'
BEFORE = '167b8a216011830d38243cc45f66d1c821b521b6fd3adcf7637e88d4921f3458'
MARKER = 'ZM-LEGACY-ROUTE-CANONICAL-20261105'
RULES = (
    '\n# ' + MARKER + ' -- only proven legacy URLs; keep existing working targets\n'
    'RewriteRule ^auction/?$ /auctions/ [R=301,L,NC,NE]\n'
    'RewriteRule ^economic-reports/?$ /economy/ [R=301,L,NC,NE]\n'
    'RewriteRule ^ai/?$ /agents/ [R=301,L,NC,NE]\n'
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guard() -> bytes:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('CPANEL_USER_MISMATCH')
    if HOME.is_symlink() or TARGET.is_symlink() or TARGET.parent.is_symlink():
        raise RuntimeError('SYMLINK_TARGET_REFUSED')
    if not TARGET.is_file() or not BACKUPS.parent.is_dir():
        raise RuntimeError('ROUTE_FILE_OR_PRIVATE_BACKUP_ROOT_MISSING')
    data = TARGET.read_bytes()
    if sha(data) != BEFORE:
        raise RuntimeError('LIVE_ROUTING_SHA_DRIFT')
    return data


def patched(data: bytes) -> bytes:
    text = data.decode('utf-8')
    if MARKER in text:
        raise RuntimeError('ROUTES_ALREADY_FIXED')
    anchors = list(re.finditer(r'(?mi)^RewriteEngine\s+On\s*$', text))
    if len(anchors) != 1:
        raise RuntimeError('APACHE_REWRITE_ENGINE_ANCHOR_CHANGED')
    for pattern in (r'\^auction/\?', r'\^economic-reports/\?', r'\^ai/\?'):
        if re.search(pattern, text):
            raise RuntimeError('EXISTING_LEGACY_RULE_NEEDS_MANUAL_REVIEW')
    at = anchors[0].end()
    return (text[:at] + RULES + text[at:]).encode('utf-8')


def write_atomic(data: bytes, mode: int) -> None:
    fd, path = tempfile.mkstemp(prefix='.zm-route-release-', dir=TARGET.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if TARGET.is_symlink() or not TARGET.is_file():
            raise RuntimeError('TARGET_CHANGED_BEFORE_ATOMIC_REPLACE')
        os.replace(path, TARGET)
    finally:
        Path(path).unlink(missing_ok=True)


def destination(run: str) -> Path:
    if not re.fullmatch(r'[0-9]{9,20}', run):
        raise RuntimeError('INVALID_RUN_ID')
    return BACKUPS / ('run-' + run)


def preview() -> None:
    data = guard()
    new = patched(data)
    print('ZM_ROUTE_PREVIEW=' + json.dumps({'before': sha(data), 'after': sha(new),
                                           'added_bytes': len(new) - len(data),
                                           'redirects': 3, 'old_paths': ['/auction/', '/economic-reports/', '/ai/']}))


def publish(run: str) -> None:
    data = guard()
    new = patched(data)
    bdir = destination(run)
    if bdir.exists() or bdir.is_symlink():
        raise RuntimeError('BACKUP_COLLISION')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    bdir.mkdir(mode=0o700)
    bfile = bdir / 'original.htaccess'
    with bfile.open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    mode = stat.S_IMODE(TARGET.stat().st_mode)
    manifest = {'run': run, 'before': sha(data), 'after': sha(new), 'mode': mode}
    m = bdir / 'manifest.json'
    with m.open('x') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(json.dumps(manifest))
        stream.flush()
        os.fsync(stream.fileno())
    if sha(TARGET.read_bytes()) != BEFORE:
        raise RuntimeError('CONCURRENT_ROUTING_CHANGE')
    write_atomic(new, mode)
    if sha(TARGET.read_bytes()) != sha(new):
        raise RuntimeError('POSTWRITE_MISMATCH')
    print('ZM_ROUTE_PUBLISHED=' + json.dumps({'run': run, 'redirects': 3,
                                             'backed_up': True, 'db_or_payments_changed': False}))


def rollback(run: str) -> None:
    bdir = destination(run)
    if not bdir.is_dir() or bdir.is_symlink():
        raise RuntimeError('BACKUP_MISSING')
    meta = json.loads((bdir / 'manifest.json').read_text())
    old = (bdir / 'original.htaccess').read_bytes()
    if meta['run'] != run or sha(old) != BEFORE or meta['before'] != BEFORE:
        raise RuntimeError('BACKUP_FAILED_CHECKSUM')
    if TARGET.is_symlink() or sha(TARGET.read_bytes()) not in (BEFORE, meta['after']):
        raise RuntimeError('CONCURRENT_CHANGE_PREVENTS_ROLLBACK')
    if sha(TARGET.read_bytes()) == meta['after']:
        write_atomic(old, meta['mode'])
    print('ZM_ROUTE_ROLLBACK=RESTORED')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'preview':
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise SystemExit('USAGE: preview | publish RUN_ID | rollback RUN_ID')
