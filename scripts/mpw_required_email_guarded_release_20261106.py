#!/usr/bin/env python3
"""One-file, fail-closed MojPlayWin checkout email enforcement release.

This is a one-time cPanel/Passenger source update. It cannot create orders,
send email, touch payment records, change settings, or enable recovery routes.
Expected source fingerprints are deliberately immutable.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tempfile


APP = Path('/home/zomorod2/Saeit-staging')
PUBLIC = Path('/home/zomorod2/mojplaywin.com')
BACKUPS = Path('/home/zomorod2/.local/share/mpw-required-email-20261106')
RELATIVE = Path('services/mpw_trx_guest_commerce.py')
BEFORE = 'fd4b9a0b045d911cf72bbfa933dbad8e468349f708bf420cdf62d2c462ca1c7e'
AFTER = '8f16a9095cee3d39c7178d0d39d99f82e89d26ff05bcaef36019398cbf89625c'


def abort(reason):
    raise RuntimeError('MPW_REQUIRED_EMAIL_ABORT:' + reason)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def secure_file(path):
    if (path.is_symlink() or path.parent.is_symlink() or not path.is_file()
            or path.stat().st_uid != os.geteuid() or path.stat().st_nlink != 1):
        abort('UNSAFE_FILE:' + path.name)
    return path.read_bytes()


def guard_host():
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        abort('WRONG_ACCOUNT')
    for root in (APP, PUBLIC):
        if root.is_symlink() or not root.is_dir() or root.resolve() != root:
            abort('UNSAFE_ROOT')
    wsgi = secure_file(PUBLIC / 'passenger_wsgi.py')
    if b"APP='/home/zomorod2/Saeit-staging'" not in wsgi:
        abort('WRONG_PASSENGER_APP')
    marker = PUBLIC / 'tmp/restart.txt'
    if marker.is_symlink() or marker.parent.is_symlink() or not marker.parent.is_dir():
        abort('UNSAFE_RESTART_MARKER')


def verify_source(data):
    if len(data) > 75000 or digest(data) != AFTER:
        abort('UNREVIEWED_EMAIL_SOURCE')
    src = data.decode('utf-8')
    compile(src, str(RELATIVE), 'exec')
    for required in ('def _required_checkout_email(request):',
                     'checkout_email = _required_checkout_email(request) if create else None',
                     'raise Http404("Account email must match purchase email")',
                     'def patch_commercial(namespace):'):
        if required not in src:
            abort('MISSING_EMAIL_GUARD')


def current_flags():
    source = secure_file(APP / 'config/settings.py').decode('utf-8')
    for required in ('MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED = True',
                     'MPW_GUEST_RECOVERY_ENABLED = False',
                     'MPW_GUEST_RECOVERY_EMAIL_APPROVED = False'):
        if required not in source:
            abort('UNSAFE_EMAIL_RECOVERY_SETTING:' + required.split(' =')[0])


def preflight(stage):
    guard_host()
    if stage.is_symlink() or not stage.is_dir():
        abort('UNSAFE_STAGE')
    staged_file = stage / RELATIVE
    if not staged_file.resolve().is_relative_to(stage.resolve()):
        abort('STAGED_PATH_ESCAPE')
    staged = secure_file(staged_file)
    verify_source(staged)
    live = secure_file(APP / RELATIVE)
    if digest(live) not in (BEFORE, AFTER):
        abort('LIVE_SOURCE_DRIFT:' + digest(live))
    current_flags()
    print('MPW_REQUIRED_EMAIL_PREFLIGHT=PASS;LIVE=' + digest(live) +
          ';STAGED=' + digest(staged) + ';EMAIL_SENT=0;ORDERS_CREATED=0;PAYMENTS=0', flush=True)
    return live, staged


def atomic_replace(path, new, expected):
    if digest(secure_file(path)) != expected:
        abort('CONCURRENT_LIVE_EDIT')
    fd, tmp = tempfile.mkstemp(prefix='.mpw-email-', dir=path.parent)
    try:
        os.fchmod(fd, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd, 'wb') as stream:
            stream.write(new)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def restart():
    marker = PUBLIC / 'tmp/restart.txt'
    if marker.is_symlink() or marker.parent.is_symlink():
        abort('RESTART_PATH_DRIFT')
    marker.touch()


def verify():
    guard_host()
    live = secure_file(APP / RELATIVE)
    verify_source(live)
    current_flags()
    print('MPW_REQUIRED_EMAIL_VERIFY=PASS;SERVER_EMAIL_REQUIRED=TRUE;'
          'GUEST_REGISTRATION_REQUIRED=FALSE;OUTBOUND_EMAIL=OFF', flush=True)


def publish(stage, run_id):
    live, staged = preflight(stage)
    if digest(live) == AFTER:
        verify()
        print('MPW_REQUIRED_EMAIL_RELEASE=ALREADY_INSTALLED', flush=True)
        return
    if not re.fullmatch(r'[0-9]{8,20}', run_id):
        abort('INVALID_RUN_ID')
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    if BACKUPS.is_symlink() or stat.S_IMODE(BACKUPS.stat().st_mode) & 0o077:
        abort('UNSAFE_BACKUPS')
    target = BACKUPS / run_id
    if target.exists() or target.is_symlink():
        abort('BACKUP_COLLISION')
    target.mkdir(mode=0o700)
    with (target / 'guest.before').open('xb') as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(live)
        out.flush()
        os.fsync(out.fileno())
    with (target / 'manifest.json').open('x') as out:
        os.fchmod(out.fileno(), 0o600)
        json.dump({'before': BEFORE, 'after': AFTER, 'run': run_id}, out)
        out.flush()
        os.fsync(out.fileno())
    path = APP / RELATIVE
    replaced = False
    try:
        atomic_replace(path, staged, BEFORE)
        replaced = True
        restart()
        verify()
    except BaseException:
        if replaced and digest(secure_file(path)) == AFTER:
            atomic_replace(path, live, AFTER)
            restart()
        raise
    print('MPW_REQUIRED_EMAIL_RELEASE=APPLIED;FILES=1;EMAIL_SENT=0;'
          'ORDERS_CREATED=0;PAYMENTS_CHANGED=0', flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'preflight':
        preflight(Path(sys.argv[2]))
    elif len(sys.argv) == 4 and sys.argv[1] == 'publish':
        publish(Path(sys.argv[2]), sys.argv[3])
    elif len(sys.argv) == 2 and sys.argv[1] == 'verify':
        verify()
    else:
        raise SystemExit('Usage: preflight STAGE | publish STAGE RUN_ID | verify')
