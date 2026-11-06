#!/usr/bin/env python3
"""Give the live industry index HTML a targeted browser revalidation header.

Changes only the industry's .htaccess. Saves original bytes, validates public
headers and supports exact rollback. Does not change other page types or apps.
"""
from __future__ import annotations

import json
import os
import re
import stat
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

WEB = Path('/home/zomorod2/public_html')
DIR = WEB / 'industry'
CONFIG = DIR / '.htaccess'
INDEX = DIR / 'index.html'
BACKUP = Path('/home/zomorod2/.private/industry-html-cache-backups')
MARKER = 'zm-industry-html-cache-20261106'
BLOCK = '''\n# zm-industry-html-cache-20261106:start
# Ensure browsers revalidate this frequently updated public landing page.
<IfModule mod_headers.c>
  <Files "index.html">
    Header set Cache-Control "no-cache, must-revalidate, max-age=0"
  </Files>
</IfModule>
# zm-industry-html-cache-20261106:end
'''


def validate():
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('WRONG_SITE_USER')
    if DIR.is_symlink() or CONFIG.is_symlink() or not CONFIG.is_file():
        raise RuntimeError('UNSAFE_CONFIG_PATH')
    if not INDEX.is_file() or INDEX.is_symlink():
        raise RuntimeError('UNSAFE_INDEX_PATH')
    if BACKUP.is_symlink() or BACKUP.parent.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_PATH')
    if 'zm-production-oee-20261106:page' not in INDEX.read_text(encoding='utf-8'):
        raise RuntimeError('INDUSTRY_OEE_NOT_LIVE_ON_ORIGIN')


def transform(content):
    if BLOCK in content:
        if content.count(MARKER + ':start') != 1 or content.count(MARKER + ':end') != 1:
            raise RuntimeError('DUPLICATED_CACHE_POLICY')
        return 'already-applied', content
    if MARKER in content:
        raise RuntimeError('PARTIAL_POLICY_DRIFT')
    if 'PassengerEnabled off' not in content:
        raise RuntimeError('STATIC_PASSENGER_POLICY_MISSING')
    if re.search(r'(?im)^\s*Header\s+(?:always\s+)?(?:set|append|merge)\s+Cache-Control\b', content):
        raise RuntimeError('PREEXISTING_CACHE_HEADER_POLICY')
    if re.search(r'(?im)^\s*Expires(?:Default|ByType)\b', content):
        raise RuntimeError('PREEXISTING_EXPIRY_POLICY')
    return 'needs-patch', content.rstrip('\n') + '\n' + BLOCK


def backup_folder(runid):
    if not re.fullmatch(r'[0-9]{5,20}', runid):
        raise RuntimeError('INVALID_RUN_ID')
    BACKUP.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUP, 0o700)
    target = BACKUP / runid
    if target.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_ID')
    return target


def atomic_write(data: bytes, mode: int):
    fd, temporary = tempfile.mkstemp(prefix='.industry-cache-', dir=str(DIR))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, CONFIG)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def preview():
    state, _ = transform(CONFIG.read_text(encoding='utf-8'))
    print('INDUSTRY_CACHE_PREVIEW=' + state)


def publish(runid):
    source = CONFIG.read_bytes()
    state, target = transform(source.decode('utf-8'))
    if state == 'already-applied':
        print('INDUSTRY_CACHE_ALREADY_APPLIED=1')
        return
    folder = backup_folder(runid)
    if folder.exists():
        raise RuntimeError('BACKUP_RUN_COLLISION')
    folder.mkdir(mode=0o700)
    (folder / 'original.htaccess').write_bytes(source)
    os.chmod(folder / 'original.htaccess', 0o600)
    mode = stat.S_IMODE(CONFIG.stat().st_mode)
    (folder / 'manifest.json').write_text(json.dumps({'mode': mode}), encoding='utf-8')
    try:
        atomic_write(target.encode('utf-8'), mode)
    except Exception:
        if CONFIG.read_bytes() == target.encode('utf-8'):
            atomic_write(source, mode)
        raise
    print('INDUSTRY_CACHE_HEADER_PUBLISHED=1')


def verify_origin():
    if transform(CONFIG.read_text(encoding='utf-8'))[0] != 'already-applied':
        raise RuntimeError('ORIGIN_CACHE_HEADER_NOT_APPLIED')
    print('INDUSTRY_CACHE_ORIGIN_OK=1')


def verify_public():
    for attempt in range(7):
        try:
            req = Request('https://zomorodmelal.ir/industry/', headers={'User-Agent': 'Zomorod-Industry-Cache-Policy/1.0', 'Cache-Control': 'no-cache'})
            with urlopen(req, timeout=25) as response:
                data = response.read(1100000).decode('utf-8', 'replace')
                cc = response.headers.get('Cache-Control', '')
                if response.status != 200 or 'zm-production-oee-20261106:page' not in data:
                    raise RuntimeError('INDUSTRY_PAGE_NOT_FRESH')
                if 'no-cache' not in cc.lower() or 'max-age=0' not in cc.lower():
                    raise RuntimeError('INDUSTRY_CACHE_CONTROL_MISSING:' + cc)
            print('INDUSTRY_CACHE_PUBLIC_HEADER_OK=' + cc)
            return
        except Exception:
            if attempt == 6:
                raise
            time.sleep(4)


def rollback(runid):
    folder = backup_folder(runid)
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    original = (folder / 'original.htaccess').read_bytes()
    state, _ = transform(CONFIG.read_text(encoding='utf-8'))
    if state != 'already-applied':
        raise RuntimeError('REFUSE_ROLLBACK_CHANGED_CONFIG')
    if transform(original.decode('utf-8'))[0] != 'needs-patch':
        raise RuntimeError('REFUSE_BAD_BACKUP')
    atomic_write(original, int(manifest['mode']))
    print('INDUSTRY_CACHE_ORIGINAL_RESTORED=1')


def selftest():
    source = 'PassengerEnabled off\n'
    state, target = transform(source)
    assert state == 'needs-patch' and transform(target)[0] == 'already-applied'
    print('INDUSTRY_CACHE_SELFTEST_OK=1')


if __name__ == '__main__':
    if sys.argv[1:] == ['selftest']:
        selftest()
        sys.exit(0)
    validate()
    if sys.argv[1:] == ['preview']:
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'verify-origin':
        verify_origin()
        verify_public()
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise RuntimeError('UNKNOWN_MODE')
