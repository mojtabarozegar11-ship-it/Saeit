#!/usr/bin/env python3
"""Atomically route the public /apps/ URL to its already-live static index."""

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
ROUTING = HOME / 'public_html/.htaccess'
APP_INDEX = HOME / 'public_html/apps/index.html'
BACKUPS = HOME / '.private/route-repair-backups'
APP_INDEX_SHA = 'e264451f4567589a0abdacfa3a8cbf1787cb501f6124ec1a5eac04a85f4e25c6'
REQUIRED_LEGACY_MARKER = 'ZM-LEGACY-ROUTE-CANONICAL-20261105'
MARKER = 'ZM-APPS-HUB-INTERNAL-ROUTE-20261105'
NEW_RULE = '\n# ' + MARKER + '\nRewriteRule ^apps/?$ /apps/index.html [END,NC]\n'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guard() -> bytes:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('WRONG_CPANEL_USER')
    if ROUTING.is_symlink() or not ROUTING.is_file() or ROUTING.parent.is_symlink():
        raise RuntimeError('PUBLIC_ROUTING_TARGET_INVALID')
    if APP_INDEX.is_symlink() or not APP_INDEX.is_file():
        raise RuntimeError('PROVEN_LIVE_APP_HUB_MISSING')
    if digest(APP_INDEX.read_bytes()) != APP_INDEX_SHA:
        raise RuntimeError('LIVE_APP_HUB_CONTENT_CHANGED')
    original = ROUTING.read_bytes()
    text = original.decode('utf-8')
    if text.count(REQUIRED_LEGACY_MARKER) != 1:
        raise RuntimeError('EXPECTED_WORKING_LEGACY_REDIRECTS_NOT_FOUND')
    if MARKER in text or re.search(r'(?im)^\s*RewriteRule\s+\^apps', text):
        raise RuntimeError('APPS_ROUTE_ALREADY_EXISTS')
    if len(re.findall(r'(?im)^RewriteEngine\s+On\s*$', text)) != 3:
        raise RuntimeError('APACHE_ROUTING_STRUCTURE_DRIFT')
    return original


def transformed(original: bytes) -> bytes:
    text = original.decode('utf-8')
    anchor = re.search(r'(?im)^RewriteEngine\s+On\s*$', text)
    if anchor is None:
        raise RuntimeError('REWRITE_ANCHOR_MISSING')
    return (text[:anchor.end()] + NEW_RULE + text[anchor.end():]).encode('utf-8')


def atomic_write(data: bytes, mode: int) -> None:
    fd, temp_name = tempfile.mkstemp(prefix='.zm-apps-route-', dir=ROUTING.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if ROUTING.is_symlink() or not ROUTING.is_file():
            raise RuntimeError('ROUTING_REPLACED_BEFORE_ATOMIC_WRITE')
        os.replace(temp_name, ROUTING)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def folder(run: str) -> Path:
    if not re.fullmatch(r'[0-9]{9,20}', run):
        raise RuntimeError('INVALID_RUN_ID')
    return BACKUPS / ('run-' + run)


def preview() -> None:
    original = guard()
    updated = transformed(original)
    print('ZM_APPS_ROUTE_PREVIEW=' + json.dumps({
        'old_sha256': digest(original), 'new_sha256': digest(updated),
        'rule': '/apps/ internally serves /apps/index.html',
        'working_legacy_rules_preserved': True}))


def publish(run: str) -> None:
    original = guard()
    updated = transformed(original)
    bdir = folder(run)
    if bdir.exists() or bdir.is_symlink():
        raise RuntimeError('BACKUP_ALREADY_EXISTS')
    if not BACKUPS.is_dir() or BACKUPS.is_symlink():
        raise RuntimeError('PRIVATE_BACKUP_ROOT_MISSING')
    bdir.mkdir(mode=0o700)
    backup = bdir / 'original.htaccess'
    with backup.open('xb') as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(original)
        output.flush()
        os.fsync(output.fileno())
    mode = stat.S_IMODE(ROUTING.stat().st_mode)
    manifest = {'run': run, 'before': digest(original), 'after': digest(updated), 'mode': mode}
    with (bdir / 'manifest.json').open('x') as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(manifest, output)
        output.flush()
        os.fsync(output.fileno())
    if digest(ROUTING.read_bytes()) != digest(original):
        raise RuntimeError('CONCURRENT_PUBLIC_ROUTING_CHANGE')
    atomic_write(updated, mode)
    if digest(ROUTING.read_bytes()) != digest(updated):
        raise RuntimeError('PUBLIC_ROUTE_POSTWRITE_MISMATCH')
    print('ZM_APPS_ROUTE_PUBLISHED=' + json.dumps({
        'public_path': '/apps/', 'private_backup': True, 'db_changed': False}))


def rollback(run: str) -> None:
    bdir = folder(run)
    if not bdir.is_dir() or bdir.is_symlink():
        raise RuntimeError('PRIVATE_BACKUP_NOT_FOUND')
    manifest = json.loads((bdir / 'manifest.json').read_text())
    original = (bdir / 'original.htaccess').read_bytes()
    if manifest['run'] != run or digest(original) != manifest['before']:
        raise RuntimeError('PRIVATE_BACKUP_INTEGRITY_FAILED')
    current = digest(ROUTING.read_bytes())
    if current == manifest['after']:
        atomic_write(original, manifest['mode'])
    elif current != manifest['before']:
        raise RuntimeError('LIVE_ROUTING_CHANGED_PREVENT_ROLLBACK')
    print('ZM_APPS_ROUTE_ROLLBACK=RESTORED')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'preview':
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise SystemExit('USAGE: preview | publish RUN_ID | rollback RUN_ID')
