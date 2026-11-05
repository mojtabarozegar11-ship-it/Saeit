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


def template_targets() -> tuple[Path, Path]:
    active_root = staging_restart_marker().parent.parent
    active = active_root / 'core/templates/core/services.html'
    if active == SOURCE or active.is_symlink() or not active.is_file() or active.parent.is_symlink():
        raise RuntimeError('ACTIVE_STAGING_TEMPLATE_UNSAFE_OR_MISSING')
    return SOURCE, active


def guard() -> tuple[bytes, bytes]:
    guard_paths()
    targets = template_targets()
    before = SOURCE.read_bytes()
    if digest(before) != EXPECTED:
        raise RuntimeError('STAGING_TEMPLATE_CHANGED_FROM_INSPECTED_VERSION')
    for target in targets:
        if digest(target.read_bytes()) != EXPECTED:
            raise RuntimeError('STAGING_ACTIVE_OR_SOURCE_TEMPLATE_DRIFT')
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


def atomic_write(target: Path, data: bytes, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(prefix='.services-dedupe-', dir=target.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if target.is_symlink() or not target.is_file():
            raise RuntimeError('STAGING_TEMPLATE_REPLACED_DURING_WRITE')
        os.replace(tmp, target)
    finally:
        Path(tmp).unlink(missing_ok=True)


def staging_owned_lswsgi_workers() -> list[int]:
    """Require that every process mentioning the active staging root is a worker owned by this cPanel user."""
    import signal
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('SAFE_PIDFD_RESTART_UNSUPPORTED')
    root = staging_restart_marker().parent.parent
    found: list[int] = []
    matched = 0
    for folder in Path('/proc').iterdir():
        if not folder.name.isdecimal():
            continue
        try:
            raw = (folder / 'cmdline').read_bytes()
            command = raw.replace(b'\x00', b' ').decode('utf-8', 'replace')
            if str(root) not in command:
                continue
            matched += 1
            status_text = (folder / 'status').read_text('utf-8', 'replace')
            uid = re.search(r'(?m)^Uid:\s+(\d+)', status_text)
            owned = bool(uid and int(uid.group(1)) == os.geteuid())
            cwd = os.readlink(str(folder / 'cwd'))
            executable = (folder / 'exe').resolve().name
            if not (owned and cwd == str(root) and executable == 'lswsgi'
                    and 'passenger' in command.lower()):
                raise RuntimeError('NON_STAGING_OR_UNOWNED_PROCESS_PREVENTS_RESTART')
            found.append(int(folder.name))
        except FileNotFoundError:
            continue
        except (OSError, PermissionError, ValueError) as exc:
            raise RuntimeError('STAGING_PROCESS_PRECHECK_UNAVAILABLE') from exc
    if not (1 <= matched <= 10 and matched == len(found)):
        raise RuntimeError('STAGING_LSWGI_PROCESS_SET_UNSAFE')
    return found


def trigger_staging_only_restart() -> None:
    """Surgically recycle only exact-root, same-owner LiteSpeed WSGI processes."""
    import signal
    workers = staging_owned_lswsgi_workers()
    handles: list[int] = []
    try:
        for pid in workers:
            try:
                handles.append(os.pidfd_open(pid, 0))
            except ProcessLookupError:
                continue
        if not handles:
            raise RuntimeError('STAGING_LSWGI_WORKERS_CHANGED_DURING_RESTART')
        staging_restart_marker().touch(exist_ok=True)
        delivered = 0
        for fd in handles:
            try:
                signal.pidfd_send_signal(fd, signal.SIGTERM, None, 0)
                delivered += 1
            except ProcessLookupError:
                continue
        print('TARGETED_STAGING_LSWGI_RESTART=' + json.dumps(
            {'workers_seen': len(workers), 'termination_signals_delivered': delivered,
             'global_killall_used': False, 'site_scope': 'staging_only'}), flush=True)
    finally:
        for fd in handles:
            os.close(fd)


def preview() -> None:
    old, revised = guard()
    workers = staging_owned_lswsgi_workers()
    print('STAGING_SERVICES_PREVIEW=' + json.dumps({
        'eligible_staging_only_lswsgi_worker_count': len(workers),
        'old_sha': digest(old), 'new_sha': digest(revised),
        'staging_template_copies_guarded': len(template_targets()),
        'duplicate_cards_repurposed': len(CHANGES), 'total_cards_deleted': 0,
        'main_site_db_payments_factory_changed': False}))


def publish(run_id: str) -> None:
    old, revised = guard()
    targets = template_targets()
    backup_dir = run_folder(run_id)
    if backup_dir.exists() or backup_dir.is_symlink():
        raise RuntimeError('STAGING_BACKUP_COLLISION')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    backup_dir.mkdir(mode=0o700)
    modes = [stat.S_IMODE(target.stat().st_mode) for target in targets]
    manifest = {'run_id': run_id, 'old_sha': digest(old), 'new_sha': digest(revised), 'modes': modes}
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
    if any(digest(target.read_bytes()) != EXPECTED for target in targets):
        raise RuntimeError('STAGING_CONCURRENT_TEMPLATE_EDIT')
    try:
        for target, mode in zip(targets, modes):
            atomic_write(target, revised, mode)
        trigger_staging_only_restart()
        if any(digest(target.read_bytes()) != manifest['new_sha'] for target in targets):
            raise RuntimeError('STAGING_TEMPLATE_POSTWRITE_MISMATCH')
    except BaseException:
        restored = False
        for target, mode in zip(targets, modes):
            if target.is_file() and digest(target.read_bytes()) == manifest['new_sha']:
                atomic_write(target, old, mode)
                restored = True
        if restored:
            trigger_staging_only_restart()
        raise
    print('STAGING_SERVICES_PUBLISHED=' + json.dumps({
        'changed': 'staging source and active template only', 'cards_repurposed': 4,
        'private_backup': True, 'main_site_factory_or_payments_changed': False}))


def rollback(run_id: str) -> None:
    guard_paths()
    targets = template_targets()
    backup_dir = run_folder(run_id)
    if backup_dir.is_symlink() or not backup_dir.is_dir():
        raise RuntimeError('STAGING_BACKUP_NOT_FOUND')
    manifest = json.loads((backup_dir / 'manifest.json').read_text())
    old = (backup_dir / 'original.html').read_bytes()
    if manifest['run_id'] != run_id or digest(old) != manifest['old_sha']:
        raise RuntimeError('STAGING_BACKUP_VERIFICATION_FAILED')
    if len(manifest.get('modes', [])) != len(targets):
        raise RuntimeError('STAGING_BACKUP_TARGET_COUNT_MISMATCH')
    current = [digest(target.read_bytes()) for target in targets]
    if any(value not in (manifest['old_sha'], manifest['new_sha']) for value in current):
        raise RuntimeError('STAGING_TEMPLATE_CONCURRENT_EDIT_PREVENTS_ROLLBACK')
    if manifest['new_sha'] in current:
        for target, mode, value in zip(targets, manifest['modes'], current):
            if value == manifest['new_sha']:
                atomic_write(target, old, mode)
        trigger_staging_only_restart()
    print('STAGING_SERVICES_ROLLBACK=RESTORED')



def verify_origin(run_id: str) -> None:
    """Read the staging page FROM cPanel to activate Passenger before external verification."""
    from urllib.request import Request, urlopen
    import time

    guard_paths()
    backup_dir = run_folder(run_id)
    manifest_path = backup_dir / 'manifest.json'
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RuntimeError('STAGING_ORIGIN_VERIFICATION_BACKUP_UNAVAILABLE')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('run_id') != run_id:
        raise RuntimeError('STAGING_ORIGIN_MANIFEST_MISMATCH')
    if any(digest(path.read_bytes()) != manifest.get('new_sha') for path in template_targets()):
        raise RuntimeError('STAGING_ORIGIN_SOURCE_NOT_PUBLISHED')
    required = ('پژوهش‌های کاربردی', 'ابزارهای کاربردی', 'خبرنامهٔ شرکت', 'ارتباط و همکاری')
    retained = ('هوش مصنوعی', 'آموزش', 'دانشنامه')
    last_issue = 'NOT_STARTED'
    for attempt in range(12):
        try:
            url = 'https://staging.zomorodmelal.ir/?zm_origin_release=' + run_id + '-' + str(attempt)
            with urlopen(Request(url, headers={'Cache-Control': 'no-cache, no-store',
                              'Pragma': 'no-cache',
                              'User-Agent': 'ZM-Staging-Passenger-Origin-Refresh/1.0'}), timeout=9) as response:
                robots = response.headers.get('X-Robots-Tag', '')
                html = response.read(200000).decode('utf-8', 'replace')
                status = response.status
            titles = [re.sub(r'<[^>]+>', '', value).strip() for value in
                      re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.I | re.S)]
            if status == 200 and 'noindex' in robots.lower() and all(
                    titles.count(title) == 1 for title in required + retained
            ) and len(titles) == len(set(titles)):
                print('STAGING_ORIGIN_SERVICES_VERIFIED=1 headings=' + str(len(titles)), flush=True)
                return
            last_issue = 'PRE_RESTART_TEMPLATE_VISIBLE'
        except Exception as exc:
            last_issue = type(exc).__name__
        if attempt % 3 == 0:
            print('WAITING_FOR_ORIGIN_PASSENGER_RENDER attempt=' + str(attempt + 1)
                  + ' issue=' + last_issue, flush=True)
        time.sleep(5)
    raise RuntimeError('STAGING_ORIGIN_SERVICES_NOT_VISIBLE_AFTER_RESTART:' + last_issue)

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'preview':
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'verify-origin':
        verify_origin(sys.argv[2])
    else:
        raise SystemExit('USAGE: preview | publish RUN_ID | rollback RUN_ID')
