#!/usr/bin/env python3
"""One-use, exact-version cPanel repair for reverted agricultural offer URLs.

The 2026-11-06 logo publisher copied an old full services.html snapshot and
lost three context-bearing form links. This tool changes only those links.
Never writes a lead, email, or order. Refuses any concurrent content change.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

WEB = Path('/home/zomorod2/public_html')
TARGET = WEB / 'services/index.html'
ROOT = Path('/home/zomorod2/.private/zm-service-link-recovery')
EXPECTED_OLD = 'f7d6dbd2d9998518cf0fe151b2c9cb6cf9a1ecc68b0eadf67bf75156d1719f65'
OFFERS = (
    ('استعلام ارزیابی اقتصادی ←', 'economics'),
    ('استعلام مدیریت منابع ←', 'water'),
    ('استعلام امکان‌سنجی ←', 'feasibility'),
)


def digest(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def expected_new(original: bytes) -> bytes:
    html = original.decode('utf-8')
    if (html.count('zm-service-deliverables-20261106') != 2
            or html.count('zm-specialist-intent-20261106:services') != 1):
        raise RuntimeError('UNEXPECTED_SERVICES_STRUCTURE')
    for label, topic in OFFERS:
        before = ('<a href="/ask-master/index.php?service=1" '
                  'style="font-weight:bold;color:#14583a">' + label + '</a>')
        after = before.replace('?service=1"', '?service=1&amp;topic=' + topic + '"')
        if html.count(before) != 1 or after in html:
            raise RuntimeError('UNEXPECTED_OFFER_ANCHOR:' + topic)
        html = html.replace(before, after, 1)
    return html.encode('utf-8')


def validate() -> None:
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_UNTRUSTED_USER')
    boundary = TARGET.parent / '.htaccess'
    for path in (WEB, TARGET.parent, TARGET, boundary, ROOT.parent):
        if path.is_symlink():
            raise RuntimeError('REFUSE_SYMLINK')
    if not TARGET.is_file() or not boundary.is_file():
        raise RuntimeError('REFUSE_MISSING_TARGET')
    if 'PassengerEnabled off' not in boundary.read_text():
        raise RuntimeError('REFUSE_NONSTATIC_SERVICES')


def atomic(payload: bytes, mode: int) -> None:
    handle, name = tempfile.mkstemp(prefix='.zm-offer-recover-', dir=str(TARGET.parent))
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, TARGET)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def evidence_dir(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{5,20}', run_id):
        raise RuntimeError('INVALID_RUN_ID')
    return ROOT / run_id


def preview() -> None:
    validate()
    old = TARGET.read_bytes()
    if digest(old) != EXPECTED_OLD:
        raise RuntimeError('REFUSE_DIFFERENT_ORIGIN_VERSION:' + digest(old))
    new = expected_new(old)
    print('RECOVERY_OLD_SHA=' + digest(old))
    print('RECOVERY_EXPECTED_NEW_SHA=' + digest(new))
    print('RECOVERY_CONSTRAINT=THREE_LINKS_ONLY')


def publish(run_id: str) -> None:
    validate()
    old = TARGET.read_bytes()
    if digest(old) != EXPECTED_OLD:
        raise RuntimeError('REFUSE_DIFFERENT_ORIGIN_VERSION:' + digest(old))
    new = expected_new(old)
    mode = stat.S_IMODE(TARGET.stat().st_mode)
    ROOT.mkdir(parents=True, mode=0o700, exist_ok=True)
    folder = evidence_dir(run_id)
    folder.mkdir(mode=0o700)
    with (folder / 'before.html').open('xb') as file:
        file.write(old)
    (folder / 'before.html').chmod(0o600)
    (folder / 'manifest.json').write_text(json.dumps({
        'old_sha': digest(old), 'new_sha': digest(new), 'mode': mode,
        'purpose': 'restore exactly three customer-service topic URLs'
    }))
    (folder / 'manifest.json').chmod(0o600)
    if digest(TARGET.read_bytes()) != EXPECTED_OLD:
        raise RuntimeError('REFUSE_CONCURRENT_UPDATE')
    atomic(new, mode)
    print('RECOVERY_PUBLISHED_NEW_SHA=' + digest(new))


def verify(run_id: str) -> None:
    validate()
    manifest = json.loads((evidence_dir(run_id) / 'manifest.json').read_text())
    current = TARGET.read_bytes()
    if digest(current) != manifest['new_sha']:
        raise RuntimeError('RECOVERY_ORIGIN_SHA_MISMATCH')
    for _, topic in OFFERS:
        if current.count(('?service=1&amp;topic=' + topic).encode()) != 1:
            raise RuntimeError('RECOVERY_MISSING_TOPIC:' + topic)
    print('RECOVERY_ORIGIN_VERIFIED=1')


def rollback(run_id: str) -> None:
    validate()
    folder = evidence_dir(run_id)
    manifest = json.loads((folder / 'manifest.json').read_text())
    old = (folder / 'before.html').read_bytes()
    if digest(old) != manifest['old_sha']:
        raise RuntimeError('RECOVERY_BACKUP_CORRUPT')
    current = digest(TARGET.read_bytes())
    if current == manifest['old_sha']:
        print('RECOVERY_ALREADY_ROLLED_BACK=1')
        return
    if current != manifest['new_sha']:
        raise RuntimeError('REFUSE_ROLLBACK_CONCURRENT_CHANGE')
    atomic(old, manifest['mode'])
    print('RECOVERY_ROLLED_BACK=1')


def selftest() -> None:
    sample = ('zm-service-deliverables-20261106 zm-service-deliverables-20261106 '
              'zm-specialist-intent-20261106:services '
              + ' '.join('<a href="/ask-master/index.php?service=1" '
                         'style="font-weight:bold;color:#14583a">' + label + '</a>'
                         for label, _ in OFFERS)).encode()
    new = expected_new(sample)
    assert new != sample
    assert len(new) > len(sample)
    for _, topic in OFFERS:
        assert new.count(('?service=1&amp;topic=' + topic).encode()) == 1
    print('RECOVERY_SELFTEST=4_CHECKS_OK')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['selftest']:
        selftest()
    elif args == ['preview']:
        preview()
    elif len(args) == 2 and args[0] in ('publish','verify','rollback'):
        {'publish':publish, 'verify':verify, 'rollback':rollback}[args[0]](args[1])
    else:
        raise RuntimeError('UNSAFE_RECOVERY_MODE')
