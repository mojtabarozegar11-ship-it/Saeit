#!/usr/bin/env python3
"""Improve existing live service-form guidance, without submitting requests.

One existing PHP file, byte-exact predecessor from the completed guarded
preselection release, private backup, lint, atomic write and safe rollback.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

SITE = Path('/home/zomorod2/public_html')
FORM = SITE / 'ask-master/index.php'
PRIVATE = Path('/home/zomorod2/.private')
PREVIOUS = PRIVATE / 'zomorod-service-intent-backups/42153111271/manifest.json'
BACKUP = PRIVATE / 'zomorod-form-copy-backups'
EXPECTED_PREVIOUS_OLD = '006f1d640138f8f168f9140eb6c58915ccef4b8528c641295b7a6074cf8d12e3'
TEXT = {
    'پرسش از مسترایجنت زمرد ملل': 'درخواست خدمات و پرسش | زمرد ملل',
    'پاسخ‌های عمومی بدون API خارجی ارائه می‌شوند. پرسش‌های اختصاصی برای بررسی ثبت خواهند شد.': (
        'برای درخواست خدمات کشاورزی و اقتصادی، نوع فعالیت، استان و مسئله موردنظر را شرح دهید. '
        'پرسش‌های عمومی و پیگیری سفارش نیز از همین فرم امکان‌پذیر است.'),
    'پرسش شما': 'شرح درخواست یا پرسش',
    'ثبت و دریافت پاسخ اولیه': 'ثبت درخواست',
}


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate() -> None:
    if os.geteuid() == 0 or os.geteuid() != SITE.stat().st_uid:
        raise RuntimeError('FORM_COPY_REFUSE_WRONG_ACCOUNT')
    for path in (SITE, FORM, FORM.parent, PRIVATE, BACKUP):
        if path.is_symlink():
            raise RuntimeError('FORM_COPY_REFUSE_SYMLINK')
    if not FORM.is_file() or not PREVIOUS.is_file():
        raise RuntimeError('FORM_COPY_REFUSE_MISSING_PREDECESSOR')


def expected() -> str:
    predecessor = json.loads(PREVIOUS.read_text())['form']
    if predecessor['old_sha'] != EXPECTED_PREVIOUS_OLD:
        raise RuntimeError('FORM_COPY_BAD_PREDECESSOR')
    return predecessor['new_sha']


def transform(source: bytes) -> bytes:
    value = source.decode('utf-8')
    if 'zm-specialist-intent-20261106:form' not in value:
        raise RuntimeError('FORM_COPY_MISSING_SPECIALIST_SELECTION')
    for old, new in TEXT.items():
        count = value.count(old)
        if count not in ((1, 2) if old.startswith('پرسش از مسترایجنت') else (1,)):
            raise RuntimeError('FORM_COPY_UNEXPECTED_ANCHOR:' + old[:25] + ':' + str(count))
        if new in value:
            raise RuntimeError('FORM_COPY_ALREADY_PATCHED')
        value = value.replace(old, new)
    return value.encode('utf-8')


def lint(source: bytes) -> None:
    binary = shutil.which('php') or '/opt/cpanel/ea-php82/root/usr/bin/php'
    if not Path(binary).is_file():
        raise RuntimeError('FORM_COPY_PHP_CLI_MISSING')
    fd, temp = tempfile.mkstemp(prefix='.form-copy-check-', suffix='.php', dir=str(FORM.parent))
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(source)
        os.chmod(temp, 0o600)
        result = subprocess.run([binary, '-l', temp], timeout=30, capture_output=True)
        if result.returncode:
            raise RuntimeError('FORM_COPY_PHP_LINT_FAILED')
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def plan() -> tuple[bytes, bytes, int]:
    validate()
    original = FORM.read_bytes()
    if sha(original) != expected():
        raise RuntimeError('FORM_COPY_REFUSE_CONCURRENT_VERSION')
    updated = transform(original)
    lint(updated)
    return original, updated, stat.S_IMODE(FORM.stat().st_mode)


def safe_atomic(payload: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix='.form-copy-', dir=str(FORM.parent))
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp, mode)
        os.replace(temp, FORM)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def destination(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{5,20}', run_id):
        raise RuntimeError('FORM_COPY_BAD_RUN_ID')
    return BACKUP / run_id


def restore(run_id: str) -> None:
    root = destination(run_id)
    manifest = json.loads((root / 'manifest.json').read_text())
    original = (root / 'form.backup').read_bytes()
    if sha(original) != manifest['old_sha']:
        raise RuntimeError('FORM_COPY_BACKUP_CORRUPTED')
    current = sha(FORM.read_bytes())
    if current == manifest['old_sha']:
        print('FORM_COPY_ALREADY_ROLLED_BACK=1')
    elif current != manifest['new_sha']:
        raise RuntimeError('FORM_COPY_REFUSE_ROLLBACK_OTHER_EDIT')
    else:
        safe_atomic(original, manifest['mode'])
        print('FORM_COPY_ROLLED_BACK=1')


def publish(run_id: str) -> None:
    original, updated, mode = plan()
    BACKUP.mkdir(mode=0o700, exist_ok=True)
    root = destination(run_id)
    root.mkdir(mode=0o700)
    with (root / 'form.backup').open('xb') as out:
        out.write(original)
    (root / 'form.backup').chmod(0o600)
    manifest = {'old_sha': sha(original), 'new_sha': sha(updated), 'mode': mode}
    (root / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True))
    (root / 'manifest.json').chmod(0o600)
    try:
        if sha(FORM.read_bytes()) != manifest['old_sha']:
            raise RuntimeError('FORM_COPY_CHANGED_BEFORE_PUBLISH')
        safe_atomic(updated, mode)
    except Exception:
        restore(run_id)
        raise
    print('FORM_COPY_PUBLISHED=1')


def verify(run_id: str) -> None:
    validate()
    manifest = json.loads((destination(run_id) / 'manifest.json').read_text())
    current = FORM.read_bytes()
    if sha(current) != manifest['new_sha']:
        raise RuntimeError('FORM_COPY_ORIGIN_MISMATCH')
    if 'درخواست خدمات و پرسش | زمرد ملل' not in current.decode('utf-8'):
        raise RuntimeError('FORM_COPY_HEADING_MISSING')
    lint(current)
    print('FORM_COPY_ORIGIN_VERIFIED=1')


def selftest() -> None:
    source = ('zm-specialist-intent-20261106:form' +
              'پرسش از مسترایجنت زمرد ملل' * 2 + ''.join(
                  k for k in TEXT if k != 'پرسش از مسترایجنت زمرد ملل')).encode('utf-8')
    result = transform(source).decode('utf-8')
    for value in TEXT.values():
        assert value in result
    assert result.count('درخواست خدمات و پرسش | زمرد ملل') == 2
    print('FORM_COPY_GUARDED_SELFTEST_OK=1')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['selftest']:
        selftest()
    elif args == ['preview']:
        original, updated, _ = plan()
        print('FORM_COPY_PREFLIGHT_OK=' + sha(original))
        print('FORM_COPY_TARGET_SHA=' + sha(updated))
    elif len(args) == 2 and args[0] in ('publish', 'verify', 'rollback'):
        if args[0] == 'publish':
            publish(args[1])
        elif args[0] == 'verify':
            verify(args[1])
        else:
            validate()
            restore(args[1])
    else:
        raise RuntimeError('FORM_COPY_UNKNOWN_MODE')
