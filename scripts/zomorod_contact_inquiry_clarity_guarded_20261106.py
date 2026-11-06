#!/usr/bin/env python3
"""Guarded correction of outdated commercial availability copy on /contact/.

Changes one public static HTML paragraph; never alters forms, orders, payment,
customer data, staff sessions, services, or background processes.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

HOME = Path('/home/zomorod2')
WEB = HOME / 'public_html'
TARGET = WEB / 'contact/index.html'
BACKUPS = HOME / '.private/zm-contact-inquiry-clarity-backups'
EXPECTED = '5654f3f0f8a0a616877fe7996c8c40af133000b02fb5246be7db7918a4ab7e60'
OLD = ('<p class="summary">این صفحه برای معرفی و آموزش است. اطلاعات قیمت، سفارش، '
       'پیش‌بینی زنده یا انجام خدمات، تنها پس از اتصال و تأیید سامانه اجرایی معتبر خواهد بود.</p>')
NEW = ('<p class="summary">ثبت درخواست خدمات و همکاری در سامانهٔ مشتریان زمرد ملل فعال است. '
       'قیمت، دامنهٔ کار، زمان تحویل و پذیرش پروژه فقط پس از بررسی درخواست و توافق رسمی مشخص می‌شود. '
       'خرید آنلاین تا فعال‌سازی و تأیید درگاه پرداخت غیرفعال است.</p>')
CANONICAL = '<link rel="canonical" href="https://zomorodmelal.ir/contact/">'
FORM_HREF = 'href="/ask-master/index.php"'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def patch(raw: bytes, check_live_sha: bool = True) -> bytes:
    if check_live_sha and sha(raw) != EXPECTED:
        raise RuntimeError('CONTACT_COPY_ORIGIN_VERSION_CHANGED_ABORT')
    source = raw.decode('utf-8')
    if (source.count(CANONICAL) != 1 or source.count(OLD) != 1 or
            source.count(NEW) != 0 or source.count(FORM_HREF) < 1):
        raise RuntimeError('CONTACT_COPY_STRUCTURE_CHANGED_ABORT')
    updated = source.replace(OLD, NEW, 1)
    if updated.count(NEW) != 1 or updated.count(OLD) != 0:
        raise RuntimeError('CONTACT_COPY_PATCH_FAILED')
    return updated.encode('utf-8')


def validate() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError('CONTACT_COPY_WRONG_CPANEL_ACCOUNT')
    for path in (HOME, WEB, TARGET.parent, TARGET, BACKUPS.parent, BACKUPS):
        if path.is_symlink():
            raise RuntimeError('CONTACT_COPY_SYMLINK_REFUSED')
    if not TARGET.is_file() or not (10_000 <= TARGET.stat().st_size <= 80_000):
        raise RuntimeError('CONTACT_COPY_TARGET_INVALID')
    if not BACKUPS.parent.is_dir():
        raise RuntimeError('CONTACT_COPY_PRIVATE_BACKUP_ROOT_MISSING')


def replace_atomic(content: bytes, mode: int) -> None:
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=TARGET.parent, prefix='.zm-contact-clarity-', delete=False) as f:
            temp = f.name
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, mode)
        os.replace(temp, TARGET)
        temp = None
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def main(mode: str, run_id: str) -> None:
    if mode == 'selftest':
        sample = (CANONICAL + FORM_HREF + OLD).encode('utf-8')
        revised = patch(sample, check_live_sha=False)
        assert NEW.encode('utf-8') in revised and OLD.encode('utf-8') not in revised
        try:
            patch(revised, check_live_sha=False)
        except RuntimeError:
            pass
        else:
            raise AssertionError('CONTACT_COPY_REPEAT_MUST_ABORT')
        print('CONTACT_COPY_GUARD_SELFTEST_OK=1')
        return
    if not re.fullmatch(r'[0-9]{6,20}', run_id):
        raise RuntimeError('CONTACT_COPY_INVALID_RUN_ID')
    validate()
    folder = BACKUPS / run_id
    if mode in ('preview', 'publish'):
        old = TARGET.read_bytes()
        new = patch(old)
        if mode == 'preview':
            print('CONTACT_COPY_EXACT_PRODUCTION_VERSION_MATCH=1')
            return
        if folder.exists():
            raise RuntimeError('CONTACT_COPY_REPEATED_RELEASE_ID')
        folder.mkdir(mode=0o700, parents=True, exist_ok=False)
        backup = folder / 'original.html'
        with backup.open('xb') as stream:
            stream.write(old)
            stream.flush()
            os.fsync(stream.fileno())
        backup.chmod(0o600)
        if sha(TARGET.read_bytes()) != sha(old):
            raise RuntimeError('CONTACT_COPY_CONCURRENT_MODIFICATION')
        replace_atomic(new, stat.S_IMODE(TARGET.stat().st_mode))
        print('CONTACT_COPY_ONE_FILE_PUBLISHED=1')
        return
    if folder.is_symlink() or not folder.is_dir():
        raise RuntimeError('CONTACT_COPY_BACKUP_MISSING')
    backup = folder / 'original.html'
    if backup.is_symlink() or not backup.is_file():
        raise RuntimeError('CONTACT_COPY_BACKUP_NOT_REGULAR')
    old = backup.read_bytes()
    expected = patch(old)
    current = TARGET.read_bytes()
    if mode == 'verify':
        if sha(current) != sha(expected):
            raise RuntimeError('CONTACT_COPY_ORIGIN_VERIFY_FAILED')
        print('CONTACT_COPY_ORIGIN_VERIFIED=1')
        return
    if mode == 'rollback':
        if sha(current) != sha(expected):
            raise RuntimeError('CONTACT_COPY_REFUSE_FOREIGN_CHANGE_ROLLBACK')
        replace_atomic(old, stat.S_IMODE(TARGET.stat().st_mode))
        print('CONTACT_COPY_RESTORED=1')
        return
    raise RuntimeError('CONTACT_COPY_UNKNOWN_MODE')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: script MODE RUN_ID')
    main(sys.argv[1], sys.argv[2])
