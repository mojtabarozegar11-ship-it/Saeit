#!/usr/bin/env python3
"""Guarded, reversible direct service-request entry points on two live pages.

Operates only on the existing static home and agriculture HTML files.  It
never posts a customer form, opens a private customer database, or sends mail.
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
BACKUPS = HOME / '.private/zomorod-service-entry-backups'
MARKER = 'zm-service-entry-cta-20261106'

HOME_ANCHOR = ('<a class="primary-link" href="#orbit-01"><span class="cta-spark" '
               'aria-hidden="true">✦</span> ورود به دنیای زمرد ملل '
               '<span aria-hidden="true">←</span></a>')
AGRI_ANCHOR = '<a class="cta" href="#domains">انتخاب حوزهٔ کشاورزی ←</a>'

HOME_ADDITION = (
    '<!-- ' + MARKER + ':home -->'
    '<a id="zm-service-entry-home-20261106" class="primary-link" '
    'href="/ask-master/index.php" style="margin-inline-start:12px;margin-top:9px" '
    'aria-label="درخواست خدمات تخصصی کشاورزی و اقتصادی">'
    'درخواست خدمات تخصصی <span aria-hidden="true">←</span></a>'
    '<p style="font-size:clamp(13px,1.1vw,15px);margin-top:9px">'
    'امکان‌سنجی اقتصادی، بهره‌وری تولید و مدیریت منابع؛ '
    'در فرم، گزینهٔ «درخواست خدمات تخصصی» را انتخاب کنید.</p>'
)
AGRI_ADDITION = (
    '<!-- ' + MARKER + ':agriculture -->'
    '<a id="zm-service-entry-agriculture-20261106" class="cta" '
    'href="/ask-master/index.php" style="margin-inline-start:12px;margin-top:9px">'
    'استعلام خدمات تخصصی کشاورزی ←</a>'
    '<p style="font-size:14px;margin:12px 0 0">'
    'برای بررسی اقتصادی مزرعه، برنامهٔ مدیریت آب یا طراحی و ارزیابی پروژه، '
    'در فرم گزینهٔ «درخواست خدمات تخصصی» را انتخاب کنید. '
    'ارسال درخواست به معنی پذیرش پروژه یا تعیین قیمت نیست.</p>'
)

TARGETS = {
    'home': (WEB / 'index.html', HOME_ANCHOR, HOME_ADDITION,
             ('<main id="content">', '<h1 id="hero-title">')),
    'agriculture': (WEB / 'agriculture/index.html', AGRI_ANCHOR,
                    AGRI_ADDITION, ('<main class="frame">', 'کشاورزی | زمرد ملل')),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_environment() -> None:
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_SITE_USER')
    if WEB.is_symlink() or BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError('REFUSE_SYMLINK_PATH')
    for file, _, _, _ in TARGETS.values():
        if file.is_symlink() or file.parent.is_symlink() or not file.is_file():
            raise RuntimeError('REFUSE_UNEXPECTED_PUBLIC_FILE')
    route_boundary = WEB / 'agriculture/.htaccess'
    if (route_boundary.is_symlink() or not route_boundary.is_file() or
            'PassengerEnabled off' not in route_boundary.read_text(encoding='utf-8')):
        raise RuntimeError('REFUSE_NONSTATIC_AGRICULTURE_ROUTE')


def transform(key: str, source: str) -> tuple[str, str]:
    if key not in TARGETS:
        raise RuntimeError('UNKNOWN_TARGET')
    _, anchor, addition, required = TARGETS[key]
    if any(source.count(token) != 1 for token in required):
        raise RuntimeError('REFUSE_CHANGED_PAGE_STRUCTURE:' + key)
    if source.count(anchor) != 1:
        raise RuntimeError('REFUSE_CHANGED_CALL_TO_ACTION:' + key)
    marker = MARKER + ':' + key
    if marker in source:
        if source.count(marker) != 1 or source.count(addition) != 1:
            raise RuntimeError('PARTIAL_SERVICE_ENTRY_PATCH:' + key)
        return 'already-patched', source
    if MARKER in source:
        raise RuntimeError('REFUSE_FOREIGN_SERVICE_ENTRY_PATCH:' + key)
    if len(source) < (30000 if key == 'home' else 6000):
        raise RuntimeError('REFUSE_TRUNCATED_PAGE:' + key)
    return 'needs-patch', source.replace(anchor, anchor + addition, 1)


def snapshot() -> dict[str, dict]:
    validate_environment()
    result = {}
    for key, (file, _, _, _) in TARGETS.items():
        old = file.read_bytes()
        state, patched = transform(key, old.decode('utf-8'))
        result[key] = {
            'file': file,
            'old': old,
            'new': patched.encode('utf-8'),
            'sha_old': digest(old),
            'sha_new': digest(patched.encode('utf-8')),
            'mode': stat.S_IMODE(file.stat().st_mode),
            'state': state,
        }
    return result


def atomic(target: Path, content: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix='.zm-service-entry-', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def backup_folder(runid: str) -> Path:
    if not re.fullmatch(r'[0-9]{5,20}', runid):
        raise RuntimeError('REFUSE_INVALID_RUN_ID')
    return BACKUPS / runid


def restore(runid: str) -> None:
    folder = backup_folder(runid)
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    for key, (file, _, _, _) in TARGETS.items():
        metadata = manifest[key]
        old = (folder / (key + '.index.html')).read_bytes()
        if digest(old) != metadata['sha_old']:
            raise RuntimeError('REFUSE_CORRUPT_BACKUP:' + key)
        current = file.read_bytes()
        current_sha = digest(current)
        if current_sha == metadata['sha_old']:
            continue
        if current_sha != metadata['sha_new']:
            raise RuntimeError('REFUSE_ROLLBACK_OF_FOREIGN_CHANGE:' + key)
        atomic(file, old, metadata['mode'])
        print('SERVICE_ENTRY_ROLLED_BACK=' + key)


def preview() -> None:
    for key, value in snapshot().items():
        print('SERVICE_ENTRY_PREVIEW=' + key + ':' + value['state'])
        print('SERVICE_ENTRY_ORIGIN_SHA256=' + key + ':' + value['sha_old'])


def publish(runid: str) -> None:
    values = snapshot()
    if any(row['state'] != 'needs-patch' for row in values.values()):
        raise RuntimeError('REFUSE_REPEATED_OR_PARTIAL_DEPLOYMENT')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    os.chmod(BACKUPS, 0o700)
    folder = backup_folder(runid)
    folder.mkdir(mode=0o700)
    manifest = {}
    for key, row in values.items():
        backup = folder / (key + '.index.html')
        with backup.open('xb') as stream:
            stream.write(row['old'])
        backup.chmod(0o600)
        manifest[key] = {name: row[name] for name in ('sha_old', 'sha_new', 'mode')}
    metadata = folder / 'manifest.json'
    metadata.write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')
    metadata.chmod(0o600)
    try:
        for key, row in values.items():
            file = row['file']
            if file.is_symlink() or digest(file.read_bytes()) != row['sha_old']:
                raise RuntimeError('REFUSE_CONCURRENT_PAGE_UPDATE:' + key)
            atomic(file, row['new'], row['mode'])
            print('SERVICE_ENTRY_PUBLISHED=' + key)
    except Exception:
        restore(runid)
        raise


def verify(runid: str) -> None:
    manifest = json.loads((backup_folder(runid) / 'manifest.json').read_text(encoding='utf-8'))
    for key, row in snapshot().items():
        if row['state'] != 'already-patched' or row['sha_old'] != manifest[key]['sha_new']:
            raise RuntimeError('SERVICE_ENTRY_VERIFICATION_FAILED:' + key)
        print('SERVICE_ENTRY_ORIGIN_VERIFIED=' + key)


def selftest() -> None:
    for key, (_, anchor, addition, required) in TARGETS.items():
        source = '<main>' + ''.join(required) + ('x' * 32000) + anchor
        # The mock contains no real customer or operational data.
        source = source.replace('<main>', '')
        state, result = transform(key, source)
        assert state == 'needs-patch' and result.count(addition) == 1
        assert transform(key, result)[0] == 'already-patched'
        assert 'href="/ask-master/index.php"' in result
    print('SERVICE_ENTRY_GUARDED_SELFTEST_OK=1')


if __name__ == '__main__':
    argv = sys.argv[1:]
    if argv == ['selftest']:
        selftest()
    elif argv == ['preview']:
        preview()
    elif len(argv) == 2 and argv[0] in ('publish', 'verify', 'rollback'):
        action, runid = argv
        if action == 'publish':
            publish(runid)
        elif action == 'verify':
            verify(runid)
        else:
            validate_environment()
            restore(runid)
    else:
        raise RuntimeError('UNKNOWN_OR_MISSING_MODE')
