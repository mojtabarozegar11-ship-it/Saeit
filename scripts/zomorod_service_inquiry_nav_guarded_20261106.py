#!/usr/bin/env python3
"""One-time guarded menu link to the already deployed private inquiry viewer.

Never touches customer databases, sessions or the form handlers. Requires an
exact source fingerprint and keeps a private byte-for-byte rollback backup.
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

HOME = Path('/home/zomorod2')
WEB = HOME / 'public_html'
PRIVATE = HOME / '.private/zomorod-business'
APP = PRIVATE / 'app.php'
INBOX = WEB / 'business/inquiries.php'
BACKUPS = PRIVATE / '.service-inquiry-nav-backups'
EXPECTED_SHA = '8236fd7ea839e590527b75b02ebc63b7ea8327bdfe6d111acb61877fe0dde296'
MARKER = 'zm-service-inbox-nav-20261106'
ANCHOR = "if($user)echo '<nav aria-label=\"پیمایش مدیریت\">'.$navHtml.'</nav>';"
INSERT = ("/* " + MARKER + " */\n"
          "$navHtml .= '<a href=\"/business/inquiries.php\">درخواست‌های خدمات تخصصی</a>';\n")


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate() -> None:
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('WRONG_SITE_USER')
    if PRIVATE.is_symlink() or APP.is_symlink() or INBOX.is_symlink():
        raise RuntimeError('UNSAFE_SYMLINK')
    if not APP.is_file() or not INBOX.is_file():
        raise RuntimeError('MANAGEMENT_OR_INBOX_MISSING')
    if BACKUPS.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_DIRECTORY')


def transform(source: str) -> tuple[str, str]:
    if MARKER in source:
        if source.count(MARKER) != 1 or source.count(INSERT) != 1:
            raise RuntimeError('PARTIAL_MENU_PATCH')
        return 'already-patched', source
    if sha(source.encode('utf-8')) != EXPECTED_SHA:
        raise RuntimeError('REFUSE_UNKNOWN_MANAGEMENT_VERSION')
    if source.count(ANCHOR) != 1:
        raise RuntimeError('MENU_ANCHOR_DRIFT')
    return 'needs-patch', source.replace(ANCHOR, INSERT + ANCHOR, 1)


def lint(source: str) -> None:
    binary = shutil.which('php') or '/opt/cpanel/ea-php82/root/usr/bin/php'
    if not Path(binary).is_file():
        raise RuntimeError('PHP_CLI_UNAVAILABLE')
    fd, name = tempfile.mkstemp(prefix='.inquiry-nav-lint-', suffix='.php', dir=str(PRIVATE))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(source)
        os.chmod(name, 0o600)
        p = subprocess.run([binary, '-l', name], capture_output=True, timeout=25)
        if p.returncode:
            raise RuntimeError('PHP_LINT_FAILED')
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_write(target: Path, data: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix='.inquiry-nav-', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def folder(runid: str) -> Path:
    if not re.fullmatch(r'[0-9]{5,20}', runid):
        raise RuntimeError('INVALID_RUN_ID')
    return BACKUPS / runid


def preview() -> None:
    validate()
    source = APP.read_text(encoding='utf-8')
    state, patched = transform(source)
    lint(patched)
    print('INQUIRY_NAV_PREVIEW=' + state)


def publish(runid: str) -> None:
    validate()
    source = APP.read_text(encoding='utf-8')
    state, patched = transform(source)
    if state != 'needs-patch':
        raise RuntimeError('REFUSE_REPEATED_PUBLISH')
    lint(patched)
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    target = folder(runid)
    if target.exists() or target.is_symlink():
        raise RuntimeError('BACKUP_COLLISION')
    target.mkdir(mode=0o700)
    mode = stat.S_IMODE(APP.stat().st_mode)
    backup = target / 'app.php'
    backup.write_bytes(source.encode('utf-8'))
    backup.chmod(0o600)
    manifest = {'original_sha': EXPECTED_SHA, 'patched_sha': sha(patched.encode('utf-8')), 'mode': mode}
    (target / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')
    (target / 'manifest.json').chmod(0o600)
    atomic_write(APP, patched.encode('utf-8'), mode)
    print('INQUIRY_NAV_PUBLISHED=1')


def verify(runid: str) -> None:
    validate()
    state, source = transform(APP.read_text(encoding='utf-8'))
    manifest = json.loads((folder(runid) / 'manifest.json').read_text(encoding='utf-8'))
    if state != 'already-patched' or sha(source.encode('utf-8')) != manifest['patched_sha']:
        raise RuntimeError('INQUIRY_NAV_VERIFY_DRIFT')
    lint(source)
    print('INQUIRY_NAV_VERIFIED=1')


def rollback(runid: str) -> None:
    validate()
    manifest = json.loads((folder(runid) / 'manifest.json').read_text(encoding='utf-8'))
    source = APP.read_bytes()
    backup = (folder(runid) / 'app.php').read_bytes()
    if sha(source) != manifest['patched_sha'] or sha(backup) != manifest['original_sha']:
        raise RuntimeError('REFUSE_ROLLBACK_DRIFT')
    atomic_write(APP, backup, int(manifest['mode']))
    print('INQUIRY_NAV_ROLLED_BACK=1')


def selftest() -> None:
    assert len(EXPECTED_SHA) == 64
    assert MARKER in INSERT and 'business/inquiries.php' in INSERT
    assert ANCHOR.count('$navHtml') == 1
    print('INQUIRY_NAV_SELFTEST_OK=1')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['selftest']:
        selftest()
    elif args == ['preview']:
        preview()
    elif len(args) == 2 and args[0] in ('publish', 'verify', 'rollback'):
        runid = args[1]
        if args[0] == 'publish':
            publish(runid)
        elif args[0] == 'verify':
            verify(runid)
        else:
            rollback(runid)
    else:
        raise RuntimeError('UNKNOWN_MODE')
