#!/usr/bin/env python3
"""Restore public factory hostname, preserving independent private VPS factory."""

from __future__ import annotations

import base64
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
WEBROOT = HOME / 'factory.zomorodmelal.ir'
HTACCESS = WEBROOT / '.htaccess'
INDEX = WEBROOT / 'index.html'
BACKUPS = HOME / '.private/factory-public-web-backups'
MARKER = 'ZM-FACTORY-PUBLIC-20261105'
OLD_LINK_HTML_SHA = '2d68e6367969fd3cfec3c0674a66be12c6fe8b80ab8c2636c1578fd6fcbe5f4f'
EXPECTED_DIRECTIVES = {
    'PassengerEnabled on',
    'PassengerAppRoot /home/zomorod2/factory.zomorodmelal.ir',
    'PassengerBaseURI /',
    'PassengerPython /home/zomorod2/virtualenv/Saeit/3.11/bin/python',
    'PassengerAppType wsgi',
    'PassengerStartupFile passenger_wsgi.py',
}
NEW_HTACCESS = (
    '# ' + MARKER + ' -- public information page only; no VPS factory operations\n'
    'PassengerEnabled off\n'
    'DirectoryIndex index.html\n'
    '<IfModule mod_headers.c>\n'
    '    Header always set X-Robots-Tag "noindex, nofollow, noarchive"\n'
    '</IfModule>\n'
).encode('utf-8')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_user_and_paths() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('UNEXPECTED_CPANEL_USER')
    if WEBROOT.is_symlink() or not WEBROOT.is_dir() or BACKUPS.parent.is_symlink() or not BACKUPS.parent.is_dir():
        raise RuntimeError('WEBROOT_OR_PRIVATE_BACKUP_PARENT_INVALID')
    if HTACCESS.is_symlink() or not HTACCESS.is_file() or INDEX.is_symlink():
        raise RuntimeError('FACTORY_ENTRYPOINT_INVALID')


def guard() -> tuple[bytes, bytes]:
    check_user_and_paths()
    if INDEX.exists():
        raise RuntimeError('EXISTING_FACTORY_PUBLIC_INDEX_WILL_NOT_BE_OVERWRITTEN')
    old = HTACCESS.read_bytes()
    if not 150 <= len(old) <= 1000:
        raise RuntimeError('FACTORY_PASSENGER_CONFIG_SIZE_UNEXPECTED')
    lines = {line.strip() for line in old.decode('utf-8').splitlines()
             if line.strip() and not line.lstrip().startswith('#')}
    if lines != EXPECTED_DIRECTIVES or len([line for line in old.decode('utf-8').splitlines()
                                              if line.strip() and not line.lstrip().startswith('#')]) != 6:
        raise RuntimeError('FACTORY_PASSENGER_CONFIG_CHANGED_OR_CONTAINS_EXTRA_RULES')
    if Path('/home/zomorod2/virtualenv/Saeit/3.11/bin/python').exists():
        raise RuntimeError('EXPECTED_MISSING_INTERPRETER_NOW_EXISTS_REFUSE_REPLACEMENT')
    encoded = os.environ.get('FACTORY_HTML_B64')
    if encoded:
        html = base64.b64decode(encoded, validate=True)
    else:
        asset = Path(__file__).with_name('factory-index.html')
        if asset.is_symlink() or not asset.is_file():
            raise RuntimeError('FACTORY_PUBLIC_ASSET_MISSING')
        html = asset.read_bytes()
    if not 2500 < len(html) < 25000 or b'<html lang="fa" dir="rtl">' not in html or b'noindex,nofollow,noarchive' not in html:
        raise RuntimeError('FACTORY_PUBLIC_ASSET_CONTENT_INVALID')
    if b'https://zomorodmelal.ir/apps/' not in html:
        raise RuntimeError('FACTORY_PUBLIC_LINK_MISSING')
    return old, html


def release_dir(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{9,20}', run_id):
        raise RuntimeError('INVALID_RUN_ID')
    return BACKUPS / ('run-' + run_id)


def atomic_file(target: Path, data: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix='.factory-public-', dir=WEBROOT)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if target.is_symlink():
            raise RuntimeError('FACTORY_TARGET_BECAME_SYMLINK')
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)


def preview() -> None:
    old, html = guard()
    print('FACTORY_PUBLIC_PREVIEW=' + json.dumps({
        'previous_config_sha': digest(old), 'new_config_sha': digest(NEW_HTACCESS),
        'html_sha': digest(html), 'operational_vps_files_modified': False,
        'production_database_or_payments_modified': False}))


def publish(run_id: str) -> None:
    old, html = guard()
    folder = release_dir(run_id)
    if folder.exists() or folder.is_symlink():
        raise RuntimeError('PRIVATE_BACKUP_COLLISION')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    folder.mkdir(mode=0o700)
    prior = folder / 'original.htaccess'
    with prior.open('xb') as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(old)
        out.flush()
        os.fsync(out.fileno())
    manifest = {
        'run_id': run_id, 'old_sha': digest(old), 'new_sha': digest(NEW_HTACCESS),
        'html_sha': digest(html), 'mode': stat.S_IMODE(HTACCESS.stat().st_mode),
    }
    with (folder / 'manifest.json').open('x') as out:
        os.fchmod(out.fileno(), 0o600)
        json.dump(manifest, out)
        out.flush()
        os.fsync(out.fileno())
    if digest(HTACCESS.read_bytes()) != digest(old) or INDEX.exists():
        raise RuntimeError('FACTORY_PUBLIC_CONCURRENT_CHANGE')
    try:
        atomic_file(INDEX, html, 0o644)
        atomic_file(HTACCESS, NEW_HTACCESS, manifest['mode'])
        if digest(HTACCESS.read_bytes()) != manifest['new_sha'] or digest(INDEX.read_bytes()) != manifest['html_sha']:
            raise RuntimeError('FACTORY_PUBLIC_POSTWRITE_MISMATCH')
    except BaseException:
        if HTACCESS.is_file() and digest(HTACCESS.read_bytes()) == manifest['new_sha']:
            atomic_file(HTACCESS, old, manifest['mode'])
        if INDEX.is_file() and not INDEX.is_symlink() and digest(INDEX.read_bytes()) == manifest['html_sha']:
            INDEX.unlink()
        raise
    print('FACTORY_PUBLIC_PUBLISHED=' + json.dumps({
        'hostname': 'factory.zomorodmelal.ir', 'reversible_private_backup': True,
        'only_public_webroot_modified': True, 'factory_cycle_modified': False}))


def rollback(run_id: str) -> None:
    check_user_and_paths()
    folder = release_dir(run_id)
    if folder.is_symlink() or not folder.is_dir():
        raise RuntimeError('FACTORY_PRIVATE_BACKUP_NOT_FOUND')
    manifest = json.loads((folder / 'manifest.json').read_text())
    prior = (folder / 'original.htaccess').read_bytes()
    if manifest.get('run_id') != run_id or digest(prior) != manifest['old_sha']:
        raise RuntimeError('FACTORY_BACKUP_INTEGRITY_FAIL')
    current = digest(HTACCESS.read_bytes())
    if current == manifest['new_sha']:
        atomic_file(HTACCESS, prior, manifest['mode'])
    elif current != manifest['old_sha']:
        raise RuntimeError('FACTORY_CONCURRENT_CHANGE_PREVENTS_ROLLBACK')
    if INDEX.is_file() and not INDEX.is_symlink() and digest(INDEX.read_bytes()) == manifest['html_sha']:
        INDEX.unlink()
    elif INDEX.exists() or INDEX.is_symlink():
        raise RuntimeError('FACTORY_INDEX_CONCURRENT_CHANGE_PREVENTS_ROLLBACK')
    print('FACTORY_PUBLIC_ROLLBACK=RESTORED_PREVIOUS_ROUTING')


def desired_public_html() -> bytes:
    encoded = os.environ.get('FACTORY_HTML_B64')
    if not encoded:
        raise RuntimeError('CORRECTED_PUBLIC_ASSET_MISSING')
    data = base64.b64decode(encoded, validate=True)
    if (b'https://zomorodmelal.ir/industry/' not in data or
            b'https://zomorodmelal.ir/business/' in data or
            b'<html lang="fa" dir="rtl">' not in data or not 2500 < len(data) < 25000):
        raise RuntimeError('CORRECTED_PUBLIC_ASSET_FAILED_CONTENT_CHECK')
    return data


def relink_guard() -> bytes:
    check_user_and_paths()
    if digest(HTACCESS.read_bytes()) != digest(NEW_HTACCESS):
        raise RuntimeError('FACTORY_PUBLIC_ROUTING_CHANGED')
    if not INDEX.is_file() or INDEX.is_symlink():
        raise RuntimeError('FACTORY_PUBLIC_INDEX_MISSING')
    old = INDEX.read_bytes()
    if digest(old) != OLD_LINK_HTML_SHA:
        raise RuntimeError('FACTORY_PUBLIC_INDEX_CHANGED_FROM_EXPECTED_RELEASE')
    return old


def relink_preview() -> None:
    original = relink_guard()
    corrected = desired_public_html()
    print('FACTORY_PUBLIC_LINK_PREVIEW=' + json.dumps({
        'old_sha': digest(original), 'new_sha': digest(corrected),
        'only_public_factory_html_modified': True}))


def relink_publish(run_id: str) -> None:
    original = relink_guard()
    corrected = desired_public_html()
    folder = BACKUPS / ('run-' + run_id + '-link')
    release_dir(run_id)  # validates run ID before making any files
    if folder.exists() or folder.is_symlink():
        raise RuntimeError('FACTORY_LINK_BACKUP_COLLISION')
    folder.mkdir(mode=0o700)
    original_path = folder / 'original-index.html'
    with original_path.open('xb') as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(original)
        out.flush()
        os.fsync(out.fileno())
    manifest = {'run_id': run_id, 'old_sha': digest(original),
                'new_sha': digest(corrected)}
    with (folder / 'manifest.json').open('x') as out:
        os.fchmod(out.fileno(), 0o600)
        json.dump(manifest, out)
        out.flush()
        os.fsync(out.fileno())
    if digest(INDEX.read_bytes()) != manifest['old_sha']:
        raise RuntimeError('CONCURRENT_FACTORY_INDEX_EDIT')
    try:
        atomic_file(INDEX, corrected, 0o644)
        if digest(INDEX.read_bytes()) != manifest['new_sha']:
            raise RuntimeError('FACTORY_LINK_POSTWRITE_MISMATCH')
    except BaseException:
        if INDEX.is_file() and digest(INDEX.read_bytes()) == manifest['new_sha']:
            atomic_file(INDEX, original, 0o644)
        raise
    print('FACTORY_PUBLIC_LINK_CORRECTED=' + json.dumps({
        'destination': 'https://zomorodmelal.ir/industry/',
        'private_backup': True, 'autonomous_runtime_modified': False}))


def relink_rollback(run_id: str) -> None:
    release_dir(run_id)
    folder = BACKUPS / ('run-' + run_id + '-link')
    if folder.is_symlink() or not folder.is_dir():
        raise RuntimeError('FACTORY_LINK_BACKUP_MISSING')
    manifest = json.loads((folder / 'manifest.json').read_text())
    original = (folder / 'original-index.html').read_bytes()
    if manifest['run_id'] != run_id or digest(original) != manifest['old_sha']:
        raise RuntimeError('FACTORY_LINK_BACKUP_INTEGRITY_FAIL')
    if digest(INDEX.read_bytes()) == manifest['new_sha']:
        atomic_file(INDEX, original, 0o644)
    elif digest(INDEX.read_bytes()) != manifest['old_sha']:
        raise RuntimeError('FACTORY_LINK_CONCURRENT_EDIT_PREVENTS_ROLLBACK')
    print('FACTORY_PUBLIC_LINK_ROLLBACK=RESTORED')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'preview':
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == 'relink-preview':
        relink_preview()
    elif len(sys.argv) == 3 and sys.argv[1] == 'relink-publish':
        relink_publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'relink-rollback':
        relink_rollback(sys.argv[2])
    else:
        raise SystemExit('USAGE: preview | publish RUN_ID | rollback RUN_ID')
