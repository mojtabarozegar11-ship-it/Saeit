#!/usr/bin/env python3
"""Reversible, staging-only fix for unreadable service-card headings."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import signal
import stat
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen


HOME = Path('/home/zomorod2')
SOURCE = HOME / 'Saeit-staging/core/templates/core/services.html'
WEB_CONF = HOME / 'Saeit-staging-web/.htaccess'
BACKUPS = HOME / '.private/staging-service-contrast-backups'
MARKER = 'zm-staging-service-card-contrast-20261105'
NEEDLE = ('{% block extra_css %}<link rel="stylesheet" '
          'href="{% static \'site/home-luxury.css\' %}">{% endblock %}')
REPLACEMENT = (
    '{% block extra_css %}<link rel="stylesheet" '
    'href="{% static \'site/home-luxury.css\' %}">'
    '<style id="' + MARKER + '">'
    '.services-page .services-grid h2{color:#f4efe4}'
    '</style>{% endblock %}'
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def app_roots() -> tuple[Path, Path]:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('WRONG_CPANEL_USER')
    if WEB_CONF.is_symlink() or not WEB_CONF.is_file():
        raise RuntimeError('STAGING_WEB_CONFIG_UNSAFE')
    cfg = WEB_CONF.read_text('utf-8', 'strict')
    match = re.search(r'(?m)^PassengerAppRoot\s+([^\s]+)\s*$', cfg)
    if not match:
        raise RuntimeError('STAGING_PASSENGER_ROOT_MISSING')
    active = Path(match.group(1).strip('"'))
    canonical = HOME / 'Saeit-staging'
    if (active.is_symlink() or not active.is_dir() or
            HOME / 'Saeit-staging/admin-smoke' not in active.parents or
            canonical.is_symlink() or not canonical.is_dir() or active == canonical):
        raise RuntimeError('STAGING_APP_ROOT_OUT_OF_SCOPE')
    return canonical, active


def targets() -> tuple[Path, Path]:
    canonical, active = app_roots()
    files = (SOURCE, active / 'core/templates/core/services.html')
    for target in files:
        if (target.is_symlink() or target.parent.is_symlink() or
                not target.is_file() or target.stat().st_size > 90000):
            raise RuntimeError('STAGING_TEMPLATE_UNSAFE:' + str(target))
    if files[0] == files[1] or files[0].parents[3] != canonical:
        raise RuntimeError('STAGING_SOURCE_OR_ACTIVE_TEMPLATE_MISMATCH')
    return files


def prepared() -> tuple[bytes, bytes]:
    files = targets()
    old = files[0].read_bytes()
    if any(path.read_bytes() != old for path in files[1:]):
        raise RuntimeError('STAGING_TEMPLATE_COPIES_DIFFER')
    source = old.decode('utf-8', 'strict')
    if source.count(MARKER) or source.count(NEEDLE) != 1:
        raise RuntimeError('CONTRAST_PATCH_PRESENT_OR_TEMPLATE_CHANGED')
    if source.count('class="services-grid"') != 1:
        raise RuntimeError('SERVICES_GRID_STRUCTURE_CHANGED')
    for required in ('پژوهش‌های کاربردی', 'ابزارهای کاربردی',
                     'خبرنامهٔ شرکت', 'ارتباط و همکاری'):
        if source.count('<h2>' + required + '</h2>') != 1:
            raise RuntimeError('EXPECTED_STAGING_CARD_MISSING:' + required)
    new = source.replace(NEEDLE, REPLACEMENT, 1).encode('utf-8')
    if new.replace(REPLACEMENT.encode(), NEEDLE.encode(), 1) != old:
        raise RuntimeError('PATCH_IS_NOT_ISOLATED')
    return old, new


def restart_markers() -> tuple[Path, Path]:
    canonical, active = app_roots()
    markers = tuple(root / 'tmp/restart.txt' for root in (canonical, active))
    for index, marker in enumerate(markers):
        if (marker.parent.is_symlink() or not marker.parent.is_dir() or
                marker.is_symlink() or
                (marker.exists() and not marker.is_file()) or
                (index == 0 and not marker.is_file()) or
                not os.access(marker.parent, os.W_OK)):
            raise RuntimeError('STAGING_RESTART_MARKER_UNSAFE')
    return markers


def staging_workers() -> list[int]:
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('SAFE_PIDFD_RESTART_UNSUPPORTED')
    canonical, active = app_roots()
    allowed = {str(canonical): 0, str(active): 0}
    found: list[int] = []
    for item in Path('/proc').iterdir():
        if not item.name.isdecimal():
            continue
        try:
            cwd = os.readlink(item / 'cwd')
            if cwd not in allowed:
                continue
            status = (item / 'status').read_text('utf-8', 'replace')
            uid = re.search(r'(?m)^Uid:\s+(\d+)', status)
            command = (item / 'cmdline').read_bytes().replace(b'\0', b' ').lower()
            exe = (item / 'exe').resolve().name
            if not (uid and int(uid.group(1)) == os.geteuid()
                    and exe == 'lswsgi' and b'passenger' in command):
                raise RuntimeError('UNOWNED_OR_UNEXPECTED_STAGING_WORKER')
            found.append(int(item.name))
            allowed[cwd] += 1
        except FileNotFoundError:
            continue
        except (OSError, PermissionError, ValueError) as exc:
            raise RuntimeError('CANNOT_GUARD_STAGING_WORKER') from exc
    if not (1 <= len(found) <= 20 and 1 <= allowed[str(canonical)] <= 12
            and allowed[str(active)] <= 10):
        raise RuntimeError('STAGING_WORKER_SET_CHANGED')
    return found


def recycle_staging_only() -> None:
    workers = staging_workers()
    markers = restart_markers()
    handles = []
    try:
        for pid in workers:
            try:
                handles.append(os.pidfd_open(pid, 0))
            except ProcessLookupError:
                continue
        if not handles:
            raise RuntimeError('STAGING_WORKERS_ALREADY_DISAPPEARED')
        for marker in markers:
            marker.touch(exist_ok=True)
        sent = 0
        for fd in handles:
            try:
                signal.pidfd_send_signal(fd, signal.SIGKILL, None, 0)
                sent += 1
            except ProcessLookupError:
                continue
        if sent < 1:
            raise RuntimeError('NO_STAGING_PROCESS_RECYCLED')
        print('STAGING_ONLY_WORKERS_RECYCLED=' + str(sent), flush=True)
    finally:
        for fd in handles:
            os.close(fd)


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix='.service-contrast-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('TEMPLATE_TARGET_CHANGED_DURING_WRITE')
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def folder(run_id: str) -> Path:
    if not re.fullmatch(r'\d{9,20}', run_id):
        raise RuntimeError('INVALID_RUN_ID')
    return BACKUPS / ('run-' + run_id)


def preview() -> None:
    old, new = prepared()
    restart_markers()
    count = len(staging_workers())
    print('STAGING_CONTRAST_PREVIEW=' + json.dumps({
        'old_sha': sha(old), 'new_sha': sha(new), 'template_copies': 2,
        'eligible_staging_workers': count, 'outside_staging_changes': False}), flush=True)


def publish(run_id: str) -> None:
    old, new = prepared()
    files = targets()
    restart_markers()
    staging_workers()
    if BACKUPS.parent.is_symlink() or not BACKUPS.parent.is_dir():
        raise RuntimeError('PRIVATE_BACKUP_PARENT_UNSAFE')
    dest = folder(run_id)
    if dest.exists() or dest.is_symlink():
        raise RuntimeError('PRIVATE_BACKUP_COLLISION')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    dest.mkdir(mode=0o700)
    modes = [stat.S_IMODE(p.stat().st_mode) for p in files]
    with (dest / 'original.html').open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(old)
        stream.flush()
        os.fsync(stream.fileno())
    with (dest / 'manifest.json').open('x') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump({'run_id': run_id, 'old_sha': sha(old), 'new_sha': sha(new),
                   'modes': modes}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    if any(sha(p.read_bytes()) != sha(old) for p in files):
        raise RuntimeError('CONCURRENT_STAGING_EDIT_ABORT')
    try:
        for path, mode in zip(files, modes):
            atomic_write(path, new, mode)
        recycle_staging_only()
        if any(sha(p.read_bytes()) != sha(new) for p in files):
            raise RuntimeError('POSTWRITE_TEMPLATE_INTEGRITY_FAILED')
    except BaseException:
        restored = False
        for path, mode in zip(files, modes):
            if path.is_file() and sha(path.read_bytes()) == sha(new):
                atomic_write(path, old, mode)
                restored = True
        if restored:
            recycle_staging_only()
        raise
    print('STAGING_CONTRAST_PUBLISHED=' + json.dumps({
        'backup': str(dest), 'templates_changed': 2,
        'main_site_vps_factory_payments_changed': False}), flush=True)


def rollback(run_id: str) -> None:
    dest = folder(run_id)
    if dest.is_symlink() or not dest.is_dir():
        raise RuntimeError('PRIVATE_BACKUP_NOT_FOUND')
    meta = json.loads((dest / 'manifest.json').read_text())
    old = (dest / 'original.html').read_bytes()
    if meta['run_id'] != run_id or sha(old) != meta['old_sha']:
        raise RuntimeError('BACKUP_CHECKSUM_INVALID')
    files = targets()
    current = [sha(p.read_bytes()) for p in files]
    if any(value not in (meta['old_sha'], meta['new_sha']) for value in current):
        raise RuntimeError('CONCURRENT_STAGING_CHANGE_PREVENTS_ROLLBACK')
    restored = False
    for path, mode, value in zip(files, meta['modes'], current):
        if value == meta['new_sha']:
            atomic_write(path, old, mode)
            restored = True
    if restored:
        recycle_staging_only()
    print('STAGING_CONTRAST_ROLLBACK=RESTORED', flush=True)


def verify_origin(run_id: str) -> None:
    dest = folder(run_id)
    meta = json.loads((dest / 'manifest.json').read_text())
    if any(sha(p.read_bytes()) != meta['new_sha'] for p in targets()):
        raise RuntimeError('STAGING_SOURCE_NOT_PUBLISHED')
    last = 'NOT_CHECKED'
    for attempt in range(12):
        try:
            req = Request('https://staging.zomorodmelal.ir/?contrast=' + run_id + '-' + str(attempt),
                          headers={'Cache-Control': 'no-cache, no-store', 'Pragma': 'no-cache'})
            with urlopen(req, timeout=10) as response:
                html = response.read(200000).decode('utf-8', 'replace')
                if response.status == 200 and 'noindex' in response.headers.get('X-Robots-Tag', '').lower() \
                        and html.count(MARKER) == 1:
                    print('STAGING_CONTRAST_ORIGIN_VERIFIED=1', flush=True)
                    return
                last = 'OLD_STAGING_TEMPLATE_STILL_VISIBLE'
        except Exception as exc:
            last = type(exc).__name__
        time.sleep(5)
    raise RuntimeError('STAGING_CONTRAST_NOT_VISIBLE:' + last)


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
        raise SystemExit('USAGE: preview | publish RUN_ID | rollback RUN_ID | verify-origin RUN_ID')
