#!/usr/bin/env python3
"""Attach real tool and inquiry actions to all 340 MojPlayWin topic pages.

One guarded production PHP source edit, with private backup and rollback.
No buyer data, email, order, price, routing or topic catalogue changes.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = Path('/home/zomorod2/mojplaywin.com')
SOURCE = ROOT / 'design-preview-20261017/mpw-site-integrity-20261019/topic.php'
HTACCESS = ROOT / '.htaccess'
BACKUPS = Path('/home/zomorod2/.local/share/mpw-topic-conversion-backups')
EXPECTED_SOURCE_SHA = '6812fdc0075a5ccb6d9ff1589da32fc4b6ce69e375d06d76855e3f96e27aff50'
ANCHOR = b"echo '</main>';footer_html();"
MARKER = b'data-mpw-topic-earning-path="20261106"'
INSERT = (
    b'echo \'<section class="mpw-topic-action" data-mpw-topic-earning-path="20261106" '
    b'aria-labelledby="mpw-topic-action-title"><h2 id="mpw-topic-action-title">'
    b'Put this topic to work</h2><p>Use a free practical tool or send a project '
    b'inquiry describing your goal, constraints and the result you need. '
    b'An inquiry does not create an order or require a payment.</p>'
    b'<p><a class="go" href="/mpw-editorial/revenue/index.html">'
    b'Open 12 practical tools</a> '
    b'<a class="go" href="/mpw-editorial/revenue/inquiry.php?service=general">'
    b'Request a project review</a></p></section>\';\n'
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transform(raw: bytes) -> bytes:
    if (len(raw) < 2000 or len(raw) > 50000 or raw.count(ANCHOR) != 1 or
            MARKER in raw or raw.count(b'function head_html(') != 1 or
            raw.count(b'top_nav();') != 1 or raw.count(b'footer_html();') != 1 or
            b"safe($selected['title'])" not in raw):
        raise RuntimeError('Live topic engine differs from audited precondition')
    updated = raw.replace(ANCHOR, INSERT + ANCHOR)
    if updated.count(MARKER) != 1 or updated.replace(INSERT + ANCHOR, ANCHOR) != raw:
        raise RuntimeError('Topic CTA insertion validation failed')
    return updated


def verify_host() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('Wrong hosting account')
    if ROOT.is_symlink() or ROOT.resolve() != ROOT or not ROOT.is_dir():
        raise RuntimeError('Unexpected document root')
    if SOURCE.is_symlink() or not SOURCE.is_file() or HTACCESS.is_symlink():
        raise RuntimeError('Topic engine path invalid')
    if 'mpw-site-integrity-20261019/topic.php' not in HTACCESS.read_text('utf-8', 'replace'):
        raise RuntimeError('Active PHP route no longer matches')
    st = SOURCE.stat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_nlink != 1
            or stat.S_IMODE(st.st_mode) & 0o022):
        raise RuntimeError('Unexpected PHP source ownership/permissions')
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError('Unsafe backup directory')


def lint(candidate: bytes) -> None:
    php = next((p for p in ('/usr/local/bin/php', '/usr/bin/php',
                           '/opt/cpanel/ea-php82/root/usr/bin/php')
                if Path(p).is_file() and os.access(p, os.X_OK)), None)
    if php is None:
        php = shutil.which('php')
    if not php:
        raise RuntimeError('PHP linter unavailable; no live write permitted')
    fd, name = tempfile.mkstemp(prefix='.mpw-topic-lint-', suffix='.php', dir=SOURCE.parent)
    try:
        with os.fdopen(fd, 'wb') as fp:
            fp.write(candidate)
        result = subprocess.run([php, '-l', name], capture_output=True,
                                text=True, timeout=15)
        if result.returncode != 0:
            raise RuntimeError('PHP syntax validation failed: ' + result.stderr[:200])
    finally:
        os.unlink(name)


def atomic(path: Path, content: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix='.mpw-topic-release-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def filepaths(run_id: str) -> tuple[Path, Path]:
    if not re.fullmatch(r'[0-9]{8,20}', run_id):
        raise RuntimeError('Invalid one-off run ID')
    return (BACKUPS / (run_id + '.original.php'),
            BACKUPS / (run_id + '.published.sha256'))


def command(op: str, run_id: str = '') -> None:
    if op == 'selftest':
        fixture = (b'<?php\nfunction head_html(){}\nfunction safe(){}\n'
                   b'top_nav();\necho safe($selected[\'title\']);\n'
                   + ANCHOR + b'\n') + b' ' * 2100
        assert transform(fixture).count(MARKER) == 1
        try:
            transform(transform(fixture))
        except RuntimeError:
            pass
        else:
            raise AssertionError('Duplicate changes must be refused')
        print('MPW_TOPIC_CONVERSION_SELFTEST=PASS')
        return

    verify_host()
    current = SOURCE.read_bytes()
    if op == 'preflight':
        if sha(current) != EXPECTED_SOURCE_SHA:
            raise RuntimeError('Production topic engine has changed since read-only audit')
        lint(transform(current))
        print('MPW_TOPIC_CONVERSION_PREFLIGHT=PASS original_sha256=' + sha(current))
        return

    backup, marker = filepaths(run_id)
    if op == 'publish':
        if sha(current) != EXPECTED_SOURCE_SHA:
            raise RuntimeError('Preflight source drift; publication stopped')
        new = transform(current)
        lint(new)
        BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
        if stat.S_IMODE(BACKUPS.stat().st_mode) != 0o700:
            raise RuntimeError('Backup folder must be private')
        if backup.exists() or marker.exists() or backup.is_symlink() or marker.is_symlink():
            raise RuntimeError('This release ID already exists')
        fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as fp:
            fp.write(current)
            fp.flush()
            os.fsync(fp.fileno())
        atomic(marker, (sha(new) + '\n').encode(), 0o600)
        if sha(SOURCE.read_bytes()) != sha(current):
            raise RuntimeError('Concurrent PHP source edit')
        mode = stat.S_IMODE(SOURCE.stat().st_mode)
        atomic(SOURCE, new, mode)
        if sha(SOURCE.read_bytes()) != sha(new):
            atomic(SOURCE, current, mode)
            raise RuntimeError('Source verification failed; restored')
        print('MPW_TOPIC_CONVERSION_PUBLISHED=PASS sha256=' + sha(new))
        return

    if op == 'rollback':
        if not backup.is_file() or backup.is_symlink() or not marker.is_file() or marker.is_symlink():
            raise RuntimeError('Release backup unavailable')
        if sha(current) != marker.read_text().strip():
            raise RuntimeError('Updated source changed; refusing rollback')
        previous = backup.read_bytes()
        if sha(previous) != EXPECTED_SOURCE_SHA:
            raise RuntimeError('Original backup hash invalid')
        lint(previous)
        atomic(SOURCE, previous, stat.S_IMODE(SOURCE.stat().st_mode))
        print('MPW_TOPIC_CONVERSION_ROLLBACK=PASS')
        return
    raise RuntimeError('Expected selftest, preflight, publish or rollback')


if __name__ == '__main__':
    command(*sys.argv[1:])
