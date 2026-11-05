#!/usr/bin/env python3
"""Cautious cPanel/Passenger release of four Zomorod public guide routes.

Injected SPECIALTY_SOURCE_BASE64 is supplied by the workflow from the matching
repository source file. This installer never modifies the site database.
"""
from __future__ import annotations

import ast
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

SPECIALTY_SOURCE_BASE64 = None  # Packed by the workflow; never a network fetch.
APP = Path('/home/zomorod2/Saeit')
HOME = APP.parent
URLS = APP / 'config/urls.py'
SOURCE = APP / 'core/specialty_pages.py'
HTACCESS = HOME / 'public_html/.htaccess'
RESTART = APP / 'tmp/restart.txt'
BACKUPS = APP / '.route-backups'
LOCK = BACKUPS / 'specialty-pages-20261105.lock'
SECTIONS = ('carpets', 'real-estate', 'restaurant', 'signals')
IMPORT = b'from core.specialty_pages import specialty_page\n'
ROUTES = b''.join(
    ('    path("' + slug + '/", specialty_page, {"section": "' + slug + '"}, name="specialty_' + slug.replace('-', '_') + '"),\n').encode()
    for slug in SECTIONS
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get(path: str) -> tuple[int, bytes, str]:
    req = Request('https://zomorodmelal.ir' + path + ('&' if '?' in path else '?')
                  + 'zm_specialty_release=' + secrets.token_hex(8),
                  headers={'User-Agent': 'ZM-Specialty-Guard/1.0',
                           'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
    try:
        with urlopen(req, timeout=9) as resp:
            return resp.status, resp.read(190_000), resp.url
    except HTTPError as exc:
        return exc.code, exc.read(2000), exc.url


def guard_account() -> None:
    if os.getuid() != HOME.stat().st_uid:
        raise RuntimeError('HOST_ACCOUNT_UID_MISMATCH')
    for p in (APP, SOURCE.parent, URLS.parent, RESTART):
        if p.is_symlink():
            raise RuntimeError('SYMLINK_REFUSED:' + str(p))
    if not RESTART.is_file() or RESTART.stat().st_uid != os.getuid() or not os.access(RESTART, os.W_OK):
        raise RuntimeError('PASSENGER_RESTART_UNAVAILABLE')
    ht = HTACCESS.read_text(errors='replace')
    roots = re.findall(r'^\s*PassengerAppRoot\s+([^\r\n#]+)', ht, re.M | re.I)
    if len(roots) != 1 or roots[0].strip(' \t\"\'') != str(APP):
        raise RuntimeError('PASSENGER_ROOT_NOT_THIS_SITE')
    ast.parse((APP / 'config/settings.py').read_text(), filename='settings.py')
    ast.parse((APP / 'passenger_wsgi.py').read_text(), filename='passenger_wsgi.py')


def atomic_write(target: Path, content: bytes, mode: int) -> None:
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.zm-specialty-', delete=False) as out:
            tmp = out.name
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, stat.S_IMODE(mode))
        os.replace(tmp, target)
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def public_baseline() -> None:
    for route in ('/', '/newsletter/'):
        status, _, _ = get(route)
        if status != 200:
            raise RuntimeError('BASELINE_UNHEALTHY:' + route + ':' + str(status))
    status, _, dest = get('/staff/')
    if status != 200 or not dest.startswith('https://zomorodmelal.ir/admin/login/'):
        raise RuntimeError('STAFF_AUTH_REDIRECT_CHANGED')


def guides_ready() -> tuple[bool, list[str]]:
    problems = []
    for route in SECTIONS:
        try:
            status, body, _ = get('/' + route + '/')
            if status != 200 or b'<html lang="fa" dir="rtl">' not in body or route.encode() not in body:
                problems.append(route + ':' + str(status) + ':NOT_NEW_GUIDE')
            elif route == 'signals' and 'سیگنال زنده'.encode() not in body:
                problems.append('signals:INACCURATE_RISK_LABEL')
        except Exception as exc:
            problems.append(route + ':' + exc.__class__.__name__)
    try:
        public_baseline()
    except Exception as exc:
        problems.append('BASELINE:' + str(exc))
    return not problems, problems


def await_guides(attempts: int) -> tuple[bool, list[str]]:
    problems = []
    streak = 0
    for i in range(attempts):
        ready, problems = guides_ready()
        streak = streak + 1 if ready else 0
        if streak >= 2:
            return True, []
        if i + 1 < attempts:
            time.sleep(3)
    return False, problems


def run() -> dict[str, object]:
    if not isinstance(SPECIALTY_SOURCE_BASE64, bytes):
        raise RuntimeError('WORKFLOW_SOURCE_NOT_PACKED')
    source_new = base64.b64decode(SPECIALTY_SOURCE_BASE64, validate=True)
    ast.parse(source_new, filename='specialty_pages.py')
    if b'"signals"' not in source_new or b'"carpets"' not in source_new:
        raise RuntimeError('MISSING_EXPECTED_PAGE_REGISTRY')
    guard_account()
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    with LOCK.open('a+b') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        urls_old = URLS.read_bytes()
        ast.parse(urls_old, filename='live_urls.py')
        if SOURCE.exists() or SOURCE.is_symlink():
            raise RuntimeError('SPECIALTY_SOURCE_ALREADY_EXISTS_REVIEW_REQUIRED')
        for slug in SECTIONS:
            if re.search(rb'path\s*\(\s*[\"\']' + slug.encode() + rb'/[\"\']', urls_old):
                raise RuntimeError('ROUTE_ALREADY_PRESENT:' + slug)
        if IMPORT in urls_old or urls_old.count(b'urlpatterns = [\n') != 1:
            raise RuntimeError('LIVE_URLS_UNEXPECTED_STRUCTURE')
        for slug in SECTIONS:
            status, _, _ = get('/' + slug + '/')
            if status != 404:
                raise RuntimeError('ROUTE_NO_LONGER_404:' + slug + ':' + str(status))
        public_baseline()
        anchor = b'urlpatterns = [\n'
        urls_new = urls_old.replace(anchor, IMPORT + b'\n' + anchor + ROUTES, 1)
        ast.parse(urls_new, filename='new_urls.py')
        # Keep an immutable backup of the exact live URL file before any change.
        backup = BACKUPS / ('urls-specialties-20261105-' + digest(urls_old)[:12] + '.py')
        if backup.exists() and digest(backup.read_bytes()) != digest(urls_old):
            raise RuntimeError('BACKUP_CONTENT_CONFLICT')
        if not backup.exists():
            with backup.open('xb') as f:
                f.write(urls_old)
                f.flush()
                os.fsync(f.fileno())
            backup.chmod(0o600)
        if URLS.read_bytes() != urls_old:
            raise RuntimeError('CONCURRENT_URL_EDIT_ABORT')
        urls_mode = URLS.stat().st_mode
        deployed = False
        changed = False
        try:
            atomic_write(SOURCE, source_new, 0o644)
            deployed = True
            atomic_write(URLS, urls_new, urls_mode)
            changed = True
            os.utime(RESTART, None)
            ok, problems = await_guides(12)
            if ok:
                return {
                    'status': 'LIVE_VERIFIED', 'routes': list(SECTIONS),
                    'source_sha256': digest(source_new), 'urls_old_sha256': digest(urls_old),
                    'urls_new_sha256': digest(urls_new), 'backup': str(backup),
                    'public_check': '2_CONSECUTIVE_SUCCESSES', 'passenger_reloaded': True,
                }
            raise RuntimeError('PUBLIC_GUIDE_CHECK_FAILED:' + ','.join(problems))
        except Exception as exc:
            # Do not overwrite concurrent edits, even during rollback.
            if changed:
                if URLS.read_bytes() != urls_new:
                    raise RuntimeError('CONCURRENT_URL_CHANGE_ABORT_MANUAL_ROLLBACK') from exc
                atomic_write(URLS, urls_old, urls_mode)
            if deployed:
                if SOURCE.read_bytes() != source_new:
                    raise RuntimeError('CONCURRENT_PAGE_CHANGE_ABORT_MANUAL_ROLLBACK') from exc
                SOURCE.unlink()
            os.utime(RESTART, None)
            # Do not claim successful rollback unless exact source restored.
            if URLS.read_bytes() != urls_old or SOURCE.exists():
                raise RuntimeError('ROLLBACK_FILE_STATE_INVALID') from exc
            try:
                public_baseline()
            except Exception as restore_exc:
                raise RuntimeError('ROLLED_BACK_BUT_SITE_HEALTH_UNKNOWN:' + str(restore_exc)) from exc
            raise RuntimeError('ROLLED_BACK_AFTER_RELEASE_FAILURE:' + str(exc)) from exc


if __name__ == '__main__':
    if sys.argv[1:] != ['guarded']:
        raise SystemExit('USAGE: guarded')
    try:
        result = run()
        print('ZM_SPECIALTY_DEPLOY_RESULT=' + json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    except Exception as exc:
        print('ZM_SPECIALTY_DEPLOY_FAILED=' + str(exc), flush=True)
        raise
