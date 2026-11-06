#!/usr/bin/env python3
"""One-file guarded release: preserve encrypted inquiries, disable owner mail.

Only reviewed inquiry PHP bytes are accepted. No customer record is accessed,
no form is submitted, and no email, payment or order action is performed.
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


ROOT = Path('/home/zomorod2/mojplaywin.com/mpw-editorial/revenue')
TARGET = ROOT / 'inquiry.php'
BACKUPS = Path('/home/zomorod2/.local/share/mpw-owner-email-lock-releases')
BEFORE_SHA = '3eb53d0cc5f556a34b53a7b2894a4653a4575d5a140e2180134716a6a995aaf1'
AFTER_SHA = 'd2a3400d2b94d23603c879dfba7ebbf70782a2d26c33cb5476d14ce1be3912f6'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_candidate(data: bytes) -> None:
    if digest(data) != AFTER_SHA or len(data) > 26000 or len(data) < 8000:
        raise RuntimeError('Candidate differs from reviewed inquiry PHP')
    required = (b'$reference=store_inquiry($record);', b'record_inquiry_metric($slug);',
                b'openssl_encrypt(', b'function key_bytes(',
                b'Automatic email notifications are disabled',
                b'No automatic email receipt or response is sent by this form.')
    if any(token not in data for token in required):
        raise RuntimeError('Secure inquiry contract missing')
    if (b'@mail(' in data or b'mail(' in data or b'event=inquiry_submitted' in data):
        raise RuntimeError('Automatic mail or browser-forgeable metric is disallowed')


def guard() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('Wrong hosting account')
    if ROOT.is_symlink() or ROOT.resolve() != ROOT or not ROOT.is_dir():
        raise RuntimeError('Unexpected live root')
    if TARGET.is_symlink() or not TARGET.is_file():
        raise RuntimeError('Unexpected inquiry PHP path')
    st = TARGET.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) & 0o022:
        raise RuntimeError('Unsafe live source permissions')
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError('Unsafe private backup directory')


def php_lint(data: bytes) -> None:
    php = next((str(p) for p in map(Path, ('/usr/local/bin/php', '/usr/bin/php',
               '/opt/cpanel/ea-php82/root/usr/bin/php')) if p.is_file() and os.access(p, os.X_OK)), None)
    if php is None:
        php = shutil.which('php')
    if not php:raise RuntimeError('PHP linter unavailable')
    fd, tmp = tempfile.mkstemp(prefix='.mpw-inquiry-mail-lint-', suffix='.php', dir=ROOT)
    try:
        with os.fdopen(fd, 'wb') as handle:handle.write(data)
        result = subprocess.run([php, '-l', tmp], capture_output=True, text=True, timeout=16)
        if result.returncode:raise RuntimeError('PHP lint failure: '+result.stderr[:200])
    finally:
        os.unlink(tmp)


def atomic(data: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix='.mpw-inquiry-mail-', dir=ROOT)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(name,TARGET)
        dfd=os.open(ROOT,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(dfd)
        finally:os.close(dfd)
    finally:
        if os.path.exists(name):os.unlink(name)


def paths(run_id: str) -> tuple[Path, Path]:
    if not re.fullmatch(r'[0-9]{8,20}',run_id):raise RuntimeError('Invalid release id')
    return BACKUPS/(run_id+'.original.php'), BACKUPS/(run_id+'.published.sha256')


def run(op: str, run_id: str='') -> None:
    if op == 'selftest':
        try:verify_candidate(b'unapproved source')
        except RuntimeError:pass
        else:raise AssertionError('Unapproved content must fail closed')
        print('MPW_OWNER_EMAIL_LOCK_SELFTEST=PASS');return
    guard()
    current=TARGET.read_bytes()
    if op in ('preflight','publish'):
        candidate=sys.stdin.buffer.read(30000)
        verify_candidate(candidate)
        if digest(current) != BEFORE_SHA:raise RuntimeError('Live inquiry source has drifted')
        php_lint(candidate)
        if op=='preflight':print('MPW_OWNER_EMAIL_LOCK_PREFLIGHT=PASS');return
        backup, marker = paths(run_id)
        BACKUPS.mkdir(mode=0o700,parents=True,exist_ok=True)
        if stat.S_IMODE(BACKUPS.stat().st_mode)!=0o700 or backup.exists() or marker.exists():
            raise RuntimeError('Unsafe or reused private backup')
        fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(current);f.flush();os.fsync(f.fileno())
        fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write((AFTER_SHA+'\n').encode());f.flush();os.fsync(f.fileno())
        if digest(TARGET.read_bytes())!=BEFORE_SHA:raise RuntimeError('Concurrent source change')
        mode=stat.S_IMODE(TARGET.stat().st_mode)
        try:
            atomic(candidate,mode)
            if digest(TARGET.read_bytes()) != AFTER_SHA:raise RuntimeError('Published PHP hash mismatch')
        except BaseException:
            if digest(TARGET.read_bytes())==AFTER_SHA:atomic(current,mode)
            raise
        print('MPW_OWNER_EMAIL_LOCK_PUBLISHED=PASS;NO_AUTOMATIC_MAIL=TRUE');return
    if op=='rollback':
        backup,marker=paths(run_id)
        if not backup.is_file() or backup.is_symlink() or not marker.is_file() or marker.is_symlink():
            raise RuntimeError('Owned release backup unavailable')
        if digest(current)!=AFTER_SHA or marker.read_text().strip()!=AFTER_SHA:
            raise RuntimeError('Live source changed; refusing rollback')
        original=backup.read_bytes()
        if digest(original)!=BEFORE_SHA:raise RuntimeError('Backup integrity failed')
        php_lint(original)
        atomic(original,stat.S_IMODE(TARGET.stat().st_mode))
        print('MPW_OWNER_EMAIL_LOCK_ROLLBACK=PASS');return
    raise RuntimeError('Expected selftest, preflight, publish or rollback')


if __name__=='__main__':run(*sys.argv[1:])
