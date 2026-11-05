#!/usr/bin/env python3
"""Guarded correction of one public personnel link to the authenticated staff login.

Only /home/zomorod2/Saeit/templates/base.html may be changed. No database,
payments, application configuration, or unrelated site file is touched.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HOME = Path('/home/zomorod2')
TARGET = HOME / 'Saeit/templates/base.html'
EXPECTED = 'db7e1f8d890489891ab30ad605957cceab0d16f54a358165808b682ace6bcf67'
OLD = b'href="/personnel/"'
NEW = b'href="/staff/"'
PAGE = 'https://zomorodmelal.ir/newsletter/'
BACKUP = HOME / 'Saeit/.route-backups/base-personnel-link-20261105-db7e1f8d.html'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def live_markup() -> bytes:
    # An independent URL for every read prevents an earlier successful gold
    # navigation verification from being reused as a cached personnel result.
    nonce = secrets.token_hex(12)
    req = Request(PAGE + '?' + urlencode({'zm_personnel_nav_guard': nonce}), headers={
        'User-Agent': 'ZM-Personnel-Navigation-Guard/1.1', 'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'})
    with urlopen(req, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError('PUBLIC_NEWSLETTER_NOT_HTTP_200')
        return response.read(220_000)


def replace_atomically(data: bytes, mode: int) -> None:
    temp: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.zm-nav.', dir=TARGET.parent,
                                         delete=False) as f:
            temp = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, stat.S_IMODE(mode))
        os.replace(temp, TARGET)
        temp = None
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def apply() -> dict[str, object]:
    if os.getuid() != HOME.stat().st_uid or TARGET.is_symlink():
        raise RuntimeError('ACCOUNT_OR_TARGET_MISMATCH')
    old_data = TARGET.read_bytes()
    if sha(old_data) != EXPECTED:
        raise RuntimeError('MAIN_TEMPLATE_CHANGED_ABORT:' + sha(old_data))
    if old_data.count(OLD) != 1:
        raise RuntimeError('PERSONNEL_LINK_OCCURRENCES_CHANGED_ABORT')
    # Confirm the source URL is still broken and staff access is login-gated.
    if OLD not in live_markup():
        raise RuntimeError('LIVE_TEMPLATE_NO_LONGER_MATCHES_ABORT')
    request = Request('https://zomorodmelal.ir/staff/',
                      headers={'User-Agent': 'ZM-Personnel-Navigation-Guard/1.1'})
    with urlopen(request, timeout=15) as response:
        if (response.status != 200 or
                not response.url.startswith('https://zomorodmelal.ir/admin/login/')):
            raise RuntimeError('STAFF_LOGIN_NOT_ENFORCED')
    fixed = old_data.replace(OLD, NEW)
    if fixed.count(NEW) != old_data.count(NEW) + 1 or fixed.count(OLD) != 0:
        raise RuntimeError('INVALID_NAV_PATCH')
    BACKUP.parent.mkdir(mode=0o700, exist_ok=True)
    # Fail closed if a backup of the same name has unexpected content.
    if BACKUP.exists():
        if sha(BACKUP.read_bytes()) != EXPECTED:
            raise RuntimeError('BACKUP_CONFLICT_ABORT')
    else:
        with BACKUP.open('xb') as f:
            f.write(old_data)
            f.flush()
            os.fsync(f.fileno())
        BACKUP.chmod(0o600)
    old_mode = TARGET.stat().st_mode
    replace_atomically(fixed, old_mode)
    if sha(TARGET.read_bytes()) != sha(fixed):
        replace_atomically(old_data, old_mode)
        raise RuntimeError('DISK_VERIFICATION_FAILED_ROLLED_BACK')
    try:
        new_public = live_markup()
        verified = NEW in new_public and OLD not in new_public
    except Exception:
        verified = False
    if not verified:
        replace_atomically(old_data, old_mode)
        if sha(TARGET.read_bytes()) != EXPECTED:
            raise RuntimeError('ROLLBACK_FAILED_REQUIRES_OPERATOR')
        return {'status': 'PUBLIC_NOT_REFRESHED_ROLLED_BACK',
                'live_links_fixed': 0, 'backup_sha256': EXPECTED,
                'main_template_sha256': EXPECTED, 'other_paths_touched': 0}
    return {'status': 'LIVE_VERIFIED', 'live_links_fixed': 1,
            'backup_sha256': EXPECTED, 'main_template_sha256': sha(fixed),
            'other_paths_touched': 0}


if __name__ == '__main__':
    if sys.argv[1:] != ['guarded']:
        raise SystemExit('USAGE: guarded')
    print('PERSONNEL_NAV_GUARDED_RESULT=' + json.dumps(apply(), sort_keys=True), flush=True)
