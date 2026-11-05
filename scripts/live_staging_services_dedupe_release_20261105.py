#!/usr/bin/env python3
"""Exact-hash reversible correction of duplicated services cards in staging."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from pathlib import Path


HOME = Path('/home/zomorod2')
SOURCE = HOME / 'Saeit-staging/core/templates/core/services.html'
WEB_CONF = HOME / 'Saeit-staging-web/.htaccess'
BACKUPS = HOME / '.private/staging-services-backups'
EXPECTED = '195994985017c1cbc0247969f9215fbcb34d4cc3bd4f8aeeac92ff270d7350bc'
CHANGES = {
    '<article class="services-domain services-domain-market"><div class="services-no">08</div><span>MARKET · COMMERCE</span><h2>بازار</h2><p>محصول، سفارش، فروش، مزایده و اتصال زنجیره‌های شرکت به بازار.</p><a href="/market/">ورود به بازار ↗</a></article>':
    '<article class="services-domain services-domain-research"><div class="services-no">08</div><span>RESEARCH · PROJECTS</span><h2>پژوهش‌های کاربردی</h2><p>آشنایی با طرح‌های پژوهشی، ژنتیکی و توسعهٔ فناوری شرکت در درگاه رسمی.</p><a href="https://zomorodmelal.ir/research/projects/">مشاهدهٔ طرح‌های پژوهشی ↗</a></article>',
    '<article class="services-domain services-domain-platform"><div class="services-no">12</div><span>ACADEMY · LEARNING</span><h2>آموزش</h2><p>آموزش و مهارت برای ورود، رشد و استفاده حرفه‌ای از اکوسیستم خدماتی.</p><a href="/education/">ورود به آموزش ↗</a></article>':
    '<article class="services-domain services-domain-platform"><div class="services-no">12</div><span>TOOLS · APPLICATIONS</span><h2>ابزارهای کاربردی</h2><p>دسترسی به ابزارها و برنامه‌های رایگانِ منتشرشده در وب‌سایت رسمی شرکت.</p><a href="https://zomorodmelal.ir/apps/">مشاهدهٔ ابزارهای کاربردی ↗</a></article>',
    '<article class="services-domain services-domain-platform"><div class="services-no">13</div><span>AI · INTELLIGENCE</span><h2>هوش مصنوعی</h2><p>ابزارها و عامل‌های هوشمند برای پژوهش، تحلیل و اجرای کنترل‌شده.</p><a href="/agents/">ورود به هوش مصنوعی ↗</a></article>':
    '<article class="services-domain services-domain-platform"><div class="services-no">13</div><span>NEWS · BULLETIN</span><h2>خبرنامهٔ شرکت</h2><p>مطالعهٔ مطالب و اطلاعیه‌های عمومی منتشرشده در درگاه رسمی زمرد ملل.</p><a href="https://zomorodmelal.ir/newsletter/">ورود به خبرنامه ↗</a></article>',
    '<article class="services-domain services-domain-platform"><div class="services-no">14</div><span>KNOWLEDGE · ENCYCLOPEDIA</span><h2>دانشنامه</h2><p>مرجع ساختاریافته دانش، مفاهیم و محتوای قابل استفاده پلتفرم.</p><a href="/knowledge/">ورود به دانشنامه ↗</a></article>':
    '<article class="services-domain services-domain-platform"><div class="services-no">14</div><span>CONTACT · COLLABORATION</span><h2>ارتباط و همکاری</h2><p>مسیر رسمی تماس با شرکت و بررسی فرصت‌های همکاری تخصصی.</p><a href="https://zomorodmelal.ir/contact/">راه‌های ارتباط رسمی ↗</a></article>',
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guard_paths() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('CPANEL_USER_MISMATCH')
    if SOURCE.is_symlink() or not SOURCE.is_file() or SOURCE.parent.is_symlink():
        raise RuntimeError('STAGING_SERVICE_TEMPLATE_INVALID')
    if WEB_CONF.is_symlink() or not WEB_CONF.is_file() or not BACKUPS.parent.is_dir():
        raise RuntimeError('STAGING_OR_PRIVATE_BACKUP_INVALID')
    if not str(SOURCE).startswith(str(HOME / 'Saeit-staging/core/templates/core/')):
        raise RuntimeError('WRONG_TEMPLATE_ROOT')


def staging_restart_marker() -> Path:
    cfg = WEB_CONF.read_text('utf-8', 'replace')
    match = re.search(r'(?m)^PassengerAppRoot\s+([^\s]+)\s*$', cfg)
    if not match:
        raise RuntimeError('STAGING_PASSENGER_ROOT_UNKNOWN')
    root = Path(match.group(1).strip('"'))
    base = HOME / 'Saeit-staging/admin-smoke'
    if root.is_symlink() or not root.is_dir() or base not in root.parents:
        raise RuntimeError('STAGING_PASSENGER_ROOT_OUT_OF_SCOPE')
    temp = root / 'tmp'
    if temp.is_symlink() or not temp.is_dir():
        raise RuntimeError('STAGING_PASSENGER_RESTART_DIRECTORY_UNAVAILABLE')
    marker = temp / 'restart.txt'
    if marker.is_symlink() or (marker.exists() and not marker.is_file()):
        raise RuntimeError('STAGING_PASSENGER_RESTART_MARKER_INVALID')
    return marker


def guard() -> tuple[bytes, bytes]:
    guard_paths()
    staging_restart_marker()  # assert safe staging-only restart path before writes
    before = SOURCE.read_bytes()
    if digest(before) != EXPECTED:
        raise RuntimeError('STAGING_TEMPLATE_CHANGED_FROM_INSPECTED_VERSION')
    source = before.decode('utf-8')
    revised = source
    for old, new in CHANGES.items():
        if revised.count(old) != 1:
            raise RuntimeError('EXPECTED_DUPLICATE_CARD_NOT_UNIQUE')
        revised = revised.replace(old, new, 1)
    if source.count('<article') != revised.count('<article') or source.count('{{') != revised.count('{{'):
        raise RuntimeError('TEMPLATE_RENDER_STRUCTURE_CHANGED')
    for url in ('/research/projects/', '/apps/', '/newsletter/', '/contact/'):
        if url not in revised:
            raise RuntimeError('NEW_PUBLIC_LINK_MISSING')
    return before, revised.encode('utf-8')


def run_folder(run_id: str) -> Path:
    if not re.fullmatch('[0-9]{9,20}', run_id):
        raise RuntimeError('INVALID_RELEASE_ID')
    return BACKUPS / ('run-' + run_id)


def atomic_write(data: bytes, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(prefix='.services-dedupe-', dir=SOURCE.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if SOURCE.is_symlink() or not SOURCE.is_file():
            raise RuntimeError('STAGING_TEMPLATE_REPLACED_DURING_WRITE')
        os.replace(tmp, SOURCE)
    finally:
        Path(tmp).unlink(missing_ok=True)


def trigger_staging_only_restart() -> None:
    marker = staging_restart_marker()
    marker.touch(exist_ok=True)


def preview() -> None:
    old, revised = guard()
    print('STAGING_SERVICES_PREVIEW=' + json.dumps({
        'old_sha': digest(old), 'new_sha': digest(revised),
        'duplicate_cards_repurposed': len(CHANGES), 'total_cards_deleted': 0,
        'main_site_db_payments_factory_changed': False}))


def publish(run_id: str) -> None:
    old, revised = guard()
    backup_dir = run_folder(run_id)
    if backup_dir.exists() or backup_dir.is_symlink():
        raise RuntimeError('STAGING_BACKUP_COLLISION')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    backup_dir.mkdir(mode=0o700)
    mode = stat.S_IMODE(SOURCE.stat().st_mode)
    manifest = {'run_id': run_id, 'old_sha': digest(old), 'new_sha': digest(revised), 'mode': mode}
    with (backup_dir / 'original.html').open('xb') as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(old)
        out.flush()
        os.fsync(out.fileno())
    with (backup_dir / 'manifest.json').open('x') as out:
        os.fchmod(out.fileno(), 0o600)
        json.dump(manifest, out)
        out.flush()
        os.fsync(out.fileno())
    if digest(SOURCE.read_bytes()) != EXPECTED:
        raise RuntimeError('STAGING_CONCURRENT_TEMPLATE_EDIT')
    try:
        atomic_write(revised, mode)
        trigger_staging_only_restart()
        if digest(SOURCE.read_bytes()) != manifest['new_sha']:
            raise RuntimeError('STAGING_TEMPLATE_POSTWRITE_MISMATCH')
    except BaseException:
        if SOURCE.is_file() and digest(SOURCE.read_bytes()) == manifest['new_sha']:
            atomic_write(old, mode)
            trigger_staging_only_restart()
        raise
    print('STAGING_SERVICES_PUBLISHED=' + json.dumps({
        'changed': 'staging template only', 'cards_repurposed': 4,
        'private_backup': True, 'main_site_factory_or_payments_changed': False}))


def rollback(run_id: str) -> None:
    guard_paths()
    backup_dir = run_folder(run_id)
    if backup_dir.is_symlink() or not backup_dir.is_dir():
        raise RuntimeError('STAGING_BACKUP_NOT_FOUND')
    manifest = json.loads((backup_dir / 'manifest.json').read_text())
    old = (backup_dir / 'original.html').read_bytes()
    if manifest['run_id'] != run_id or digest(old) != manifest['old_sha']:
        raise RuntimeError('STAGING_BACKUP_VERIFICATION_FAILED')
    current = digest(SOURCE.read_bytes())
    if current == manifest['new_sha']:
        atomic_write(old, manifest['mode'])
        trigger_staging_only_restart()
    elif current != manifest['old_sha']:
        raise RuntimeError('STAGING_TEMPLATE_CONCURRENT_EDIT_PREVENTS_ROLLBACK')
    print('STAGING_SERVICES_ROLLBACK=RESTORED')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'preview':
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise SystemExit('USAGE: preview | publish RUN_ID | rollback RUN_ID')
