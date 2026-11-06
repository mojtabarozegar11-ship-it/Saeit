#!/usr/bin/env python3
"""Publish the reviewed two-file server-side inquiry counter correction.

All source SHAs are pinned; original PHP files receive private recoverable
backups. This script never reads or changes encrypted inquiries, keys, email,
checkout, orders or financial data, and never issues a form POST.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = Path('/home/zomorod2/mojplaywin.com/mpw-editorial/revenue')
FILES = ('inquiry.php', 'metrics.php')
BEFORE = {
    'inquiry.php': '146ab64058576a83946bbcc4a3bd3fd383684e0b5b56ca603100abdf9acf71f2',
    'metrics.php': '911874fbdcdc5aae96e1d77e253d799820f5979067e46a86eedd44314d085a22',
}
AFTER = {
    'inquiry.php': '3eb53d0cc5f556a34b53a7b2894a4653a4575d5a140e2180134716a6a995aaf1',
    'metrics.php': 'f2ece31added13e9771c19d1ba6acd4147bc3a0bd90bee57f6cd3c9f3fd7df45',
}
BACKUPS = Path('/home/zomorod2/.local/share/mpw-inquiry-counter-releases')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_candidate(files: dict[str, bytes]) -> None:
    if set(files) != set(FILES):
        raise RuntimeError('Unexpected source artifact inventory')
    for filename in FILES:
        if sha(files[filename]) != AFTER[filename]:
            raise RuntimeError('Unreviewed source artifact: ' + filename)
    inquiry = files['inquiry.php']
    metrics = files['metrics.php']
    if (inquiry.count(b'function record_inquiry_metric(') != 1 or
            inquiry.count(b'record_inquiry_metric($slug);') != 1 or
            b'event=inquiry_submitted' in inquiry or
            b"if ((int)($_SERVER['CONTENT_LENGTH']??0)>12000)" not in inquiry or
            inquiry.count(b"@mail('support@mojplaywin.com'") != 1 or
            b'$reference=store_inquiry($record);' not in inquiry or
            b'openssl_encrypt' not in inquiry):
        raise RuntimeError('Unexpected commercial inquiry implementation')
    if (b"$events=['quote_click','tool_generated','game_interacted'];" not in metrics or
            b"$slugs=['website-doctor'" not in metrics or
            b'inquiry_submitted' in metrics):
        raise RuntimeError('Unexpected public metric event policy')


def load_payload() -> dict[str, bytes]:
    content = sys.stdin.buffer.read(80000)
    if len(content) >= 80000 or len(content) < 4000:
        raise RuntimeError('Missing or oversized reviewed file payload')
    data = json.loads(content)
    if not isinstance(data, dict) or set(data) != set(FILES):
        raise RuntimeError('Wrong payload manifest')
    files = {key: base64.b64decode(data[key], validate=True) for key in FILES}
    validate_candidate(files)
    return files


def verify_host() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('Wrong cPanel owner')
    if ROOT.is_symlink() or ROOT.resolve() != ROOT or not ROOT.is_dir():
        raise RuntimeError('Revenue route unavailable')
    for filename in FILES:
        path = ROOT / filename
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('Unexpected live PHP source path')
        st = path.stat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) & 0o022):
            raise RuntimeError('Unexpected live source permissions')
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError('Unsafe backup location')


def php_binary() -> str:
    for filename in ('/usr/local/bin/php', '/usr/bin/php',
                     '/opt/cpanel/ea-php82/root/usr/bin/php'):
        if Path(filename).is_file() and os.access(filename, os.X_OK):
            return filename
    php = shutil.which('php')
    if not php:
        raise RuntimeError('PHP lint interpreter unavailable')
    return php


def lint_php(content: bytes) -> None:
    fd, temp = tempfile.mkstemp(prefix='.mpw-inquiry-lint-', suffix='.php', dir=ROOT)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content)
        result = subprocess.run([php_binary(), '-l', temp], capture_output=True,
                                text=True, timeout=18)
        if result.returncode:
            raise RuntimeError('Candidate PHP syntax error: ' + result.stderr[:200])
    finally:
        os.unlink(temp)


def atomic(path: Path, content: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix='.mpw-inquiry-metric-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def release_paths(run_id: str) -> tuple[Path, Path]:
    if not re.fullmatch(r'[0-9]{8,20}', run_id):
        raise RuntimeError('Invalid release ID')
    return BACKUPS / run_id, BACKUPS / run_id / 'manifest.json'


def command(op: str, run_id: str = '') -> None:
    if op == 'selftest':
        bad = {key: b'not-the-reviewed-source' for key in FILES}
        try:
            validate_candidate(bad)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Unreviewed source must be rejected')
        assert BEFORE['inquiry.php'] != AFTER['inquiry.php']
        assert BEFORE['metrics.php'] != AFTER['metrics.php']
        print('MPW_INQUIRY_COUNTER_SELFTEST=PASS')
        return

    files = load_payload() if op in ('preflight', 'publish') else None
    verify_host()
    current = {key: (ROOT / key).read_bytes() for key in FILES}
    if op in ('preflight', 'publish'):
        if any(sha(current[key]) != BEFORE[key] for key in FILES):
            raise RuntimeError('Live inquiry or metric file differs from preflight evidence')
        for key in FILES:
            lint_php(files[key])
        if op == 'preflight':
            print('MPW_INQUIRY_COUNTER_PREFLIGHT=PASS;NO_POST_OR_EMAIL=TRUE')
            return

    folder, manifest = release_paths(run_id)
    if op == 'publish':
        BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
        if stat.S_IMODE(BACKUPS.stat().st_mode) != 0o700 or folder.exists():
            raise RuntimeError('Unsafe or reused private release location')
        folder.mkdir(mode=0o700)
        for filename in FILES:
            path = folder / (filename + '.original')
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(current[filename])
                handle.flush()
                os.fsync(handle.fileno())
        saved = json.dumps({'before': BEFORE, 'after': AFTER}, sort_keys=True).encode()
        atomic(manifest, saved, 0o600)
        changed = []
        try:
            for filename in FILES:
                path = ROOT / filename
                if sha(path.read_bytes()) != BEFORE[filename]:
                    raise RuntimeError('Concurrent commercial PHP source change')
                atomic(path, files[filename], stat.S_IMODE(path.stat().st_mode))
                changed.append(filename)
                if sha(path.read_bytes()) != AFTER[filename]:
                    raise RuntimeError('Live PHP write verification failed')
        except BaseException:
            for filename in reversed(changed):
                path = ROOT / filename
                if sha(path.read_bytes()) == AFTER[filename]:
                    atomic(path, current[filename], stat.S_IMODE(path.stat().st_mode))
            raise
        print('MPW_INQUIRY_COUNTER_PUBLISHED=PASS;FILES=2;NO_POST_OR_EMAIL=TRUE')
        return

    if op == 'rollback':
        if not folder.is_dir() or folder.is_symlink() or not manifest.is_file() or manifest.is_symlink():
            raise RuntimeError('Backups not available for rollback')
        metadata = json.loads(manifest.read_text('utf-8'))
        if metadata != {'before': BEFORE, 'after': AFTER}:
            raise RuntimeError('Unexpected backup manifest')
        if any(sha(current[key]) != AFTER[key] for key in FILES):
            raise RuntimeError('Concurrent source modifications block rollback')
        restored = {}
        for filename in FILES:
            path = folder / (filename + '.original')
            if not path.is_file() or path.is_symlink():
                raise RuntimeError('Private original source missing')
            restored[filename] = path.read_bytes()
            if sha(restored[filename]) != BEFORE[filename]:
                raise RuntimeError('Backup original checksum mismatch')
            lint_php(restored[filename])
        for filename in FILES:
            path = ROOT / filename
            atomic(path, restored[filename], stat.S_IMODE(path.stat().st_mode))
        print('MPW_INQUIRY_COUNTER_ROLLBACK=PASS')
        return
    raise RuntimeError('Expected selftest, preflight, publish or rollback')


if __name__ == '__main__':
    command(*sys.argv[1:])
