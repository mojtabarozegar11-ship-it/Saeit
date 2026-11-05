#!/usr/bin/env python3
"""One-off safe publish and rollback of the missing /apps/ public directory."""

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
WEBROOT = HOME / 'public_html'
APPS_DIR = WEBROOT / 'apps'
TARGET = APPS_DIR / 'index.html'
EXPECTED = 'e264451f4567589a0abdacfa3a8cbf1787cb501f6124ec1a5eac04a85f4e25c6'
ASSET = Path(__file__).with_name('apps-index.html')
MANIFEST = Path(__file__).with_name('manifest.json')


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guard() -> bytes:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('REFUSE_UNEXPECTED_CPANEL_USER')
    if not WEBROOT.is_dir() or WEBROOT.is_symlink():
        raise RuntimeError('INVALID_PUBLIC_WEBROOT')
    if APPS_DIR.exists() or APPS_DIR.is_symlink():
        raise RuntimeError('APPS_DIRECTORY_APPEARED_OR_ALREADY_EXISTS')
    if not ASSET.is_file() or ASSET.is_symlink() or ASSET.parent.is_symlink():
        raise RuntimeError('RELEASE_ASSET_MISSING_OR_SYMLINK')
    data = ASSET.read_bytes()
    if checksum(data) != EXPECTED or b'<html lang="fa" dir="rtl">' not in data:
        raise RuntimeError('RELEASE_ASSET_HASH_OR_STRUCTURE_MISMATCH')
    if b'/store/free-products/wheat-seed-rate-planner-v1/index.html' not in data:
        raise RuntimeError('REAL_APPLICATION_LINK_MISSING')
    return data


def preview() -> None:
    data = guard()
    print('ZM_APPS_HUB_PREVIEW=' + json.dumps({
        'new_directory': str(APPS_DIR), 'html_bytes': len(data),
        'asset_sha256': checksum(data), 'existing_application_files_overwritten': 0}))


def publish() -> None:
    data = guard()
    if MANIFEST.exists():
        raise RuntimeError('RELEASE_ALREADY_ATTEMPTED')
    APPS_DIR.mkdir(mode=0o755)
    try:
        fd, tmp = tempfile.mkstemp(prefix='.apps-hub-', dir=APPS_DIR)
        try:
            os.fchmod(fd, 0o644)
            with os.fdopen(fd, 'wb') as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            if TARGET.exists() or TARGET.is_symlink():
                raise RuntimeError('TARGET_EXISTS_BEFORE_PUBLISH')
            os.replace(tmp, TARGET)
        finally:
            Path(tmp).unlink(missing_ok=True)
        if checksum(TARGET.read_bytes()) != EXPECTED or stat.S_IMODE(TARGET.stat().st_mode) != 0o644:
            raise RuntimeError('POSTWRITE_VERIFY_FAILED')
        with MANIFEST.open('x') as output:
            os.fchmod(output.fileno(), 0o600)
            json.dump({'sha256': EXPECTED, 'path': str(TARGET),
                       'created_directory': True}, output)
            output.flush()
            os.fsync(output.fileno())
        print('ZM_APPS_HUB_PUBLISHED=' + json.dumps({
            'path': '/apps/', 'bytes': len(data), 'verified_sha256': EXPECTED,
            'replaced_existing_files': False, 'db_or_payments_changed': False}))
    except BaseException:
        if TARGET.is_file() and not TARGET.is_symlink() and checksum(TARGET.read_bytes()) == EXPECTED:
            TARGET.unlink()
        if APPS_DIR.is_dir() and not any(APPS_DIR.iterdir()):
            APPS_DIR.rmdir()
        raise


def rollback() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('REFUSE_UNEXPECTED_CPANEL_USER')
    if not MANIFEST.is_file() or MANIFEST.is_symlink():
        raise RuntimeError('RELEASE_MANIFEST_MISSING')
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get('sha256') != EXPECTED or manifest.get('path') != str(TARGET):
        raise RuntimeError('RELEASE_MANIFEST_MISMATCH')
    if TARGET.is_file() and not TARGET.is_symlink() and checksum(TARGET.read_bytes()) == EXPECTED:
        TARGET.unlink()
    elif TARGET.exists() or TARGET.is_symlink():
        raise RuntimeError('CONCURRENT_CHANGE_PREVENTS_ROLLBACK')
    if APPS_DIR.is_dir() and not any(APPS_DIR.iterdir()):
        APPS_DIR.rmdir()
    print('ZM_APPS_HUB_ROLLBACK=RESTORED_PRIOR_404')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'preview':
        preview()
    elif len(sys.argv) == 2 and sys.argv[1] == 'publish':
        publish()
    elif len(sys.argv) == 2 and sys.argv[1] == 'rollback':
        rollback()
    else:
        raise SystemExit('USAGE: preview | publish | rollback')
