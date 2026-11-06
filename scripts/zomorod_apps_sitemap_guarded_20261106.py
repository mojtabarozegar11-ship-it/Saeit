#!/usr/bin/env python3
"""Reversibly include the existing, indexable /apps/ page in the live sitemap.

Runs as the cPanel account, limits writes to a single known XML file, refuses
concurrent changes, and preserves a byte-exact rollback copy outside public_html.
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
BACKUPS = HOME / '.backups/zomorod-apps-sitemap-20261106'
EXPECTED = '8e96f30d6167566eecf28667af247be8b8ac49a44f8947497a5401674cf49a38'
APP_URL = 'https://zomorodmelal.ir/apps/'
APP_ENTRY = '<url><loc>' + APP_URL + '</loc><lastmod>2026-11-06</lastmod></url>'
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def patch(raw: bytes, check_live_sha: bool = True) -> bytes:
    if check_live_sha and sha(raw) != EXPECTED:
        raise RuntimeError('APPS_SITEMAP_PRODUCTION_DRIFT_ABORT')
    old = ET.fromstring(raw)
    if old.tag != NS + 'urlset':
        raise RuntimeError('APPS_SITEMAP_UNEXPECTED_ROOT')
    locs = [e.text for e in old.findall('.//' + NS + 'loc')]
    if (len(locs) != 152 or len(set(locs)) != len(locs)
            or APP_URL in locs
            or not all(x.startswith('https://zomorodmelal.ir/') for x in locs)
            or 'https://zomorodmelal.ir/services/' not in locs
            or 'https://zomorodmelal.ir/amozeshgah/' not in locs):
        raise RuntimeError('APPS_SITEMAP_ENTRY_INVENTORY_CHANGED_ABORT')
    text = raw.decode('utf-8')
    if text.count('</urlset>') != 1:
        raise RuntimeError('APPS_SITEMAP_CLOSING_TAG_UNEXPECTED')
    new = text.replace('</urlset>', '\n  ' + APP_ENTRY + '\n</urlset>', 1).encode('utf-8')
    parsed = ET.fromstring(new)
    new_locs = [e.text for e in parsed.findall('.//' + NS + 'loc')]
    if new_locs != locs + [APP_URL] or sha(new) == sha(raw):
        raise RuntimeError('APPS_SITEMAP_UNRELATED_CONTENT_CHANGED')
    return new


def validate_target() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError('APPS_SITEMAP_WRONG_ACCOUNT')
    for p in (HOME / 'public_html', TARGET, BACKUPS):
        if p.is_symlink():
            raise RuntimeError('APPS_SITEMAP_SYMLINK_REFUSED')
    if not TARGET.is_file() or TARGET.stat().st_size > 300_000:
        raise RuntimeError('APPS_SITEMAP_TARGET_NOT_REGULAR')
    if BACKUPS.exists() and not BACKUPS.is_dir():
        raise RuntimeError('APPS_SITEMAP_BACKUP_PATH_UNSAFE')


def atomic_replace(path: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.zm-apps-xml-', delete=False) as f:
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


def live_public_xml(run_id: str) -> bytes:
    req = Request('https://zomorodmelal.ir/sitemap.xml?apps_sitemap=' + run_id
                  + '-' + str(time.time_ns()), headers={
                      'User-Agent': 'Zomorod-Apps-Sitemap-Verify/1.0',
                      'Cache-Control': 'no-cache'})
    with urlopen(req, timeout=25) as response:
        if response.status != 200 or 'xml' not in response.headers.get('Content-Type', '').lower():
            raise RuntimeError('APPS_SITEMAP_PUBLIC_RESPONSE_NOT_XML')
        return response.read(300_001)


def main(mode: str, run_id: str) -> None:
    if mode == 'selftest':
        example = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                   + ''.join('<url><loc>https://zomorodmelal.ir/%s/</loc></url>' %
                             ('services' if i == 0 else 'amozeshgah' if i == 1
                              else 'audit-page-%03d' % i) for i in range(152))
                   + '</urlset>').encode('utf-8')
        assert patch(example, check_live_sha=False).count(APP_URL.encode()) == 1
        print('APPS_SITEMAP_SELFTEST_OK')
        return
    if not re.fullmatch(r'[0-9]{6,20}', run_id):
        raise RuntimeError('APPS_SITEMAP_INVALID_RUN_ID')
    validate_target()
    backup_dir = BACKUPS / run_id
    if mode in ('preview', 'publish'):
        before = TARGET.read_bytes()
        after = patch(before)
        if mode == 'preview':
            print('APPS_SITEMAP_EXACT_PRODUCTION_SHA_MATCH')
            return
        if backup_dir.exists():
            raise RuntimeError('APPS_SITEMAP_RUN_ID_ALREADY_USED')
        backup_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        backup = backup_dir / 'sitemap.original.xml'
        with backup.open('xb') as f:
            f.write(before)
            f.flush()
            os.fsync(f.fileno())
        backup.chmod(0o600)
        if sha(TARGET.read_bytes()) != sha(before):
            raise RuntimeError('APPS_SITEMAP_CONCURRENT_CHANGE_BEFORE_SWAP')
        atomic_replace(TARGET, after)
        print('APPS_SITEMAP_ATOMICALLY_PUBLISHED')
        return
    if mode == 'verify':
        before = (backup_dir / 'sitemap.original.xml').read_bytes()
        expected = patch(before)
        if sha(TARGET.read_bytes()) != sha(expected):
            raise RuntimeError('APPS_SITEMAP_ORIGIN_DIGEST_MISMATCH')
        for attempt in range(6):
            try:
                if sha(live_public_xml(run_id)) == sha(expected):
                    print('APPS_SITEMAP_PUBLIC_VERIFIED')
                    return
            except Exception:
                if attempt == 5:
                    raise
            if attempt < 5:
                time.sleep(3)
        raise RuntimeError('APPS_SITEMAP_PUBLIC_CONTENT_MISMATCH')
    if mode == 'rollback':
        if not backup_dir.is_dir():
            print('APPS_SITEMAP_NOTHING_TO_ROLL_BACK')
            return
        original = (backup_dir / 'sitemap.original.xml').read_bytes()
        if sha(TARGET.read_bytes()) != sha(patch(original)):
            raise RuntimeError('APPS_SITEMAP_CONCURRENT_MODIFICATION_REFUSE_ROLLBACK')
        atomic_replace(TARGET, original)
        print('APPS_SITEMAP_ROLLED_BACK')
        return
    raise RuntimeError('APPS_SITEMAP_UNKNOWN_MODE')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: SCRIPT MODE RUN_ID')
    main(sys.argv[1], sys.argv[2])
