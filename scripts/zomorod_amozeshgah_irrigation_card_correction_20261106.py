#!/usr/bin/env python3
"""Correct one public academy card: link an actual calculator, not an article."""
from __future__ import annotations
import hashlib
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

HOME = Path('/home/zomorod2')
TARGET = HOME / 'public_html/amozeshgah/index.html'
BACKUPS = HOME / '.backups/zomorod-amozeshgah-interactive-card-20261106'
EXPECTED = '96b6f3bb020c714bc658d988df81479b09ba9a4f7ee1d5560a57e44be1203e61'
VERSION = 'data-zm-interactive-irrigation="20261106"'
OLD = ('<a class="offer zm-active-offer" href="/resources/20261025/farm-risk/">'
       '<small>FREE · RISK ASSESSMENT</small><h3>بررسی ریسک فعالیت کشاورزی</h3>'
       '<p>برای تحلیل اولیهٔ ریسک‌های تولید و تصمیم‌گیری از این ابزار استفاده کنید.</p>'
       '<b>مشاهدهٔ ابزار ریسک ←</b></a>')
NEW = ('<a class="offer zm-active-offer" href="/topics/tools/irrigation-planner/" '
       + VERSION + '><small>FREE · IRRIGATION PLANNING</small>'
       '<h3>محاسبهٔ نیاز آب آبیاری</h3>'
       '<p>داده‌های اقلیمی و مشخصات مزرعه را وارد کنید و حجم آب و زمان پمپاژ را محاسبه کنید.</p>'
       '<b>باز کردن محاسبه‌گر آبیاری ←</b></a>')


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def patch(raw: bytes, verify_hash: bool = True) -> bytes:
    if verify_hash and digest(raw) != EXPECTED:
        raise RuntimeError('IRRIGATION_CARD_BASELINE_CHANGED_ABORT')
    content = raw.decode('utf-8')
    if content.count('data-zm-functional-catalog="20261106"') != 1 or content.count(OLD) != 1:
        raise RuntimeError('IRRIGATION_CARD_CONTEXT_CHANGED_ABORT')
    result = content.replace(OLD, NEW, 1)
    if result.count(VERSION) != 1 or result.count('/topics/tools/irrigation-planner/') != 1:
        raise RuntimeError('IRRIGATION_CARD_RESULT_INVALID')
    return result.encode('utf-8')


def guard() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError('IRRIGATION_CARD_CPANEL_USER_INVALID')
    for path in (HOME / 'public_html', TARGET.parent, TARGET, BACKUPS):
        if path.is_symlink():
            raise RuntimeError('IRRIGATION_CARD_SYMLINK_REFUSED')
    if not TARGET.is_file() or TARGET.stat().st_size > 300_000:
        raise RuntimeError('IRRIGATION_CARD_UNEXPECTED_TARGET')
    if BACKUPS.exists() and not BACKUPS.is_dir():
        raise RuntimeError('IRRIGATION_CARD_BACKUP_UNSAFE')


def atomic(data: bytes) -> None:
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=TARGET.parent, prefix='.zm-irrigation-', delete=False) as handle:
            tmp = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, TARGET.stat().st_mode & 0o777)
        os.replace(tmp, TARGET)
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def get_public() -> bytes:
    req = Request('https://zomorodmelal.ir/amozeshgah/?zm_irrigation=' + str(time.time_ns()),
                  headers={'Cache-Control': 'no-cache', 'User-Agent': 'ZM-Interactive-Card/1.0'})
    with urlopen(req, timeout=20) as reply:
        if reply.status != 200:
            raise RuntimeError('IRRIGATION_CARD_PUBLIC_NOT_200')
        return reply.read(300_001)


def main(mode: str, ident: str) -> None:
    if not re.fullmatch(r'[0-9]{6,20}', ident):
        raise RuntimeError('IRRIGATION_CARD_INVALID_RUN_ID')
    if mode == 'selftest':
        fixture = ('<html><section data-zm-functional-catalog="20261106">' + OLD + '</section></html>').encode()
        if VERSION.encode() not in patch(fixture, verify_hash=False):
            raise RuntimeError('IRRIGATION_CARD_SELFTEST_FAILED')
        print('IRRIGATION_CARD_SELFTEST=yes')
        return
    guard()
    backup = BACKUPS / ident
    if mode in ('preview', 'publish'):
        old = TARGET.read_bytes()
        updated = patch(old)
        if backup.exists():
            raise RuntimeError('IRRIGATION_CARD_RUN_ID_ALREADY_USED')
        if mode == 'preview':
            print('IRRIGATION_CARD_BASELINE_MATCH=yes')
            return
        backup.mkdir(mode=0o700, parents=True, exist_ok=False)
        with (backup / 'index.original.html').open('xb') as f:
            f.write(old)
            f.flush()
            os.fsync(f.fileno())
        (backup / 'index.original.html').chmod(0o600)
        atomic(updated)
        print('IRRIGATION_CARD_PUBLISHED=yes')
        return
    if mode == 'verify':
        if not backup.is_dir():
            raise RuntimeError('IRRIGATION_CARD_BACKUP_MISSING')
        original = (backup / 'index.original.html').read_bytes()
        updated = patch(original)
        if digest(TARGET.read_bytes()) != digest(updated):
            raise RuntimeError('IRRIGATION_CARD_CONCURRENT_CHANGE')
        for attempt in range(6):
            try:
                served = get_public()
                if VERSION.encode() in served and NEW.encode() in served and OLD.encode() not in served:
                    print('IRRIGATION_CARD_PUBLIC_VERIFIED=yes')
                    return
            except Exception:
                pass
            if attempt < 5:
                time.sleep(3)
        raise RuntimeError('IRRIGATION_CARD_PUBLIC_NOT_UPDATED')
    if mode == 'rollback':
        if not backup.is_dir():
            print('IRRIGATION_CARD_NOTHING_TO_ROLLBACK=yes')
            return
        original = (backup / 'index.original.html').read_bytes()
        if digest(TARGET.read_bytes()) != digest(patch(original)):
            raise RuntimeError('IRRIGATION_CARD_CONCURRENT_MODIFICATION_REFUSE_ROLLBACK')
        atomic(original)
        print('IRRIGATION_CARD_ROLLED_BACK=yes')
        return
    raise RuntimeError('IRRIGATION_CARD_UNKNOWN_MODE')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: SCRIPT MODE RUN_ID')
    main(sys.argv[1], sys.argv[2])
