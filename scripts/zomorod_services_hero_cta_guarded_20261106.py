#!/usr/bin/env python3
"""Connect existing live services hero directly to the real inquiry funnel.

No new offers, DB changes or messages. One SHA-guarded HTML replacement with
an exact private backup, atomic publish and conservative rollback.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

HOME = Path('/home/zomorod2')
WEB = HOME / 'public_html'
PAGE = WEB / 'services/index.html'
PREVIOUS = HOME / '.private/zomorod-farm-margin-backups/42166899770/manifest.json'
EXPECTED = '9b9df3f31b9a0981ab8e3ec1103aae450bc14d4f5be1acccfb6dc259cfb46462'
BACKUP = HOME / '.private/zomorod-hero-cta-backups'
MARKER = 'zm-service-hero-cta-20261106'
OLD = ('<div class="zm-actions"><a class="zm-link" href="/company/">'
       'بررسی ساختار فعالیت شرکت ←</a><a class="zm-link zm-link-ghost" '
       'href="/agriculture/">راهنماهای کشاورزی ↗</a></div>')
NEW = ('<div class="zm-actions" data-zm-hero-cta="' + MARKER + '">'
       '<a class="zm-link" href="/ask-master/index.php?service=1">'
       'درخواست خدمات و پیشنهاد تخصصی ←</a>'
       '<a class="zm-link zm-link-ghost" '
       'href="#zm-farm-margin-calculator-20261106">'
       'محاسبهٔ اقتصادی مزرعه ↘</a></div>')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate() -> None:
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('HERO_REFUSE_WRONG_SITE_USER')
    for part in (WEB, PAGE.parent, PAGE, PREVIOUS, BACKUP, BACKUP.parent):
        if part.is_symlink():
            raise RuntimeError('HERO_REFUSE_SYMLINK')
    if not PAGE.is_file() or not PREVIOUS.is_file():
        raise RuntimeError('HERO_REQUIRED_PREDECESSOR_MISSING')
    htaccess = PAGE.parent / '.htaccess'
    if not htaccess.is_file() or 'PassengerEnabled off' not in htaccess.read_text():
        raise RuntimeError('HERO_REFUSE_NOT_STATIC_PAGE')
    if json.loads(PREVIOUS.read_text())['new_sha'] != EXPECTED:
        raise RuntimeError('HERO_REFUSE_UNRECOGNIZED_PREDECESSOR')


def transformed(raw: bytes) -> bytes:
    page = raw.decode('utf-8')
    if page.count(OLD) != 1 or MARKER in page:
        raise RuntimeError('HERO_CHANGED_OR_ALREADY_APPLIED')
    for marker in ('zm-farm-margin-calculator-20261106',
                   'zm-service-deliverables-20261106',
                   'zm-specialist-intent-20261106:services'):
        if marker not in page:
            raise RuntimeError('HERO_MISSING_EXISTING_FUNCTION:' + marker)
    return page.replace(OLD, NEW, 1).encode('utf-8')


def preflight() -> tuple[bytes, bytes, int]:
    validate()
    old = PAGE.read_bytes()
    if sha(old) != EXPECTED:
        raise RuntimeError('HERO_REFUSE_DIFFERENT_LIVE_VERSION')
    return old, transformed(old), stat.S_IMODE(PAGE.stat().st_mode)


def atomic(data: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix='.zm-hero-cta-', dir=str(PAGE.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, PAGE)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def folder(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{5,20}', run_id):
        raise RuntimeError('HERO_INVALID_RUN_ID')
    return BACKUP / run_id


def rollback(run_id: str) -> None:
    root = folder(run_id)
    manifest = json.loads((root / 'manifest.json').read_text())
    prior = (root / 'services.backup').read_bytes()
    if sha(prior) != manifest['old_sha']:
        raise RuntimeError('HERO_CORRUPT_BACKUP')
    current = sha(PAGE.read_bytes())
    if current == manifest['new_sha']:
        atomic(prior, manifest['mode'])
        print('HERO_ROLLED_BACK=1')
    elif current == manifest['old_sha']:
        print('HERO_ALREADY_ROLLED_BACK=1')
    else:
        raise RuntimeError('HERO_REFUSE_OVERWRITE_NEWER_CHANGE')


def publish(run_id: str) -> None:
    old, updated, mode = preflight()
    BACKUP.mkdir(mode=0o700, exist_ok=True)
    root = folder(run_id)
    root.mkdir(mode=0o700)
    with (root / 'services.backup').open('xb') as stream:
        stream.write(old)
    (root / 'services.backup').chmod(0o600)
    manifest = {'old_sha': sha(old), 'new_sha': sha(updated), 'mode': mode}
    (root / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True))
    (root / 'manifest.json').chmod(0o600)
    try:
        if sha(PAGE.read_bytes()) != manifest['old_sha']:
            raise RuntimeError('HERO_CONCURRENT_EDIT')
        atomic(updated, mode)
    except Exception:
        rollback(run_id)
        raise
    print('HERO_PUBLISHED=1')


def verify(run_id: str) -> None:
    validate()
    manifest = json.loads((folder(run_id) / 'manifest.json').read_text())
    raw = PAGE.read_bytes()
    if sha(raw) != manifest['new_sha'] or raw.count(MARKER.encode()) != 1:
        raise RuntimeError('HERO_ORIGIN_VERIFY_FAILED')
    print('HERO_ORIGIN_VERIFIED=1')


def selftest() -> None:
    sample = ('<main>zm-farm-margin-calculator-20261106 '
              'zm-service-deliverables-20261106 '
              'zm-specialist-intent-20261106:services ' + OLD + '</main>').encode('utf-8')
    updated = transformed(sample).decode('utf-8')
    assert updated.count(MARKER) == 1 and updated.count('service=1') == 1
    assert updated.count('#zm-farm-margin-calculator-20261106') == 1
    assert 'بررسی ساختار فعالیت شرکت ←' not in updated
    print('HERO_GUARDED_SELFTEST_OK=1')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['selftest']:
        selftest()
    elif args == ['preview']:
        old, updated, _ = preflight()
        print('HERO_PREFLIGHT_ORIGIN_SHA=' + sha(old))
        print('HERO_TARGET_SHA=' + sha(updated))
    elif len(args) == 2 and args[0] in ('publish', 'verify', 'rollback'):
        if args[0] == 'publish':
            publish(args[1])
        elif args[0] == 'verify':
            verify(args[1])
        else:
            validate()
            rollback(args[1])
    else:
        raise RuntimeError('HERO_UNKNOWN_MODE')
