#!/usr/bin/env python3
"""Publish four static Zomorod guide pages under the main cPanel DocumentRoot.

No application code, configuration, database, or live pre-existing file is
modified. On failure, remove only directories created by this exact run.
"""
from __future__ import annotations

import base64
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
ACCOUNT = Path('/home/zomorod2')
DOCUMENT_ROOT = ACCOUNT / 'public_html'
HTACCESS = DOCUMENT_ROOT / '.htaccess'
APP = ACCOUNT / 'Saeit'
SECTIONS = ('carpets', 'real-estate', 'restaurant', 'signals')


def public(path: str) -> tuple[int, bytes, str]:
    url = 'https://zomorodmelal.ir' + path + ('&' if '?' in path else '?') + 'zm_static=' + secrets.token_hex(10)
    req = Request(url, headers={'User-Agent': 'ZM-Static-Guide-Guard/1.0',
                                'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
    try:
        with urlopen(req, timeout=9) as response:
            return response.status, response.read(160_000), response.url
    except HTTPError as exc:
        return exc.code, exc.read(2500), exc.url


def guard_host() -> None:
    if os.getuid() != ACCOUNT.stat().st_uid:
        raise RuntimeError('HOST_ACCOUNT_MISMATCH')
    for p in (DOCUMENT_ROOT, HTACCESS):
        if p.is_symlink() or not p.exists():
            raise RuntimeError('DOCUMENT_ROOT_SYMLINK_OR_MISSING')
    text = HTACCESS.read_text(errors='replace')
    roots = re.findall(r'^\s*PassengerAppRoot\s+([^\r\n#]+)', text, re.M | re.I)
    if len(roots) != 1 or roots[0].strip(' \t\"\'') != str(APP):
        raise RuntimeError('MAIN_DOMAIN_PASSENGER_ROOT_MISMATCH')


def baseline() -> None:
    for path in ('/', '/newsletter/'):
        s, _, _ = public(path)
        if s != 200:
            raise RuntimeError('EXISTING_PAGE_UNHEALTHY:' + path + ':' + str(s))
    s, _, final = public('/staff/')
    if s != 200 or not final.startswith('https://zomorodmelal.ir/admin/login/'):
        raise RuntimeError('STAFF_LOGIN_REDIRECT_CHANGED')


def ready() -> tuple[bool, list[str]]:
    issues = []
    for slug in SECTIONS:
        try:
            status, body, _ = public('/' + slug + '/')
            if status != 200 or b'<html lang="fa" dir="rtl">' not in body or slug.encode() not in body:
                issues.append(slug + ':' + str(status))
            if slug == 'signals' and status == 200 and 'سیگنال زنده'.encode() not in body:
                issues.append('signals:RISK_LABEL_MISSING')
        except Exception as exc:
            issues.append(slug + ':' + exc.__class__.__name__)
    try:
        baseline()
    except Exception as exc:
        issues.append('BASELINE:' + str(exc))
    return not issues, issues


def run() -> dict[str, object]:
    if not isinstance(STATIC_PAGES_BASE64, dict) or set(STATIC_PAGES_BASE64) != set(SECTIONS):
        raise RuntimeError('PAGE_EXPORT_NOT_PACKED')
    pages = {key: base64.b64decode(value, validate=True) for key, value in STATIC_PAGES_BASE64.items()}
    for name, body in pages.items():
        if (b'<html lang="fa" dir="rtl">' not in body or
                ('https://zomorodmelal.ir/' + name + '/').encode() not in body or
                (name == 'signals' and 'سیگنال زنده'.encode() not in body)):
            raise RuntimeError('INVALID_EXPORTED_PAGE:' + name)
    guard_host()
    targets = [DOCUMENT_ROOT / s for s in SECTIONS]
    if any(p.exists() or p.is_symlink() for p in targets):
        raise RuntimeError('SPECIALTY_DOCUMENT_ROOT_PATH_ALREADY_EXISTS_ABORT')
    for s in SECTIONS:
        status, _, _ = public('/' + s + '/')
        if status != 404:
            raise RuntimeError('SPECIALTY_PATH_NO_LONGER_404:' + s + ':' + str(status))
    baseline()
    created = []
    try:
        for slug, directory in zip(SECTIONS, targets):
            directory.mkdir(mode=0o755, exist_ok=False)
            created.append((directory, pages[slug]))
            os.chmod(directory, 0o755)
            target = directory / 'index.html'
            tmp = None
            try:
                with tempfile.NamedTemporaryFile(dir=directory, prefix='.zm-static-', delete=False) as f:
                    tmp = f.name
                    f.write(pages[slug]); f.flush(); os.fsync(f.fileno())
                os.chmod(tmp, 0o644)
                os.replace(tmp, target)
                tmp = None
            finally:
                if tmp and os.path.exists(tmp):
                    os.unlink(tmp)
        last_issues = []
        streak = 0
        for index in range(14):
            healthy, last_issues = ready()
            streak = streak + 1 if healthy else 0
            if streak >= 2:
                return {
                    'status': 'LIVE_VERIFIED', 'routes': list(SECTIONS),
                    'served_from': 'public_html/<section>/index.html',
                    'page_sha256': {s: hashlib.sha256(pages[s]).hexdigest() for s in SECTIONS},
                    'healthy_checks': 2,
                    'application_code_touched': False,
                }
            if index < 13:
                time.sleep(3)
        raise RuntimeError('PUBLIC_VALIDATION_FAILED:' + ','.join(last_issues))
    except Exception as err:
        # Created directories have no prior user data. Abort cleanup on any
        # unexpected file or concurrent edit; never erase another actor's work.
        for directory, expected in reversed(created):
            index = directory / 'index.html'
            entries = list(directory.iterdir())
            if not entries:
                directory.rmdir()
                continue
            if entries != [index] or index.is_symlink() or index.read_bytes() != expected:
                raise RuntimeError('CONCURRENT_STATIC_FILE_CHANGE_MANUAL_REVIEW:' + str(directory)) from err
            index.unlink()
            directory.rmdir()
        baseline()
        raise RuntimeError('ROLLED_BACK_STATIC_RELEASE:' + str(err)) from err


if __name__ == '__main__':
    if sys.argv[1:] != ['guarded']:
        raise SystemExit('USAGE: guarded')
    try:
        print('ZM_STATIC_SPECIALTY_RESULT=' + json.dumps(run(), sort_keys=True), flush=True)
    except Exception as exc:
        print('ZM_STATIC_SPECIALTY_FAILED=' + str(exc), flush=True)
        raise
