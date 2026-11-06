#!/usr/bin/env python3
"""Add the newly functional public training center to the static XML sitemap.

No unrelated sitemap entries are removed, and no authenticated services are
contacted. Guarded by an exact SHA-256 of the published production sitemap.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import Request, urlopen

HOME = Path('/home/zomorod2')
TARGET = HOME / 'public_html/sitemap.xml'
BACKUPS = HOME / '.backups/zomorod-amozeshgah-sitemap-20261106'
EXPECTED = 'df973cb8adc503fb740fd76fbb309dd29a7f2fba9784214527b02eeca10b17e4'
LOC = '<loc>https://zomorodmelal.ir/amozeshgah/</loc>'
ENTRY = '<url><loc>https://zomorodmelal.ir/amozeshgah/</loc><lastmod>2026-11-06</lastmod></url>'


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def patch(raw: bytes, enforce_sha: bool = True) -> bytes:
    if enforce_sha and digest(raw) != EXPECTED:
        raise RuntimeError('ACADEMY_SITEMAP_LIVE_VERSION_CHANGED_ABORT')
    text = raw.decode('utf-8')
    if text.count('</urlset>') != 1 or LOC in text:
        raise RuntimeError('ACADEMY_SITEMAP_STRUCTURE_CHANGED_ABORT')
    old = ET.fromstring(raw)
    ns = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    existing = [x.text for x in old.findall('.//' + ns + 'loc')]
    if (len(existing) != 151 or len(set(existing)) != len(existing) or
            not any(x.endswith('/services/') for x in existing)):
        raise RuntimeError('ACADEMY_SITEMAP_STRUCTURE_UNEXPECTED')
    modified = text.replace('</urlset>', '\n  ' + ENTRY + '\n</urlset>', 1).encode('utf-8')
    parsed = ET.fromstring(modified)
    published = [x.text for x in parsed.findall('.//' + ns + 'loc')]
    if published != existing + ['https://zomorodmelal.ir/amozeshgah/']:
        raise RuntimeError('ACADEMY_SITEMAP_OLD_ENTRIES_CHANGED')
    return modified


def guard() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError('ACADEMY_SITEMAP_WRONG_USER')
    for path in (HOME / 'public_html', TARGET, BACKUPS):
        if path.is_symlink():
            raise RuntimeError('ACADEMY_SITEMAP_SYMLINK_REFUSED')
    if not TARGET.is_file() or TARGET.stat().st_size > 300_000:
        raise RuntimeError('ACADEMY_SITEMAP_TARGET_NOT_REGULAR')
    if BACKUPS.exists() and not BACKUPS.is_dir():
        raise RuntimeError('ACADEMY_SITEMAP_BACKUP_UNSAFE')


def replace(path: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.zm-xml-', delete=False) as f:
            temporary = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def public_xml() -> bytes:
    req = Request('https://zomorodmelal.ir/sitemap.xml?zm_version=' + str(time.time_ns()),
                  headers={'Cache-Control': 'no-cache', 'User-Agent': 'ZM-Academy-Sitemap-Audit/1.0'})
    with urlopen(req, timeout=22) as response:
        if response.status != 200:
            raise RuntimeError('ACADEMY_SITEMAP_PUBLIC_STATUS_BAD')
        return response.read(300_001)


def main(mode: str, run_id: str) -> None:
    if not re.fullmatch('[0-9]{6,20}', run_id):
        raise RuntimeError('ACADEMY_SITEMAP_BAD_RUN_ID')
    if mode == 'selftest':
        # Test XML parsing of the insertion against the already captured
        # public sitemap; the exact real input is hash-checked on cPanel.
        example = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                   + ''.join('<url><loc>https://zomorodmelal.ir/services/</loc></url>' if i == 0 else
                             '<url><loc>https://zomorodmelal.ir/test-%d/</loc></url>' % i
                             for i in range(151)) + '</urlset>')
        if LOC.encode() not in patch(example.encode('utf-8'), enforce_sha=False):
            raise RuntimeError('ACADEMY_SITEMAP_SELFTEST_FAILED')
        print('ACADEMY_SITEMAP_SELFTEST=yes')
        return
    guard()
    backup = BACKUPS / run_id
    if mode in ('preview', 'publish'):
        old = TARGET.read_bytes()
        new = patch(old)
        if backup.exists():
            raise RuntimeError('ACADEMY_SITEMAP_RUN_ID_ALREADY_USED')
        if mode == 'preview':
            print('ACADEMY_SITEMAP_SHA_MATCH=yes')
            return
        backup.mkdir(mode=0o700, parents=True, exist_ok=False)
        with (backup / 'sitemap.original.xml').open('xb') as f:
            f.write(old)
            f.flush()
            os.fsync(f.fileno())
        (backup / 'sitemap.original.xml').chmod(0o600)
        replace(TARGET, new)
        print('ACADEMY_SITEMAP_PUBLISHED=yes')
        return
    if mode == 'verify':
        if not backup.is_dir():
            raise RuntimeError('ACADEMY_SITEMAP_BACKUP_MISSING')
        old = (backup / 'sitemap.original.xml').read_bytes()
        expected = patch(old)
        if digest(TARGET.read_bytes()) != digest(expected):
            raise RuntimeError('ACADEMY_SITEMAP_CHANGED_DURING_RELEASE')
        for attempt in range(6):
            try:
                public = public_xml()
                if LOC.encode() in public and digest(public) == digest(expected):
                    print('ACADEMY_SITEMAP_PUBLIC_VERIFIED=yes')
                    return
            except Exception:
                pass
            if attempt < 5:
                time.sleep(3)
        raise RuntimeError('ACADEMY_SITEMAP_NOT_PUBLIC')
    if mode == 'rollback':
        if not backup.is_dir():
            print('ACADEMY_SITEMAP_NOTHING_TO_ROLLBACK=yes')
            return
        old = (backup / 'sitemap.original.xml').read_bytes()
        if digest(TARGET.read_bytes()) != digest(patch(old)):
            raise RuntimeError('ACADEMY_SITEMAP_CONCURRENT_MODIFICATION_REFUSE_ROLLBACK')
        replace(TARGET, old)
        print('ACADEMY_SITEMAP_ROLLED_BACK=yes')
        return
    raise RuntimeError('ACADEMY_SITEMAP_UNKNOWN_MODE')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: SCRIPT MODE RUN_ID')
    main(sys.argv[1], sys.argv[2])
