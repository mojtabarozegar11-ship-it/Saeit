#!/usr/bin/env python3
"""Reversible, one-file commercial navigation and SEO correction on live Zomorod.

This release only changes the public static homepage HTML. It never touches
payments, customer submissions, databases, sessions, or background workers.
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
PUBLIC = HOME / 'public_html'
TARGET = PUBLIC / 'index.html'
PRIVATE = HOME / '.private'
BACKUPS = PRIVATE / 'zm-home-services-seo-backups'
OLD_META = ('<meta name="description" content="زمرد ملل؛ تحقیقات و پژوهش‌های علمی '
            'و ژنتیکی در حوزه‌های کشاورزی، صنعت و فناوری.">')
NEW_META = ('<meta name="description" content="شرکت خدمات کشاورزی زمرد ملل؛ '
            'تحلیل اقتصادی مزرعه، مدیریت منابع آب، امکان‌سنجی طرح تولید و '
            'پژوهش‌های کاربردی. ثبت درخواست خدمات تخصصی و همکاری.">')
OLD_NAV = '<a href="#orbit-15"><span>✦</span>خدمات</a>'
NEW_NAV = '<a href="/services/"><span>✦</span>خدمات</a>'
EXISTING_FORM_ID = 'id="zm-service-entry-home-20261106"'
EXISTING_FORM_URL = 'href="/ask-master/index.php?service=1"'


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def transform(source: str) -> tuple[str, str]:
    if source.count(EXISTING_FORM_ID) != 1 or source.count(EXISTING_FORM_URL) < 1:
        raise RuntimeError('REFUSE_MISSING_EXISTING_LIVE_LEAD_PATH')
    if source.count('<link rel="canonical" href="https://zomorodmelal.ir/">') != 1:
        raise RuntimeError('REFUSE_DIFFERENT_CANONICAL_PAGE')
    old = (source.count(OLD_META), source.count(OLD_NAV))
    new = (source.count(NEW_META), source.count(NEW_NAV))
    if old == (0, 0) and new == (1, 1):
        return 'already-patched', source
    if old != (1, 1) or new != (0, 0):
        raise RuntimeError('REFUSE_PARTIAL_PATCH_OR_SOURCE_DRIFT')
    result = source.replace(OLD_META, NEW_META, 1).replace(OLD_NAV, NEW_NAV, 1)
    if result.count(NEW_META) != 1 or result.count(NEW_NAV) != 1:
        raise RuntimeError('INVALID_TRANSFORMATION')
    return 'needs-patch', result


def validate_origin() -> None:
    if os.geteuid() == 0 or not PUBLIC.is_dir() or os.geteuid() != PUBLIC.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_CPANEL_ACCOUNT')
    if any(p.is_symlink() for p in (HOME, PUBLIC, PRIVATE, TARGET, BACKUPS)):
        raise RuntimeError('REFUSE_SYMLINK_BOUNDARY')
    if not PRIVATE.is_dir() or not TARGET.is_file():
        raise RuntimeError('REFUSE_MISSING_TARGET_OR_BACKUP_ROOT')
    if not (100_000 <= TARGET.stat().st_size <= 2_000_000):
        raise RuntimeError('REFUSE_UNEXPECTED_HOMEPAGE_SIZE')


def snapshot() -> dict[str, object]:
    validate_origin()
    old = TARGET.read_bytes()
    state, result = transform(old.decode('utf-8'))
    changed = result.encode('utf-8')
    return {
        'old': old,
        'new': changed,
        'old_sha': digest(old),
        'new_sha': digest(changed),
        'mode': stat.S_IMODE(TARGET.stat().st_mode),
        'state': state,
    }


def run_folder(runid: str) -> Path:
    if not re.fullmatch(r'[0-9]{5,20}', runid):
        raise RuntimeError('INVALID_RUN_IDENTIFIER')
    if BACKUPS.is_symlink():
        raise RuntimeError('REFUSE_SYMLINK_BACKUP_DIR')
    return BACKUPS / runid


def atomic_write(content: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix='.zm-home-services-seo-', dir=str(PUBLIC))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, TARGET)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def preview() -> None:
    record = snapshot()
    print('HOME_SERVICES_SEO_STATE=' + str(record['state']))
    print('HOME_SERVICES_SEO_ORIGIN_SHA=' + str(record['old_sha']))
    print('HOME_SERVICES_SEO_PROPOSED_SHA=' + str(record['new_sha']))


def publish(runid: str) -> None:
    record = snapshot()
    if record['state'] != 'needs-patch':
        raise RuntimeError('REFUSE_REPEATED_RELEASE')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    os.chmod(BACKUPS, 0o700)
    folder = run_folder(runid)
    folder.mkdir(mode=0o700)
    original = folder / 'index.html'
    with original.open('xb') as output:
        output.write(record['old'])
        output.flush()
        os.fsync(output.fileno())
    original.chmod(0o600)
    manifest = {
        'old_sha': record['old_sha'],
        'new_sha': record['new_sha'],
        'mode': record['mode'],
    }
    metadata = folder / 'manifest.json'
    with metadata.open('x', encoding='utf-8') as output:
        json.dump(manifest, output, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    metadata.chmod(0o600)
    if TARGET.is_symlink() or digest(TARGET.read_bytes()) != record['old_sha']:
        raise RuntimeError('REFUSE_CONCURRENT_HOMEPAGE_EDIT')
    atomic_write(record['new'], record['mode'])
    print('HOME_SERVICES_SEO_ORIGIN_PUBLISHED=1')


def manifest_for(runid: str) -> tuple[dict[str, object], bytes]:
    folder = run_folder(runid)
    if folder.is_symlink() or not folder.is_dir():
        raise RuntimeError('REFUSE_INVALID_RESTORE_FOLDER')
    metadata = folder / 'manifest.json'
    original = folder / 'index.html'
    if metadata.is_symlink() or original.is_symlink():
        raise RuntimeError('REFUSE_BACKUP_SYMLINK')
    manifest = json.loads(metadata.read_text(encoding='utf-8'))
    raw = original.read_bytes()
    if digest(raw) != manifest['old_sha']:
        raise RuntimeError('REFUSE_DAMAGED_BACKUP')
    return manifest, raw


def verify(runid: str) -> None:
    record = snapshot()
    manifest, _ = manifest_for(runid)
    if record['state'] != 'already-patched' or record['old_sha'] != manifest['new_sha']:
        raise RuntimeError('REFUSE_FAILED_ORIGIN_VERIFICATION')
    print('HOME_SERVICES_SEO_ORIGIN_VERIFIED=1')


def rollback(runid: str) -> None:
    validate_origin()
    manifest, original = manifest_for(runid)
    current = TARGET.read_bytes()
    if digest(current) == manifest['old_sha']:
        print('HOME_SERVICES_SEO_ALREADY_RESTORED=1')
        return
    if digest(current) != manifest['new_sha']:
        raise RuntimeError('REFUSE_ROLLBACK_OF_FOREIGN_CHANGE')
    atomic_write(original, int(manifest['mode']))
    if digest(TARGET.read_bytes()) != manifest['old_sha']:
        raise RuntimeError('BACKUP_RESTORE_VERIFICATION_FAILED')
    print('HOME_SERVICES_SEO_RESTORED=1')


def selftest() -> None:
    original = ('<head><link rel="canonical" href="https://zomorodmelal.ir/">'
                + OLD_META + '</head><body>' + OLD_NAV + EXISTING_FORM_ID
                + ' ' + EXISTING_FORM_URL + '</body>')
    state, new = transform(original)
    assert state == 'needs-patch'
    assert NEW_META in new and NEW_NAV in new
    assert transform(new) == ('already-patched', new)
    for broken in (original.replace(OLD_NAV, ''), original.replace(OLD_META, ''),
                   original + OLD_NAV):
        try:
            transform(broken)
        except RuntimeError:
            pass
        else:
            raise AssertionError('DRIFT_MUST_FAIL_CLOSED')
    print('HOME_SERVICES_SEO_SELFTEST_OK=1')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['selftest']:
        selftest()
    elif args == ['preview']:
        preview()
    elif len(args) == 2 and args[0] in ('publish', 'verify', 'rollback'):
        action, run_id = args
        {'publish': publish, 'verify': verify, 'rollback': rollback}[action](run_id)
    else:
        raise RuntimeError('UNKNOWN_OR_UNSAFE_MODE')
