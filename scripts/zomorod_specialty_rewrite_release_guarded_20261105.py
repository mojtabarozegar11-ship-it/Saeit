#!/usr/bin/env python3
"""Guarded publish of four static guides with one scoped Apache rewrite rule.

The existing .htaccess is backed up and hash-guarded. No other public route,
application file, existing folder, database, or credential is modified.
"""
from __future__ import annotations

import base64
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
from urllib.error import HTTPError
from urllib.request import Request, urlopen

STATIC_PAGES_BASE64 = None  # Packed from core/specialty_pages.py by CI.
HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit'
DOCROOT = HOME / 'public_html'
HTACCESS = DOCROOT / '.htaccess'
FOLDER = DOCROOT / 'zm-specialty-guides'
BACKUPS = APP / '.route-backups'
LOCK = BACKUPS / 'specialty-htaccess-20261105.lock'
EXPECTED_HT_SHA = '39988da61efd4504eb43329c7baeea63510ddf8e3a96c64835c6add0a8cfb7a1'
SECTIONS = ('carpets', 'real-estate', 'restaurant', 'signals')
BLOCK = b'# Zomorod specialty public guides; scoped and reversible (2026-11-05)\n' \
        b'RewriteRule ^(carpets|real-estate|restaurant|signals)/?$ zm-specialty-guides/$1/index.html [END,NC]\n'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check(path):
    url = 'https://zomorodmelal.ir' + path + ('&' if '?' in path else '?') + 'zm_route=' + secrets.token_hex(9)
    req = Request(url, headers={'User-Agent': 'ZM-Scoped-Rewrite-Guard/1.0',
                                'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
    try:
        resp = urlopen(req, timeout=9)
    except HTTPError as exc:
        resp = exc
    with resp:
        return resp.status, resp.read(170_000), resp.url


def baseline():
    for route in ('/', '/newsletter/'):
        s, _, _ = check(route)
        if s != 200:
            raise RuntimeError('BASELINE_NOT_200:' + route + ':' + str(s))
    s, _, final = check('/staff/')
    if s != 200 or not final.startswith('https://zomorodmelal.ir/admin/login/'):
        raise RuntimeError('STAFF_LOGIN_REDIRECT_NOT_PRESERVED')


def all_ready():
    failures = []
    for slug in SECTIONS:
        try:
            s, body, _ = check('/' + slug + '/')
            if s != 200 or b'<html lang="fa" dir="rtl">' not in body or slug.encode() not in body:
                failures.append(slug + ':HTTP_' + str(s))
            if slug == 'signals' and s == 200 and 'سیگنال زنده'.encode() not in body:
                failures.append('signals:MISSING_ACCURACY_NOTICE')
        except Exception as err:
            failures.append(slug + ':' + type(err).__name__)
    try:
        baseline()
    except Exception as err:
        failures.append('BASELINE:' + str(err))
    return not failures, failures


def atomic_write(target, content, mode):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.zm-guard-', delete=False) as f:
            tmp = f.name
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, stat.S_IMODE(mode))
        os.replace(tmp, target)
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def validate_environment():
    if os.getuid() != HOME.stat().st_uid or HTACCESS.is_symlink() or DOCROOT.is_symlink():
        raise RuntimeError('ACCOUNT_OR_HTACCESS_SYMLINK_UNEXPECTED')
    roots = re.findall(r'^\s*PassengerAppRoot\s+([^\r\n#]+)', HTACCESS.read_text(errors='replace'), re.M | re.I)
    if len(roots) != 1 or roots[0].strip(' \t\"\'') != str(APP):
        raise RuntimeError('MAIN_DOMAIN_PASSENGER_ROOT_MISMATCH')
    if FOLDER.exists() or FOLDER.is_symlink():
        raise RuntimeError('DEDICATED_GUIDE_FOLDER_ALREADY_EXISTS_ABORT')


def new_htaccess(old):
    if sha(old) != EXPECTED_HT_SHA:
        raise RuntimeError('HTACCESS_CHANGED_SINCE_READ_ONLY_AUDIT:' + sha(old))
    if b'zm-specialty-guides' in old:
        raise RuntimeError('SPECIALTY_REWRITE_ALREADY_EXISTS')
    lines = old.splitlines(keepends=True)
    index = [i for i, line in enumerate(lines)
             if line.lstrip().startswith(b'RewriteRule ^authors/mojtaba-rozegar/?$ ')
             and b'[L,NC]' in line]
    if len(index) != 1:
        raise RuntimeError('EXPECTED_STATIC_REWRITE_ANCHOR_NOT_FOUND')
    eol = b'\r\n' if lines[index[0]].endswith(b'\r\n') else b'\n'
    block = BLOCK.replace(b'\n', eol)
    lines.insert(index[0] + 1, block)
    result = b''.join(lines)
    if result.count(b'zm-specialty-guides/$1/index.html') != 1:
        raise RuntimeError('REWRITE_PATCH_CARDINALITY_ERROR')
    return result


def run():
    if not isinstance(STATIC_PAGES_BASE64, dict) or set(STATIC_PAGES_BASE64) != set(SECTIONS):
        raise RuntimeError('STATIC_GUIDES_NOT_PACKED')
    pages = {s: base64.b64decode(STATIC_PAGES_BASE64[s], validate=True) for s in SECTIONS}
    for slug, page in pages.items():
        if b'<html lang="fa" dir="rtl">' not in page or ('https://zomorodmelal.ir/' + slug + '/').encode() not in page:
            raise RuntimeError('GUIDE_RENDER_INVALID:' + slug)
    validate_environment()
    BACKUPS.mkdir(exist_ok=True, mode=0o700)
    with LOCK.open('a+b') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        validate_environment()
        old = HTACCESS.read_bytes()
        patched = new_htaccess(old)
        for slug in SECTIONS:
            s, _, _ = check('/' + slug + '/')
            if s != 404:
                raise RuntimeError('LIVE_SPECIALTY_PATH_CHANGED:' + slug + ':' + str(s))
        baseline()
        backup = BACKUPS / 'public-html-htaccess-specialties-20261105-39988da61efd.bak'
        if backup.exists() and sha(backup.read_bytes()) != sha(old):
            raise RuntimeError('BACKUP_HASH_CONFLICT')
        if not backup.exists():
            with backup.open('xb') as out:
                out.write(old); out.flush(); os.fsync(out.fileno())
            backup.chmod(0o600)
        old_mode = HTACCESS.stat().st_mode
        made_dir = False
        changed = False
        try:
            FOLDER.mkdir(mode=0o755, exist_ok=False)
            made_dir = True
            os.chmod(FOLDER, 0o755)
            for slug in SECTIONS:
                location = FOLDER / slug
                location.mkdir(mode=0o755)
                os.chmod(location, 0o755)
                atomic_write(location / 'index.html', pages[slug], 0o644)
            if HTACCESS.read_bytes() != old:
                raise RuntimeError('CONCURRENT_HTACCESS_CHANGE_ABORT')
            atomic_write(HTACCESS, patched, old_mode)
            changed = True
            streak = 0
            failures = []
            for i in range(14):
                good, failures = all_ready()
                streak = streak + 1 if good else 0
                if streak >= 2:
                    return {'status': 'LIVE_VERIFIED', 'routes': list(SECTIONS),
                            'htaccess_old_sha256': sha(old), 'htaccess_new_sha256': sha(patched),
                            'backup': str(backup), 'static_folder': str(FOLDER),
                            'public_verifications': 2, 'existing_pages_healthy': True}
                if i < 13:
                    time.sleep(3)
            raise RuntimeError('PUBLIC_VALIDATION_FAILED:' + ','.join(failures))
        except Exception as err:
            if changed:
                if HTACCESS.read_bytes() != patched:
                    raise RuntimeError('CONCURRENT_HTACCESS_CHANGE_MANUAL_REVIEW') from err
                atomic_write(HTACCESS, old, old_mode)
            if made_dir:
                # Delete exclusively our own just-created folder. If any file
                # changed, stop rather than erase concurrent work.
                if sorted(x.name for x in FOLDER.iterdir()) != sorted(SECTIONS):
                    raise RuntimeError('CONCURRENT_GUIDE_FOLDER_CHANGE_MANUAL_REVIEW') from err
                for slug in SECTIONS:
                    folder = FOLDER / slug
                    files = list(folder.iterdir())
                    if len(files) != 1 or files[0].name != 'index.html' or files[0].is_symlink() or files[0].read_bytes() != pages[slug]:
                        raise RuntimeError('CONCURRENT_GUIDE_FILE_CHANGE_MANUAL_REVIEW:' + slug) from err
                for slug in SECTIONS:
                    folder = FOLDER / slug
                    (folder / 'index.html').unlink()
                    folder.rmdir()
                FOLDER.rmdir()
            if HTACCESS.read_bytes() != old:
                raise RuntimeError('ROLLBACK_HTACCESS_SHA_MISMATCH') from err
            baseline()
            raise RuntimeError('ROLLED_BACK_REWRITE_RELEASE:' + str(err)) from err


if __name__ == '__main__':
    if sys.argv[1:] != ['guarded']:
        raise SystemExit('USAGE: guarded')
    try:
        print('ZM_REWRITE_SPECIALTY_RESULT=' + json.dumps(run(), sort_keys=True), flush=True)
    except Exception as exc:
        print('ZM_REWRITE_SPECIALTY_FAILED=' + str(exc), flush=True)
        raise
