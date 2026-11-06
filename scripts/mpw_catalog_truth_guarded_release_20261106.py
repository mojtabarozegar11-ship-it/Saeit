#!/usr/bin/env python3
"""Auditable one-literal correction for MojPlayWin's public TRX catalog.

Audit/verify are read-only. Publish changes exactly one previously located
source file, with private backup and rollback. No checkout, email or DB writes.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tempfile


ROOT = Path('/home/zomorod2/Saeit-staging')
PUBLIC = Path('/home/zomorod2/mojplaywin.com')
SEARCH_ROOT = ROOT / 'mpw_commerce'
BACKUPS = Path('/home/zomorod2/.local/share/mpw-catalog-truth-20261106')
OLD = b'Your TRX invoice, verified payment receipt and secure download arrive by email.'
NEW = (b'Your TRX invoice opens in this browser. After confirmed TRX payment, '
       b'use My TRX purchases in this browser to access your download. '
       b'Emailed receipts and recovery on another device are not yet available.')
MAX_FILES = 2500
MAX_TOTAL = 10_000_000
MAX_FILE = 250_000


def fail(code):
    raise RuntimeError('MPW_CATALOG_TRUTH_ABORT:' + code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def trusted_dir(path):
    if (path.is_symlink() or not path.is_dir() or path.resolve() != path
            or path.stat().st_uid != os.geteuid()):
        fail('UNTRUSTED_DIRECTORY:' + path.name)


def guard():
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        fail('WRONG_ACCOUNT')
    for path in (ROOT, PUBLIC, SEARCH_ROOT, PUBLIC / 'tmp'):
        trusted_dir(path)
    wsgi = PUBLIC / 'passenger_wsgi.py'
    if wsgi.is_symlink() or not wsgi.is_file() or wsgi.stat().st_uid != os.geteuid():
        fail('INVALID_PASSENGER')
    if b"APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_bytes():
        fail('WRONG_APP')
    marker = PUBLIC / 'tmp/restart.txt'
    if marker.is_symlink():
        fail('INVALID_RESTART_MARKER')


def safe_file(path):
    if (path.is_symlink() or not path.is_file()
            or not path.resolve().is_relative_to(SEARCH_ROOT)
            or path.stat().st_uid != os.geteuid()
            or path.stat().st_nlink != 1 or path.stat().st_size > MAX_FILE):
        fail('UNSAFE_TARGET')
    parent = path.parent
    while parent != SEARCH_ROOT:
        trusted_dir(parent)
        parent = parent.parent
    return path.read_bytes()


def locate():
    guard()
    found = []
    total = 0
    count = 0
    for path in SEARCH_ROOT.rglob('*'):
        if path.is_symlink():
            fail('SYMLINK_IN_APP')
        if not path.is_file() or path.suffix not in ('.py', '.html'):
            continue
        if any(part in ('migrations', '__pycache__', 'tests') for part in path.parts):
            continue
        count += 1
        total += path.stat().st_size
        if count > MAX_FILES or total > MAX_TOTAL:
            fail('SEARCH_LIMIT')
        if path.stat().st_size > MAX_FILE:
            continue
        data = safe_file(path)
        if OLD in data or NEW in data:
            found.append((path, data))
    if len(found) != 1:
        fail('UNIQUE_SOURCE_NOT_FOUND:' + str(len(found)))
    path, data = found[0]
    before_count, after_count = data.count(OLD), data.count(NEW)
    if (before_count, after_count) not in ((1, 0), (0, 1)):
        fail('NON_UNIQUE_COPY')
    return path, data, before_count == 1


def checked_syntax(path, data):
    if path.suffix == '.py':
        compile(data.decode('utf-8'), str(path), 'exec')
    elif path.suffix == '.html':
        sys.path.insert(0, str(ROOT))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        import django
        django.setup()
        from django.template import engines
        engines['django'].from_string(data.decode('utf-8'))
    else:
        fail('UNREVIEWED_EXTENSION')


def atomic_replace(path, new, expected):
    if digest(safe_file(path)) != expected:
        fail('CONCURRENT_EDIT')
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.mpw-catalog-')
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(new)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restart():
    (PUBLIC / 'tmp/restart.txt').touch()


def command(operation, run_id=None):
    path, current, needs_change = locate()
    relative = str(path.relative_to(ROOT))
    if operation == 'audit':
        if needs_change:
            checked_syntax(path, current.replace(OLD, NEW, 1))
        print('MPW_CATALOG_TRUTH_AUDIT=' + json.dumps({
            'path': relative, 'sha256': digest(current),
            'state': 'READY' if needs_change else 'ALREADY_CORRECT',
            'changes': 0, 'orders': 0, 'emails': 0,
        }, sort_keys=True), flush=True)
        return
    if operation == 'verify':
        if needs_change:
            fail('MISLEADING_COPY_STILL_LIVE')
        checked_syntax(path, current)
        print('MPW_CATALOG_TRUTH_VERIFY=PASS;SOURCE=' + relative +
              ';EMAIL_CLAIM_CORRECTED=TRUE;ORDERS=0;MAIL=0', flush=True)
        return
    if operation != 'publish' or not run_id or not re.fullmatch(r'[0-9]{8,20}', run_id):
        fail('INVALID_OPERATION')
    if not needs_change:
        print('MPW_CATALOG_TRUTH_RELEASE=ALREADY_CORRECT', flush=True)
        return
    updated = current.replace(OLD, NEW, 1)
    checked_syntax(path, updated)
    if BACKUPS.is_symlink():
        fail('UNSAFE_BACKUP_DIR')
    BACKUPS.mkdir(parents=True, mode=0o700, exist_ok=True)
    if (BACKUPS.stat().st_uid != os.geteuid()
            or stat.S_IMODE(BACKUPS.stat().st_mode) != 0o700):
        fail('BACKUP_PERMISSIONS')
    folder = BACKUPS / run_id
    folder.mkdir(mode=0o700)
    with (folder / 'source.before').open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(current)
        stream.flush()
        os.fsync(stream.fileno())
    replaced = False
    try:
        atomic_replace(path, updated, digest(current))
        replaced = True
        restart()
        if digest(safe_file(path)) != digest(updated):
            fail('POST_WRITE_MISMATCH')
    except BaseException:
        if replaced and digest(safe_file(path)) == digest(updated):
            atomic_replace(path, current, digest(updated))
            restart()
        raise
    print('MPW_CATALOG_TRUTH_RELEASE=APPLIED;SOURCE=' + relative +
          ';FILES=1;ORDERS=0;MAIL=0;PAYMENTS=0', flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] in ('audit', 'verify'):
        command(sys.argv[1])
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        command('publish', sys.argv[2])
    else:
        raise SystemExit('Usage: audit | publish RUN_ID | verify')
