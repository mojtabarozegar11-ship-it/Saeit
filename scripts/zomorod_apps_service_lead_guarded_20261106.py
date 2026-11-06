#!/usr/bin/env python3
"""Guarded customer journey from the live free farming tool to paid services.

Only the public apps/index.html page can change. Customer forms, database and
payments remain untouched. All production writes are backed up and reversible.
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
PUBLIC = HOME / 'public_html'
TARGET = PUBLIC / 'apps/index.html'
BACKUPS = HOME / '.private/zm-apps-service-lead-backups'
EXPECTED = 'e264451f4567589a0abdacfa3a8cbf1787cb501f6124ec1a5eac04a85f4e25c6'
OLD_NAV = '<a href="/research/">پژوهش‌ها</a><a href="/store/">فروشگاه</a>'
NEW_NAV = '<a href="/research/">پژوهش‌ها</a><a href="/services/">خدمات تخصصی</a><a href="/store/">فروشگاه</a>'
OLD_END = '    </section>\n  </main>'
CTA = ('      <p><a class="button" href="/ask-master/index.php?service=1">'
       'درخواست تحلیل تخصصی مزرعه و استعلام خدمات ←</a></p>\n')
NEW_END = CTA + OLD_END
CANONICAL = '<link rel="canonical" href="https://zomorodmelal.ir/apps/">'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def transform(raw: bytes, require_hash: bool = True) -> tuple[str, bytes]:
    if require_hash and sha(raw) != EXPECTED:
        raise RuntimeError('APPS_LEAD_PRODUCTION_DRIFT_ABORT')
    text = raw.decode('utf-8')
    if text.count(CANONICAL) != 1 or text.count('id="guidance-title"') != 1:
        raise RuntimeError('APPS_LEAD_UNEXPECTED_PAGE_ABORT')
    if (text.count(OLD_NAV), text.count(OLD_END), text.count(CTA)) != (1, 1, 0):
        raise RuntimeError('APPS_LEAD_PAGE_STRUCTURE_CHANGED_ABORT')
    if 'href="/ask-master/index.php?service=1"' in text or NEW_NAV in text:
        raise RuntimeError('APPS_LEAD_LINK_ALREADY_PRESENT_ABORT')
    output = text.replace(OLD_NAV, NEW_NAV, 1).replace(OLD_END, NEW_END, 1)
    if output.count(NEW_NAV) != 1 or output.count(CTA) != 1 or output.count(OLD_END) != 1:
        raise RuntimeError('APPS_LEAD_TRANSFORM_BAD')
    return 'needs-patch', output.encode('utf-8')


def validate_target() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError('APPS_LEAD_WRONG_CPANEL_ACCOUNT')
    for path in (HOME, PUBLIC, PUBLIC / 'apps', TARGET, BACKUPS):
        if path.is_symlink():
            raise RuntimeError('APPS_LEAD_SYMLINK_REFUSED')
    if not TARGET.is_file() or not (3_000 <= TARGET.stat().st_size <= 100_000):
        raise RuntimeError('APPS_LEAD_TARGET_UNEXPECTED')
    if not (HOME / '.private').is_dir():
        raise RuntimeError('APPS_LEAD_PRIVATE_BACKUP_ROOT_MISSING')


def atomic_replace(data: bytes, file_mode: int) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=TARGET.parent, prefix='.zm-apps-lead-', delete=False) as f:
            temporary = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, file_mode)
        os.replace(temporary, TARGET)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main(mode: str, run_id: str) -> None:
    if mode == 'selftest':
        sample = (CANONICAL + OLD_NAV + 'id="guidance-title"' + OLD_END).encode('utf-8')
        _, result = transform(sample, require_hash=False)
        assert NEW_NAV.encode() in result and CTA.encode() in result
        try:
            transform(result, require_hash=False)
        except RuntimeError:
            pass
        else:
            raise AssertionError('REPEATED_APPS_LEAD_PATCH_MUST_ABORT')
        print('APPS_LEAD_SELFTEST_OK')
        return
    if not re.fullmatch(r'[0-9]{6,20}', run_id):
        raise RuntimeError('APPS_LEAD_BAD_RUN_ID')
    validate_target()
    release_dir = BACKUPS / run_id
    if mode in ('preview', 'publish'):
        raw = TARGET.read_bytes()
        _, new = transform(raw)
        if mode == 'preview':
            print('APPS_LEAD_EXACT_ORIGIN_SHA_VERIFIED')
            return
        if release_dir.exists():
            raise RuntimeError('APPS_LEAD_RUN_ID_ALREADY_USED')
        release_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
        backup = release_dir / 'index.original.html'
        with backup.open('xb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        backup.chmod(0o600)
        if TARGET.is_symlink() or sha(TARGET.read_bytes()) != sha(raw):
            raise RuntimeError('APPS_LEAD_CONCURRENT_SOURCE_CHANGE_ABORT')
        atomic_replace(new, stat.S_IMODE(TARGET.stat().st_mode))
        print('APPS_LEAD_ONE_FILE_PUBLISHED')
        return
    if not release_dir.is_dir() or release_dir.is_symlink():
        raise RuntimeError('APPS_LEAD_BACKUP_MISSING')
    backup = release_dir / 'index.original.html'
    if backup.is_symlink():
        raise RuntimeError('APPS_LEAD_BACKUP_SYMLINK_REFUSED')
    old = backup.read_bytes()
    _, expected = transform(old)
    live = TARGET.read_bytes()
    if mode == 'verify':
        if sha(live) != sha(expected):
            raise RuntimeError('APPS_LEAD_ORIGIN_CHANGED')
        print('APPS_LEAD_ORIGIN_VERIFIED')
        return
    if mode == 'rollback':
        if sha(live) != sha(expected):
            raise RuntimeError('APPS_LEAD_FOREIGN_CHANGE_REFUSE_ROLLBACK')
        atomic_replace(old, stat.S_IMODE(TARGET.stat().st_mode))
        print('APPS_LEAD_ORIGINAL_RESTORED')
        return
    raise RuntimeError('APPS_LEAD_UNSAFE_MODE')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: script MODE RUN_ID')
    main(sys.argv[1], sys.argv[2])
