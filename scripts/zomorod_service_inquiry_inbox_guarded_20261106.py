#!/usr/bin/env python3
"""Additive, rollbackable private service-inquiry viewer for the live business desk.

No client rows are read, sent or modified by this installer. The management app,
ask-master handlers and both SQLite databases are left unchanged.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HOME = Path('/home/zomorod2')
WEB = HOME / 'public_html'
PRIVATE = HOME / '.private/zomorod-business'
BACKUPS = PRIVATE / '.service-inquiry-inbox-installs'
ARCHIVE_PREFIX = '.service-inquiry-inbox-'
BUSINESS_APP = PRIVATE / 'app.php'
EXPECTED_BUSINESS_SHA = '8236fd7ea839e590527b75b02ebc63b7ea8327bdfe6d111acb61877fe0dde296'
TARGETS = {
    'content/zomorod-business/inquiries-entry.php': WEB / 'business/inquiries.php',
    'content/zomorod-business/service_inquiries.php': PRIVATE / 'service_inquiries.php',
}
POINTER = PRIVATE / 'service_inquiries_source.path'
SQLITE_NAME = 'master_customer_inbox.sqlite3'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validated_runid(value: str) -> str:
    if not re.fullmatch(r'[0-9]{5,20}', value):
        raise RuntimeError('INVALID_RUN_ID')
    return value


def validate_host() -> Path:
    if os.geteuid() == 0 or not WEB.is_dir() or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_SITE_USER')
    for directory in (PRIVATE, WEB / 'business'):
        if directory.is_symlink() or not directory.is_dir():
            raise RuntimeError('UNSAFE_TARGET_DIRECTORY')
    if BUSINESS_APP.is_symlink() or not BUSINESS_APP.is_file() or sha(BUSINESS_APP.read_bytes()) != EXPECTED_BUSINESS_SHA:
        raise RuntimeError('BUSINESS_LIVE_SOURCE_DRIFT')
    for target in (*TARGETS.values(), POINTER):
        if target.exists() or target.is_symlink():
            raise RuntimeError('EXISTING_TARGET_REFUSE_OVERWRITE')
    private_root = HOME / '.private'
    candidates = [p for p in private_root.rglob(SQLITE_NAME) if p.is_file() and not p.is_symlink()]
    if len(candidates) != 1:
        raise RuntimeError('REQUEST_DATABASE_NOT_UNIQUE')
    dbpath = candidates[0].resolve()
    if not dbpath.is_relative_to(private_root.resolve()):
        raise RuntimeError('REQUEST_DATABASE_OUTSIDE_PRIVATE_ROOT')
    uri = 'file:' + str(dbpath) + '?mode=ro&immutable=1'
    with sqlite3.connect(uri, uri=True, timeout=2) as db:
        columns = {r[1] for r in db.execute('PRAGMA table_info(customer_questions)')}
    expected = {'id', 'tenant', 'kind', 'question', 'created_utc', 'full_name',
                'email', 'processing_status', 'master_processed_utc'}
    if not expected <= columns:
        raise RuntimeError('REQUEST_DATABASE_SCHEMA_DRIFT')
    return dbpath


def archive_path(runid: str) -> Path:
    return PRIVATE / f'{ARCHIVE_PREFIX}{runid}.tgz'


def package(runid: str) -> dict[Path, bytes]:
    path = archive_path(runid)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 250000:
        raise RuntimeError('INVALID_PACKAGE')
    found: dict[Path, bytes] = {}
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        if len(members) != 2 or {m.name for m in members} != set(TARGETS):
            raise RuntimeError('PACKAGE_MEMBER_SET_DRIFT')
        for member in members:
            if not member.isfile() or member.size > 180000 or member.name not in TARGETS:
                raise RuntimeError('INVALID_PACKAGE_MEMBER')
            inp = archive.extractfile(member)
            if inp is None:
                raise RuntimeError('UNREADABLE_PACKAGE_MEMBER')
            content = inp.read()
            if not content.startswith(b'<?php\n'):
                raise RuntimeError('UNEXPECTED_PHP_SOURCE')
            found[TARGETS[member.name]] = content
    return found


def php_lint(code: bytes) -> None:
    handle, name = tempfile.mkstemp(prefix='.inquiry-lint-', suffix='.php', dir=str(PRIVATE))
    try:
        with os.fdopen(handle, 'wb') as out:
            out.write(code)
        os.chmod(name, 0o600)
        binary = '/opt/cpanel/ea-php82/root/usr/bin/php'
        if not Path(binary).is_file():
            binary = 'php'
        result = subprocess.run([binary, '-l', name], capture_output=True, timeout=20)
        if result.returncode:
            raise RuntimeError('PHP_LINT_FAILED')
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_new(path: Path, content: bytes, mode: int) -> None:
    if path.exists() or path.is_symlink():
        raise RuntimeError('EXISTING_TARGET_REFUSE_OVERWRITE')
    fd, temp = tempfile.mkstemp(prefix='.inquiry-install-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp, mode)
        os.link(temp, path)  # atomic no-clobber installation
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def publish(runid: str) -> None:
    dbpath = validate_host()
    sources = package(runid)
    for code in sources.values():
        php_lint(code)
    if BACKUPS.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_DIRECTORY')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    folder = BACKUPS / runid
    if folder.exists() or folder.is_symlink():
        raise RuntimeError('BACKUP_COLLISION')
    folder.mkdir(mode=0o700)
    artifacts = {**sources, POINTER: (str(dbpath) + '\n').encode('utf-8')}
    manifest = {'runid': runid, 'created': {str(p): sha(b) for p, b in artifacts.items()},
                'business_app_sha': EXPECTED_BUSINESS_SHA}
    (folder / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')
    (folder / 'manifest.json').chmod(0o600)
    created = []
    try:
        for path, data in artifacts.items():
            atomic_new(path, data, 0o600 if path != WEB / 'business/inquiries.php' else 0o644)
            created.append(path)
        print('INQUIRY_INBOX_INSTALLED=3')
    except Exception:
        for path in reversed(created):
            if path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == manifest['created'][str(path)]:
                path.unlink()
        raise


def verify(runid: str) -> None:
    folder = BACKUPS / runid
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    for filename, expected in manifest['created'].items():
        path = Path(filename)
        if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != expected:
            raise RuntimeError('INSTALLED_ARTIFACT_DRIFT')
    if sha(BUSINESS_APP.read_bytes()) != manifest['business_app_sha']:
        raise RuntimeError('BUSINESS_APP_CHANGED_DURING_INSTALL')
    php_lint((WEB / 'business/inquiries.php').read_bytes())
    php_lint((PRIVATE / 'service_inquiries.php').read_bytes())
    print('INQUIRY_INBOX_ORIGIN_VERIFIED=3')


def rollback(runid: str) -> None:
    folder = BACKUPS / runid
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    for filename, expected in manifest['created'].items():
        path = Path(filename)
        if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != expected:
            raise RuntimeError('REFUSE_ROLLBACK_UNRECOGNIZED_FILE')
    for filename in manifest['created']:
        Path(filename).unlink()
    print('INQUIRY_INBOX_ROLLED_BACK=3')


def selftest() -> None:
    assert len(TARGETS) == 2
    assert len(EXPECTED_BUSINESS_SHA) == 64
    assert POINTER.parent == PRIVATE
    assert all(p.parent in (PRIVATE, WEB / 'business') for p in TARGETS.values())
    print('INQUIRY_INBOX_SELFTEST_OK=1')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['selftest']:
        selftest()
    elif len(args) == 2 and args[0] in ('preview', 'publish', 'verify', 'rollback'):
        runid = validated_runid(args[1])
        if args[0] == 'preview':
            db = validate_host()
            sources = package(runid)
            for code in sources.values():
                php_lint(code)
            print('INQUIRY_INBOX_PREFLIGHT_OK=1')
        elif args[0] == 'publish':
            publish(runid)
        elif args[0] == 'verify':
            verify(runid)
        else:
            rollback(runid)
    else:
        raise RuntimeError('UNKNOWN_OR_UNSAFE_MODE')
