#!/usr/bin/env python3
"""Safely correct the live personnel link and reload its exact Passenger app.

This changes only one href in the main template and updates the existing
restart.txt mtime. It never touches databases, credentials, or other apps.
Failure means atomic template rollback and a second app reload.
"""
from __future__ import annotations

import ast
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit'
TARGET = APP / 'templates/base.html'
MARKER = APP / 'tmp/restart.txt'
HTACCESS = HOME / 'public_html/.htaccess'
BACKUP = APP / '.route-backups/base-personnel-link-20261105-db7e1f8d.html'
EXPECTED = 'db7e1f8d890489891ab30ad605957cceab0d16f54a358165808b682ace6bcf67'
OLD = b'href="/personnel/"'
NEW = b'href="/staff/"'
NEWSLETTER = 'https://zomorodmelal.ir/newsletter/'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get(path: str) -> tuple[bytes, str]:
    suffix = ('?zm_live_nav_restart=' + secrets.token_hex(12)) if '?' not in path else ''
    req = Request(path + suffix, headers={'User-Agent': 'ZM-Nav-Passenger-Guard/1.0',
                                         'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
    with urlopen(req, timeout=8) as response:
        if response.status != 200:
            raise RuntimeError('PUBLIC_NON_200')
        return response.read(220_000), response.url


def source_guard() -> None:
    if os.getuid() != HOME.stat().st_uid or TARGET.is_symlink() or MARKER.is_symlink():
        raise RuntimeError('ACCOUNT_OR_SYMLINK_MISMATCH')
    if not MARKER.is_file() or MARKER.stat().st_uid != os.getuid():
        raise RuntimeError('EXISTING_PASSENGER_RESTART_MARKER_REQUIRED')
    if not os.access(MARKER, os.W_OK):
        raise RuntimeError('PASSENGER_RESTART_MARKER_NOT_WRITABLE')
    # Confirm the domain belongs to this app, not the separate staging program.
    htaccess = HTACCESS.read_text(errors='replace')
    roots = re.findall(r'^\s*PassengerAppRoot\s+([^\r\n#]+)', htaccess, re.M | re.I)
    if len(roots) != 1 or roots[0].strip(' \t\"\'') != str(APP):
        raise RuntimeError('MAIN_PASSENGER_APP_ROOT_MISMATCH')
    src = (APP / 'config/settings.py').read_text(errors='replace')
    tree = ast.parse(src)
    templates = [n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'TEMPLATES' for t in n.targets)]
    if len(templates) != 1:
        raise RuntimeError('TEMPLATE_CONFIG_AMBIGUOUS')
    snippet = ast.get_source_segment(src, templates[0]) or ''
    if ('APP_DIRS' not in snippet or
            not ('BASE_DIR / "templates"' in snippet or "BASE_DIR / 'templates'" in snippet)):
        raise RuntimeError('TEMPLATE_LOAD_PATH_UNEXPECTED')
    if '\"loaders\"' in snippet or "'loaders'" in snippet:
        raise RuntimeError('TEMPLATE_LOADER_NO_LONGER_DEFAULT')
    for source in (APP / 'passenger_wsgi.py', APP / 'config/urls.py'):
        ast.parse(source.read_text(errors='replace'), filename=str(source))


def atomic_write(data: bytes, mode: int) -> None:
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=TARGET.parent, prefix='.nav.', delete=False) as f:
            tmp = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, stat.S_IMODE(mode))
        os.replace(tmp, TARGET)
        tmp = None
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)


def passenger_reload() -> None:
    # cPanel/Passenger reloads only the app identified by its AppRoot.
    os.utime(MARKER, None)


def public_ready(expected_new: bool) -> bool:
    try:
        news, _ = get(NEWSLETTER)
        if news.count(b'href="/tala/"') != 2:
            return False
        if expected_new:
            if OLD in news or NEW not in news:
                return False
        elif OLD not in news:
            return False
        _, _ = get('https://zomorodmelal.ir/')
        _, final_staff = get('https://zomorodmelal.ir/staff/')
        if not final_staff.startswith('https://zomorodmelal.ir/admin/login/'):
            return False
        return True
    except Exception:
        return False


def await_public(expected_new: bool, attempts: int) -> bool:
    # Passenger checks restart.txt on requests and may throttle its check.
    streak = 0
    for i in range(attempts):
        if public_ready(expected_new):
            streak += 1
            if streak >= 2:
                return True
        else:
            streak = 0
        if i < attempts - 1:
            time.sleep(2)
    return False


def run() -> dict[str, object]:
    source_guard()
    old = TARGET.read_bytes()
    if sha(old) != EXPECTED or old.count(OLD) != 1:
        raise RuntimeError('EXPECTED_MAIN_TEMPLATE_MISMATCH_ABORT:' + sha(old))
    if not public_ready(False):
        raise RuntimeError('PUBLIC_PREFLIGHT_NOT_HEALTHY_ABORT')
    corrected = old.replace(OLD, NEW)
    if corrected.count(OLD) or corrected.count(NEW) != old.count(NEW) + 1:
        raise RuntimeError('INVALID_PATCH_ABORT')
    BACKUP.parent.mkdir(exist_ok=True, mode=0o700)
    if BACKUP.exists():
        if sha(BACKUP.read_bytes()) != EXPECTED:
            raise RuntimeError('EXISTING_BACKUP_SHA_MISMATCH_ABORT')
    else:
        with BACKUP.open('xb') as f:
            f.write(old)
            f.flush()
            os.fsync(f.fileno())
        BACKUP.chmod(0o600)
    with BACKUP.open('rb') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        if sha(TARGET.read_bytes()) != EXPECTED:
            raise RuntimeError('CONCURRENT_TEMPLATE_CHANGE_ABORT')
        mode = TARGET.stat().st_mode
        atomic_write(corrected, mode)
        passenger_reload()
        if await_public(True, attempts=9):
            return {'status': 'LIVE_VERIFIED', 'new_href': '/staff/',
                    'live_links_fixed': 1, 'old_sha256': EXPECTED,
                    'new_sha256': sha(corrected), 'passenger_reloaded': True,
                    'files_edited': ['Saeit/templates/base.html', 'Saeit/tmp/restart.txt']}
        if sha(TARGET.read_bytes()) != sha(corrected):
            raise RuntimeError('CONCURRENT_WRITER_DETECTED_REQUIRES_MANUAL_REVIEW')
        atomic_write(old, mode)
        passenger_reload()
        if sha(TARGET.read_bytes()) != EXPECTED:
            raise RuntimeError('ROLLBACK_SHA_FAILED')
        if not await_public(False, attempts=7):
            raise RuntimeError('ROLLBACK_SITE_NOT_HEALTHY_REQUIRES_MANUAL_REVIEW')
        return {'status': 'ROLLED_BACK_PUBLIC_VERIFICATION_FAILED',
                'live_links_fixed': 0, 'template_sha256': EXPECTED,
                'passenger_reloaded': True,
                'files_edited': ['Saeit/templates/base.html', 'Saeit/tmp/restart.txt']}


if __name__ == '__main__':
    if sys.argv[1:] != ['guarded']:
        raise SystemExit('USAGE: guarded')
    result = run()
    print('PERSONNEL_PASSENGER_RESTART_RESULT=' + json.dumps(result, sort_keys=True), flush=True)
    if result['status'] != 'LIVE_VERIFIED':
        raise SystemExit(1)
