#!/usr/bin/env python3
"""Reversible search-index guard for the real public staging subdomain only."""

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
WEBROOT = HOME / 'Saeit-staging-web'
TARGET = WEBROOT / '.htaccess'
BACKUPS = HOME / '.private/staging-robots-backups'
MARKER = 'ZM-STAGING-NOINDEX-20261105'
BLOCK = (
    '# ' + MARKER + ' -- staging only; never apply to the public production site\n'
    '<IfModule mod_headers.c>\n'
    '    Header always set X-Robots-Tag "noindex, nofollow, noarchive"\n'
    '</IfModule>\n\n'
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guard() -> bytes:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('CPANEL_USER_MISMATCH')
    if WEBROOT.is_symlink() or not WEBROOT.is_dir() or TARGET.is_symlink() or not TARGET.is_file():
        raise RuntimeError('STAGING_ROOT_INVALID')
    if TARGET.parent != WEBROOT or not BACKUPS.parent.is_dir() or BACKUPS.parent.is_symlink():
        raise RuntimeError('STAGING_TARGET_OR_BACKUP_PARENT_CHANGED')
    old = TARGET.read_bytes()
    if not 100 <= len(old) <= 15000:
        raise RuntimeError('STAGING_HTACCESS_UNEXPECTED_SIZE')
    decoded = old.decode('utf-8')
    if 'PassengerAppRoot' not in decoded or 'Saeit-staging/' not in decoded:
        raise RuntimeError('STAGING_PASSENGER_ROUTING_UNEXPECTED')
    if MARKER in decoded or re.search(r'(?i)X-Robots-Tag', decoded):
        raise RuntimeError('ROBOTS_GUARD_ALREADY_PRESENT_OR_DIFFERENT')
    return old


def replacement(old: bytes) -> bytes:
    return BLOCK.encode('utf-8') + old


def write_atomic(data: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix='.staging-robots-', dir=WEBROOT)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if TARGET.is_symlink() or not TARGET.is_file():
            raise RuntimeError('STAGING_FILE_CHANGED_DURING_WRITE')
        os.replace(name, TARGET)
    finally:
        Path(name).unlink(missing_ok=True)


def run_folder(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{9,20}', run_id):
        raise RuntimeError('INVALID_RUN_ID')
    return BACKUPS / ('run-' + run_id)


def preview() -> None:
    before = guard()
    after = replacement(before)
    print('STAGING_ROBOTS_PREVIEW=' + json.dumps({
        'target': 'staging.zomorodmelal.ir only',
        'before_sha': sha(before), 'after_sha': sha(after),
        'header': 'X-Robots-Tag: noindex, nofollow, noarchive',
        'production_app_or_database_touched': False}))


def publish(run_id: str) -> None:
    old = guard()
    new = replacement(old)
    backup_dir = run_folder(run_id)
    if backup_dir.exists() or backup_dir.is_symlink():
        raise RuntimeError('STAGING_BACKUP_COLLISION')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    backup_dir.mkdir(mode=0o700)
    original = backup_dir / 'original.htaccess'
    with original.open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(old)
        stream.flush()
        os.fsync(stream.fileno())
    mode = stat.S_IMODE(TARGET.stat().st_mode)
    manifest = {'run': run_id, 'old_sha': sha(old), 'new_sha': sha(new), 'mode': mode}
    with (backup_dir / 'manifest.json').open('x') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(manifest, stream)
        stream.flush()
        os.fsync(stream.fileno())
    if sha(TARGET.read_bytes()) != sha(old):
        raise RuntimeError('CONCURRENT_STAGING_CONFIG_CHANGE')
    write_atomic(new, mode)
    if sha(TARGET.read_bytes()) != sha(new):
        raise RuntimeError('STAGING_ROBOTS_POSTWRITE_MISMATCH')
    print('STAGING_ROBOTS_PUBLISHED=' + json.dumps({
        'target': 'staging.zomorodmelal.ir', 'private_backup': True,
        'live_site_migrations': False, 'mail_or_payments_changed': False}))


def rollback(run_id: str) -> None:
    backup_dir = run_folder(run_id)
    if not backup_dir.is_dir() or backup_dir.is_symlink():
        raise RuntimeError('PRIVATE_STAGING_BACKUP_MISSING')
    meta = json.loads((backup_dir / 'manifest.json').read_text())
    old = (backup_dir / 'original.htaccess').read_bytes()
    if meta['run'] != run_id or sha(old) != meta['old_sha']:
        raise RuntimeError('BACKUP_CHECKSUM_FAILED')
    current = sha(TARGET.read_bytes())
    if current == meta['new_sha']:
        write_atomic(old, meta['mode'])
    elif current != meta['old_sha']:
        raise RuntimeError('CONCURRENT_CHANGE_PREVENTS_ROLLBACK')
    print('STAGING_ROBOTS_ROLLBACK=RESTORED')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'preview':
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise SystemExit('USAGE: preview | publish RUN_ID | rollback RUN_ID')
